"""
短期负荷预测 API 路由

遵循规范：docs/spec/后端开发规范.md
- API 层负责将 Service 层的 ValueError 转换为 HTTPException
- 使用 Pydantic 模型进行请求/响应校验
- RESTful 设计风格
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query, status, Depends
from pydantic import BaseModel
from webapp.tools.mongo import DATABASE
from webapp.services.short_term_load_forecast_service import ShortTermLoadForecastService
from webapp.models.short_term_load_forecast import (
    ShortTermLoadForecastCurveResponse,
    ShortTermLoadForecastAccuracyMetrics,
    ShortTermLoadForecastListItem,
)
from webapp.tools.mongo import DATABASE

logger = logging.getLogger(__name__)

router = APIRouter(tags=["短期负荷预测"])


def get_forecast_service() -> ShortTermLoadForecastService:
    """获取短期负荷预测服务实例（依赖注入）"""
    return ShortTermLoadForecastService(DATABASE)


class MultipleForecastsResponse(BaseModel):
    """多个预测曲线响应模型"""

    forecast_date: str
    curves: list[ShortTermLoadForecastCurveResponse]



@router.get("/curve")
def get_short_term_load_forecast_curve(
    forecast_date: str,
    forecast_type: str = "d+1"
):
    """直接获取短期负荷预测曲线"""
    from datetime import datetime
    from webapp.services.short_term_load_forecast_service import ShortTermLoadForecastService
    from fastapi import HTTPException

    try:
        # 验证日期格式
        date_obj = datetime.strptime(forecast_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(status_code=400, detail="无效的日期格式，请使用 YYYY-MM-DD")

    try:
        # 获取服务实例并查询数据
        service = ShortTermLoadForecastService(DATABASE)
        result = service.get_forecast_curve(date_obj, forecast_type)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")


@router.get(
    "/multiple-curves",
    response_model=MultipleForecastsResponse,
    summary="获取多个预测曲线",
    description="获取指定预测日期的多个预测类型曲线（d+1, d+2, d+3）"
)
def get_multiple_forecasts(
    forecast_date: str = Query(..., description="预测日期（业务日），格式：YYYY-MM-DD"),
    forecast_types: Optional[str] = Query(None, description="预测类型列表，逗号分隔，如：d+1,d+2,d+3"),
    service: ShortTermLoadForecastService = Depends(get_forecast_service)
):
    """
    获取指定预测日期的多个预测类型曲线

    **示例**：
    - `GET /api/v1/short-term-load-forecast/multiple-curves?forecast_date=2025-01-10`
    - `GET /api/v1/short-term-load-forecast/multiple-curves?forecast_date=2025-01-10&forecast_types=d+1,d+2`
    """
    try:
        date = datetime.strptime(forecast_date, "%Y-%m-%d")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的日期格式: {forecast_date}，应为 YYYY-MM-DD"
        ) from e

    # 解析预测类型列表
    types_list = None
    if forecast_types:
        types_list = [t.strip() for t in forecast_types.split(",")]

    try:
        result = service.get_multiple_forecasts(date, types_list)
        return result
    except ValueError as e:
        logger.error("获取多个预测曲线失败: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error("获取多个预测曲线时发生异常: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误"
        ) from e


@router.get(
    "/accuracy",
    response_model=ShortTermLoadForecastAccuracyMetrics,
    summary="获取预测精度指标",
    description="计算指定预测的精度指标（MAE, MAPE, RMSE等），需要有实际数据才能计算"
)
def get_forecast_accuracy(
    forecast_date: str = Query(..., description="预测日期（业务日），格式：YYYY-MM-DD"),
    forecast_type: str = Query("d+1", description="预测类型：d+1, d+2, d+3"),
    service: ShortTermLoadForecastService = Depends(get_forecast_service)
):
    """
    获取预测精度指标

    **示例**：
    - `GET /api/v1/short-term-load-forecast/accuracy?forecast_date=2025-01-10&forecast_type=d+1`

    **注意**：仅当预测目标日期已有实际数据时才能计算精度
    """
    try:
        date = datetime.strptime(forecast_date, "%Y-%m-%d")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的日期格式: {forecast_date}，应为 YYYY-MM-DD"
        ) from e

    try:
        result = service.get_forecast_accuracy(date, forecast_type)
        return result
    except ValueError as e:
        logger.warning("获取预测精度失败: %s", e)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        ) from e
    except Exception as e:
        logger.error("获取预测精度时发生异常: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误"
        ) from e


@router.get(
    "/list",
    response_model=list[ShortTermLoadForecastListItem],
    summary="获取预测列表",
    description="获取指定日期范围内的预测列表"
)
def get_forecast_list(
    start_date: str = Query(..., description="起始日期，格式：YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期，格式：YYYY-MM-DD"),
    service: ShortTermLoadForecastService = Depends(get_forecast_service)
):
    """
    获取预测列表

    **示例**：
    - `GET /api/v1/short-term-load-forecast/list?start_date=2025-01-01&end_date=2025-01-10`
    """
    try:
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"无效的日期格式，应为 YYYY-MM-DD"
        ) from e

    if start > end:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="起始日期不能晚于结束日期"
        )

    try:
        result = service.get_forecast_list(start, end)
        return result
    except Exception as e:
        logger.error("获取预测列表时发生异常: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="服务器内部错误"
        ) from e
