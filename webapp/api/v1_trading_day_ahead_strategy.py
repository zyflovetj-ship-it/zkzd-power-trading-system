"""
日前交易策略 API 路由
"""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from webapp.tools.mongo import DATABASE
from webapp.services.day_ahead_trading_strategy_service import DayAheadTradingStrategyService

router = APIRouter(tags=["日前交易策略"])
logger = logging.getLogger(__name__)


@router.post(
    "/generate",
    summary="生成日前交易方案",
    description="根据客户和目标日期生成日前交易方案"
)
def generate_plan(
    customer_id: str,
    target_date: date,
    strategy_type: str = Query("balanced", description="策略类型")
):
    """
    生成日前交易方案

    参数:
        customer_id: 客户ID
        target_date: 目标日期
        strategy_type: 策略类型 (conservative, balanced, aggressive)

    返回:
        日前交易方案数据
    """
    service = DayAheadTradingStrategyService(DATABASE)
    try:
        result = service.generate_day_ahead_plan(customer_id, target_date, strategy_type)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"生成日前交易方案失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成日前交易方案失败: {str(e)}")


@router.get(
    "/get",
    summary="获取日前交易方案",
    description="根据方案ID获取详细信息"
)
def get_plan(
    plan_id: str
):
    """
    获取日前交易方案详情

    参数:
        plan_id: 方案ID

    返回:
        日前交易方案数据
    """
    service = DayAheadTradingStrategyService(DATABASE)
    try:
        result = service.get_day_ahead_plan(plan_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"未找到日前交易方案 {plan_id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取日前交易方案失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取日前交易方案失败: {str(e)}")


@router.get(
    "/recommendations",
    summary="获取高优先级交易建议",
    description="获取指定日期和客户的高优先级交易建议"
)
def get_priority_recommendations(
    customer_id: str,
    target_date: date
):
    """
    获取高优先级交易建议

    参数:
        customer_id: 客户ID
        target_date: 目标日期

    返回:
        高优先级建议列表
    """
    service = DayAheadTradingStrategyService(DATABASE)
    try:
        result = service.get_priority_recommendations(customer_id, target_date)
        return {"recommendations": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取交易建议失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取交易建议失败: {str(e)}")
