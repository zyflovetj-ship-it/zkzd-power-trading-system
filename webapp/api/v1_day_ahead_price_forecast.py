"""
日前价格预测 API 路由
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from webapp.tools.mongo import DATABASE
from webapp.services.day_ahead_price_forecast_service import DayAheadPriceForecastService

router = APIRouter(tags=["日前价格预测"])
logger = logging.getLogger(__name__)


@router.get(
    "/versions",
    summary="获取预测版本列表",
    description="获取指定目标日期的所有预测版本"
)
def get_forecast_versions(
    target_date: str = Query(..., description="目标日期 YYYY-MM-DD"),
    forecast_type: str = Query("d1_price", description="预测类型: d1_price 或 d2_price")
):
    """
    获取指定目标日期的所有预测版本

    参数:
        target_date: 目标日期（格式：YYYY-MM-DD）
        forecast_type: 预测类型（默认：d1_price）

    返回:
        预测版本列表，按创建时间倒序排列
    """
    service = DayAheadPriceForecastService(DATABASE)
    try:
        date_obj = datetime.strptime(target_date, "%Y-%m-%d")
        return service.get_forecast_versions(date_obj, forecast_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取预测版本列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取预测版本列表失败: {str(e)}")


@router.get(
    "/data",
    summary="获取图表数据",
    description="获取预测曲线和实际曲线的合并数据"
)
def get_chart_data(
    forecast_id: str = Query(..., description="预测批次ID"),
    target_date: str = Query(..., description="目标日期 YYYY-MM-DD")
):
    """
    获取图表数据（预测曲线 + 实际曲线）

    参数:
        forecast_id: 预测批次ID
        target_date: 目标日期（格式：YYYY-MM-DD）

    返回:
        图表数据，包含预测值、实际值和置信区间
    """
    service = DayAheadPriceForecastService(DATABASE)
    try:
        date_obj = datetime.strptime(target_date, "%Y-%m-%d")
        return service.get_chart_data(forecast_id, date_obj)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取图表数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取图表数据失败: {str(e)}")


@router.get(
    "/accuracy",
    summary="获取准确度评估详情",
    description="获取指定预测批次的准确度指标"
)
def get_accuracy_details(
    forecast_id: str = Query(..., description="预测批次ID")
):
    """
    获取准确度评估详情

    参数:
        forecast_id: 预测批次ID

    返回:
        准确度数据，包括 WMAPE、MAE、RMSE、分时段准确率等
    """
    service = DayAheadPriceForecastService(DATABASE)
    try:
        result = service.get_accuracy_details(forecast_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"未找到预测批次 {forecast_id} 的准确度数据")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取准确度数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取准确度数据失败: {str(e)}")
