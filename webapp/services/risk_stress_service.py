"""
压力测试服务（P1）

与 VaR 的分工
-------------
VaR 用统计分布回答"平常日子亏多少"，会低估厚尾；
压力测试用确定性情景回答"极端日子亏多少"，不依赖分布假设，是监管最看重的部分。

场景设计原则
------------
1. 场景必须可解释、可复现：只做价格/负荷/合约的确定性变换，不引入随机性。
2. 覆盖中国现货市场的真实风险源：价格尖峰、负电价、负荷骤变、机组停运、
   合约违约、偏差考核。
3. 每个场景输出三件事：PnL 冲击额、预计追加保证金、是否击穿限额。
"""

from __future__ import annotations

import logging
import uuid
from datetime import date
from typing import Any, Dict, List, Optional

import numpy as np
from pymongo.database import Database

from webapp.models.risk import PEAK_PERIODS, PERIODS_PER_DAY, VALLEY_PERIODS, period_label
from webapp.models.risk_advanced import (
    AlertEvent,
    MODEL_VERSION_P1,
    StressResult,
    StressScenario,
    StressSuiteResult,
)
from webapp.services.risk_engine_service import RiskEngineService

logger = logging.getLogger(__name__)

#: 内置场景库。写入 risk_stress_scenario 集合后可覆盖。
DEFAULT_SCENARIOS: List[StressScenario] = [
    StressScenario(
        scenario_id="price-up-80", name="电价普涨 80%", category="价格", severity="high",
        description="现货价格整体上浮 80%，用于检验购电成本冲击",
        price_mult=1.8,
    ),
    StressScenario(
        scenario_id="price-crash-70", name="电价暴跌 70%", category="价格", severity="high",
        description="现货价格跌至三成，用于检验售电侧价差与超配亏损",
        price_mult=0.3,
    ),
    StressScenario(
        scenario_id="negative-price", name="午间负电价", category="价格", severity="high",
        description="谷段价格压至 -50 元/MWh，模拟新能源大发时段",
        price_mult=0.6, valley_price_override=-50.0,
    ),
    StressScenario(
        scenario_id="peak-spike-2.5", name="晚峰价格尖峰 2.5 倍", category="价格", severity="medium",
        description="17:00-20:00 晚峰价格放大 2.5 倍",
        peak_price_mult=2.5,
    ),
    StressScenario(
        scenario_id="load-up-15", name="负荷骤增 15%", category="负荷", severity="medium",
        description="气温骤升或用户投产，负荷上浮 15%",
        load_mult=1.15,
    ),
    StressScenario(
        scenario_id="load-down-15", name="负荷骤减 15%", category="负荷", severity="medium",
        description="需求下滑，负荷下浮 15%",
        load_mult=0.85,
    ),
    StressScenario(
        scenario_id="unit-outage-20", name="机组停运，锁定电量减 20%", category="供应", severity="high",
        description="自有/合约机组非计划停运，锁定电量下降 20%",
        contract_mult=0.8,
    ),
    StressScenario(
        scenario_id="contract-default", name="中长期合约违约", category="信用", severity="high",
        description="交易对手违约，锁定电量归零，全部暴露在现货",
        contract_mult=0.0,
    ),
    StressScenario(
        scenario_id="deviation-penalty", name="偏差考核触发", category="考核", severity="medium",
        description="负荷偏差 10%，按 0.1 元/kWh 计罚",
        load_mult=1.10, penalty_rate=0.1,
    ),
]

_PEAK_MASK = np.array([i in PEAK_PERIODS for i in range(PERIODS_PER_DAY)])
_VALLEY_MASK = np.array([i in VALLEY_PERIODS for i in range(PERIODS_PER_DAY)])


class RiskStressService:
    """压力测试与预警。"""

    def __init__(self, db: Database, engine: Optional[RiskEngineService] = None) -> None:
        self.db = db
        self.engine = engine or RiskEngineService(db)

    # ---------------------------------------------------------------- 场景库

    def list_scenarios(self) -> List[StressScenario]:
        """读 risk_stress_scenario；为空时回退内置场景库。"""
        docs = list(self.db.risk_stress_scenario.find({"enabled": True}))
        if not docs:
            return list(DEFAULT_SCENARIOS)
        out: List[StressScenario] = []
        for d in docs:
            d.pop("_id", None)
            try:
                out.append(StressScenario(**d))
            except Exception as exc:
                logger.warning("场景 %s 定义非法，已跳过: %s", d.get("scenario_id"), exc)
        return out or list(DEFAULT_SCENARIOS)

    def seed_scenarios(self) -> int:
        """把内置场景写入集合（幂等）。"""
        n = 0
        for sc in DEFAULT_SCENARIOS:
            if self.db.risk_stress_scenario.count_documents({"scenario_id": sc.scenario_id}) == 0:
                self.db.risk_stress_scenario.insert_one(sc.model_dump())
                n += 1
        return n

    # -------------------------------------------------------------- 执行套件

    def run_suite(self, delivery_date: date) -> StressSuiteResult:
        """跑全部场景，返回汇总与最差场景。"""
        scenarios = self.list_scenarios()
        results: List[StressResult] = []
        warnings: List[str] = []

        base = self.engine.build_exposure(delivery_date)
        if not any(p.fwd_price for p in base["curve"]):
            warnings.append("交割日无电价，压力测试的 PnL 冲击不可信")
        if not any(p.load_mwh for p in base["curve"]):
            warnings.append("交割日无负荷，压力测试的敞口不可信")

        for sc in scenarios:
            try:
                results.append(self.run_scenario(delivery_date, sc, base_exposure=base))
            except Exception as exc:
                logger.warning("场景 %s 执行失败: %s", sc.scenario_id, exc)
                warnings.append(f"场景 {sc.scenario_id} 执行失败: {exc}")

        if not results:
            return StressSuiteResult(delivery_date=delivery_date, warnings=warnings)

        worst = min(results, key=lambda r: r.pnl_impact)
        return StressSuiteResult(
            delivery_date=delivery_date,
            scenarios=sorted(results, key=lambda r: r.pnl_impact),
            worst_scenario_id=worst.scenario_id,
            worst_pnl_impact=round(worst.pnl_impact, 2),
            total_margin_call=round(sum(max(0.0, r.margin_call_estimate) for r in results), 2),
            warnings=warnings,
        )

    def run_scenario(
        self,
        delivery_date: date,
        scenario: StressScenario,
        base_exposure: Optional[Dict[str, Any]] = None,
    ) -> StressResult:
        """执行单个场景。"""
        exp = base_exposure or self.engine.build_exposure(delivery_date)
        curve = exp["curve"]

        base_price = np.array([p.fwd_price for p in curve], dtype=float)
        base_load = np.array([p.load_mwh for p in curve], dtype=float)
        base_contract = np.array([p.contract_mwh for p in curve], dtype=float)
        base_net = base_contract - base_load
        base_amount = float((base_net * base_price).sum())

        # --- 价格变换
        price = base_price * scenario.price_mult + scenario.price_add
        if scenario.peak_price_mult != 1.0:
            price = np.where(_PEAK_MASK, price * scenario.peak_price_mult, price)
        if scenario.valley_price_override is not None:
            price = np.where(_VALLEY_MASK, float(scenario.valley_price_override), price)

        # --- 负荷 / 合约变换
        load = base_load * scenario.load_mult
        contract = base_contract * scenario.contract_mult
        net = contract - load

        stressed_amount = float((net * price).sum())
        period_impact = (net * price) - (base_net * base_price)
        pnl_impact = float(period_impact.sum())

        worst_idx = int(np.argmin(period_impact))
        worst_impact = float(period_impact[worst_idx])

        # --- 偏差考核罚金：偏差电量(MWh) × 1000(kWh/MWh) × 罚金系数(元/kWh)
        penalty = 0.0
        if scenario.penalty_rate > 0:
            deviation_mwh = float(np.abs(load - base_load).sum())
            penalty = deviation_mwh * 1000.0 * scenario.penalty_rate

        # --- 保证金追加估算：按不利冲击全额估算（实际按交易所/合同比例调整）
        margin_call = max(0.0, -pnl_impact)

        warnings: List[str] = []
        breaches = self._check_stressed_limits(stressed_amount, net)

        return StressResult(
            scenario_id=scenario.scenario_id,
            name=scenario.name,
            category=scenario.category,
            severity=scenario.severity,
            base_price_exposure=round(base_amount, 2),
            stressed_price_exposure=round(stressed_amount, 2),
            pnl_impact=round(pnl_impact - penalty, 2),
            impact_ratio=round(abs(pnl_impact) / max(abs(base_amount), 1e-9), 4),
            worst_period_index=worst_idx,
            worst_period_label=period_label(worst_idx),
            worst_period_impact=round(worst_impact, 2),
            margin_call_estimate=round(margin_call, 2),
            penalty_estimate=round(penalty, 2),
            limit_breaches=breaches,
            warnings=warnings,
        )

    def _check_stressed_limits(self, stressed_amount: float, net: np.ndarray) -> List[Dict[str, Any]]:
        """对情景后的组合再做一次限额检查。"""
        limits = list(self.db.risk_limit.find({"enabled": True}))
        if not limits:
            limits = self.engine._default_limits()

        metrics = {
            "total_price_exposure": abs(stressed_amount),
            "net_position_mwh": abs(float(net.sum())),
            "max_period_mwh": float(np.max(np.abs(net))) if net.size else 0.0,
        }
        out: List[Dict[str, Any]] = []
        for lim in limits:
            ltype = lim.get("limit_type")
            if ltype not in metrics:
                continue
            threshold = float(lim.get("threshold", 0) or 0)
            if threshold <= 0:
                continue
            ratio = metrics[ltype] / threshold
            if ratio >= float(lim.get("warn_ratio", 0.8)):
                out.append(
                    {
                        "limit_id": str(lim.get("limit_id")),
                        "limit_type": ltype,
                        "threshold": threshold,
                        "actual": round(metrics[ltype], 2),
                        "usage_ratio": round(ratio, 4),
                        "severity": "breach" if ratio >= 1.0 else "warning",
                    }
                )
        return out

    # ------------------------------------------------------------------ 预警

    def generate_alerts(self, delivery_date: date, dedup: bool = True) -> List[AlertEvent]:
        """汇总数据/限额/回测/压力测试的问题，生成预警事件。"""
        alerts: List[AlertEvent] = []

        # 1. 数据校验
        try:
            v = self.engine.validate_inputs(delivery_date)
            for chk in v["checks"]:
                if chk["level"] == "fail":
                    alerts.append(
                        AlertEvent(
                            alert_type="data",
                            severity="critical",
                            title=f"数据校验未通过：{chk['name']}",
                            message=chk["detail"],
                            source=f"validate:{chk['name']}",
                            delivery_date=delivery_date,
                        )
                    )
        except Exception as exc:
            logger.warning("预警-数据校验失败: %s", exc)

        # 2. 限额
        try:
            exposure = self.engine.build_exposure(delivery_date)
            var = self.engine.compute_var(delivery_date)
            for b in self.engine.check_limits(exposure["summary"], var.var_yuan):
                alerts.append(
                    AlertEvent(
                        alert_type="limit",
                        severity="critical" if b.severity == "breach" else "warning",
                        title=f"限额{'突破' if b.severity == 'breach' else '预警'}：{b.limit_type}",
                        message=(
                            f"实际 {b.actual:,.2f} / 限额 {b.threshold:,.2f}，"
                            f"使用率 {b.usage_ratio:.1%}"
                        ),
                        source=f"limit:{b.limit_id}",
                        delivery_date=delivery_date,
                    )
                )
        except Exception as exc:
            logger.warning("预警-限额检查失败: %s", exc)

        # 3. 回测
        try:
            from webapp.services.risk_backtest_service import RiskBacktestService

            bt = RiskBacktestService(self.db, self.engine).run(delivery_date)
            if bt.samples > 0 and not bt.passed:
                alerts.append(
                    AlertEvent(
                        alert_type="backtest",
                        severity="warning",
                        title="VaR 回测未通过",
                        message=bt.verdict,
                        source=f"backtest:{bt.method}",
                        delivery_date=delivery_date,
                    )
                )
        except Exception as exc:
            logger.warning("预警-回测失败: %s", exc)

        # 4. 压力测试
        #    阈值不能挂在"净敞口"上：净敞口接近 0 时任何微小冲击都会被放大成告警。
        #    改用组合名义规模（Σ|合约电量|×价格）的比例阈值，并设绝对下限防噪声。
        try:
            suite = self.run_suite(delivery_date)
            exp = self.engine.build_exposure(delivery_date)
            notional = sum(abs(p.contract_mwh) * p.fwd_price for p in exp["curve"])
            # 下限只用于防止名义规模为 0 时阈值退化为 0，不做业务性过滤
            floor_yuan = 1.0
            warn_ratio, crit_ratio = 0.05, 0.20
            base_threshold = max(notional * warn_ratio, floor_yuan)

            for r in suite.scenarios:
                if r.pnl_impact >= 0:
                    continue
                loss = abs(r.pnl_impact)
                if loss < base_threshold:
                    continue
                ratio = loss / notional if notional > 0 else 0.0
                severity = "critical" if ratio >= crit_ratio else "warning"
                alerts.append(
                    AlertEvent(
                        alert_type="stress",
                        severity=severity,
                        title=f"压力测试损失：{r.name}",
                        message=(
                            f"情景冲击 {r.pnl_impact:,.2f} 元（占名义规模 {ratio:.1%}），"
                            f"最不利时段 {r.worst_period_label}（{r.worst_period_impact:,.2f} 元）"
                        ),
                        source=f"stress:{r.scenario_id}",
                        delivery_date=delivery_date,
                    )
                )
        except Exception as exc:
            logger.warning("预警-压力测试失败: %s", exc)

        # 落库 + 去重
        saved: List[AlertEvent] = []
        for a in alerts:
            a.alert_id = uuid.uuid4().hex[:16]
            if dedup:
                exists = self.db.risk_alert_event.count_documents(
                    {
                        "alert_type": a.alert_type,
                        "source": a.source,
                        "delivery_date": a.delivery_date.isoformat() if a.delivery_date else None,
                        "status": "open",
                    }
                )
                if exists:
                    continue
            doc = a.model_dump(mode="json")
            doc["delivery_date"] = a.delivery_date.isoformat() if a.delivery_date else None
            doc["created_at"] = a.created_at
            self.db.risk_alert_event.insert_one(doc)
            saved.append(a)
        return saved

    def list_alerts(self, status: str = "open", limit: int = 100) -> List[Dict[str, Any]]:
        q: Dict[str, Any] = {}
        if status:
            q["status"] = status
        docs = list(self.db.risk_alert_event.find(q).sort("created_at", -1).limit(limit))
        for d in docs:
            d["alert_id"] = str(d.get("_id"))
            d.pop("_id", None)
        return docs
