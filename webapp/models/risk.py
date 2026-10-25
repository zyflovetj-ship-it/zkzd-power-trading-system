"""
风险域公共模型与口径常量（P0）

口径铁律（本模块是所有风险指标的唯一定义来源）
------------------------------------------------
1. **电量**：内部计算一律 MWh。入库口径允许 kWh / MW / kW，但转换只在边界做一次，
   通过 `to_mwh()` 显式声明单位，禁止隐式混用。
2. **电价**：一律 元/MWh，与 `day_ahead_spot_price.value` 一致（历史数据 180~780）。
3. **时间粒度**：固定 96 点（15 分钟）。`period_index = hour * 4 + minute // 15`，
   timestamp 取该时段**起点**。
4. **跨期运算**：合约量、负荷量必须先落到同一 (日期, period_index) 再相减。
   禁止"月总量 − 15 分钟点值"这类跨期、跨单位运算。
   —— 旧 `risk_exposure_service` 的敞口恒为 0/异常，根因即在此。

历史数据约定（已知缺陷，P0 只读兼容）
------------------------------------------------
`init_*_mock_data.py` 把当日第 96 点（24:00）写成了**次日 00:00**，
与次日 period 0 撞点。因此取某日曲线统一用半开区间
`[当日00:00, 次日00:00)`，24:00 点归属次日，避免重复计数。
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field

# ---------------------------------------------------------------- 口径常量

PERIODS_PER_DAY = 96
PERIOD_MINUTES = 15
HOURS_PER_PERIOD = PERIOD_MINUTES / 60.0          # 0.25 h

#: 单位 → MWh 换算系数。MW/kW 是功率，乘 0.25h 才是本时段电量。
UNIT_TO_MWH: Dict[str, float] = {
    "MWh": 1.0,
    "kWh": 1e-3,
    "GWh": 1e3,
    "MW": HOURS_PER_PERIOD,        # 功率 × 0.25h
    "kW": HOURS_PER_PERIOD * 1e-3,
}

#: 各数据源的入库单位。改动前请先核对数据生产脚本，勿凭字段名猜。
SOURCE_UNIT: Dict[str, str] = {
    "retail_contracts.purchasing_electricity_quantity": "kWh",
    "user_load_data.value": "kW",
    "short_term_load_forecast.value": "kW",
    "day_ahead_spot_price.value": "元/MWh",
    "real_time_spot_price.value": "元/MWh",
}

#: 峰/谷时段（可配置）。0..95，含端点。
PEAK_PERIODS = tuple(range(68, 81))     # 17:00-20:00 晚峰
VALLEY_PERIODS = tuple(range(0, 25))    # 00:00-06:00 低谷

MODEL_VERSION = "risk-p0.1.0"


class ExposureBucket(str, Enum):
    PEAK = "peak"
    FLAT = "flat"
    VALLEY = "valley"


# ---------------------------------------------------------------- 基础工具


def to_mwh(value: float, unit: str) -> float:
    """把任意口径的电量换算成 MWh。单位非法直接抛错，不做静默兜底。"""
    if unit not in UNIT_TO_MWH:
        raise ValueError(f"不支持的电量单位: {unit!r}，可选: {sorted(UNIT_TO_MWH)}")
    return float(value) * UNIT_TO_MWH[unit]


def period_index_of(ts: datetime) -> int:
    """timestamp → period_index(0..95)。秒级舍入到所在 15 分钟块。"""
    return ts.hour * 4 + ts.minute // PERIOD_MINUTES


def period_label(idx: int) -> str:
    if not 0 <= idx < PERIODS_PER_DAY:
        raise ValueError(f"period_index 越界: {idx}")
    return f"{idx * PERIOD_MINUTES // 60:02d}:{idx * PERIOD_MINUTES % 60:02d}"


def period_start(idx: int, day: date) -> datetime:
    """period_index + 日期 → 该时段起点 datetime。"""
    if not 0 <= idx < PERIODS_PER_DAY:
        raise ValueError(f"period_index 越界: {idx}")
    return datetime.combine(day, time(0, 0)) + timedelta(minutes=idx * PERIOD_MINUTES)


def day_period_starts(day: date) -> List[datetime]:
    """某日 96 个时段起点。"""
    base = datetime.combine(day, time(0, 0))
    return [base + timedelta(minutes=i * PERIOD_MINUTES) for i in range(PERIODS_PER_DAY)]


def bucket_of(idx: int) -> ExposureBucket:
    if idx in PEAK_PERIODS:
        return ExposureBucket.PEAK
    if idx in VALLEY_PERIODS:
        return ExposureBucket.VALLEY
    return ExposureBucket.FLAT


# ---------------------------------------------------------------- 输出模型


class PeriodExposure(BaseModel):
    """单个时段的敞口明细。"""

    period_index: int = Field(..., ge=0, lt=PERIODS_PER_DAY)
    period_label: str = Field(..., description="时段标签，如 17:15")
    timestamp: datetime = Field(..., description="时段起点")
    bucket: ExposureBucket = Field(..., description="峰/平/谷")

    contract_mwh: float = Field(0.0, description="批发侧锁定电量(MWh，多头)")
    load_mwh: float = Field(0.0, description="负荷预测/实际(MWh，需交付)")
    net_position_mwh: float = Field(0.0, description="净敞口(MWh)，正=超配多头，负=欠配空头")
    fwd_price: float = Field(0.0, description="该时段远期/代理价格(元/MWh)")
    price_exposure: float = Field(0.0, description="价格敞口(元)，正=涨价有利")


class ExposureSummary(BaseModel):
    """分时段敞口汇总。标量指标全部由 96 点曲线派生，不独立计算。"""

    delivery_date: date
    total_contract_mwh: float = 0.0
    total_load_mwh: float = 0.0
    total_net_mwh: float = 0.0
    peak_net_mwh: float = 0.0
    flat_net_mwh: float = 0.0
    valley_net_mwh: float = 0.0
    max_long_period_mwh: float = 0.0
    max_short_period_mwh: float = 0.0
    price_exposure_yuan: float = 0.0
    coverage_ratio: float = Field(0.0, description="锁定电量 / 负荷电量，1.0 为完全覆盖")
    risk_level: str = Field("low", description="low / medium / high")
    warnings: List[str] = Field(default_factory=list, description="口径降级或数据缺失提示")


class PeriodRiskContribution(BaseModel):
    period_index: int
    period_label: str
    exposure_yuan: float = Field(..., description="该时段敞口金额(元)")
    sigma_yuan: float = Field(..., description="该时段 P&L 标准差(元)")
    var_contribution: float = Field(..., description="对组合 VaR 的贡献(元)")


class VarResult(BaseModel):
    method: str = Field(..., description="parametric / historical")
    confidence: float = 0.95
    horizon_days: int = 1
    var_yuan: float = 0.0
    cvar_yuan: float = 0.0
    portfolio_sigma_yuan: float = 0.0
    sample_days: int = 0
    contributions: List[PeriodRiskContribution] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class LimitBreach(BaseModel):
    limit_id: str
    scope: str
    limit_type: str
    threshold: float
    actual: float
    usage_ratio: float
    severity: str = Field(..., description="warning(软限) / breach(硬限)")


class RiskSnapshotMeta(BaseModel):
    """快照可复现元信息：任何历史指标都能按 (model_version, data_fingerprint) 原样重算。"""

    as_of: datetime
    delivery_date: date
    model_version: str = MODEL_VERSION
    data_fingerprint: str
    input_counts: Dict[str, int] = Field(default_factory=dict)
    params: Dict[str, float] = Field(default_factory=dict)
