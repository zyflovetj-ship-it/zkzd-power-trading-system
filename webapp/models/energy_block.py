"""能量块（Energy Block）数据模型。

能量块 = (时段, 电量, 价格) 三元组，中长期与现货共用同一结构：
  - 中长期（mid_long）：按 月×峰平谷 或 日×时刻 申报
  - 现货（day_ahead/real_time）：按 96 点时段申报，每时段最多 10 段量价对
"""
from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, Field

MarketType = Literal["mid_long", "day_ahead", "real_time"]
SubjectType = Literal["customer", "unit", "trading_unit"]
PeriodType = Literal["peak", "flat", "valley", "time"]
BlockStatus = Literal["draft", "submitted", "cleared", "cancelled"]


class EnergyBlockItem(BaseModel):
    """单个能量块。"""

    period_type: PeriodType = Field("time", description="时段类型：peak/flat/valley/time")
    time_str: Optional[str] = Field(None, description="具体时刻 HH:MM（period_type=time 时必填）")
    segment: int = Field(1, ge=1, description="段序号（现货每时段 ≤10 段）")
    volume_mwh: float = Field(..., gt=0, description="电量（MWh）")
    price: float = Field(..., ge=0, description="价格（元/MWh）")


class EnergyBlockSetCreate(BaseModel):
    """一次申报（能量块集合）。"""

    market_type: MarketType = Field(..., description="市场类型")
    subject_type: SubjectType = Field("customer", description="标的类型")
    subject_id: str = Field(..., description="标的ID（客户/机组/交易单元）")
    subject_name: Optional[str] = Field(None, description="标的名称")
    trade_period: Optional[str] = Field(None, description="交易品种：annual/monthly/intra_month/daily")
    start_date: str = Field(..., description="执行开始 YYYY-MM-DD")
    end_date: Optional[str] = Field(None, description="执行结束 YYYY-MM-DD（现货=当日）")
    total_volume_mwh: Optional[float] = Field(None, description="申报总电量（用于总量守恒校验）")
    expected_ratio: Optional[Dict[str, float]] = Field(
        None, description="期望峰平谷电量占比，如 {peak:0.3, flat:0.4, valley:0.3}"
    )
    direction: Literal["buy", "sell"] = Field("buy", description="申报方向：买/卖（决定报价单调性）")
    price_cap: float = Field(1500.0, gt=0, description="价格上限（元/MWh）")
    status: BlockStatus = Field("draft", description="状态")
    blocks: List[EnergyBlockItem] = Field(default_factory=list, description="能量块列表")
