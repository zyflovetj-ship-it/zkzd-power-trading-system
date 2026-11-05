"""中长期/绿电合同量价数据模型（江苏 2027 新规）。

对齐《套餐测算模板-新v2.xlsx》「中长期及绿电量价数据」页：
  12 个合同块（年度合计/年度绿电/月度竞价/月内能量块/月度绿电/月内绿电/
  上旬/中旬/下旬/第二次月内绿电/小时级绿电/月内小时级绿电）
  × 12 个月 × 24 时段 的 电量(MWh) + 价格(元/MWh)。

用途：为逐点引擎提供「逐点中长期价」序列（模板 分时!B142），
      替代原先的"月度均价兜底"。
"""
from typing import List, Optional

from pydantic import BaseModel, Field


#: 12 种合同类型（对齐 Excel 合同块名称）
CONTRACT_TYPES: List[str] = [
    "年度合计",
    "年度绿电",
    "月度竞价",
    "月内能量块",
    "月度绿电",
    "月内绿电",
    "上旬",
    "中旬",
    "下旬",
    "第二次月内绿电",
    "小时级绿电",
    "月内小时级绿电",
]

#: 年度类合同（价格全时段取同一价，对齐 Excel $Q$2/$Q$32 绝对引用）
ANNUAL_CONTRACT_TYPES = {"年度合计", "年度绿电"}

#: 24 时段标签
TIME_PERIODS: List[str] = [
    "00:00-01:00", "01:00-02:00", "02:00-03:00", "03:00-04:00",
    "04:00-05:00", "05:00-06:00", "06:00-07:00", "07:00-08:00",
    "08:00-09:00", "09:00-10:00", "10:00-11:00", "11:00-12:00",
    "12:00-13:00", "13:00-14:00", "14:00-15:00", "15:00-16:00",
    "16:00-17:00", "17:00-18:00", "18:00-19:00", "19:00-20:00",
    "20:00-21:00", "21:00-22:00", "22:00-23:00", "23:00-24:00",
]


class MidLongContractPoint(BaseModel):
    """单条合同量价记录：某合同类型 × 某月 × 某时段的量与价。

    customer_id 为空表示"全市场统一合同价"（对齐 Excel 模板口径）；
    非空表示该客户专属长协（客户级）。客户级优先于全局。
    """

    year: Optional[int] = Field(None, description="年份（可空，空则视为不限年）")
    customer_id: Optional[str] = Field(None, description="客户ID（空=全市场统一；非空=客户级专属）")
    customer_name: Optional[str] = Field(None, description="客户名称（便于展示，可空）")
    month: int = Field(..., ge=1, le=12, description="月份 1-12")
    contract_type: str = Field(..., description="合同类型（12 种之一）")
    time_index: int = Field(..., ge=0, le=23, description="时段序号 0-23")
    time_period: str = Field(..., description="时段标签，如 00:00-01:00")
    volume_mwh: float = Field(0.0, description="该时段电量（MWh）")
    price: float = Field(0.0, description="该时段价格（元/MWh）")


class MidLongContractBatch(BaseModel):
    """批量导入请求：一组合同量价记录。"""

    year: int = Field(..., description="年份")
    items: List[MidLongContractPoint] = Field(default_factory=list, description="量价记录列表")
