import traceback
from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field, ConfigDict
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


# ==================== 调度配置子模型 ====================

class ScheduleConfig(BaseModel):
    """调度配置"""
    trigger_type: Literal["cron", "interval", "date"] = Field("cron", description="触发类型")
    cron_expression: Optional[str] = Field(None, description="Cron表达式，如 '0 8 * * *'")
    interval_seconds: Optional[int] = Field(None, description="间隔秒数")
    run_at: Optional[datetime] = Field(None, description="一次性执行时间")


class RetryConfig(BaseModel):
    """重试配置"""
    max_retries: int = Field(3, ge=0, description="最大重试次数")
    retry_delay_seconds: int = Field(60, ge=1, description="重试间隔(秒)")


class AlertConfig(BaseModel):
    """告警配置"""
    on_failure: bool = Field(True, description="失败时告警")
    on_success: bool = Field(False, description="成功时告警")
    alert_level: Literal["P0", "P1", "P2", "P3"] = Field("P2", description="告警级别")


# ==================== 任务配置模型 ====================

class TaskConfigCreate(BaseModel):
    """任务配置创建模型"""
    name: str = Field(..., min_length=1, description="任务唯一名称")
    display_name: str = Field(..., min_length=1, description="显示名称")
    description: str = Field("", description="任务描述")
    task_type: str = Field("default", description="任务类型")
    is_enabled: bool = Field(True, description="是否启用")
    schedule_config: ScheduleConfig = Field(default_factory=ScheduleConfig, description="调度配置")
    retry_config: RetryConfig = Field(default_factory=RetryConfig, description="重试配置")
    alert_config: AlertConfig = Field(default_factory=AlertConfig, description="告警配置")


class TaskConfigUpdate(BaseModel):
    """任务配置更新模型"""
    display_name: Optional[str] = Field(None, min_length=1, description="显示名称")
    description: Optional[str] = Field(None, description="任务描述")
    is_enabled: Optional[bool] = Field(None, description="是否启用")
    schedule_config: Optional[ScheduleConfig] = Field(None, description="调度配置")
    retry_config: Optional[RetryConfig] = Field(None, description="重试配置")
    alert_config: Optional[AlertConfig] = Field(None, description="告警配置")


class TaskConfigFull(BaseMongoModel):
    """任务配置完整模型（对应数据库）"""
    name: str = Field(..., description="任务唯一名称")
    display_name: str = Field(..., description="显示名称")
    description: str = Field("", description="任务描述")
    task_type: str = Field("default", description="任务类型")
    is_enabled: bool = Field(True, description="是否启用")
    schedule_config: ScheduleConfig = Field(default_factory=ScheduleConfig)
    retry_config: RetryConfig = Field(default_factory=RetryConfig)
    alert_config: AlertConfig = Field(default_factory=AlertConfig)
    last_run_at: Optional[datetime] = Field(None, description="上次执行时间")
    last_run_status: Optional[str] = Field(None, description="上次执行状态")
    next_run_at: Optional[datetime] = Field(None, description="下次执行时间")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")
    updated_at: datetime = Field(default_factory=datetime.now, description="更新时间")
    created_by: Optional[str] = Field(None, description="创建人")
    updated_by: Optional[str] = Field(None, description="更新人")


class TaskConfigListItem(BaseModel):
    """任务配置列表项"""
    id: str = Field(..., description="ID")
    name: str = Field(..., description="任务唯一名称")
    display_name: str = Field(..., description="显示名称")
    description: str = Field("", description="任务描述")
    task_type: str = Field(..., description="任务类型")
    is_enabled: bool = Field(..., description="是否启用")
    schedule_config: ScheduleConfig = Field(..., description="调度配置")
    last_run_at: Optional[datetime] = Field(None, description="上次执行时间")
    last_run_status: Optional[str] = Field(None, description="上次执行状态")
    next_run_at: Optional[datetime] = Field(None, description="下次执行时间")
    updated_at: datetime = Field(..., description="更新时间")


class TaskConfigListResponse(BaseModel):
    """任务配置列表响应"""
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    items: List[TaskConfigListItem] = Field(..., description="任务列表")


# ==================== 执行日志模型 ====================

class ExecutionLogCreate(BaseModel):
    """执行日志创建模型"""
    task_name: str = Field(..., description="任务名称")
    task_type: str = Field(..., description="任务类型")
    status: Literal["running", "success", "failed", "skipped"] = Field(..., description="执行状态")
    started_at: datetime = Field(default_factory=datetime.now, description="开始时间")
    finished_at: Optional[datetime] = Field(None, description="结束时间")
    duration_ms: Optional[int] = Field(None, description="执行耗时(毫秒)")
    result_summary: Optional[str] = Field(None, description="结果摘要")
    error_message: Optional[str] = Field(None, description="错误消息")
    error_traceback: Optional[str] = Field(None, description="错误堆栈")
    trigger_type: Literal["scheduled", "manual"] = Field("scheduled", description="触发类型")
    triggered_by: Optional[str] = Field(None, description="触发人")


class ExecutionLogFull(BaseMongoModel):
    """执行日志完整模型"""
    task_name: str = Field(..., description="任务名称")
    task_type: str = Field(..., description="任务类型")
    status: str = Field(..., description="执行状态")
    started_at: datetime = Field(..., description="开始时间")
    finished_at: Optional[datetime] = Field(None, description="结束时间")
    duration_ms: Optional[int] = Field(None, description="执行耗时(毫秒)")
    result_summary: Optional[str] = Field(None, description="结果摘要")
    error_message: Optional[str] = Field(None, description="错误消息")
    error_traceback: Optional[str] = Field(None, description="错误堆栈")
    trigger_type: str = Field("scheduled", description="触发类型")
    triggered_by: Optional[str] = Field(None, description="触发人")
    created_at: datetime = Field(default_factory=datetime.now, description="创建时间")


class ExecutionLogListItem(BaseModel):
    """执行日志列表项"""
    id: str = Field(..., description="ID")
    task_name: str = Field(..., description="任务名称")
    task_type: str = Field(..., description="任务类型")
    status: str = Field(..., description="执行状态")
    started_at: datetime = Field(..., description="开始时间")
    finished_at: Optional[datetime] = Field(None, description="结束时间")
    duration_ms: Optional[int] = Field(None, description="执行耗时(毫秒)")
    result_summary: Optional[str] = Field(None, description="结果摘要")
    error_message: Optional[str] = Field(None, description="错误消息")
    trigger_type: str = Field(..., description="触发类型")
    triggered_by: Optional[str] = Field(None, description="触发人")


class ExecutionLogListResponse(BaseModel):
    """执行日志列表响应"""
    total: int = Field(..., description="总数量")
    page: int = Field(..., description="当前页码")
    page_size: int = Field(..., description="每页大小")
    items: List[ExecutionLogListItem] = Field(..., description="日志列表")


# ==================== 统计模型 ====================

class SchedulerStats(BaseModel):
    """调度统计概览"""
    total_tasks: int = Field(..., description="总任务数")
    enabled_tasks: int = Field(..., description="启用任务数")
    disabled_tasks: int = Field(..., description="禁用任务数")
    recent_success_count: int = Field(0, description="最近成功次数")
    recent_failed_count: int = Field(0, description="最近失败次数")
    recent_running_count: int = Field(0, description="最近运行中次数")


class TrendDataPoint(BaseModel):
    """趋势数据点"""
    date: str = Field(..., description="日期")
    total_count: int = Field(0, description="执行总数")
    success_count: int = Field(0, description="成功次数")
    failed_count: int = Field(0, description="失败次数")
    success_rate: float = Field(0.0, description="成功率(%)")


class ToggleRequest(BaseModel):
    """启用/禁用请求"""
    is_enabled: bool = Field(..., description="是否启用")


class TriggerResponse(BaseModel):
    """触发响应"""
    task_name: str = Field(..., description="任务名称")
    status: str = Field(..., description="状态")
    message: str = Field(..., description="消息")
