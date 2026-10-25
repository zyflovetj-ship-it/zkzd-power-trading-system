"""
RPA 监控 API 路由

提供 RPA 任务执行监控相关的 API 端点。
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Query
from typing import Optional
from datetime import datetime, date

from webapp.tools.mongo import DATABASE
from webapp.services.rpa_monitor_service import RpaMonitorService
from webapp.tools.security import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter()


def get_rpa_monitor_service() -> RpaMonitorService:
    """获取 RPA 监控服务实例"""
    return RpaMonitorService(DATABASE)


@router.get(
    "/execution/daily",
    status_code=status.HTTP_200_OK,
    summary="获取每日执行摘要",
    description="获取指定日期的任务执行摘要，包括各状态统计和任务列表",
    tags=["RPA监控"]
)
async def get_daily_summary(
    date: Optional[str] = Query(None, description="查询日期（YYYY-MM-DD），默认今日"),
    current_user: dict = Depends(get_current_active_user)
):
    """获取每日执行摘要"""
    service = get_rpa_monitor_service()

    # 默认查询今日
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    try:
        result = service.get_daily_summary(date)
        return result
    except Exception as e:
        logger.error(f"获取每日摘要失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据失败: {str(e)}"
        )


@router.get(
    "/execution/history",
    status_code=status.HTTP_200_OK,
    summary="获取执行历史",
    description="获取指定日期的执行历史记录，按批次聚类（5分钟间隔）",
    tags=["RPA监控"]
)
async def get_execution_history(
    date: Optional[str] = Query(None, description="查询日期（YYYY-MM-DD），默认今日"),
    current_user: dict = Depends(get_current_active_user)
):
    """获取执行历史"""
    service = get_rpa_monitor_service()

    # 默认查询今日
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    try:
        result = service.get_execution_history(date)
        return result
    except Exception as e:
        logger.error(f"获取执行历史失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据失败: {str(e)}"
        )


@router.get(
    "/alerts",
    status_code=status.HTTP_200_OK,
    summary="获取告警列表",
    description="获取指定日期的实时告警",
    tags=["RPA监控"]
)
async def get_alerts(
    date: Optional[str] = Query(None, description="查询日期（YYYY-MM-DD），默认今日"),
    current_user: dict = Depends(get_current_active_user)
):
    """获取告警列表"""
    service = get_rpa_monitor_service()

    # 默认查询今日
    if not date:
        date = datetime.now().strftime("%Y-%m-%d")

    try:
        alerts = service.calculate_alerts(date)
        return {"date": date, "alerts": alerts}
    except Exception as e:
        logger.error(f"获取告警失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据失败: {str(e)}"
        )


@router.post(
    "/tasks/{pipeline_name}/{task_key}/retry",
    status_code=status.HTTP_201_CREATED,
    summary="创建重试请求",
    description="为指定任务创建重试请求，RPA客户端将轮询并执行",
    tags=["RPA监控"]
)
async def create_retry_request(
    pipeline_name: str,
    task_key: str,
    current_user: dict = Depends(get_current_active_user)
):
    """创建重试请求"""
    service = get_rpa_monitor_service()

    try:
        result = service.create_retry_request(
            pipeline_name=pipeline_name,
            task_key=task_key,
            operator=getattr(current_user, "username", "unknown")
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"创建重试请求失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建重试请求失败: {str(e)}"
        )


@router.get(
    "/tasks/{pipeline_name}/{task_key}/retry-status",
    status_code=status.HTTP_200_OK,
    summary="获取重试状态",
    description="获取指定任务的最新重试请求状态",
    tags=["RPA监控"]
)
async def get_retry_status(
    pipeline_name: str,
    task_key: str,
    current_user: dict = Depends(get_current_active_user)
):
    """获取重试状态"""
    service = get_rpa_monitor_service()

    try:
        result = service.get_retry_status(pipeline_name, task_key)
        if not result:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到任务 {pipeline_name}/{task_key} 的重试请求"
            )
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取重试状态失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取数据失败: {str(e)}"
        )
