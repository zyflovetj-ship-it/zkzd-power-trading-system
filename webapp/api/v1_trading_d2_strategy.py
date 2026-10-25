"""
D-2 交易策略 API 路由
"""

import logging
from datetime import date

from fastapi import APIRouter, HTTPException, Query

from webapp.tools.mongo import DATABASE
from webapp.services.d2_trading_strategy_service import D2TradingStrategyService

router = APIRouter(tags=["D-2交易策略"])
logger = logging.getLogger(__name__)


@router.post(
    "/generate",
    summary="生成D-2交易策略",
    description="根据客户和目标日期生成D-2交易策略"
)
def generate_strategy(
    customer_id: str,
    target_date: date,
    compare_with: str = "current_contract,pure_spot"
):
    """
    生成 D-2 交易策略

    参数:
        customer_id: 客户ID
        target_date: 目标日期
        compare_with: 对比基准（逗号分隔）

    返回:
        D-2 交易策略数据
    """
    service = D2TradingStrategyService(DATABASE)
    try:
        compare_with_list = [s.strip() for s in compare_with.split(",")]
        result = service.generate_d2_strategy(customer_id, target_date, compare_with_list)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"生成 D-2 交易策略失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成 D-2 交易策略失败: {str(e)}")


@router.get(
    "/get",
    summary="获取D-2交易策略",
    description="根据策略ID获取详细信息"
)
def get_strategy(
    strategy_id: str
):
    """
    获取 D-2 交易策略详情

    参数:
        strategy_id: 策略ID

    返回:
        D-2 交易策略数据
    """
    service = D2TradingStrategyService(DATABASE)
    try:
        result = service.get_d2_strategy(strategy_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"未找到 D-2 交易策略 {strategy_id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取 D-2 交易策略失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取 D-2 交易策略失败: {str(e)}")


@router.get(
    "/risks",
    summary="获取风险预警",
    description="获取指定日期和客户的风险预警"
)
def get_risk_alerts(
    target_date: date,
    customer_id: str
):
    """
    获取风险预警

    参数:
        target_date: 目标日期
        customer_id: 客户ID

    返回:
        风险预警列表
    """
    service = D2TradingStrategyService(DATABASE)
    try:
        result = service.get_risk_alerts(target_date, customer_id)
        return {"risk_alerts": result}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取风险预警失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取风险预警失败: {str(e)}")


@router.get(
    "/backtesting",
    summary="获取回测数据",
    description="获取客户的回测结果"
)
def get_backtesting_results(
    customer_id: str,
    period_days: int = Query(30, description="回测周期天数", ge=1, le=365)
):
    """
    获取回测数据

    参数:
        customer_id: 客户ID
        period_days: 回测周期天数

    返回:
        回测结果数据
    """
    service = D2TradingStrategyService(DATABASE)
    try:
        result = service.get_backtesting_results(customer_id, period_days)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取回测数据失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取回测数据失败: {str(e)}")
