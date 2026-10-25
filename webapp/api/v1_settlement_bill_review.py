import logging
from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from typing import Optional

from webapp.tools.mongo import DATABASE
from webapp.services.settlement_bill_review_service import SettlementBillReviewService
from webapp.tools.security import User, get_current_active_user
from webapp.utils.excel_export import SAMPLE_DATA_NOTICE, build_excel_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["settlement"])


def get_service() -> SettlementBillReviewService:
    return SettlementBillReviewService(DATABASE)


@router.get("/")
async def get_bills(
    status: str = Query("ALL", description="账单状态过滤：ALL/PENDING/REVIEWED/DIFFERENCE"),
    current_user: User = Depends(get_current_active_user),
):
    """获取平台账单复核列表，支持按状态过滤"""
    try:
        return get_service().get_bills(status=status)
    except Exception as e:
        logger.error(f"获取平台账单复核失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/export", summary="导出账单复核数据")
async def export_bills(
    status: str = Query("ALL", description="账单状态过滤"),
    current_user: User = Depends(get_current_active_user),
):
    """导出账单复核列表。表头为中文，供人工归档，不参与前端类型契约。"""
    data = get_service().get_bills(status=status)
    columns = [
        ("billNo", "账单编号"),
        ("customer", "客户"),
        ("period", "账期"),
        ("platformAmount", "平台金额(元)"),
        ("systemAmount", "系统金额(元)"),
        ("diff", "差额(元)"),
        ("status", "状态"),
    ]
    # 账单主数据尚无来源（bills 集合为空），当前为样例数据，导出必须自带声明
    return build_excel_response(
        data.get("bills", []), columns, "bill_review",
        data_notice={
            "数据性质": "样例（演示）数据",
            "说明": SAMPLE_DATA_NOTICE,
            "缺失原因": "bills 集合为空，平台账单尚未接入",
        },
    )


@router.post("/{bill_no}/review", summary="复核账单")
async def review_bill(
    bill_no: str,
    action: str = Body(..., embed=True, description="操作: approve/reject"),
    reason: str = Body(None, embed=True, description="复核原因"),
    current_user: User = Depends(get_current_active_user),
):
    """复核指定账单，动作留痕到 bills_review_log。"""
    try:
        return get_service().review_bill(
            bill_no, action, current_user.username, reason)
    except ValueError as e:
        msg = str(e)
        code = status.HTTP_404_NOT_FOUND if "不存在" in msg else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=msg)
