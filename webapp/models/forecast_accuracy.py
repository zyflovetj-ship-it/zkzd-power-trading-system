from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class AccuracyMetric(BaseModel):
    mae: float = Field(0.0, description="平均绝对误差")
    mape: float = Field(0.0, description="平均绝对百分比误差(%)")
    rmse: float = Field(0.0, description="均方根误差")


class ForecastAccuracyItem(BaseModel):
    date: str = Field(..., description="日期")
    mae: float = Field(..., description="MAE")
    mape: float = Field(..., description="MAPE(%)")
    rmse: float = Field(..., description="RMSE")


class ForecastAccuracyData(BaseModel):
    forecast_type: str = Field(..., description="预测类型")
    metrics: AccuracyMetric = Field(default_factory=AccuracyMetric, description="综合精度指标")
    trend: List[ForecastAccuracyItem] = Field(default_factory=list, description="精度趋势")
    scatter: List[dict] = Field(default_factory=list, description="预测vs实际散点数据")
