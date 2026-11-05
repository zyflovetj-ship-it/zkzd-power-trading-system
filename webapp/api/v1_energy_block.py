"""能量块申报接口（中长期 / 日前 / 实时 共用）。"""
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from webapp.models.energy_block import EnergyBlockSetCreate
from webapp.services.energy_block_service import EnergyBlockService
from webapp.tools.mongo import DATABASE
from webapp.tools.security import User, get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/energy-blocks", tags=["Energy Blocks"])


@router.post("/validate", summary="校验能量块（不落库）")
def validate_blocks(
    payload: EnergyBlockSetCreate,
    current_user: User = Depends(get_current_active_user),
):
    try:
        return EnergyBlockService(DATABASE).validate(payload)
    except Exception as e:
        logger.error("校验能量块失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"校验失败: {e}")


@router.post("", summary="提交能量块申报", status_code=status.HTTP_201_CREATED)
def create_blocks(
    payload: EnergyBlockSetCreate,
    current_user: User = Depends(get_current_active_user),
):
    try:
        return EnergyBlockService(DATABASE).create(payload, operator=current_user.username)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("提交能量块失败: %s", e, exc_info=True)
        raise HTTPException(status_code=500, detail=f"提交失败: {e}")


@router.get("", summary="能量块申报列表")
def list_blocks(
    market_type: Optional[str] = Query(None, description="mid_long/day_ahead/real_time"),
    subject_id: Optional[str] = Query(None, description="标的ID"),
    limit: int = Query(50, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
):
    return {"items": EnergyBlockService(DATABASE).list_sets(market_type, subject_id, limit)}


@router.get("/{set_id}", summary="能量块申报详情")
def get_blocks(
    set_id: str,
    current_user: User = Depends(get_current_active_user),
):
    try:
        return EnergyBlockService(DATABASE).get_set(set_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.delete("/{set_id}", summary="删除能量块申报")
def delete_blocks(
    set_id: str,
    current_user: User = Depends(get_current_active_user),
):
    n = EnergyBlockService(DATABASE).delete_set(set_id)
    if not n:
        raise HTTPException(status_code=404, detail=f"能量块集合不存在: {set_id}")
    return {"deleted": n}
