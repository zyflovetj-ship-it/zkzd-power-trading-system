"""
中长期合同价格分析 - API路由
"""
from fastapi import APIRouter, Query, HTTPException, status
from datetime import datetime
import logging

from webapp.tools.mongo import DATABASE
from webapp.services.contract_price_service import ContractPriceService
from webapp.models.contract_price import DailySummaryResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contract-price", tags=["contract-price"])


def get_service():
    return ContractPriceService(DATABASE)


@router.get(
    "/daily-summary",
    response_model=DailySummaryResponse,
    summary="获取中长期合同日汇总数据",
    description="获取指定日期的中长期合同汇总指标、价格曲线和明细表格"
)
def get_daily_summary(
    date: str = Query(..., description="日期 YYYY-MM-DD"),
    entity: str = Query("全市场", description="实体名称"),
    spot_type: str = Query("day_ahead", description="现货类型: day_ahead(日前) 或 real_time(实时)")
):
    # 调试日志
    print(f"[API] get_daily_summary called: date={date}, entity={entity}, spot_type={spot_type}")
    logger.info(f"[API] get_daily_summary called: date={date}, entity={entity}, spot_type={spot_type}")

    try:
        # 验证日期格式
        datetime.strptime(date, "%Y-%m-%d")

        service = get_service()
        return service.get_daily_summary(date, entity, spot_type)

    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="日期格式无效，请使用 YYYY-MM-DD 格式"
        )
    except Exception as e:
        logger.error(f"Error in get_daily_summary: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
