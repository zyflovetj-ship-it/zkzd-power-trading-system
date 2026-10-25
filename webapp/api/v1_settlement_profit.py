import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional

from webapp.tools.mongo import DATABASE
from webapp.services.settlement_profit_service import SettlementProfitService
from webapp.tools.security import get_current_active_user
from webapp.utils.excel_export import REAL_DATA_NOTICE, build_excel_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["settlement"])


def get_service() -> SettlementProfitService:
    return SettlementProfitService(DATABASE)


@router.get("/")
async def get_profit(current_user: dict = Depends(get_current_active_user)):
    """获取经营利润分析数据"""
    try:
        return get_service().get_profit()
    except Exception as e:
        logger.error(f"获取经营利润分析失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/export", summary="导出经营利润数据")
async def export_profit(current_user: dict = Depends(get_current_active_user)):
    """导出经营利润月度明细。"""
    data = get_service().get_profit()
    columns = [
        ("month", "月份"),
        ("revenue", "收入(元)"),
        ("cost", "成本(元)"),
        ("gross", "毛利(元)"),
        ("margin", "毛利率(%)"),
    ]
    return build_excel_response(
        data.get("rows", []), columns, "settlement_profit",
        data_notice={
            "数据性质": "真实业务数据",
            "说明": REAL_DATA_NOTICE,
            "口径": "负荷为 15 分钟平均功率(kW)，电量 = kW × 0.25h；电价为元/MWh",
        },
    )
