import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional

from webapp.tools.mongo import DATABASE
from webapp.services.settlement_retail_service import SettlementRetailService
from webapp.tools.security import get_current_active_user
from webapp.utils.excel_export import REAL_DATA_NOTICE, build_excel_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["settlement"])


def get_service() -> SettlementRetailService:
    return SettlementRetailService(DATABASE)


@router.get("/")
async def get_rows(current_user: dict = Depends(get_current_active_user)):
    """获取零售用户结算列表"""
    try:
        return get_service().get_rows()
    except Exception as e:
        logger.error(f"获取零售用户结算失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/export", summary="导出零售结算数据")
async def export_retail(current_user: dict = Depends(get_current_active_user)):
    """导出零售用户结算列表。"""
    data = get_service().get_rows()
    columns = [
        ("customer", "客户"),
        ("contract", "合同号"),
        ("usage", "用电量(kWh)"),
        ("price", "结算电价(元/MWh)"),
        ("amount", "结算金额(元)"),
        ("payStatus", "回款状态"),
    ]
    return build_excel_response(
        data.get("rows", []), columns, "settlement_retail",
        data_notice={
            "数据性质": "真实业务数据",
            "说明": REAL_DATA_NOTICE,
            "口径": "负荷为 15 分钟平均功率(kW)，电量 = kW × 0.25h；电价为元/MWh",
        },
    )
