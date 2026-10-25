import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional

from webapp.tools.mongo import DATABASE
from webapp.services.risk_position_service import RiskPositionService
from webapp.tools.security import get_current_active_user
from webapp.utils.excel_export import REAL_DATA_NOTICE, build_excel_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["risk"])


def get_service() -> RiskPositionService:
    return RiskPositionService(DATABASE)


@router.get("/")
async def get_contracts(current_user: dict = Depends(get_current_active_user)):
    """获取持仓合约列表"""
    try:
        return get_service().get_contracts()
    except Exception as e:
        logger.error(f"获取持仓合约失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/export", summary="导出持仓合约数据")
async def export_contracts(current_user: dict = Depends(get_current_active_user)):
    """导出持仓合约列表。"""
    data = get_service().get_contracts()
    columns = [
        ("customer", "客户"),
        ("contractNo", "合同号"),
        ("volume", "合同电量(MWh)"),
        ("avgPrice", "均价(元/MWh)"),
        ("startDate", "起始日"),
        ("endDate", "到期日"),
        ("coverage", "覆盖率(%)"),
    ]
    return build_excel_response(
        data.get("contracts", []), columns, "risk_position",
        data_notice={
            "数据性质": "真实业务数据",
            "说明": REAL_DATA_NOTICE,
            "口径": "负荷为 15 分钟平均功率(kW)，电量 = kW × 0.25h；电价为元/MWh",
        },
    )
