"""风险数据监控服务（P0）

职责：把"哪些数据该有、有没有、对不对"变成可执行的检查项，并驱动一次完整的
风险重算：数据质量门禁 → 敞口/VaR/限额 → 快照 → 预警 → 监控日志。

设计原则
--------
1. 检查项用统一结构输出（check / level / actual / expected / detail），便于前端和告警共用。
2. 数据不齐时**不做无意义重算**，而是明确拦截并告警（不是静默返回 0）。
3. 每次执行落一条 risk_monitor_log，可回溯"当时发生了什么"。
4. 快照幂等：同一交割日 + 同一数据指纹不重复插入。
"""

import hashlib
import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from webapp.services.risk_engine_service import RiskEngineService
from webapp.services.risk_stress_service import RiskStressService

logger = logging.getLogger(__name__)

MONITOR_LOG_COLLECTION = "risk_monitor_log"

#: 各数据源的期望点数与容差
SOURCE_RULES = {
    "day_ahead_spot_price": {"field": "timestamp", "expected": 96, "unit": "点/日"},
    "real_time_spot_price": {"field": "timestamp", "expected": 96, "unit": "点/日"},
    "user_load_data": {"field": "timestamp", "expected": 96, "unit": "点/日"},
    "short_term_load_forecast": {"field": "timestamp", "expected": 96, "unit": "点/日"},
    "load_curve_user": {"field": "datetime", "expected": 48, "unit": "点/日"},
    "settlement_curve_user": {"field": "datetime", "expected": 48, "unit": "点/日"},
}

#: 价格合理区间（元/MWh），与 init_spot_price_data 生成范围及 463 号文限价对齐
PRICE_MIN = 100.0
PRICE_MAX = 800.0


class RiskMonitorService:
    """风险数据监控与自动重算。"""

    def __init__(self, db, engine: Optional[RiskEngineService] = None) -> None:
        self.db = db
        self.engine = engine or RiskEngineService(db)
        self.stress = RiskStressService(db)

    # ------------------------------------------------------------------ 入口

    def run(self, delivery_date: Optional[date] = None) -> Dict[str, Any]:
        """执行一次完整监控 + 重算。

        :param delivery_date: 交割日；默认取最新有完整价格数据的业务日
        :return: 监控报告（含 checks / metrics / snapshot_id / alerts / blocked）
        """
        d = delivery_date or self._latest_complete_day()
        started = datetime.now()
        report: Dict[str, Any] = {
            "delivery_date": d.isoformat(),
            "started_at": started,
            "checks": [],
            "metrics": {},
            "alerts": [],
            "snapshot_id": None,
            "blocked": False,
        }

        # --- 1) 数据质量门禁
        checks = self.check_data_quality(d)
        report["checks"] = checks
        # 拦截分级：点数不齐 / 价格越界 / 定价缺失 = 结构性失败，必须拦截；
        # data_freshness 过期 = 时效失败，只告警不拦截（否则历史数据期会彻底停摆）。
        blocking = {"day_ahead_spot_price", "real_time_spot_price", "user_load_data",
                    "short_term_load_forecast", "load_curve_user", "settlement_curve_user",
                    "price_range", "pricing_config"}
        fails = [c for c in checks if c["level"] == "fail" and c["check"] in blocking]
        report["blocked"] = bool(fails)
        report["warnings"] = [c for c in checks if c["level"] in ("warn", "fail")]

        if fails:
            logger.warning("风险重算被数据质量门禁拦截: %s", [c["check"] for c in fails])
            report["alerts"] = self._emit_quality_alerts(d, checks)
            self._write_log(report)
            return report

        # --- 2) 重算：敞口 / VaR / 限额 / 压力测试
        try:
            exposure = self.engine.build_exposure(d)
            var = self.engine.compute_var(d)
            limits = self.engine.check_limits(exposure["summary"], var.var_yuan)
            stress = self.stress.run_suite(d)
            report["metrics"] = {
                "net_position_mwh": exposure["summary"].total_net_mwh,
                "price_exposure_yuan": exposure["summary"].price_exposure_yuan,
                "coverage_ratio": exposure["summary"].coverage_ratio,
                "var_yuan": var.var_yuan,
                "cvar_yuan": var.cvar_yuan,
                "max_severity": "breach" if any(
                    b.severity == "breach" for b in limits
                ) else ("warning" if limits else "ok"),
                "worst_scenario_impact": stress.worst_pnl_impact,
                "limit_breaches": len(limits),
            }

            # --- 3) 快照（幂等）
            report["snapshot_id"] = self._save_snapshot(d, report["metrics"])
            # --- 4) 限额/数据预警
            report["alerts"] = self._emit_risk_alerts(d, checks, limits, var, stress)
        except Exception as exc:
            logger.error("风险重算失败: %s", exc, exc_info=True)
            report["blocked"] = True
            report["alerts"].append({
                "alert_type": "engine",
                "severity": "critical",
                "title": "风险重算失败",
                "message": str(exc),
            })

        self._write_log(report)
        return report

    # ------------------------------------------------------- 数据质量检查

    def check_data_quality(self, d: date) -> List[Dict[str, Any]]:
        """按 SOURCE_RULES 检查数据完整性、时效性与价格合理性。"""
        checks: List[Dict[str, Any]] = []
        window_start, window_end = self._day_window(d)
        price_col = self.db.day_ahead_spot_price

        for source, rule in SOURCE_RULES.items():
            col = self.db[source]
            field = rule["field"]
            expected = rule["expected"]
            cnt = col.count_documents({field: {"$gt": window_start, "$lte": window_end}})
            checks.append({
                "check": source,
                "level": "ok" if cnt >= expected else ("warn" if cnt >= expected * 0.9 else "fail"),
                "actual": cnt,
                "expected": expected,
                "detail": "%d/%d %s" % (cnt, expected, rule["unit"]),
            })

        # 价格合理性（当日电价越界检查）
        prices = [
            x["value"] for x in price_col.find(
                {"timestamp": {"$gt": window_start, "$lte": window_end}, "value": {"$ne": None}},
                {"value": 1, "_id": 0},
            )
        ]
        if prices:
            lo, hi = min(prices), max(prices)
            bad = sum(1 for p in prices if p < PRICE_MIN or p > PRICE_MAX)
            checks.append({
                "check": "price_range",
                "level": "ok" if bad == 0 else "fail",
                "actual": bad,
                "expected": 0,
                "detail": "区间 %.2f~%.2f 元/MWh，越界 %d 点" % (lo, hi, bad),
            })
        else:
            checks.append({
                "check": "price_range",
                "level": "fail", "actual": 0, "expected": "非空",
                "detail": "当日无电价数据",
            })

        # 双源曲线一致性
        dev = self._curve_deviation(d)
        checks.append({
            "check": "curve_consistency",
            "level": "ok" if dev is not None and abs(dev) <= 0.05 else "warn",
            "actual": round(dev, 4) if dev is not None else None,
            "expected": "<=0.05",
            "detail": "负荷/结算曲线日电量偏差率",
        })

        # 数据时效性：价格/负荷是否还在滚动更新
        latest_price = price_col.find_one({}, sort=[("timestamp", -1)])
        newest = latest_price.get("timestamp") if latest_price else None
        age_days = (
            (datetime.now() - newest).total_seconds() / 86400
            if isinstance(newest, datetime) else 999.0
        )
        checks.append({
            "check": "data_freshness",
            # 时效性只告警不拦截：重算历史交割日仍有价值，
            # 但长期不更新会让"当日风控"失去意义，必须显式暴露。
            "level": "ok" if age_days <= 2 else ("warn" if age_days <= 7 else "fail"),
            "actual": round(age_days, 1),
            "expected": "<=2 天",
            "detail": "最新电价数据距今 %.1f 天" % age_days,
        })

        # 定价主数据
        pkg = self.db.retail_packages.find_one({}) or {}
        cfg = pkg.get("pricing_config") or {}
        fp = cfg.get("fixed_price_value")
        ok_price = isinstance(fp, (int, float)) and 0.33144 <= float(fp) <= 0.49716
        checks.append({
            "check": "pricing_config",
            "level": "ok" if ok_price else "fail",
            "actual": fp,
            "expected": "[0.33144, 0.49716]",
            "detail": "套餐固定电价（元/kWh）",
        })

        # 快照时效：本次 run 会生成/复用快照，故以"当日是否已有快照"为准，
        # 不再拿上次快照的年龄误报 warn。
        has_today = self.db.risk_metric_snapshot.count_documents({
            "delivery_date": d.isoformat(),
        }) > 0
        checks.append({
            "check": "snapshot_freshness",
            "level": "ok" if has_today else "warn",
            "actual": "当日已有" if has_today else "当日无",
            "expected": "当日有快照",
            "detail": "交割日快照就绪状态",
        })
        return checks

    # ------------------------------------------------------------ 辅助

    @staticmethod
    def _day_window(d: date):
        """业务日窗口：左开右闭（24:00 存为次日 00:00，归属前一日）。"""
        start = datetime(d.year, d.month, d.day)
        return start, start + timedelta(days=1)

    def _latest_complete_day(self) -> date:
        """取最近一个价格数据完整的业务日。"""
        cursor = self.db.day_ahead_spot_price.find(
            {}, {"timestamp": 1, "_id": 0}
        ).sort("timestamp", -1).limit(1)
        doc = next(cursor, None)
        ts = (doc or {}).get("timestamp")
        if isinstance(ts, datetime):
            return ts.date() if ts.hour != 0 or ts.minute != 0 else (ts - timedelta(days=1)).date()
        return date.today()

    def _curve_deviation(self, d: date) -> Optional[float]:
        start, end = self._day_window(d)
        totals = {}
        for c in ("load_curve_user", "settlement_curve_user"):
            docs = self.db[c].find(
                {"datetime": {"$gt": start, "$lte": end}}, {"load_kwh": 1, "_id": 0}
            )
            totals[c] = sum(float(x.get("load_kwh") or 0) for x in docs)
        base = totals["settlement_curve_user"]
        if base <= 0:
            return None
        return (totals["load_curve_user"] - base) / base

    def _save_snapshot(self, d: date, metrics: Dict[str, Any]) -> Optional[str]:
        """幂等落快照：同日 + 同数据指纹不重复写。"""
        fingerprint = self._fingerprint(d)
        exists = self.db.risk_metric_snapshot.find_one({
            "delivery_date": d.isoformat(),
            "data_fingerprint": fingerprint,
        })
        if exists:
            return str(exists["_id"])
        doc = {
            "as_of": datetime.now(),
            "delivery_date": d.isoformat(),
            "model_version": "risk-p0.1.0",
            "data_fingerprint": fingerprint,
            "monitor_metrics": metrics,
            "source": "risk_monitor_task",
            "created_at": datetime.now(),
        }
        r = self.db.risk_metric_snapshot.insert_one(doc)
        self.db[MONITOR_LOG_COLLECTION].create_index([("started_at", -1)])
        return str(r.inserted_id)

    def _fingerprint(self, d: date) -> str:
        start, end = self._day_window(d)
        parts = [
            "date=" + d.isoformat(),
            "price=" + str(self.db.day_ahead_spot_price.count_documents(
                {"timestamp": {"$gt": start, "$lte": end}})),
            "load=" + str(self.db.user_load_data.count_documents(
                {"timestamp": {"$gt": start, "$lte": end}})),
            "contracts=" + str(self.db.retail_contracts.count_documents({})),
        ]
        return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:16]

    def _emit_quality_alerts(self, d: date, checks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for c in checks:
            if c["level"] != "fail":
                continue
            doc = {
                "alert_id": "", "alert_type": "data",
                "severity": "critical",
                "title": "数据质量门禁拦截：" + c["check"],
                "message": c["detail"],
                "source": "monitor:" + c["check"],
                "delivery_date": d.isoformat(),
                "status": "open",
                "created_at": datetime.now(),
            }
            if self.db.risk_alert_event.count_documents({
                "source": doc["source"], "delivery_date": d.isoformat(), "status": "open",
            }) == 0:
                self.db.risk_alert_event.insert_one(doc)
            out.append({"alert_type": "data", "severity": "critical", "title": doc["title"],
                        "message": doc["message"]})
        return out

    def _emit_risk_alerts(self, d, checks, limits, var, stress) -> List[Dict[str, Any]]:
        out = self._emit_quality_alerts(d, checks)
        for b in limits:
            if b.severity != "breach":
                continue
            doc = {
                "alert_id": "", "alert_type": "limit", "severity": "critical",
                "title": "限额突破：" + b.limit_type,
                "message": "实际 %.2f / 限额 %.2f，使用率 %.1f%%" % (
                    b.actual, b.threshold, b.usage_ratio * 100),
                "source": "limit:" + b.limit_id,
                "delivery_date": d.isoformat(), "status": "open",
                "created_at": datetime.now(),
            }
            if self.db.risk_alert_event.count_documents({
                "source": doc["source"], "delivery_date": d.isoformat(), "status": "open",
            }) == 0:
                self.db.risk_alert_event.insert_one(doc)
            out.append({"alert_type": "limit", "severity": "critical", "title": doc["title"],
                        "message": doc["message"]})
        return out

    def _write_log(self, report: Dict[str, Any]) -> None:
        self.db[MONITOR_LOG_COLLECTION].insert_one({
            "delivery_date": report["delivery_date"],
            "started_at": report["started_at"],
            "finished_at": datetime.now(),
            "blocked": report["blocked"],
            "checks": report["checks"],
            "metrics": report["metrics"],
            "snapshot_id": report["snapshot_id"],
            "alert_count": len(report["alerts"]),
            "created_at": datetime.now(),
        })

    def latest_report(self) -> Dict[str, Any]:
        """最近一次监控结果，供 API/看板使用。"""
        doc = self.db[MONITOR_LOG_COLLECTION].find_one({}, sort=[("started_at", -1)])
        if not doc:
            return {"status": "never_run", "items": []}
        doc["_id"] = str(doc["_id"])
        return {"status": "ok", "report": doc}

    def history(self, limit: int = 20) -> List[Dict[str, Any]]:
        docs = self.db[MONITOR_LOG_COLLECTION].find({}, sort=[("started_at", -1)]).limit(limit)
        out = []
        for x in docs:
            x["_id"] = str(x["_id"])
            out.append(x)
        return out
