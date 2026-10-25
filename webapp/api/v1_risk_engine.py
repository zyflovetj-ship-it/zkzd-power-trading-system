"""
风险引擎 API（P0）

挂载方式（需人工确认后再改 main.py，避免影响线上）：
    from webapp.api import v1_risk_engine
    app.include_router(
        v1_risk_engine.router,
        prefix="/api/v1",
        dependencies=[Depends(get_current_active_user)],
    )

与旧 /api/v1/risk-exposure 并存，互不影响。
"""

from __future__ import annotations

import logging
from datetime import date, datetime, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from webapp.models.risk import MODEL_VERSION
from webapp.services.risk_backtest_service import RiskBacktestService
from webapp.services.risk_engine_service import RiskEngineConfig, RiskEngineService
from webapp.services.risk_stress_service import RiskStressService
from webapp.tools.mongo import DATABASE
from webapp.tools.security import User, get_current_active_user

logger = logging.getLogger(__name__)

# 注意：zk-energy-new 已占用 /api/v1/risk/exposure（旧敞口）与
# /api/v1/risk/position-contracts（持仓），故本引擎统一挂在 /api/v1/risk-engine 下，零冲突。
router = APIRouter(prefix="/risk-engine", tags=["风险管理引擎"])


def _service() -> RiskEngineService:
    return RiskEngineService(DATABASE)


def _parse_date(value: Optional[str]) -> date:
    if not value:
        return date.today()
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="date 格式应为 YYYY-MM-DD",
        )


@router.get("/meta", summary="风险引擎元信息与口径说明")
async def get_meta(current_user: User = Depends(get_current_active_user)):
    cfg = RiskEngineConfig()
    return {
        "model_version": MODEL_VERSION,
        "periods_per_day": 96,
        "units": {
            "contract": cfg.contract_unit,
            "load": cfg.load_unit,
            "price": "元/MWh",
            "internal_energy": "MWh",
        },
        "notes": [
            "敞口 = 合约锁定电量 − 负荷，正为超配多头，负为欠配空头",
            "VaR 采用分时段相关性模型，波动率为同点隔日对数收益（日频）",
            "所有降级路径写入 warnings 字段，不静默返回 0",
        ],
    }


@router.get("/validate", summary="入库数据自洽性校验（算前先看这个）")
async def validate_inputs(
    date_str: Optional[str] = Query(None, alias="date", description="交割日 YYYY-MM-DD"),
    current_user: User = Depends(get_current_active_user),
):
    delivery = _parse_date(date_str)
    try:
        return _service().validate_inputs(delivery)
    except Exception as exc:
        logger.error("数据校验失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"数据校验失败: {exc}")


@router.get("/exposure", summary="获取指定交割日的 96 点敞口曲线与汇总")
async def get_exposure(
    date_str: Optional[str] = Query(None, alias="date", description="交割日 YYYY-MM-DD，默认今天"),
    current_user: User = Depends(get_current_active_user),
):
    delivery = _parse_date(date_str)
    try:
        result = _service().build_exposure(delivery)
    except Exception as exc:
        logger.error("计算风险敞口失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"计算风险敞口失败: {exc}")
    return {
        "summary": result["summary"].model_dump(mode="json"),
        "curve": [p.model_dump(mode="json") for p in result["curve"]],
    }


@router.get("/var", summary="计算组合 VaR / CVaR（含分时段贡献）")
async def get_var(
    date_str: Optional[str] = Query(None, alias="date", description="交割日 YYYY-MM-DD"),
    confidence: float = Query(0.95, description="置信度，支持 0.90 / 0.95 / 0.99"),
    horizon_days: int = Query(1, ge=1, le=30, description="持有期（天）"),
    method: str = Query("parametric", description="parametric / historical"),
    current_user: User = Depends(get_current_active_user),
):
    if method not in ("parametric", "historical"):
        raise HTTPException(status_code=400, detail="method 仅支持 parametric / historical")
    delivery = _parse_date(date_str)
    try:
        var = _service().compute_var(delivery, confidence, horizon_days, method)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("计算 VaR 失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"计算 VaR 失败: {exc}")
    return var.model_dump(mode="json")


@router.get("/limits", summary="限额使用情况与突破明细")
async def get_limits(
    date_str: Optional[str] = Query(None, alias="date", description="交割日 YYYY-MM-DD"),
    current_user: User = Depends(get_current_active_user),
):
    delivery = _parse_date(date_str)
    service = _service()
    try:
        exposure = service.build_exposure(delivery)
        var = service.compute_var(delivery)
        breaches = service.check_limits(exposure["summary"], var.var_yuan)
    except Exception as exc:
        logger.error("限额检查失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"限额检查失败: {exc}")
    return {
        "delivery_date": delivery.isoformat(),
        "summary": exposure["summary"].model_dump(mode="json"),
        "var_yuan": var.var_yuan,
        "breaches": [b.model_dump() for b in breaches],
        "max_severity": "breach" if any(b.severity == "breach" for b in breaches)
        else ("warning" if breaches else "ok"),
    }


@router.post("/snapshot", summary="落风险快照（可回溯复现）")
async def create_snapshot(
    date_str: Optional[str] = Query(None, alias="date", description="交割日 YYYY-MM-DD"),
    current_user: User = Depends(get_current_active_user),
):
    delivery = _parse_date(date_str)
    try:
        return _service().save_snapshot(delivery)
    except Exception as exc:
        logger.error("落风险快照失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"落风险快照失败: {exc}")


@router.get("/snapshots", summary="查询历史风险快照")
async def list_snapshots(
    days: int = Query(7, ge=1, le=90, description="回溯天数"),
    limit: int = Query(50, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
):
    since = datetime.now() - timedelta(days=days)
    cursor = (
        DATABASE.risk_metric_snapshot.find({"as_of": {"$gte": since}})
        .sort("as_of", -1)
        .limit(limit)
    )
    items = []
    for doc in cursor:
        items.append(
            {
                "snapshot_id": str(doc.get("_id")),
                "as_of": doc.get("as_of"),
                "delivery_date": doc.get("delivery_date"),
                "model_version": doc.get("model_version"),
                "data_fingerprint": doc.get("data_fingerprint"),
                "risk_level": (doc.get("summary") or {}).get("risk_level"),
                "price_exposure_yuan": (doc.get("summary") or {}).get("price_exposure_yuan"),
                "var_yuan": (doc.get("var") or {}).get("var_yuan"),
            }
        )
    return {"total": len(items), "items": items}


# ============================ P1：回测 / 压力测试 / 预警 ============================


@router.get("/backtest", summary="VaR 滚动回测（Kupiec + Christoffersen）")
async def run_backtest(
    date_str: Optional[str] = Query(None, alias="date", description="交割日 YYYY-MM-DD"),
    confidence: float = Query(0.95, description="置信度，支持 0.90 / 0.95 / 0.99"),
    window_days: int = Query(20, ge=12, le=120, description="滚动估计窗口(天)"),
    method: str = Query("parametric", description="parametric / historical"),
    current_user: User = Depends(get_current_active_user),
):
    delivery = _parse_date(date_str)
    try:
        result = RiskBacktestService(DATABASE).run(delivery, confidence, window_days, method)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.error("VaR 回测失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"VaR 回测失败: {exc}")
    return result.model_dump(mode="json")


@router.get("/stress/scenarios", summary="压力测试场景库")
async def list_stress_scenarios(current_user: User = Depends(get_current_active_user)):
    scenarios = RiskStressService(DATABASE).list_scenarios()
    return {"total": len(scenarios), "items": [s.model_dump() for s in scenarios]}


@router.post("/stress/seed", summary="写入内置场景库（幂等）")
async def seed_stress_scenarios(current_user: User = Depends(get_current_active_user)):
    try:
        n = RiskStressService(DATABASE).seed_scenarios()
    except Exception as exc:
        logger.error("写入场景库失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"写入场景库失败: {exc}")
    return {"inserted": n}


@router.post("/stress/run", summary="跑全部压力测试场景")
async def run_stress_suite(
    date_str: Optional[str] = Query(None, alias="date", description="交割日 YYYY-MM-DD"),
    current_user: User = Depends(get_current_active_user),
):
    delivery = _parse_date(date_str)
    try:
        suite = RiskStressService(DATABASE).run_suite(delivery)
    except Exception as exc:
        logger.error("压力测试失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"压力测试失败: {exc}")
    return suite.model_dump(mode="json")


@router.post("/alerts/generate", summary="生成预警事件（数据/限额/回测/压力）")
async def generate_alerts(
    date_str: Optional[str] = Query(None, alias="date", description="交割日 YYYY-MM-DD"),
    current_user: User = Depends(get_current_active_user),
):
    delivery = _parse_date(date_str)
    try:
        events = RiskStressService(DATABASE).generate_alerts(delivery)
    except Exception as exc:
        logger.error("生成预警失败: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=f"生成预警失败: {exc}")
    return {"generated": len(events), "items": [e.model_dump(mode="json") for e in events]}


@router.get("/alerts", summary="查询预警事件")
async def list_alerts(
    status: str = Query("open", description="open / ack / closed，传空串查全部"),
    limit: int = Query(100, ge=1, le=500),
    current_user: User = Depends(get_current_active_user),
):
    items = RiskStressService(DATABASE).list_alerts(status, limit)
    return {"total": len(items), "items": items}
