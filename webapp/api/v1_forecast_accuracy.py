from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import StreamingResponse
from typing import Optional
from datetime import datetime
import io
import logging
from urllib.parse import quote
import pandas as pd
from webapp.services.forecast_accuracy_service import ForecastAccuracyService
from webapp.utils.excel_export import build_excel_response
from webapp.tools.mongo import DATABASE
from webapp.tools.security import get_current_active_user, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/forecast-accuracy", tags=["预测精度分析"])


@router.get("", response_model=dict, summary="获取预测精度数据")
async def get_forecast_accuracy(
    forecast_type: str = Query("short_term_load", description="预测类型: short_term_load/medium_long_term_load/price"),
    days: int = Query(30, ge=1, le=90, description="分析天数"),
    current_user: User = Depends(get_current_active_user)
):
    service = ForecastAccuracyService(DATABASE)
    try:
        return service.get_accuracy(forecast_type, days)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.get("/export", summary="导出预测精度数据")
async def export_forecast_accuracy(
    forecast_type: str = Query("short_term_load", description="预测类型: short_term_load/medium_long_term_load/price"),
    days: int = Query(30, ge=1, le=90, description="分析天数"),
    current_user: User = Depends(get_current_active_user)
):
    """按预测类型导出精度趋势明细（日期/预测值/实际值/偏差率/APE）。"""
    try:
        data = ForecastAccuracyService(DATABASE).get_accuracy(forecast_type, days)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    columns = [
        ("date", "日期"),
        ("forecast_value", "预测值"),
        ("actual_value", "实际值"),
        ("deviation", "偏差"),
        ("deviation_rate", "偏差率(%)"),
    ]
    return build_excel_response(data.get("trend", []), columns, "forecast_accuracy_" + forecast_type)


