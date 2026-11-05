from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status

from webapp.models.retail_package import PackageListResponse, RetailPackage
from webapp.services.package_service import PackageService
from webapp.services.pricing_engine import PricingEngine
from webapp.services.package_calc_service import PackageCalcService
from webapp.tools.mongo import DATABASE
from webapp.tools.security import User, get_current_active_user

router = APIRouter(prefix="/retail-packages", tags=["Retail Packages"])

@router.post("", response_model=dict, status_code=status.HTTP_201_CREATED)
async def create_package(
    package: RetailPackage,
    save_as_draft: bool = True,
    current_user: User = Depends(get_current_active_user)
):
    """创建新的零售套餐"""
    service = PackageService(DATABASE)
    try:
        result = service.create(
            package_data=package.dict(exclude_unset=True),
            status="draft" if save_as_draft else "active",
            operator=current_user.username
        )
        return result
    except ValueError as e:
        error_msg = str(e)
        if "名称已存在" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )

@router.put("/{package_id}", response_model=dict)
async def update_package(
    package_id: str,
    package: RetailPackage,
    current_user: User = Depends(get_current_active_user)
):
    """更新套餐"""
    service = PackageService(DATABASE)
    try:
        result = service.update(
            package_id=package_id,
            package_data=package.dict(exclude_unset=True),
            operator=current_user.username
        )
        return result
    except ValueError as e:
        error_msg = str(e)
        if "名称已存在" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail=error_msg
            )
        elif "状态" in error_msg or "不存在" in error_msg or "无效" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )

@router.post("/{package_id}/copy", response_model=dict, status_code=status.HTTP_201_CREATED)
async def copy_package(
    package_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """复制套餐"""
    service = PackageService(DATABASE)
    try:
        result = service.copy_package(
            package_id=package_id,
            operator=current_user.username
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.get("", response_model=PackageListResponse)
async def list_packages(
    keyword: Optional[str] = None,
    package_type: Optional[str] = None,
    is_green_power: Optional[str] = None,
    model_code: Optional[str] = None,
    status: Optional[str] = None,
    page: int = 1,
    page_size: int = 20,
    current_user: User = Depends(get_current_active_user)
):
    """获取套餐列表"""
    service = PackageService(DATABASE)
    result = service.list(
        filters={
            "keyword": keyword,
            "package_type": package_type,
            "is_green_power": is_green_power,
            "model_code": model_code,
            "status": status
        },
        page=page,
        page_size=page_size
    )
    return result

@router.post("/{package_id}/activate", response_model=dict)
async def activate_package(
    package_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """激活套餐"""
    service = PackageService(DATABASE)
    try:
        result = service.change_status(
            package_id=package_id,
            new_status="active",
            operator=current_user.username
        )
        return result
    except ValueError as e:
        error_msg = str(e)
        if error_msg.startswith("RISK_WARNING::"):
            # 参数越界：要求法定代表人二次确认
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "code": "RISK_WARNING",
                    "message": "套餐参数越界触发风险预警，须经法定代表人确认后方可激活（交易工作指引第五条）",
                    "violations": error_msg.replace("RISK_WARNING::", ""),
                    "action": "请调用 POST /retail-packages/{id}/legal-confirm 完成法定代表人确认",
                },
            )
        if "不允许的状态转换" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )

@router.post("/{package_id}/archive", response_model=dict)
async def archive_package(
    package_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """归档套餐"""
    service = PackageService(DATABASE)
    try:
        result = service.change_status(
            package_id=package_id,
            new_status="archived",
            operator=current_user.username
        )
        return result
    except ValueError as e:
        error_msg = str(e)
        if "不允许的状态转换" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )

@router.get("/{package_id}", response_model=dict)
async def get_package(
    package_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """获取套餐详情"""
    service = PackageService(DATABASE)
    try:
        result = service.get_by_id(package_id)
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )

@router.delete("/{package_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_package(
    package_id: str,
    current_user: User = Depends(get_current_active_user)
):
    """删除套餐（仅草稿状态）"""
    service = PackageService(DATABASE)
    try:
        service.delete(package_id)
        return None  # 204 No Content
    except ValueError as e:
        error_msg = str(e)
        if "状态" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=error_msg
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )


# =====================================================================
# 套餐测算（江苏 2027 新规）
# =====================================================================
@router.post("/{package_id}/calc-from-load", response_model=dict)
async def calc_from_load(
    package_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user),
):
    """路径A：按历史负荷曲线测算套餐电费。

    payload: { customer_id, period(YYYY-MM), market{wholesale_price,share_price,reference_price}, params{...} }
    """
    service = PackageService(DATABASE)
    try:
        package = service.get_by_id(package_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    calc = PackageCalcService(DATABASE)
    return calc.calc_from_load(
        package=package,
        customer_id=payload.get("customer_id"),
        period=payload.get("period"),
        market=payload.get("market") or {},
        overrides=payload.get("params"),
        auto_market=bool(payload.get("auto_market", False)),
        holding_ratio=float(payload.get("holding_ratio", 0.9)),
        k2_ratio=float(payload.get("k2_ratio", 0.05)),
        mid_long_price=payload.get("mid_long_price"),
    )


@router.post("/{package_id}/calc-from-bill", response_model=dict)
async def calc_from_bill(
    package_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user),
):
    """路径B：按核查联测算套餐电费，并与现状实收电费对比。

    payload: { bill{period,total_mwh,peak_mwh,flat_mwh,valley_mwh,current_amount,...},
               market{wholesale_price,share_price,reference_price}, params{...} }
    """
    service = PackageService(DATABASE)
    try:
        package = service.get_by_id(package_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    bill = payload.get("bill") or {}
    calc = PackageCalcService(DATABASE)
    return calc.calc_from_bill(
        package=package,
        bill=bill,
        market=payload.get("market") or {},
        overrides=payload.get("params"),
    )


# =====================================================================
# 年度批量测算 & 2027 新规合规校验
# =====================================================================
@router.post("/{package_id}/calc-annual", response_model=dict)
async def calc_annual(
    package_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user),
):
    """逐用户 × 12 月批量测算（2027 新规全链路）。

    payload:
      year: 2026
      customer_ids: ["..."]           # 为空则取全部客户
      auto_market: true
      holding_ratio: 0.9
      k2_ratio: 0.05
      mid_long_price: null
      market: {share_cost_compensation, share_imbalance, share_market_adjust}
      params: {peak_coef, valley_coef, service_fee, f_ratio, k1_share, k2_share, k3_share, green_mode, env_value}
    """
    service = PackageService(DATABASE)
    try:
        package = service.get_by_id(package_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    year = int(payload.get("year") or 2026)
    customer_ids = payload.get("customer_ids") or []
    if not customer_ids:
        customer_ids = [str(d["_id"]) for d in DATABASE["customers"].find({}, {"_id": 1})]

    calc = PackageCalcService(DATABASE)
    return calc.calc_annual(
        package=package,
        customer_ids=customer_ids,
        year=year,
        market=payload.get("market") or {},
        overrides=payload.get("params"),
        auto_market=bool(payload.get("auto_market", True)),
        holding_ratio=float(payload.get("holding_ratio", 0.9)),
        k2_ratio=float(payload.get("k2_ratio", 0.05)),
        mid_long_price=payload.get("mid_long_price"),
        ktype=payload.get("ktype"),
        pointwise=bool(payload.get("pointwise", True)),
        market_source=str(payload.get("market_source", "manual")),
    )


@router.get("/compliance/rules", response_model=dict)
async def compliance_rules(current_user: User = Depends(get_current_active_user)):
    """2027 新规套餐参数合规规则清单。"""
    from webapp.services.compliance_service import ComplianceService
    return {"rules": ComplianceService.rules(), "defaults": ComplianceService().validate({})["params"]}


@router.post("/compliance/validate", response_model=dict)
async def validate_compliance(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user),
):
    """校验套餐参数是否符合 2027 新规（附件2）。body 直接传参数 dict。"""
    from webapp.services.compliance_service import ComplianceService
    return ComplianceService().validate(payload)


# =====================================================================
# 风险预警 & 法定代表人二次确认
# =====================================================================
@router.get("/{package_id}/risk-warning", response_model=dict)
async def get_risk_warning(
    package_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """查询套餐风险预警状态（是否越界、是否已获法定代表人确认）。"""
    from webapp.services.risk_warning_service import RiskWarningService
    try:
        return RiskWarningService(DATABASE).evaluate_by_id(package_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/{package_id}/legal-confirm", response_model=dict)
async def legal_confirm(
    package_id: str,
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user),
):
    """法定代表人二次确认。

    payload: {confirmed_by: "法人姓名", note: "说明", attachment_name: "授权书.pdf"}
    """
    from webapp.services.risk_warning_service import RiskWarningService
    try:
        return RiskWarningService(DATABASE).confirm(
            package_id=package_id,
            operator=current_user.username,
            confirmed_by=payload.get("confirmed_by"),
            note=payload.get("note"),
            attachment_name=payload.get("attachment_name"),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/{package_id}/confirm-logs", response_model=dict)
async def confirm_logs(
    package_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """法定代表人确认审计留痕。"""
    from webapp.services.risk_warning_service import RiskWarningService
    return {"items": RiskWarningService(DATABASE).logs(package_id)}
