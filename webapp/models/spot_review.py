"""
现货交易复盘 Pydantic 数据模型

包含两个集合的数据模型：
1. spot_transactions - 96点交易记录
2. spot_trading_reviews - 复盘报告聚合
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any, Dict, Literal
from datetime import datetime as dt
from bson import ObjectId


class PyObjectId(ObjectId):
    @classmethod
    def __get_pydantic_core_schema__(cls, source_type: Any, handler):
        from pydantic_core import core_schema
        return core_schema.union_schema([
            core_schema.is_instance_schema(ObjectId),
            core_schema.no_info_plain_validator_function(cls.validate),
        ], serialization=core_schema.plain_serializer_function_ser_schema(
            lambda x: str(x)
        ))

    @classmethod
    def validate(cls, v):
        if isinstance(v, ObjectId):
            return v
        if isinstance(v, str):
            if not ObjectId.is_valid(v):
                raise ValueError("Invalid ObjectId")
            return ObjectId(v)
        raise ValueError("Invalid ObjectId")


class BaseMongoModel(BaseModel):
    model_config = ConfigDict(
        populate_by_name=True,
        arbitrary_types_allowed=True
    )

    id: PyObjectId = Field(default_factory=PyObjectId, alias="_id")


# ========== 96点交易记录 ==========

class SpotTransactionCreate(BaseModel):
    customer_id: str = Field(..., description="客户ID")
    customer_name: str = Field(..., description="客户名称")
    date: str = Field(..., description="业务日期 YYYY-MM-DD")
    datetime: dt = Field(..., description="时间点")
    spot_type: Literal["day_ahead", "real_time"] = Field(..., description="现货类型")
    volume_mwh: float = Field(..., description="电量(MWh)")
    price_yuan_mwh: float = Field(..., description="价格(元/MWh)")
    cost_yuan: float = Field(..., description="成本(元)")
    source: Literal["actual", "forecast"] = Field(..., description="数据来源: actual/forecast")


class SpotTransaction(SpotTransactionCreate, BaseMongoModel):
    created_at: dt = Field(default_factory=dt.now, description="创建时间")


class SpotTransactionListItem(BaseModel):
    id: str = Field(..., description="记录ID")
    customer_id: str = Field(..., description="客户ID")
    customer_name: str = Field(..., description="客户名称")
    date: str = Field(..., description="业务日期")
    datetime: dt = Field(..., description="时间点")
    spot_type: str = Field(..., description="现货类型")
    volume_mwh: float = Field(..., description="电量(MWh)")
    price_yuan_mwh: float = Field(..., description="价格(元/MWh)")
    cost_yuan: float = Field(..., description="成本(元)")
    source: str = Field(..., description="数据来源")
    created_at: dt = Field(..., description="创建时间")


# ========== 复盘报告聚合 ==========

class OverviewStats(BaseModel):
    total_cost: float = Field(0.0, description="总成本(元)")
    total_volume: float = Field(0.0, description="总电量(MWh)")
    avg_price: float = Field(0.0, description="平均价格(元/MWh)")
    market_avg_price: float = Field(0.0, description="市场平均价格(元/MWh)")
    cost_saving: float = Field(0.0, description="成本节约(元)")
    saving_rate: float = Field(0.0, description="节约率(%)")


class TimeSlotAnalysisItem(BaseModel):
    slot_name: str = Field(..., description="时段名称(峰/平/谷)")
    volume_ratio: float = Field(0.0, description="电量占比(%)")
    cost_ratio: float = Field(0.0, description="成本占比(%)")
    avg_price: float = Field(0.0, description="平均价格(元/MWh)")


class ForecastAccuracy(BaseModel):
    mae: float = Field(0.0, description="平均绝对误差(MAE)")
    mape: float = Field(0.0, description="平均绝对百分比误差(MAPE)(%)")
    rmse: float = Field(0.0, description="均方根误差(RMSE)")
    within_5pct_rate: float = Field(0.0, description="5%内命中率(%)")


class SpecialEvent(BaseModel):
    event_time: str = Field(..., description="事件时间")
    event_type: str = Field(..., description="事件类型: price_anomaly/deviation_extreme")
    description: str = Field(..., description="事件描述")
    impact_cost: float = Field(0.0, description="影响成本(元)")


class OptimizationSuggestion(BaseModel):
    category: str = Field(..., description="优化类别")
    description: str = Field(..., description="优化描述")
    estimated_saving: float = Field(0.0, description="预计节约(元)")


class SpotTradingReviewCreate(BaseModel):
    customer_id: str = Field(..., description="客户ID")
    customer_name: str = Field(..., description="客户名称")
    review_date: str = Field(..., description="复盘日期 YYYY-MM-DD")
    review_type: Literal["daily", "weekly", "monthly"] = Field("daily", description="复盘类型")
    overview: OverviewStats = Field(default_factory=OverviewStats, description="概览统计")
    time_slot_analysis: List[TimeSlotAnalysisItem] = Field(default_factory=list, description="时段分析")
    forecast_accuracy: ForecastAccuracy = Field(default_factory=ForecastAccuracy, description="预测精度")
    special_events: List[SpecialEvent] = Field(default_factory=list, description="风险事件")
    optimization_suggestions: List[OptimizationSuggestion] = Field(default_factory=list, description="优化建议")


class SpotTradingReview(SpotTradingReviewCreate, BaseMongoModel):
    created_at: dt = Field(default_factory=dt.now, description="创建时间")
    created_by: str = Field("", description="创建人")


class SpotTradingReviewListItem(BaseModel):
    id: str = Field(..., description="报告ID")
    customer_id: str = Field(..., description="客户ID")
    customer_name: str = Field(..., description="客户名称")
    review_date: str = Field(..., description="复盘日期")
    review_type: str = Field(..., description="复盘类型")
    overview: OverviewStats = Field(default_factory=OverviewStats, description="概览统计")
    created_at: dt = Field(..., description="创建时间")


# ========== API 请求/响应模型 ==========

class GenerateReviewRequest(BaseModel):
    customer_id: str = Field(..., description="客户ID")
    review_date: str = Field(..., description="复盘日期 YYYY-MM-DD")
    review_type: Literal["daily", "weekly", "monthly"] = Field("daily", description="复盘类型")


class Point96DataItem(BaseModel):
    time: str = Field(..., description="业务时间标签 00:15/24:00等")
    actual_volume: Optional[float] = Field(None, description="实际电量(MWh)")
    actual_price: Optional[float] = Field(None, description="实际价格(元/MWh)")
    actual_cost: Optional[float] = Field(None, description="实际成本(元)")
    forecast_volume: Optional[float] = Field(None, description="预测电量(MWh)")
    forecast_price: Optional[float] = Field(None, description="预测价格(元/MWh)")
    forecast_cost: Optional[float] = Field(None, description="预测成本(元)")
    volume_deviation: Optional[float] = Field(None, description="电量偏差(MWh)")
    volume_deviation_rate: Optional[float] = Field(None, description="电量偏差率(%)")
    price_deviation: Optional[float] = Field(None, description="价格偏差(元/MWh)")


class Point96DataResponse(BaseModel):
    customer_id: str = Field(..., description="客户ID")
    review_date: str = Field(..., description="复盘日期")
    data: List[Point96DataItem] = Field(default_factory=list, description="96点数据")


class TimeSlotAnalysisResponse(BaseModel):
    customer_id: str = Field(..., description="客户ID")
    review_date: str = Field(..., description="复盘日期")
    time_slot_analysis: List[TimeSlotAnalysisItem] = Field(default_factory=list, description="时段分析")


class ForecastAccuracyResponse(BaseModel):
    customer_id: str = Field(..., description="客户ID")
    review_date: str = Field(..., description="复盘日期")
    forecast_accuracy: ForecastAccuracy = Field(default_factory=ForecastAccuracy, description="预测精度")


class SpecialEventsResponse(BaseModel):
    customer_id: str = Field(..., description="客户ID")
    review_date: str = Field(..., description="复盘日期")
    special_events: List[SpecialEvent] = Field(default_factory=list, description="风险事件")


class ReviewGenerateResponse(BaseModel):
    id: str = Field(..., description="报告ID")
    customer_id: str = Field(..., description="客户ID")
    customer_name: str = Field(..., description="客户名称")
    review_date: str = Field(..., description="复盘日期")
    review_type: str = Field(..., description="复盘类型")
    overview: OverviewStats = Field(default_factory=OverviewStats, description="概览统计")
    time_slot_analysis: List[TimeSlotAnalysisItem] = Field(default_factory=list, description="时段分析")
    forecast_accuracy: ForecastAccuracy = Field(default_factory=ForecastAccuracy, description="预测精度")
    special_events: List[SpecialEvent] = Field(default_factory=list, description="风险事件")
    optimization_suggestions: List[OptimizationSuggestion] = Field(default_factory=list, description="优化建议")
    created_at: dt = Field(..., description="创建时间")
