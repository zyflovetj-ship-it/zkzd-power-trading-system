"""
现货交易复盘 API 路由

前缀: /api/v1/review/spot
端点:
1. POST /generate - 生成复盘报告
2. GET /96-point-data - 获取96点复盘数据
3. GET /time-slot-analysis - 获取时段分析
4. GET /forecast-accuracy - 获取预测精度
5. GET /special-events - 获取风险事件
"""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

from webapp.tools.security import User, get_current_active_user
from webapp.services.spot_review_service import SpotReviewService
from webapp.tools.mongo import DATABASE
from webapp.models.spot_review import (
    GenerateReviewRequest,
    ReviewGenerateResponse,
    Point96DataResponse,
    TimeSlotAnalysisResponse,
    ForecastAccuracyResponse,
    SpecialEventsResponse,
)

router = APIRouter()


@router.post(
    "/generate",
    response_model=ReviewGenerateResponse,
    summary="生成复盘报告",
)
async def generate_review(
    request: GenerateReviewRequest,
    current_user: User = Depends(get_current_active_user),
):
    """
    生成现货交易复盘报告

    流程：查询交易数据 → 计算概览统计 → 时段分析 → 预测精度 → 识别风险事件 → 生成优化建议 → 存入spot_trading_reviews
    """
    try:
        service = SpotReviewService(DATABASE)
        result = service.generate_review(
            customer_id=request.customer_id,
            review_date=request.review_date,
            review_type=request.review_type,
            operator=current_user.username,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成复盘报告失败: {str(e)}")


@router.get(
    "/96-point-data",
    response_model=Point96DataResponse,
    summary="获取96点复盘数据",
)
async def get_96_point_data(
    customer_id: str = Query(..., description="客户ID"),
    review_date: str = Query(..., description="复盘日期 YYYY-MM-DD"),
    current_user: User = Depends(get_current_active_user),
):
    """
    获取96点复盘数据

    返回96点的实际交易数据+预测数据+偏差
    """
    try:
        service = SpotReviewService(DATABASE)
        result = service.get_96_point_data(
            customer_id=customer_id,
            review_date=review_date,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取96点复盘数据失败: {str(e)}")


@router.get(
    "/time-slot-analysis",
    response_model=TimeSlotAnalysisResponse,
    summary="获取时段分析",
)
async def get_time_slot_analysis(
    customer_id: str = Query(..., description="客户ID"),
    review_date: str = Query(..., description="复盘日期 YYYY-MM-DD"),
    current_user: User = Depends(get_current_active_user),
):
    """
    获取时段分析

    返回各时段(峰/平/谷)的交易量占比/成本占比/均价
    """
    try:
        service = SpotReviewService(DATABASE)
        result = service.get_time_slot_analysis(
            customer_id=customer_id,
            review_date=review_date,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取时段分析失败: {str(e)}")


@router.get(
    "/forecast-accuracy",
    response_model=ForecastAccuracyResponse,
    summary="获取预测精度",
)
async def get_forecast_accuracy(
    customer_id: str = Query(..., description="客户ID"),
    review_date: str = Query(..., description="复盘日期 YYYY-MM-DD"),
    current_user: User = Depends(get_current_active_user),
):
    """
    获取预测精度

    返回MAE/MAPE/RMSE/5%内命中率
    """
    try:
        service = SpotReviewService(DATABASE)
        result = service.get_forecast_accuracy(
            customer_id=customer_id,
            review_date=review_date,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取预测精度失败: {str(e)}")


@router.get(
    "/special-events",
    response_model=SpecialEventsResponse,
    summary="获取风险事件",
)
async def get_special_events(
    customer_id: str = Query(..., description="客户ID"),
    review_date: str = Query(..., description="复盘日期 YYYY-MM-DD"),
    current_user: User = Depends(get_current_active_user),
):
    """
    获取风险事件

    返回异常价格事件/极端偏差事件
    """
    try:
        service = SpotReviewService(DATABASE)
        result = service.get_special_events(
            customer_id=customer_id,
            review_date=review_date,
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取风险事件失败: {str(e)}")
