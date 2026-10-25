"""
短期负荷预测数据模型

遵循规范：docs/spec/后端开发规范.md
"""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class ShortTermLoadForecastTimePoint(BaseModel):
    """短期负荷预测时间点数据模型（用于API响应）"""

    time: str = Field(..., description="时间标签，格式为 HH:MM 或 24:00")
    forecast_value: float = Field(..., description="预测负荷值（MW）")
    actual_value: Optional[float] = Field(None, description="实际负荷值（MW），仅历史数据有")
    timestamp: str = Field(..., description="ISO格式时间戳")


class ShortTermLoadForecastCurveResponse(BaseModel):
    """短期负荷预测曲线响应模型"""

    forecast_date: str = Field(..., description="预测日期（业务日），格式：YYYY-MM-DD")
    forecast_target_date: str = Field(..., description="预测目标日期，格式：YYYY-MM-DD")
    forecast_type: str = Field(..., description="预测类型：d+1, d+2, d+3")
    data: list[ShortTermLoadForecastTimePoint] = Field(..., description="96点预测曲线数据")
    total_points: int = Field(..., description="数据点总数")
    completeness: float = Field(..., description="数据完整性百分比")
    has_actual: bool = Field(False, description="是否包含实际值")


class ShortTermLoadForecastAccuracyMetrics(BaseModel):
    """短期负荷预测精度指标"""

    forecast_date: str = Field(..., description="预测日期（业务日）")
    forecast_target_date: str = Field(..., description="预测目标日期")
    forecast_type: str = Field(..., description="预测类型")
    mae: Optional[float] = Field(None, description="平均绝对误差（MW）")
    mape: Optional[float] = Field(None, description="平均绝对百分比误差（%）")
    rmse: Optional[float] = Field(None, description="均方根误差（MW）")
    max_error: Optional[float] = Field(None, description="最大误差（MW）")
    max_error_time: Optional[str] = Field(None, description="最大误差发生时刻")


class ShortTermLoadForecastListItem(BaseModel):
    """短期负荷预测列表项（用于查询列表）"""

    forecast_date: str = Field(..., description="预测日期（业务日）")
    forecast_target_date: str = Field(..., description="预测目标日期")
    forecast_types: list[str] = Field(..., description="可用的预测类型列表")
    has_actual: bool = Field(False, description="是否有实际值可供对比")
    created_at: Optional[str] = Field(None, description="创建时间")
