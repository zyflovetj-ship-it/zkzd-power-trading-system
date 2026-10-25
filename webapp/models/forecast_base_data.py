from pydantic import BaseModel, Field
from typing import List, Optional


class TimeSeriesDataPoint(BaseModel):
    """时序数据点（96点中的一个）"""
    time: str = Field(..., description="业务时间标签，例如: 00:15, 23:45, 24:00")
    value: float = Field(..., description="数值")
    timestamp: str = Field(..., description="ISO 时间戳字符串")


class DataAvailability(BaseModel):
    """数据可用性单元格"""
    data_item_id: int = Field(..., ge=1, le=15, description="数据项ID (1-15)")
    data_item_name: Optional[str] = Field(None, description="数据项名称")
    date: str = Field(..., description="日期 YYYY-MM-DD")
    is_available: bool = Field(..., description="该数据项在该日期是否存在数据（以12:00是否存在作为判定）")
    sample_timestamp: Optional[str] = Field(None, description="样本时间点（12:00）的时间戳，若无则为None")


class DataAvailabilityResponse(BaseModel):
    """数据可用性响应"""
    base_date: str = Field(..., description="基准日期 YYYY-MM-DD")
    date_range: List[str] = Field(..., description="日期列表")
    availability_matrix: List[List[DataAvailability]] = Field(..., description="可用性矩阵：15行×N列")


class CurveDataRequest(BaseModel):
    """曲线数据请求"""
    data_item_id: int = Field(..., ge=1, le=15, description="数据项ID (1-15)")
    date: str = Field(..., description="日期 YYYY-MM-DD")


class CurveDataResponse(BaseModel):
    """单条曲线数据响应"""
    data_item_id: int = Field(..., ge=1, le=15, description="数据项ID (1-15)")
    data_item_name: str = Field(..., description="数据项名称")
    date: str = Field(..., description="日期 YYYY-MM-DD")
    data: List[TimeSeriesDataPoint] = Field(..., description="96点时序数据")
    total_points: int = Field(..., description="有效点数量")
    completeness: float = Field(..., description="数据完整度百分比（0-100，保留两位小数）")


class MultipleCurvesResponse(BaseModel):
    """多曲线数据响应"""
    curves: List[CurveDataResponse]

