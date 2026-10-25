"""
中长期合同价格分析 - 数据模型
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date


class PeriodData(BaseModel):
    """单个时段的量价数据"""
    period: int = Field(..., ge=1, le=48, description="时段序号 (1-48)")
    quantity_mwh: float = Field(..., description="电量 (MWh)")
    price_yuan_per_mwh: float = Field(..., description="价格 (元/MWh)")


class ContractTypeSummary(BaseModel):
    """按合同类型和周期的汇总数据"""
    contract_type: str = Field(..., description="合同类型")
    contract_period: str = Field(..., description="交易周期")
    daily_total_quantity: float = Field(..., description="日电量 (MWh)")
    daily_avg_price: float = Field(..., description="均价 (元/MWh)")
    max_price: Optional[float] = Field(None, description="最高价 (元/MWh)")
    min_price: Optional[float] = Field(None, description="最低价 (元/MWh)")
    peak_valley_spread: Optional[float] = Field(None, description="峰谷差 (元/MWh)")


class DailySummaryKPIs(BaseModel):
    """日汇总指标"""
    total_quantity: float = Field(..., description="总电量 (MWh)")
    overall_avg_price: float = Field(..., description="整体均价 (元/MWh)")
    price_range_min: float = Field(..., description="价格区间下限")
    price_range_max: float = Field(..., description="价格区间上限")
    # 各周期占比
    yearly_ratio: float = Field(..., description="年度占比 (%)")
    monthly_ratio: float = Field(..., description="月度占比 (%)")
    within_month_ratio: float = Field(..., description="月内占比 (%)")
    # 各周期均价
    yearly_avg_price: Optional[float] = Field(None, description="年度均价")
    monthly_avg_price: Optional[float] = Field(None, description="月度均价")
    within_month_avg_price: Optional[float] = Field(None, description="月内均价")


class CurvePoint(BaseModel):
    """曲线数据点"""
    period: int = Field(..., description="时段序号")
    time_str: str = Field(..., description="时间字符串 HH:MM")
    price: float = Field(..., description="价格 (元/MWh)")
    quantity: Optional[float] = Field(None, description="电量 (MWh)")


class DailySummaryResponse(BaseModel):
    """日汇总响应"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    kpis: DailySummaryKPIs = Field(..., description="汇总指标")
    contract_curves: List[CurvePoint] = Field(..., description="中长期整体价格曲线")
    spot_curves: List[CurvePoint] = Field(..., description="日前现货价格曲线")
    type_summary: List[ContractTypeSummary] = Field(..., description="按类型汇总表格")
    # 按合同类型的曲线数据，用于前端筛选
    curves_by_type: dict = Field(default_factory=dict, description="按合同类型的曲线数据 {类型名: [CurvePoint]}")
    # 按交易周期的曲线数据
    curves_by_period: dict = Field(default_factory=dict, description="按交易周期的曲线数据 {周期名: [CurvePoint]}")




class DailyCurvesRequest(BaseModel):
    """曲线数据请求"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    contract_types: Optional[List[str]] = Field(None, description="合同类型筛选")
    contract_periods: Optional[List[str]] = Field(None, description="交易周期筛选")
    include_spot: bool = Field(True, description="是否包含现货对标")


class CurveData(BaseModel):
    """单条曲线数据"""
    label: str = Field(..., description="曲线标签")
    contract_type: str = Field(..., description="合同类型")
    contract_period: str = Field(..., description="交易周期")
    color: str = Field(..., description="建议颜色")
    points: List[CurvePoint] = Field(..., description="曲线数据点")


class DailyCurvesResponse(BaseModel):
    """曲线数据响应"""
    date: str = Field(..., description="日期 YYYY-MM-DD")
    curves: List[CurveData] = Field(..., description="曲线列表")
    spot_curve: Optional[CurveData] = Field(None, description="现货对标曲线")
