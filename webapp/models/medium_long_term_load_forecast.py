"""
中长期负荷预测数据模型

用于系统级中长期负荷预测，支持月度粒度的预测数据和置信区间。
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator
from datetime import datetime
from typing import List


class MonthlyForecastPoint(BaseModel):
    """月度负荷预测数据点"""

    month: str = Field(..., description="月份标签，格式 YYYY-MM")
    forecast_value: float = Field(..., description="预测负荷值（MW）", ge=0)
    upper_bound: float = Field(..., description="预测上限（MW）", ge=0)
    lower_bound: float = Field(..., description="预测下限（MW）", ge=0)
    timestamp: str = Field(..., description="ISO格式时间戳")

    @field_validator('upper_bound')
    @classmethod
    def upper_bound_must_be_gte_forecast(cls, v, info):
        """确保上限不小于预测值"""
        if 'forecast_value' in info.data and v < info.data['forecast_value']:
            raise ValueError('upper_bound must be greater than or equal to forecast_value')
        return v

    @field_validator('lower_bound')
    @classmethod
    def lower_bound_must_be_lte_forecast(cls, v, info):
        """确保下限不大于预测值"""
        if 'forecast_value' in info.data and v > info.data['forecast_value']:
            raise ValueError('lower_bound must be less than or equal to forecast_value')
        return v


class MediumLongTermLoadForecastResponse(BaseModel):
    """中长期负荷预测响应"""

    forecast_date: str = Field(..., description="预测发布日期，格式 YYYY-MM-DD")
    forecast_horizon_months: int = Field(..., description="预测时间范围（月数）", ge=1)
    data: List[MonthlyForecastPoint] = Field(..., description="月度预测数据列表")
    total_months: int = Field(..., description="总月份数")

    @field_validator('data')
    @classmethod
    def data_length_matches_horizon(cls, v, info):
        """确保数据长度与预测时间范围匹配"""
        if 'forecast_horizon_months' in info.data and len(v) != info.data['forecast_horizon_months']:
            raise ValueError('data length must match forecast_horizon_months')
        return v


class MediumLongTermLoadForecastCreate(BaseModel):
    """创建中长期负荷预测请求"""

    forecast_date: str = Field(..., description="预测发布日期，格式 YYYY-MM-DD")
    forecast_horizon_months: int = Field(..., description="预测时间范围（月数）", ge=1, le=12)
    base_load_value: float = Field(..., description="基础负荷值（MW），用于生成模拟数据", ge=0)
    confidence_interval_ratio: float = Field(
        default=0.1,
        description="置信区间比例，默认10%，用于生成上下限",
        ge=0.01,
        le=0.5
    )
