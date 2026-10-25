"""
D-2价格预测 API 路由
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query

from webapp.tools.mongo import DATABASE
from webapp.services.price_forecast_service import PriceForecastService

router = APIRouter(tags=["D-2价格预测"])
logger = logging.getLogger(__name__)


@router.get(
    "/d2/by-date",
    summary="获取D-2价格预测数据",
    description="根据预测执行日期获取D-2价格预测的完整批次数据（未来10天）"
)
def get_d2_forecast_by_date(
    forecast_date: str = Query(..., description="预测执行日期 YYYY-MM-DD")
):
    """
    获取指定预测执行日期的 D-2 价格预测数据

    参数:
        forecast_date: 预测执行日期（格式：YYYY-MM-DD）

    返回:
        预测批次数据，包含未来10天共960个预测点（96点/天）
    """
    service = PriceForecastService(DATABASE)
    try:
        date_obj = datetime.strptime(forecast_date, "%Y-%m-%d")
        return service.get_d2_forecast_by_date(date_obj)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取D-2预测数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取D-2预测数据失败: {str(e)}")


@router.get(
    "/d2/comparison",
    summary="获取D-2预测对比分析",
    description="对比D-2预测值与实际值，计算误差指标"
)
def get_d2_comparison(
    target_date: str = Query(..., description="目标日期 YYYY-MM-DD")
):
    """
    获取指定目标日期的 D-2 预测与实际值对比数据

    参数:
        target_date: 目标日期（格式：YYYY-MM-DD）

    返回:
        96点对比数据和误差指标（MAE、RMSE、MAPE、准确度）
    """
    service = PriceForecastService(DATABASE)
    try:
        date_obj = datetime.strptime(target_date, "%Y-%m-%d")
        return service.get_d2_comparison(date_obj)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取对比数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取对比数据失败: {str(e)}")


@router.get(
    "/d2/accuracy-stats",
    summary="获取D-2预测准确度统计",
    description="获取指定时间范围内的D-2预测准确度统计数据"
)
def get_d2_accuracy_stats(
    start_date: str = Query(..., description="起始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD")
):
    """
    获取指定时间范围的 D-2 预测准确度统计

    参数:
        start_date: 起始日期（格式：YYYY-MM-DD）
        end_date: 结束日期（格式：YYYY-MM-DD）

    返回:
        准确度统计数据，包括月平均值、最佳/最差日期、达标率等
    """
    service = PriceForecastService(DATABASE)
    try:
        start_obj = datetime.strptime(start_date, "%Y-%m-%d")
        end_obj = datetime.strptime(end_date, "%Y-%m-%d")
        return service.get_d2_accuracy_stats(start_obj, end_obj)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"获取准确度统计失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取准确度统计失败: {str(e)}")
