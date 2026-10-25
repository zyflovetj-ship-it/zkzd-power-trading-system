"""
合同曲线 API 路由
"""

import logging
from datetime import datetime

from fastapi import APIRouter, HTTPException

from webapp.tools.mongo import DATABASE
from webapp.services.contract_curve_service import ContractCurveService

router = APIRouter(tags=["合同曲线"])
logger = logging.getLogger(__name__)


@router.post(
    "/generate",
    summary="生成合同曲线",
    description="根据客户、目标月份和优化参数生成最优合同曲线"
)
def generate_contract_curve(
    customer_id: str,
    target_year: int,
    target_month: int,
    objective: str = "balanced",
    contract_coverage: float = 0.85
):
    """
    生成合同曲线

    参数:
        customer_id: 客户ID
        target_year: 目标年份
        target_month: 目标月份 (1-12)
        objective: 优化目标 (cost_min, risk_min, balanced)
        contract_coverage: 合同覆盖率 (0.5-1.0)

    返回:
        合同曲线数据，包括日度合同电量、汇总指标、风险指标等
    """
    service = ContractCurveService(DATABASE)
    try:
        optimization_params = {
            "objective": objective,
            "contract_coverage": contract_coverage,
            "risk_aversion": 0.5 if objective == "balanced" else (0.2 if objective == "cost_min" else 0.8)
        }

        result = service.generate_contract_curve(
            customer_id,
            target_year,
            target_month,
            optimization_params
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"生成合同曲线失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成合同曲线失败: {str(e)}")


@router.get(
    "/get",
    summary="获取合同曲线",
    description="根据合同曲线ID获取详细信息"
)
def get_contract_curve(
    curve_id: str
):
    """
    获取合同曲线详情

    参数:
        curve_id: 合同曲线ID

    返回:
        合同曲线数据
    """
    service = ContractCurveService(DATABASE)
    try:
        result = service.get_contract_curve(curve_id)
        if result is None:
            raise HTTPException(status_code=404, detail=f"未找到合同曲线 {curve_id}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"获取合同曲线失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取合同曲线失败: {str(e)}")


@router.get(
    "/scenarios",
    summary="获取情景分析",
    description="获取合同曲线的情景分析数据（价格/负荷敏感度）"
)
def analyze_scenarios(
    curve_id: str,
    scenario_type: str = "price_sensitivity"
):
    """
    获取情景分析

    参数:
        curve_id: 合同曲线ID
        scenario_type: 情景类型 (price_sensitivity, load_sensitivity)

    返回:
        情景分析数据
    """
    service = ContractCurveService(DATABASE)
    try:
        result = service.analyze_scenarios(curve_id, scenario_type)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"获取情景分析失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取情景分析失败: {str(e)}")


@router.get(
    "/list",
    summary="获取客户合同曲线列表",
    description="获取指定客户和月份的所有合同曲线（不同优化目标）"
)
def get_customer_curves(
    customer_id: str,
    target_year: int,
    target_month: int
):
    """
    获取客户合同曲线列表

    参数:
        customer_id: 客户ID
        target_year: 目标年份
        target_month: 目标月份

    返回:
        合同曲线列表
    """
    service = ContractCurveService(DATABASE)
    try:
        result = service.get_customer_curves(customer_id, target_year, target_month)
        return result
    except Exception as e:
        logger.error(f"获取合同曲线列表失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取合同曲线列表失败: {str(e)}")
