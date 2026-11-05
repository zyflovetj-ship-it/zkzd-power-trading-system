"""竞价空间查询与校验接口。

GET /api/v1/market/bidding-space?date=YYYY-MM-DD        96 点竞价空间（日前/实时/偏差）
GET /api/v1/market/bidding-space/verify?date=YYYY-MM-DD 公式重算值与发布值逐点校验
"""
import logging

from fastapi import APIRouter, Depends, HTTPException, Query

from webapp.services.bidding_space_service import BiddingSpaceService
from webapp.tools.mongo import DATABASE
from webapp.tools.security import User, get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/market/bidding-space", tags=["Bidding Space"])


@router.get("", summary="获取指定日竞价空间（96点）")
def get_bidding_space(
    date: str = Query(..., description="日期 YYYY-MM-DD"),
    current_user: User = Depends(get_current_active_user),
):
    try:
        svc = BiddingSpaceService(DATABASE)
        data = svc.get_bidding_space(date)
        if not data.get("count"):
            raise HTTPException(status_code=404, detail=f"{date} 无竞价空间数据")
        return data
    except HTTPException:
        raise
    except Exception as e:
        logger.error("获取竞价空间失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"获取竞价空间失败: {e}")


@router.get("/dates", summary="有竞价空间数据的日期列表")
def list_dates(
    limit: int = Query(120, description="返回最近天数"),
    current_user: User = Depends(get_current_active_user),
):
    dates = sorted(DATABASE["daily_release"].distinct("date_str"), reverse=True)
    # 有实时竞价空间（非全 0）的日期
    rt_dates = sorted({
        row["_id"] for row in DATABASE["actual_operation"].aggregate([
            {"$match": {"bidding_space_pub": {"$gt": 0}}},
            {"$group": {"_id": "$date_str"}},
        ])
    }, reverse=True)
    return {
        "dates": dates[:limit],
        "dates_with_realtime": rt_dates[:limit],
        "total": len(dates),
        "total_with_realtime": len(rt_dates),
    }


@router.get("/verify", summary="校验竞价空间公式与发布值一致性")
def verify_bidding_space(
    date: str = Query(..., description="日期 YYYY-MM-DD"),
    current_user: User = Depends(get_current_active_user),
):
    try:
        svc = BiddingSpaceService(DATABASE)
        return svc.verify(date)
    except Exception as e:
        logger.error("校验竞价空间失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"校验失败: {e}")
