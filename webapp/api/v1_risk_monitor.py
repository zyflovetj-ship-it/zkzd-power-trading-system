"""风险监控 API（P0）"""

from datetime import datetime, date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from webapp.services.risk_monitor_service import RiskMonitorService
from webapp.tools.mongo import DATABASE
from webapp.tools.security import User, get_current_active_user

router = APIRouter(prefix="/risk-monitor", tags=["风险监控"])


def _svc() -> RiskMonitorService:
    return RiskMonitorService(DATABASE)


@router.get("/check", summary="仅执行数据质量检查，不重算")
async def check_data(
    date_str: Optional[str] = Query(None, alias="date", description="交割日 YYYY-MM-DD，默认取最新完整日"),
    current_user: User = Depends(get_current_active_user),
):
    d = None
    if date_str:
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="date 格式应为 YYYY-MM-DD")
    svc = _svc()
    d = d or svc._latest_complete_day()
    checks = svc.check_data_quality(d)
    return {
        "delivery_date": d.isoformat(),
        "overall": "fail" if any(c["level"] == "fail" for c in checks) else (
            "warn" if any(c["level"] == "warn" for c in checks) else "ok"
        ),
        "checks": checks,
    }


@router.post("/run", summary="执行一次完整监控 + 重算 + 快照")
async def run_monitor(
    date_str: Optional[str] = Query(None, alias="date"),
    current_user: User = Depends(get_current_active_user),
):
    d = None
    if date_str:
        try:
            d = date.fromisoformat(date_str)
        except ValueError:
            raise HTTPException(status_code=400, detail="date 格式错误")
    return _svc().run(d)


@router.get("/latest", summary="最近一次监控报告")
async def latest(current_user: User = Depends(get_current_active_user)):
    return _svc().latest_report()


@router.get("/history", summary="监控历史")
async def history(
    limit: int = Query(20, ge=1, le=200),
    current_user: User = Depends(get_current_active_user),
):
    return {"items": _svc().history(limit)}
