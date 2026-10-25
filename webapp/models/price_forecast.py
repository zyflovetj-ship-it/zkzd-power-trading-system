"""
D-2价格预测相关数据模型
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime


class PriceForecastPoint(BaseModel):
    """单个价格预测数据点"""
    datetime: str = Field(..., description="ISO时间戳")
    target_date: str = Field(..., description="目标日期 YYYY-MM-DD")
    predicted_price: float = Field(..., description="预测价格 (元/MWh)")
    confidence_80_lower: float = Field(..., description="80%置信区间下界")
    confidence_80_upper: float = Field(..., description="80%置信区间上界")
    confidence_90_lower: float = Field(..., description="90%置信区间下界")
    confidence_90_upper: float = Field(..., description="90%置信区间上界")


class PriceForecastBatch(BaseModel):
    """D-2价格预测批次"""
    forecast_id: str = Field(..., description="预测批次ID")
    forecast_date: str = Field(..., description="预测执行日期")
    forecast_type: str = Field(..., description="预测类型: d2_price")
    target_dates: List[str] = Field(..., description="目标日期列表 (10天)")
    data: List[PriceForecastPoint] = Field(..., description="预测数据点 (96点/天 × 10天)")


class ComparisonDataPoint(BaseModel):
    """对比分析数据点"""
    time: str = Field(..., description="时间标签 HH:MM")
    predicted: float = Field(..., description="预测值")
    actual: Optional[float] = Field(None, description="实际值")
    difference: Optional[float] = Field(None, description="偏差 (实际值-预测值)")


class ComparisonMetrics(BaseModel):
    """对比分析指标"""
    mae: float = Field(..., description="平均绝对误差")
    rmse: float = Field(..., description="均方根误差")
    mape: float = Field(..., description="平均百分比误差")
    accuracy: float = Field(..., description="预测准确度 (WMAPE)")


class ComparisonResponse(BaseModel):
    """对比分析响应"""
    target_date: str = Field(..., description="目标日期")
    data: List[ComparisonDataPoint] = Field(..., description="96点对比数据")
    metrics: ComparisonMetrics = Field(..., description="误差指标")


class AccuracyRecord(BaseModel):
    """准确度记录"""
    target_date: str = Field(..., description="目标日期")
    wmape_accuracy: float = Field(..., description="WMAPE准确度")
    mae: float = Field(..., description="平均绝对误差")
    rmse: float = Field(..., description="均方根误差")
    mape: float = Field(..., description="平均百分比误差")
    direction_accuracy: float = Field(..., description="方向准确度")


class AccuracyStatsResponse(BaseModel):
    """准确度统计响应"""
    start_date: str = Field(..., description="统计起始日期")
    end_date: str = Field(..., description="统计结束日期")
    monthly_avg: float = Field(..., description="月平均准确度")
    best_day: dict = Field(..., description="最佳准确度 {date, accuracy}")
    worst_day: dict = Field(..., description="最低准确度 {date, accuracy}")
    pass_90_count: int = Field(..., description="≥90%准确度天数")
    total_days: int = Field(..., description="总天数")
    records: List[AccuracyRecord] = Field(..., description="每日准确度记录")
