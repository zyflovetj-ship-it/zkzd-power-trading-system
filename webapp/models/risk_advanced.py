"""
风险域 P1 模型：VaR 回测、压力测试、预警事件

设计原则
--------
1. 回测是 VaR 的**准入证**：不出回测结果的 VaR 数字不可对外汇报。
   Kupiec POF 检验突破频率是否等于名义水平，Christoffersen 检验突破是否成簇。
2. 压力测试与 VaR 互补：VaR 回答"平常日子亏多少"，压力测试回答"极端日子亏多少"。
3. 预警事件必须可追溯到触发它的快照或场景，不允许无源告警。
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

MODEL_VERSION_P1 = "risk-p1.0.0"


# ------------------------------------------------------------------ 回测


class BacktestSample(BaseModel):
    """单日回测样本。"""

    day: date
    var_predicted: float = Field(..., description="模型给出的当日 VaR(元)")
    pnl_actual: float = Field(..., description="当日实际 P&L(元)，负为亏损")
    breached: bool = Field(..., description="是否突破 VaR")


class BacktestResult(BaseModel):
    """VaR 回测结果。"""

    method: str = Field(..., description="parametric / historical")
    confidence: float = 0.95
    window_days: int = Field(..., description="滚动估计窗口(天)")
    samples: int = Field(0, description="有效检验天数")
    exceptions: int = Field(0, description="实际突破次数")
    expected_exceptions: float = Field(0.0, description="名义期望突破次数 = samples × (1-置信度)")

    kupiec_lr: float = Field(0.0, description="Kupiec POF 似然比统计量")
    kupiec_pvalue: float = Field(1.0, description="POF p 值，>0.05 视为不拒绝")
    christoffersen_lr: float = Field(0.0, description="Christoffersen 独立性似然比")
    christoffersen_pvalue: float = Field(1.0, description="独立性 p 值")
    cc_lr: float = Field(0.0, description="条件覆盖联合似然比(POF+IND)")
    cc_pvalue: float = Field(1.0, description="条件覆盖 p 值")

    passed: bool = Field(False, description="POF 与独立性均通过")
    verdict: str = Field("", description="人类可读结论")
    warnings: List[str] = Field(default_factory=list)
    detail: List[BacktestSample] = Field(default_factory=list)


# ------------------------------------------------------------------ 压力测试


class StressScenario(BaseModel):
    """压力测试场景定义。

    场景是对 96 点价格曲线 / 负荷曲线的确定性变换，可组合。
    """

    scenario_id: str
    name: str
    category: str = Field(..., description="价格 / 负荷 / 信用 / 考核")
    description: str = ""

    price_mult: float = Field(1.0, description="价格整体乘数")
    price_add: float = Field(0.0, description="价格整体加项(元/MWh)")
    peak_price_mult: float = Field(1.0, description="仅峰段价格乘数")
    valley_price_override: Optional[float] = Field(None, description="谷段价格覆盖值(元/MWh)，用于负电价场景")

    load_mult: float = Field(1.0, description="负荷乘数")
    contract_mult: float = Field(1.0, description="合约电量乘数，用于违约/停运场景")
    penalty_rate: float = Field(0.0, description="偏差考核罚金系数(元/kWh 偏差)")

    severity: str = Field("medium", description="low / medium / high")
    enabled: bool = True


class StressResult(BaseModel):
    """单场景压力测试结果。"""

    scenario_id: str
    name: str
    category: str
    severity: str

    base_price_exposure: float = Field(0.0, description="基准价格敞口(元)")
    stressed_price_exposure: float = Field(0.0, description="情景下价格敞口(元)")
    pnl_impact: float = Field(0.0, description="情景冲击额(元)，负为损失")
    impact_ratio: float = Field(0.0, description="冲击额 / 基准敞口绝对值")

    worst_period_index: int = Field(0)
    worst_period_label: str = Field("")
    worst_period_impact: float = Field(0.0, description="最不利时段冲击(元)")

    margin_call_estimate: float = Field(0.0, description="预计追加保证金(元)")
    penalty_estimate: float = Field(0.0, description="偏差考核罚金估算(元)")
    limit_breaches: List[Dict[str, Any]] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class StressSuiteResult(BaseModel):
    """场景套件汇总。"""

    delivery_date: date
    scenarios: List[StressResult] = Field(default_factory=list)
    worst_scenario_id: str = ""
    worst_pnl_impact: float = 0.0
    total_margin_call: float = 0.0
    warnings: List[str] = Field(default_factory=list)


# ------------------------------------------------------------------ 预警


class AlertEvent(BaseModel):
    """预警事件。必须带 source 才能落库。"""

    alert_id: str = ""
    alert_type: str = Field(..., description="data / limit / var / backtest / stress")
    severity: str = Field(..., description="info / warning / critical")
    title: str
    message: str
    source: str = Field(..., description="触发来源标识，如 snapshot_id / scenario_id / check_name")
    delivery_date: Optional[date] = None
    created_at: datetime = Field(default_factory=datetime.now)
    status: str = Field("open", description="open / ack / closed")
