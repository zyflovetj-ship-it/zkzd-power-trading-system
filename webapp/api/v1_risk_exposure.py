import logging
from fastapi import APIRouter, Depends, HTTPException, Query, status
from typing import Optional

from webapp.tools.mongo import DATABASE
from webapp.services.risk_exposure_service import RiskExposureService
from webapp.tools.security import get_current_active_user
from webapp.utils.excel_export import REAL_DATA_NOTICE, build_multi_excel_response

logger = logging.getLogger(__name__)

router = APIRouter(tags=["risk"])


def get_service() -> RiskExposureService:
    return RiskExposureService(DATABASE)


@router.get("/")
async def get_exposure(current_user: dict = Depends(get_current_active_user)):
    """获取风险敞口分析数据"""
    try:
        return get_service().get_exposure()
    except Exception as e:
        logger.error(f"获取风险敞口失败: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e),
        )


@router.get("/export", summary="导出风险敞口分析数据")
async def export_exposure(current_user: dict = Depends(get_current_active_user)):
    """导出风险敞口：汇总 + 月度 + 逐时三张 Sheet。"""
    data = get_service().get_exposure()

    summary_rows = [{
        "totalExposure": data.get("totalExposure", 0),
        "priceExposure": data.get("priceExposure", 0),
        "volumeExposure": data.get("volumeExposure", 0),
        "var95": data.get("var95", 0),
    }]
    summary_cols = [
        ("totalExposure", "总敞口(万元)"),
        ("priceExposure", "价格风险敞口(万元)"),
        ("volumeExposure", "电量风险敞口(万元)"),
        ("var95", "VaR95(万元)"),
    ]

    monthly = data.get("monthly", [])
    monthly_cols = [
        ("month", "月份"),
        ("contract", "合约敞口(万元)"),
        ("spot", "现货敞口(万元)"),
    ]

    hours = data.get("hours", [])
    pe = data.get("priceExposureHourly", [])
    ve = data.get("volumeExposureHourly", [])
    hourly_rows = [
        {"hour": hours[i] if i < len(hours) else "",
         "price": pe[i] if i < len(pe) else 0,
         "volume": ve[i] if i < len(ve) else 0}
        for i in range(max(len(hours), len(pe), len(ve)))
    ]
    hourly_cols = [
        ("hour", "时刻"),
        ("price", "价格敞口(万元)"),
        ("volume", "电量敞口(万元)"),
    ]

    return build_multi_excel_response(
        [("汇总", summary_rows, summary_cols),
         ("月度", monthly, monthly_cols),
         ("逐时", hourly_rows, hourly_cols)],
        "risk_exposure",
        data_notice={
            "数据性质": "真实业务数据",
            "说明": REAL_DATA_NOTICE,
            "口径": "复用风险引擎 96 点敞口，聚合为 24 小时视图；金额单位万元",
        },
    )
