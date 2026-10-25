"""
月度价格预测 API 路由
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from webapp.tools.mongo import DATABASE
from webapp.services.monthly_price_forecast_service import MonthlyPriceForecastService

router = APIRouter(tags=["月度价格预测"])
logger = logging.getLogger(__name__)


@router.get(
    "/versions",
    summary="获取月度预测版本列表",
    description="获取指定目标月份的所有预测版本"
)
def get_forecast_versions(
    target_year: int = Query(..., description="目标年份", ge=2020, le=2030),
    target_month: int = Query(..., description="目标月份", ge=1, le=12),
    forecast_type: str = Query("monthly_price", description="预测类型")
):
    """
    获取指定目标月份的所有预测版本

    参数:
        target_year: 目标年份
        target_month: 目标月份 (1-12)
        forecast_type: 预测类型（默认：monthly_price）

    返回:
        预测版本列表，按创建时间倒序排列
    """
    service = MonthlyPriceForecastService(DATABASE)
    try:
        return service.get_forecast_versions(target_year, target_month, forecast_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取月度预测版本列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取月度预测版本列表失败: {str(e)}")


@router.get(
    "/data",
    summary="获取月度图表数据",
    description="获取月度预测和实际价格的合并数据，支持多种图表类型"
)
def get_chart_data(
    forecast_id: str = Query(..., description="预测批次ID"),
    chart_type: str = Query("mean_trend", description="图表类型: mean_trend, price_spread, peak_valley")
):
    """
    获取图表数据

    参数:
        forecast_id: 预测批次ID
        chart_type: 图表类型
            - mean_trend: 均价趋势图（默认）
            - price_spread: 日内价差图
            - peak_valley: 峰谷价格图

    返回:
        图表数据，包含预测值、实际值、置信区间和参考线
    """
    service = MonthlyPriceForecastService(DATABASE)
    try:
        return service.get_chart_data(forecast_id, chart_type)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取月度图表数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取月度图表数据失败: {str(e)}")


@router.get(
    "/accuracy",
    summary="获取月度准确度评估详情",
    description="获取指定预测批次的月度准确度指标"
)
def get_accuracy_details(
    forecast_id: str = Query(..., description="预测批次ID")
):
    """
    获取准确度评估详情

    参数:
        forecast_id: 预测批次ID

    返回:
        准确度数据，包括 MAPE、WMAPE、MAE、RMSE、分时段准确率、日度误差分布等
    """
    service = MonthlyPriceForecastService(DATABASE)
    try:
        result = service.get_accuracy_details(forecast_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"未找到预测批次 {forecast_id} 的准确度数据")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取月度准确度数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取月度准确度数据失败: {str(e)}")
