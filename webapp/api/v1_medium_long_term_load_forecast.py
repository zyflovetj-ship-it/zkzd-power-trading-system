"""
中长期负荷预测API路由

提供中长期负荷预测数据的RESTful API接口。
"""

import logging
from fastapi import APIRouter, HTTPException, status
from typing import List, Dict, Any

from webapp.models.medium_long_term_load_forecast import (
    MonthlyForecastPoint,
    MediumLongTermLoadForecastResponse,
    MediumLongTermLoadForecastCreate,
)
from webapp.services.medium_long_term_load_forecast_service import (
    MediumLongTermLoadForecastService,
)

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/medium-long-term-load-forecast",
    tags=["中长期负荷预测"],
)


@router.post(
    "",
    response_model=MediumLongTermLoadForecastResponse,
    status_code=status.HTTP_201_CREATED,
    summary="创建中长期负荷预测",
    description="创建一个新的中长期负荷预测，包含指定时间范围内的月度预测数据",
)
async def create_forecast(forecast_data: MediumLongTermLoadForecastCreate):
    """
    创建中长期负荷预测

    Args:
        forecast_data: 预测数据创建请求

    Returns:
        MediumLongTermLoadForecastResponse: 创建的预测数据
    """
    try:
        service = MediumLongTermLoadForecastService()
        result = service.create_forecast(forecast_data)
        logger.info(f"成功创建预测数据: {forecast_data.forecast_date}")
        return result
    except ValueError as e:
        logger.error(f"创建预测数据失败: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except Exception as e:
        logger.error(f"创建预测数据时发生错误: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"创建预测数据失败: {str(e)}",
        )


@router.get(
    "/latest",
    response_model=MediumLongTermLoadForecastResponse,
    summary="获取最新中长期负荷预测",
    description="获取最新发布的中长期负荷预测数据",
)
async def get_latest_forecast():
    """
    获取最新中长期负荷预测

    Returns:
        MediumLongTermLoadForecastResponse: 最新的预测数据
    """
    try:
        service = MediumLongTermLoadForecastService()
        result = service.get_latest_forecast()

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="未找到预测数据",
            )

        logger.info(f"成功获取最新预测数据")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取最新预测数据失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取最新预测数据失败: {str(e)}",
        )


@router.get(
    "/{forecast_date}",
    response_model=MediumLongTermLoadForecastResponse,
    summary="根据日期获取中长期负荷预测",
    description="根据预测发布日期获取中长期负荷预测数据",
)
async def get_forecast_by_date(forecast_date: str):
    """
    根据日期获取中长期负荷预测

    Args:
        forecast_date: 预测发布日期，格式 YYYY-MM-DD

    Returns:
        MediumLongTermLoadForecastResponse: 预测数据
    """
    try:
        service = MediumLongTermLoadForecastService()
        result = service.get_forecast_by_date(forecast_date)

        if result is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到日期为 {forecast_date} 的预测数据",
            )

        logger.info(f"成功获取预测数据: {forecast_date}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取预测数据失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取预测数据失败: {str(e)}",
        )


@router.get(
    "",
    response_model=List[Dict[str, Any]],
    summary="获取所有中长期负荷预测列表",
    description="获取所有中长期负荷预测的摘要列表",
)
async def get_all_forecasts():
    """
    获取所有中长期负荷预测列表

    Returns:
        List[Dict[str, Any]]: 预测数据摘要列表
    """
    try:
        service = MediumLongTermLoadForecastService()
        result = service.get_all_forecasts()
        logger.info(f"成功获取所有预测数据列表，共 {len(result)} 条")
        return result
    except Exception as e:
        logger.error(f"获取所有预测数据失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"获取所有预测数据失败: {str(e)}",
        )


@router.delete(
    "/{forecast_date}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="删除中长期负荷预测",
    description="删除指定日期的中长期负荷预测数据",
)
async def delete_forecast(forecast_date: str):
    """
    删除中长期负荷预测

    Args:
        forecast_date: 预测发布日期，格式 YYYY-MM-DD
    """
    try:
        service = MediumLongTermLoadForecastService()
        success = service.delete_forecast(forecast_date)

        if not success:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"未找到日期为 {forecast_date} 的预测数据",
            )

        logger.info(f"成功删除预测数据: {forecast_date}")
        return None
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"删除预测数据失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"删除预测数据失败: {str(e)}",
        )
