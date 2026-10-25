import logging
from datetime import datetime
from typing import List

from fastapi import APIRouter, HTTPException, Query

from webapp.tools.mongo import DATABASE
from webapp.services.forecast_base_data_service import ForecastBaseDataService
from webapp.models.forecast_base_data import (
    DataAvailabilityResponse,
    CurveDataRequest,
    MultipleCurvesResponse,
)

router = APIRouter(tags=["预测基础数据"])
logger = logging.getLogger(__name__)


@router.get(
    "/forecast-base-data/availability",
    response_model=DataAvailabilityResponse,
    summary="获取数据可用性矩阵",
    description=(
        "获取预测基础数据的可用性（以12:00是否存在作为判定）。\n\n"
        "参数：\n"
        "- base_date: 基准日期（YYYY-MM-DD）\n"
        "- date_range: 日期范围类型，recent_3（默认）, recent_7, historical_10\n\n"
        "返回：15个数据项 × N个日期的可用性矩阵"
    ),
)
def get_forecast_base_data_availability(
    base_date: str = Query(..., description="基准日期 YYYY-MM-DD"),
    date_range: str = Query("recent_3", description="日期范围类型（recent_3/recent_7/historical_10）"),
):
    service = ForecastBaseDataService(DATABASE)
    try:
        base_dt = datetime.strptime(base_date, "%Y-%m-%d")
        return service.get_data_availability(base_dt, date_range)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.error("获取数据可用性失败", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")


@router.post(
    "/forecast-base-data/curves",
    response_model=MultipleCurvesResponse,
    summary="批量获取曲线数据（96点）",
    description=(
        "根据用户选择的数据项和日期，批量获取96点曲线数据。\n\n"
        "请求体验例：\n"
        '[{\"data_item_id\": 1, \"date\": \"2025-01-10\"}, {\"data_item_id\": 6, \"date\": \"2025-01-11\"}]'
    ),
)
def get_forecast_base_data_curves(requests: List[CurveDataRequest]):
    service = ForecastBaseDataService(DATABASE)
    try:
        req_list = [{"data_item_id": r.data_item_id, "date": r.date} for r in requests]
        return service.get_multiple_curves(req_list)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception:
        logger.error("批量获取曲线数据失败", exc_info=True)
        raise HTTPException(status_code=500, detail="服务器内部错误")

