from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional

from webapp.models.scheduler import (
    TaskConfigUpdate,
    TaskConfigListResponse,
    ExecutionLogListResponse,
    SchedulerStats,
    TrendDataPoint,
    ToggleRequest,
    TriggerResponse,
)
from webapp.services.scheduler_service import SchedulerService
from webapp.tools.mongo import DATABASE
from webapp.tools.security import get_current_active_user, User

router = APIRouter(prefix="/scheduler", tags=["Scheduler"])

# 由 main.py 在 startup 时注入真正运行中的调度器实例。
# 这样 API 层与后台任务共用同一个 SchedulerService，
# 手动触发 / 启停 / 改期 才会作用到实际在跑的 APScheduler 上。
_service: Optional[SchedulerService] = None


def set_scheduler_service(service: SchedulerService) -> None:
    """注册全局调度器单例（由应用启动流程调用）。"""
    global _service
    _service = service


def get_scheduler_service() -> SchedulerService:
    """获取调度器单例。

    若启动流程尚未注入（例如被单独 import 而未经过 main.py 启动），则回退创建一个；
    此时该实例未 start()，涉及 APScheduler 的操作会明确报"调度器未运行"，而不是静默失效。
    """
    global _service
    if _service is None:
        _service = SchedulerService(DATABASE)
    return _service


@router.get("/tasks", response_model=TaskConfigListResponse, summary="获取任务列表")
async def list_tasks(
    task_type: Optional[str] = Query(None, description="任务类型筛选"),
    is_enabled: Optional[bool] = Query(None, description="启用状态筛选"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    current_user: User = Depends(get_current_active_user),
):
    """获取任务配置列表，支持按类型和启用状态筛选"""
    service = get_scheduler_service()
    return service.list_tasks(
        task_type=task_type, is_enabled=is_enabled, page=page, page_size=page_size
    )


@router.get("/tasks/{task_name}", response_model=dict, summary="获取任务详情")
async def get_task(
    task_name: str,
    current_user: User = Depends(get_current_active_user),
):
    """获取指定任务的配置详情"""
    service = get_scheduler_service()
    result = service.get_task(task_name)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"任务 '{task_name}' 不存在",
        )
    return result


@router.post(
    "/tasks/{task_name}/trigger",
    response_model=TriggerResponse,
    summary="手动触发任务",
)
async def trigger_task(
    task_name: str,
    current_user: User = Depends(get_current_active_user),
):
    """手动触发指定任务的执行"""
    service = get_scheduler_service()
    try:
        result = service.trigger_job(task_name, triggered_by=current_user.username)
        return TriggerResponse(
            task_name=result["task_name"],
            status=result["status"],
            message=result["message"],
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(e)
        )


@router.post(
    "/tasks/{task_name}/toggle",
    response_model=dict,
    summary="启用/禁用任务",
)
async def toggle_task(
    task_name: str,
    toggle_data: ToggleRequest,
    current_user: User = Depends(get_current_active_user),
):
    """启用或禁用指定任务"""
    service = get_scheduler_service()
    try:
        service.toggle_job(
            task_name=task_name,
            is_enabled=toggle_data.is_enabled,
            operator=current_user.username,
        )
        return {
            "task_name": task_name,
            "is_enabled": toggle_data.is_enabled,
            "message": f"任务已{'启用' if toggle_data.is_enabled else '禁用'}",
        }
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )


@router.put("/tasks/{task_name}", response_model=dict, summary="更新任务配置")
async def update_task(
    task_name: str,
    update_data: TaskConfigUpdate,
    current_user: User = Depends(get_current_active_user),
):
    """更新指定任务的配置（调度配置、重试配置、告警配置等）"""
    service = get_scheduler_service()
    try:
        result = service.update_task(
            task_name=task_name,
            update_data=update_data.model_dump(exclude_unset=True),
            operator=current_user.username,
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(e)
        )


@router.get(
    "/tasks/{task_name}/logs",
    response_model=ExecutionLogListResponse,
    summary="获取执行日志",
)
async def get_task_logs(
    task_name: str,
    log_status: Optional[str] = Query(None, description="状态筛选(running/success/failed/skipped)"),
    page: int = Query(1, ge=1, description="页码"),
    page_size: int = Query(20, ge=1, le=100, description="每页大小"),
    current_user: User = Depends(get_current_active_user),
):
    """获取指定任务的执行日志，支持分页"""
    service = get_scheduler_service()
    return service.get_execution_logs(
        task_name=task_name, status=log_status, page=page, page_size=page_size
    )


@router.get("/stats", response_model=SchedulerStats, summary="统计概览")
async def get_stats(
    current_user: User = Depends(get_current_active_user),
):
    """获取调度统计概览：总任务数、启用/禁用数、最近执行统计"""
    service = get_scheduler_service()
    return service.get_stats()


@router.get("/stats/trend", summary="执行趋势")
async def get_trend(
    days: int = Query(7, ge=1, le=90, description="统计天数(1-90)"),
    current_user: User = Depends(get_current_active_user),
):
    """获取执行趋势数据（最近N天的执行次数和成功率）"""
    service = get_scheduler_service()
    return service.get_trend(days=days)
