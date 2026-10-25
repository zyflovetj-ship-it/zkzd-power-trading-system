"""
月度交易策略 API 路由
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from webapp.tools.mongo import DATABASE
from webapp.services.monthly_trading_strategy_service import MonthlyTradingStrategyService

router = APIRouter(tags=["月度交易策略"])
logger = logging.getLogger(__name__)


@router.post(
    "/generate",
    summary="生成月度交易策略",
    description="根据客户、目标月份和策略配置生成最优交易策略"
)
def generate_strategy(
    customer_id: str,
    target_year: int,
    target_month: int,
    annual_contract_ratio: float = 0.70,
    monthly_bid_ratio: float = 0.20,
    spot_ratio: float = 0.10,
    optimization_objective: str = "balanced"
):
    """
    生成月度交易策略

    参数:
        customer_id: 客户ID
        target_year: 目标年份
        target_month: 目标月份 (1-12)
        annual_contract_ratio: 年度双边比例 (0.5-0.9)
        monthly_bid_ratio: 月度竞价比例 (0.0-0.3)
        spot_ratio: 现货比例 (0.0-0.3)
        optimization_objective: 优化目标 (cost, risk, balanced)

    返回:
        交易策略数据，包括优化结果、时机建议、情景分析等
    """
    service = MonthlyTradingStrategyService(DATABASE)
    try:
        strategy_config = {
            "annual_contract_ratio": annual_contract_ratio,
            "monthly_bid_ratio": monthly_bid_ratio,
            "spot_ratio": spot_ratio,
            "optimization_objective": optimization_objective
        }

        result = service.generate_strategy(
            customer_id,
            target_year,
            target_month,
            strategy_config
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"生成交易策略失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成交易策略失败: {str(e)}")


@router.get(
    "/get",
    summary="获取交易策略",
    description="根据策略ID获取详细信息"
)
def get_strategy(
    strategy_id: str
):
    """
    获取交易策略详情

    参数:
        strategy_id: 策略ID

    返回:
        交易策略数据
    """
    service = MonthlyTradingStrategyService(DATABASE)
    try:
        result = service.get_strategy(strategy_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"未找到交易策略 {strategy_id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取交易策略失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取交易策略失败: {str(e)}")


@router.get(
    "/scenarios",
    summary="获取情景分析",
    description="获取交易策略的情景分析数据"
)
def analyze_scenarios(
    strategy_id: str
):
    """
    获取情景分析

    参数:
        strategy_id: 策略ID

    返回:
        情景分析数据（高价/低价/高负荷/低负荷情景）
    """
    service = MonthlyTradingStrategyService(DATABASE)
    try:
        result = service.analyze_scenarios(strategy_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取情景分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取情景分析失败: {str(e)}")


@router.get(
    "/price-trend",
    summary="获取价格走势",
    description="获取目标月份的价格走势数据和分布统计"
)
def get_price_trend(
    target_year: int,
    target_month: int,
    forecast_type: str = "monthly_price"
):
    """
    获取价格走势

    参数:
        target_year: 目标年份
        target_month: 目标月份
        forecast_type: 预测类型（默认 monthly_price）

    返回:
        价格走势数据，包括每日预测价格和价格分布统计
    """
    service = MonthlyTradingStrategyService(DATABASE)
    try:
        result = service.get_price_trend(target_year, target_month, forecast_type)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取价格走势失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取价格走势失败: {str(e)}")


@router.get(
    "/list",
    summary="获取客户交易策略列表",
    description="获取指定客户和月份的所有交易策略（不同优化目标）"
)
def get_customer_strategies(
    customer_id: str,
    target_year: int,
    target_month: int
):
    """
    获取客户交易策略列表

    参数:
        customer_id: 客户ID
        target_year: 目标年份
        target_month: 目标月份

    返回:
        交易策略列表
    """
    service = MonthlyTradingStrategyService(DATABASE)
    try:
        result = service.get_customer_strategies(customer_id, target_year, target_month)
        return result
    except Exception as e:
        logger.error(f"获取交易策略列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取交易策略列表失败: {str(e)}")
