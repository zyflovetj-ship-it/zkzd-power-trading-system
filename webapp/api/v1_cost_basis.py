"""成本基线接口（事前综合购电成本）。

端点：
  GET  /cost-basis?month=&customer_id=      读取已计算成本基线
  POST /cost-basis/recompute                重算并落库
  GET  /cost-basis/list                     最近若干月概览
  GET  /cost-basis/components?month=        成本构成明细（图表用）
"""
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Query

from webapp.tools.mongo import DATABASE
from webapp.tools.security import User, get_current_active_user

router = APIRouter(prefix="/cost-basis", tags=["Cost Basis"])


def _svc():
    from webapp.services.cost_basis_service import CostBasisService
    return CostBasisService(DATABASE)


@router.get("", summary="读取成本基线")
def get_cost_basis(
    month: str = Query(..., description="YYYY-MM"),
    customer_id: Optional[str] = Query(None, description="客户ID（空=全部客户汇总）"),
    recompute_if_missing: bool = Query(True, description="无缓存时自动计算"),
    current_user: User = Depends(get_current_active_user),
):
    svc = _svc()
    doc = svc.get(month, customer_id)
    if doc is None:
        if not recompute_if_missing:
            raise HTTPException(status_code=404, detail="该月无成本基线，请先重算")
        doc = svc.compute(month, customer_id)
    return doc


@router.post("/recompute", summary="重算成本基线")
def recompute(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user),
):
    """payload: {month, customer_id?, share?:{cost_compensation, imbalance, market_adjust}}"""
    month = payload.get("month")
    if not month:
        raise HTTPException(status_code=400, detail="缺少 month（YYYY-MM）")
    try:
        return _svc().compute(
            month=month,
            customer_id=payload.get("customer_id"),
            share=payload.get("share"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/list", summary="成本基线月度概览")
def list_months(
    limit: int = Query(24, ge=1, le=120),
    current_user: User = Depends(get_current_active_user),
):
    return {"rows": _svc().list_months(limit)}


@router.get("/components", summary="成本构成明细")
def components(
    month: str = Query(..., description="YYYY-MM"),
    customer_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
):
    svc = _svc()
    doc = svc.get(month, customer_id) or svc.compute(month, customer_id)
    return {
        "month": month,
        "customer_id": customer_id,
        "unit_cost": doc.get("unit_cost"),
        "total_mwh": doc.get("total_mwh"),
        "total_cost": doc.get("total_cost"),
        "components": doc.get("components") or [],
        "warnings": doc.get("warnings") or [],
    }
