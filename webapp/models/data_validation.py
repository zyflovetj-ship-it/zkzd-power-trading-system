"""
负荷数据校验模块 Pydantic 数据模型

包含三个集合的数据模型：
1. load_curve_user - 48点用户级负荷曲线
2. settlement_curve_user - 48点用户级结算曲线
3. data_quality_report - 数据质量报告
"""
from pydantic import BaseModel, Field, ConfigDict
from typing import Optional, List, Any, Dict, Literal
from datetime import datetime as dt, date
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


# ========== 计量点贡献信息 ==========

class MpContribution(BaseModel):
    mp_id: str = Field(..., description="计量点ID")
    meter_id: str = Field(..., description="电表资产号")
    load_kwh: float = Field(..., description="该计量点贡献的电量(kWh)")
    allocation_percentage: float = Field(..., ge=0, le=100, description="分配比例(%)")


class AggregationMeta(BaseModel):
    mp_count: int = Field(..., description="参与聚合的计量点数量")
    mp_contributions: List[MpContribution] = Field(default_factory=list, description="各计量点贡献明细")


# ========== 48点负荷曲线（用户级） ==========

class LoadCurveUserCreate(BaseModel):
    customer_id: str = Field(..., description="客户ID")
    customer_name: str = Field(..., description="客户名称")
    datetime: dt = Field(..., description="时间点")
    load_kwh: float = Field(..., description="电量(kWh)")
    data_source: Literal["manual_import"] = "manual_import"
    import_batch_id: str = Field(..., description="导入批次ID")
    aggregation_meta: Optional[AggregationMeta] = Field(None, description="聚合元数据")


class LoadCurveUser(LoadCurveUserCreate, BaseMongoModel):
    created_at: dt = Field(default_factory=dt.now, description="创建时间")


class LoadCurveUserListItem(BaseModel):
    id: str = Field(..., description="记录ID")
    customer_id: str = Field(..., description="客户ID")
    customer_name: str = Field(..., description="客户名称")
    datetime: dt = Field(..., description="时间点")
    load_kwh: float = Field(..., description="电量(kWh)")
    data_source: str = Field(..., description="数据来源")
    import_batch_id: str = Field(..., description="导入批次ID")
    created_at: dt = Field(..., description="创建时间")


# ========== 48点结算曲线（用户级） ==========

class SettlementCurveUserCreate(BaseModel):
    customer_id: str = Field(..., description="客户ID")
    customer_name: str = Field(..., description="客户名称")
    datetime: dt = Field(..., description="时间点")
    load_kwh: float = Field(..., description="电量(kWh)")
    data_source: Literal["rpa_settlement"] = "rpa_settlement"
    rpa_batch_id: str = Field(..., description="RPA批次ID")
    aggregation_meta: Optional[AggregationMeta] = Field(None, description="聚合元数据")


class SettlementCurveUser(SettlementCurveUserCreate, BaseMongoModel):
    created_at: dt = Field(default_factory=dt.now, description="创建时间")


class SettlementCurveUserListItem(BaseModel):
    id: str = Field(..., description="记录ID")
    customer_id: str = Field(..., description="客户ID")
    customer_name: str = Field(..., description="客户名称")
    datetime: dt = Field(..., description="时间点")
    load_kwh: float = Field(..., description="电量(kWh)")
    data_source: str = Field(..., description="数据来源")
    rpa_batch_id: str = Field(..., description="RPA批次ID")
    created_at: dt = Field(..., description="创建时间")


# ========== 数据完整性分析 ==========

class CurveCompleteness(BaseModel):
    start_date: Optional[str] = Field(None, description="数据起始日期")
    end_date: Optional[str] = Field(None, description="数据结束日期")
    expected_end_date: str = Field(..., description="期望结束日期")
    total_days: int = Field(..., description="应覆盖天数")
    actual_days: int = Field(..., description="实际覆盖天数")
    missing_days: int = Field(..., description="缺失天数")
    missing_dates: List[str] = Field(default_factory=list, description="缺失日期列表")
    completeness_rate: float = Field(..., ge=0, le=100, description="完整度(%)")


class OverlapAnalysis(BaseModel):
    overlap_start_date: Optional[str] = Field(None, description="重叠起始日期")
    overlap_end_date: Optional[str] = Field(None, description="重叠结束日期")
    overlap_days: int = Field(..., description="重叠天数")
    daily_deviations: List[Dict[str, Any]] = Field(default_factory=list, description="每日偏差明细")


class CompletenessAnalysis(BaseModel):
    load_curve: Optional[CurveCompleteness] = Field(None, description="负荷曲线完整度")
    settlement_curve: Optional[CurveCompleteness] = Field(None, description="结算曲线完整度")
    overlap_analysis: Optional[OverlapAnalysis] = Field(None, description="重叠分析")


# ========== 数据校核结果 ==========

class UserLevelStatistics(BaseModel):
    mean_deviation: float = Field(..., description="平均偏差(kWh)")
    mean_deviation_rate: float = Field(..., description="平均偏差率(%)")
    max_positive_deviation: float = Field(..., description="最大正偏差(kWh)")
    max_negative_deviation: float = Field(..., description="最大负偏差(kWh)")


class MeteringPointAnalysis(BaseModel):
    mp_id: str = Field(..., description="计量点ID")
    meter_id: str = Field(..., description="电表资产号")
    current_allocation: float = Field(..., description="当前分配比例(%)")
    mean_deviation_rate: float = Field(..., description="平均偏差率(%)")


class CurveComparisonPoint(BaseModel):
    time: str = Field(..., description="时间标签")
    load_value: Optional[float] = Field(None, description="负荷曲线值(kWh)")
    settlement_value: Optional[float] = Field(None, description="结算曲线值(kWh)")
    deviation: Optional[float] = Field(None, description="偏差(kWh)")


class ValidationResult(BaseModel):
    analysis_period: str = Field(..., description="分析日期")
    data_points_compared: int = Field(..., description="对比数据点数")
    user_level_statistics: Optional[UserLevelStatistics] = Field(None, description="用户级统计")
    deep_analysis_required: bool = Field(False, description="是否需要深入分析")
    metering_point_analysis: List[MeteringPointAnalysis] = Field(default_factory=list, description="计量点级分析")
    curve_comparison_data: List[CurveComparisonPoint] = Field(default_factory=list, description="曲线对比数据")


class ReportMetadata(BaseModel):
    analysis_duration_ms: float = Field(..., description="分析耗时(ms)")
    triggered_by: str = Field(..., description="触发方式")
    trigger_user: str = Field(..., description="触发用户")


# ========== 数据质量报告 ==========

class DataQualityReportCreate(BaseModel):
    customer_id: str = Field(..., description="客户ID")
    customer_name: str = Field(..., description="客户名称")
    report_type: Literal["completeness", "validation"] = Field(..., description="报告类型")
    generated_at: dt = Field(default_factory=dt.now, description="生成时间")
    completeness_analysis: Optional[CompletenessAnalysis] = Field(None, description="完整性分析")
    validation_result: Optional[ValidationResult] = Field(None, description="校核结果")
    metadata: Optional[ReportMetadata] = Field(None, description="元数据")


class DataQualityReport(DataQualityReportCreate, BaseMongoModel):
    pass


class DataQualityReportListItem(BaseModel):
    id: str = Field(..., description="报告ID")
    customer_id: str = Field(..., description="客户ID")
    customer_name: str = Field(..., description="客户名称")
    report_type: str = Field(..., description="报告类型")
    generated_at: dt = Field(..., description="生成时间")


# ========== API 请求/响应模型 ==========

class TransformManualDataRequest(BaseModel):
    import_batch_id: str = Field(..., description="导入批次ID")


class ImportRpaDataRequest(BaseModel):
    rpa_batch_id: str = Field(..., description="RPA批次ID")
    source_collection: str = Field("mp_load_curve", description="源数据集合名称")


class AnalyzeCompletenessRequest(BaseModel):
    customer_id: str = Field(..., description="客户ID")


class ValidateCurvesRequest(BaseModel):
    customer_id: str = Field(..., description="客户ID")
    validation_date: date = Field(..., description="校核日期")
    deep_analysis_threshold: float = Field(5.0, description="深入分析阈值(%)")


class RegenerateLoadCurveRequest(BaseModel):
    customer_id: str = Field(..., description="客户ID")


class CompletenessDashboardResponse(BaseModel):
    total_customers: int = Field(..., description="总客户数")
    healthy_customers: int = Field(..., description="健康客户数(≥90%)")
    warning_customers: int = Field(..., description="预警客户数(70-89%)")
    critical_customers: int = Field(..., description="严重客户数(<70%)")
    customers: List[Dict[str, Any]] = Field(default_factory=list, description="客户列表")


class CurveComparisonResponse(BaseModel):
    customer_id: str = Field(..., description="客户ID")
    comparison_date: str = Field(..., description="对比日期")
    load_curve: List[Dict[str, Any]] = Field(default_factory=list, description="负荷曲线数据")
    settlement_curve: List[Dict[str, Any]] = Field(default_factory=list, description="结算曲线数据")
    comparison_data: List[CurveComparisonPoint] = Field(default_factory=list, description="对比数据")
