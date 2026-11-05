"""持仓合约管理服务（真实读库）

数据链路
--------
合同主数据 ← retail_contracts（合同电量 kWh、起止月份）
合约均价 ← retail_contracts.package_snapshot.pricing_config.fixed_price_value（元/kWh）
已执行电量 ← user_load_data（96 点，value = 15 分钟平均功率 kW，电量 = value × 0.25h）
覆盖率 = 已执行电量 / 合同电量
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

HOURS_PER_POINT = 0.25


class RiskPositionService:
    """持仓合约：真实读库，输出前端 camelCase 契约。"""

    def __init__(self, db) -> None:
        self.db = db

    def get_contracts(self) -> Dict[str, Any]:
        warnings: List[str] = []
        contracts = list(self.db.retail_contracts.find({}))
        if not contracts:
            warnings.append("retail_contracts 为空")

        out: List[Dict[str, Any]] = []
        for c in contracts:
            cid = str(c.get("customer_id") or "")
            cname = c.get("customer_name") or cid
            cno = c.get("contract_name") or str(c.get("_id") or "")

            qty_kwh = float(c.get("purchasing_electricity_quantity") or 0)
            start = c.get("purchase_start_month")
            end = c.get("purchase_end_month")

            avg_price = None
            cfg = ((c.get("package_snapshot") or {}).get("pricing_config") or {})
            val = cfg.get("fixed_price_value") or cfg.get("fixed_price") or cfg.get("energy_price")
            if val is not None:
                avg_price = float(val) * 1000.0  # 元/kWh -> 元/MWh
            else:
                warnings.append("合同 %s 缺零售电价，avgPrice 记 0" % cno)

            executed_kwh = self._executed_energy_kwh(cid, start, end)

            out.append({
                "customer": cname,
                "contractNo": cno,
                "volume": round(qty_kwh / 1000.0, 4),          # MWh
                "avgPrice": round(avg_price, 2) if avg_price is not None else 0.0,
                "startDate": start.strftime("%Y-%m-%d") if isinstance(start, datetime) else str(start or ""),
                "endDate": end.strftime("%Y-%m-%d") if isinstance(end, datetime) else str(end or ""),
                "coverage": round(executed_kwh / qty_kwh * 100.0, 2) if qty_kwh else 0.0,
            })

        return {"contracts": out, "warnings": warnings}

    def _executed_energy_kwh(self, customer_id: str, start, end) -> float:
        """合同期内已执行电量(kWh)。value 为功率 kW，×0.25h 得电量。"""
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            return 0.0
        month_end = (end.replace(day=1) + timedelta(days=32)).replace(day=1)
        q: Dict[str, Any] = {"timestamp": {"$gte": start, "$lt": month_end}}
        if customer_id:
            q["customer_id"] = customer_id
        total = 0.0
        for d in self.db.user_load_data.find(q, {"value": 1, "_id": 0}):
            v = d.get("value")
            if v is not None:
                total += float(v) * HOURS_PER_POINT
        return total

    # ------------------------------------------------------------------
    # 分时持仓曲线（96 点）：合约分解持仓 vs 实际负荷 vs 敞口
    # ------------------------------------------------------------------
    def get_position_curve(self, delivery_date: str = None) -> Dict[str, Any]:
        """按日输出 96 点持仓敞口。

        持仓来源：contract_curves（合约分解后的 daily_contracts.points）
        负荷来源：user_load_data（96 点实际负荷，MWh）
        敞口 = 负荷 − 持仓（正=需现货补，负=余量可卖）
        """
        warnings: List[str] = []
        date_str = delivery_date or self._latest_curve_date()
        if not date_str:
            return {"date": None, "points": [], "summary": {}, "warnings": ["无可用合约曲线或负荷数据"]}

        position = [0.0] * 96
        hit = 0
        for cv in self.db["contract_curves"].find({"status": "active"}, {"daily_contracts": 1}):
            for dc in cv.get("daily_contracts") or []:
                if dc.get("date") != date_str:
                    continue
                pts = dc.get("points") or []
                if len(pts) != 96:
                    continue
                hit += 1
                for i, v in enumerate(pts):
                    position[i] += float(v or 0.0)
        if hit == 0:
            warnings.append("该日无合约分解曲线（请先在「合同曲线生成」中生成）")

        load = [0.0] * 96
        start = datetime.strptime(date_str, "%Y-%m-%d")
        end = start + timedelta(days=1)
        for d in self.db.user_load_data.find(
            {"timestamp": {"$gte": start, "$lt": end}}, {"timestamp": 1, "value": 1, "_id": 0}
        ):
            ts, v = d.get("timestamp"), d.get("value")
            if ts is None or v is None:
                continue
            minutes = ts.hour * 60 + ts.minute
            idx = 95 if minutes == 0 else (minutes // 15) - 1
            idx = max(0, min(95, idx))
            load[idx] += float(v) * HOURS_PER_POINT / 1000.0
        if sum(load) <= 0:
            warnings.append("该日无实际负荷数据")

        tou = {}
        try:
            from webapp.services.tou_service import get_tou_rule_by_date
            tou = get_tou_rule_by_date(start)
        except Exception:
            tou = {}

        points = []
        by_period = {"peak": {"position": 0.0, "load": 0.0}, "flat": {"position": 0.0, "load": 0.0},
                     "valley": {"position": 0.0, "load": 0.0}}
        for i in range(96):
            ts = "%02d:%02d" % (i // 4, (i % 4) * 15)
            seg = tou.get(ts, "平段")
            key = "peak" if "峰" in seg else ("valley" if "谷" in seg else "flat")
            by_period[key]["position"] += position[i]
            by_period[key]["load"] += load[i]
            points.append({
                "time_str": ts,
                "position_mwh": round(position[i], 6),
                "load_mwh": round(load[i], 6),
                "gap_mwh": round(load[i] - position[i], 6),
            })

        total_pos = sum(position)
        total_load = sum(load)
        summary = {
            "date": date_str,
            "position_mwh": round(total_pos, 4),
            "load_mwh": round(total_load, 4),
            "gap_mwh": round(total_load - total_pos, 4),
            "coverage_ratio": round(total_pos / total_load, 4) if total_load else None,
            "by_period": {
                k: {
                    "position_mwh": round(v["position"], 4),
                    "load_mwh": round(v["load"], 4),
                    "coverage_ratio": round(v["position"] / v["load"], 4) if v["load"] else None,
                } for k, v in by_period.items()
            },
        }
        return {"date": date_str, "points": points, "summary": summary, "warnings": warnings}

    def _latest_curve_date(self):
        """取合约曲线中最新的一天（没有则回退到负荷最新日期）。"""
        cv = self.db["contract_curves"].find_one({"status": "active"}, sort=[("created_at", -1)])
        if cv:
            dates = sorted(
                {d.get("date") for d in (cv.get("daily_contracts") or []) if d.get("date")},
                reverse=True,
            )
            # 优先取「既在合约曲线里、又有实际负荷」的最近一天
            for d in dates:
                try:
                    start = datetime.strptime(d, "%Y-%m-%d")
                except ValueError:
                    continue
                # 要求当天负荷点足够完整（>=90 点），避免取到残缺日
                if self.db.user_load_data.count_documents(
                    {"timestamp": {"$gte": start, "$lt": start + timedelta(days=1)}}
                ) >= 90:
                    return d
            if dates:
                return dates[0]
        doc = self.db.user_load_data.find_one({}, sort=[("timestamp", -1)])
        ts = (doc or {}).get("timestamp")
        return ts.strftime("%Y-%m-%d") if isinstance(ts, datetime) else None
