"""
RPA 监控数据模型

定义 RPA 任务执行监控相关的 Pydantic 模型。
"""
from pydantic import BaseModel, Field
from typing import Optional, List, Literal
from datetime import datetime
from enum import Enum


# ========== 告警规则枚举 ==========

class AlertLevel(str, Enum):
    """告警级别"""
    CRITICAL = "critical"   # 🔴 严重
    WARNING = "warning"     # 🟠 警告
    INFO = "info"           # 🟡 提示


class AlertRule(str, Enum):
    """告警规则类型"""
    CONSECUTIVE_FAILURE = "consecutive_failure"   # 连续失败
    DATA_DELAY = "data_delay"                     # 数据延迟
    LONG_TIME_NO_SUCCESS = "long_time_no_success" # 长时间未成功
    EXECUTION_TIMEOUT = "execution_timeout"       # 执行超时
    NOT_EXECUTED_TODAY = "not_executed_today"     # 今日未执行


# ========== 任务执行摘要模型 ==========

class TaskExecutionSummary(BaseModel):
    """单条任务执行摘要"""
    pipeline_name: str = Field(..., description="管道名称")
    task_key: str = Field(..., description="子任务标识")
    daily_status: Literal["SUCCESS", "SKIPPED", "FAILED"] = Field(..., description="每日综合状态")
    execution_time: Optional[datetime] = Field(None, description="执行时间")
    execution_count: int = Field(0, description="今日执行次数")
    last_success_date: Optional[str] = Field(None, description="上次成功日期")
    records_inserted: int = Field(0, description="新增记录数")
    records_updated: int = Field(0, description="更新记录数")
    records_skipped: int = Field(0, description="跳过记录数")
    target_collections: List[str] = Field(default_factory=list, description="目标集合列表")
    error_message: Optional[str] = Field(None, description="错误信息")
    message: Optional[str] = Field(None, description="执行消息")
    duration_seconds: Optional[float] = Field(None, description="执行耗时（秒）")


class SummaryStats(BaseModel):
    """摘要统计"""
    success: int = Field(0, description="成功数量")
    skipped: int = Field(0, description="跳过数量")
    failed: int = Field(0, description="失败数量")
    alerts: int = Field(0, description="告警数量")


class DailySummaryResponse(BaseModel):
    """今日执行摘要响应"""
    date: str = Field(..., description="查询日期")
    summary: SummaryStats = Field(..., description="统计汇总")
    tasks: List[TaskExecutionSummary] = Field(default_factory=list, description="任务列表")
    has_data: bool = Field(True, description="是否有数据")


# ========== 执行历史模型 ==========

class ExecutionHistoryItem(BaseModel):
    """单条执行历史记录"""
    pipeline_name: str = Field(..., description="管道名称")
    task_key: str = Field(..., description="子任务标识")
    execution_time: datetime = Field(..., description="执行时间")
    status: str = Field(..., description="执行状态")
    records_inserted: int = Field(0, description="新增记录数")
    records_updated: int = Field(0, description="更新记录数")
    records_skipped: int = Field(0, description="跳过记录数")
    error_message: Optional[str] = Field(None, description="错误信息")
    message: Optional[str] = Field(None, description="执行消息")
    duration_seconds: Optional[float] = Field(None, description="执行耗时（秒）")


class ExecutionBatch(BaseModel):
    """执行批次（按5分钟间隔聚类）"""
    batch_index: int = Field(..., description="批次索引（从1开始）")
    batch_time: str = Field(..., description="批次开始时间（HH:MM格式）")
    start_time: datetime = Field(..., description="批次开始时间戳")
    end_time: datetime = Field(..., description="批次结束时间戳")
    task_count: int = Field(0, description="任务数量")
    success_count: int = Field(0, description="成功数量")
    failed_count: int = Field(0, description="失败数量")
    records: List[ExecutionHistoryItem] = Field(default_factory=list, description="执行记录列表")


class ExecutionHistoryResponse(BaseModel):
    """执行历史响应"""
    date: str = Field(..., description="查询日期")
    total_batches: int = Field(0, description="总批次数")
    batches: List[ExecutionBatch] = Field(default_factory=list, description="批次列表")
    has_data: bool = Field(True, description="是否有数据")


# ========== 告警模型 ==========

class AlertItem(BaseModel):
    """告警项"""
    level: AlertLevel = Field(..., description="告警级别")
    rule: AlertRule = Field(..., description="告警规则")
    pipeline_name: str = Field(..., description="管道名称")
    task_key: str = Field(..., description="子任务标识")
    message: str = Field(..., description="告警消息")
    timestamp: Optional[datetime] = Field(None, description="触发时间")
    can_retry: bool = Field(False, description="是否可重试")


class AlertsResponse(BaseModel):
    """告警响应"""
    date: str = Field(..., description="查询日期")
    alerts: List[AlertItem] = Field(default_factory=list, description="告警列表")


# ========== 重试请求模型 ==========

class RetryRequestCreate(BaseModel):
    """重试请求创建"""
    pipeline_name: str = Field(..., description="管道名称")
    task_key: str = Field(..., description="子任务标识")


class RetryRequestResponse(BaseModel):
    """重试请求响应"""
    id: str = Field(..., description="请求ID")
    pipeline_name: str = Field(..., description="管道名称")
    task_key: str = Field(..., description="子任务标识")
    status: Literal["pending", "in_progress", "completed", "failed", "timeout"] = Field(..., description="状态")
    requested_at: datetime = Field(..., description="请求时间")
    requested_by: str = Field(..., description="请求人")
    picked_up_at: Optional[datetime] = Field(None, description="领取时间")
    completed_at: Optional[datetime] = Field(None, description="完成时间")
    result_message: Optional[str] = Field(None, description="结果消息")
