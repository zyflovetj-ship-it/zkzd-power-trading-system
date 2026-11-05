"""零售套餐测算数据模型（江苏 2027 新规口径）。

路径A：历史负荷曲线测算；路径B：核查联测算。
"""
from typing import List, Optional

from pydantic import BaseModel, Field


class MarketContext(BaseModel):
    """月度市场行情（元/MWh），口径对齐《套餐测算模板 新v2》。"""

    wholesale_price: float = Field(..., description="月度批发市场价格（封顶用，模板 T4）")
    flat_base_price: Optional[float] = Field(
        None, description="平段加权均价（分时定价基准，缺省=wholesale_price）"
    )
    reference_price: Optional[float] = Field(
        None, description="零售参考价格（模板 T2），缺省=批发价"
    )
    share_cost_compensation: Optional[float] = Field(None, description="成本补偿分摊（模板 T5）")
    share_imbalance: Optional[float] = Field(None, description="不平衡费用分摊（模板 T6）")
    share_market_adjust: Optional[float] = Field(None, description="市场调节费用分摊（模板 T7）")
    share_price: float = Field(0.0, description="（兼容）单一分摊，未给三类时生效")


class PackageCalcParams(BaseModel):
    """套餐测算参数（附件2 合规区间）。"""

    peak_coef: float = Field(1.6, description="峰段浮动系数（≥1.6，上浮≥60%）")
    valley_coef: float = Field(0.4, description="谷段浮动系数（≤0.4，下浮≥60%）")
    service_fee: Optional[float] = Field(None, description="服务费（元/MWh，模板 P3=2；缺省用 kp×1000）")
    kp: float = Field(0.002, description="浮动价格 kP（元/kWh，0.002~0.02），未给 service_fee 时生效")
    f_ratio: float = Field(0.05, description="F 系数（0~0.05）")
    k1_share: float = Field(1.0, description="K1 分摊比例")
    k2_share: float = Field(1.0, description="K2 分摊比例")
    k3_share: float = Field(1.0, description="K3 分摊比例（默认 100%）")
    include_share_in_base: bool = Field(True, description="平段价是否含零售套餐分摊（模板=True）")
    green_mode: str = Field("否", description="否/普通绿电/小时级绿电")
    env_value: float = Field(30.0, description="绿电环境价值（元/MWh，模板 T14=30）")


class PeriodVolumes(BaseModel):
    """分时电量（MWh）。"""

    peak_mwh: float = 0.0
    flat_mwh: float = 0.0
    valley_mwh: float = 0.0


class CalcFromLoadRequest(BaseModel):
    """路径A 请求：按历史负荷曲线测算。"""

    customer_id: str = Field(..., description="客户ID（user_load_data.customer_id）")
    period: str = Field(..., description="测算月份 YYYY-MM")
    market: MarketContext
    params: Optional[PackageCalcParams] = None


class BillExtract(BaseModel):
    """核查联结构化数据（供电公司电费核查联单）。"""

    customer_name: Optional[str] = Field(None, description="用户名称")
    account_id: Optional[str] = Field(None, description="户号")
    period: str = Field(..., description="计费月份 YYYY-MM")
    ktype: str = Field("单一制-100千伏安以下", description="用电类型")
    total_mwh: float = Field(..., description="月总电量（MWh）")
    peak_mwh: Optional[float] = Field(None, description="峰段电量（MWh）")
    flat_mwh: Optional[float] = Field(None, description="平段电量（MWh）")
    valley_mwh: Optional[float] = Field(None, description="谷段电量（MWh）")
    current_amount: Optional[float] = Field(None, description="现状实收电费（元）")
    basic_fee: float = Field(0.0, description="基本电费（元）")
    power_factor_fee: float = Field(0.0, description="力调电费（元）")


class CalcFromBillRequest(BaseModel):
    """路径B 请求：按核查联测算。"""

    bill: BillExtract
    market: MarketContext
    params: Optional[PackageCalcParams] = None
