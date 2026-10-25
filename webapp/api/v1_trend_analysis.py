from fastapi import APIRouter, Query, HTTPException, status
from typing import Optional
import logging

from webapp.tools.mongo import DATABASE
from webapp.services.trend_analysis_service import TrendAnalysisService
from webapp.models.trend_analysis import (
    PriceTrendResponse, 
    WeekdayAnalysisResponse, 
    VolatilityAnalysisResponse,
    ArbitrageAnalysisResponse,
    AnomalyAnalysisResponse,
    TimeSlotAnalysisResponse
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/trend-analysis", tags=["trend-analysis"])

def get_service():
    return TrendAnalysisService(DATABASE)

@router.get(
    "/price-trend",
    response_model=PriceTrendResponse,
    summary="获取价格趋势分析数据",
    description="获取指定日期范围内的 VWAP/TWAP 趋势及分时段趋势"
)
def get_price_trend(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD")
):
    try:
        service = get_service()
        return service.get_price_trend(start_date, end_date)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="日期格式无效")
    except Exception as e:
        logger.error(f"Error in get_price_trend: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/weekday-pattern",
    response_model=WeekdayAnalysisResponse,
    summary="获取星期特性分析数据",
    description="获取星期维度的价格分布（箱线图）"
)
def get_weekday_pattern(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD")
):
    try:
        service = get_service()
        return service.get_weekday_analysis(start_date, end_date)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="日期格式无效")
    except Exception as e:
        logger.error(f"Error in get_weekday_pattern: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/volatility",
    response_model=VolatilityAnalysisResponse,
    summary="获取波动性分析数据",
    description="获取日内波动率(CV)和最大价格爬坡数据"
)
def get_volatility(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD")
):
    try:
        service = get_service()
        return service.get_volatility_analysis(start_date, end_date)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="日期格式无效")
    except Exception as e:
        logger.error(f"Error in get_volatility: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/arbitrage",
    response_model=ArbitrageAnalysisResponse,
    summary="获取储能套利机会分析数据",
    description="获取每日最大价差及最优买卖策略"
)
def get_arbitrage(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD")
):
    try:
        service = get_service()
        return service.get_arbitrage_analysis(start_date, end_date)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="日期格式无效")
    except Exception as e:
        logger.error(f"Error in get_arbitrage: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/anomaly",
    response_model=AnomalyAnalysisResponse,
    summary="获取价格异常与极值分析数据",
    description="获取异常事件统计（负电价等）及每日极值"
)
def get_anomaly(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD")
):
    try:
        service = get_service()
        return service.get_anomaly_analysis(start_date, end_date)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="日期格式无效")
    except Exception as e:
        logger.error(f"Error in get_anomaly: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get(
    "/timeslot-stats",
    response_model=TimeSlotAnalysisResponse,
    summary="获取时段统计分析数据",
    description="将96个数据点聚合为48个时段,提供详细的统计指标、推荐策略和箱线图数据"
)
def get_timeslot_stats(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD")
):
    try:
        service = get_service()
        return service.get_timeslot_stats(start_date, end_date)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="日期格式无效")
    except Exception as e:
        logger.error(f"Error in get_timeslot_stats: {e}", exc_info=True)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

