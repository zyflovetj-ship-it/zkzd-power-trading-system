import logging
from fastapi import APIRouter, Body, Depends, HTTPException, status
from webapp.tools.mongo import DATABASE
from webapp.services.system_model_parameters_service import SystemModelParametersService
from webapp.tools.security import User, get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system-model-parameters"])


@router.get("/")
async def get_model_parameters(current_user: User = Depends(get_current_active_user)):
    """获取预测模型参数列表"""
    try:
        return SystemModelParametersService(DATABASE).get_models()
    except Exception as e:
        logger.error("获取预测模型参数失败: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))



@router.post("/")
async def create_model_parameter(
    data: dict = Body(...),
    current_user: User = Depends(get_current_active_user),
):
    """新增模型参数。名称为空 400，重名 409。"""
    try:
        return SystemModelParametersService(DATABASE).create_param(
            data, operator=current_user.username)
    except ValueError as e:
        msg = str(e)
        code = status.HTTP_409_CONFLICT if "已存在" in msg else status.HTTP_400_BAD_REQUEST
        logger.warning("新增模型参数失败: %s", msg)
        raise HTTPException(status_code=code, detail=msg)


@router.put("/{param_id}")
async def update_model_parameter(
    param_id: str,
    data: dict = Body(...),
    current_user: User = Depends(get_current_active_user),
):
    """更新模型参数。"""
    try:
        return SystemModelParametersService(DATABASE).update_param(
            param_id, data, operator=current_user.username)
    except ValueError as e:
        msg = str(e)
        code = status.HTTP_404_NOT_FOUND if "不存在" in msg else status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=msg)


@router.delete("/{param_id}")
async def delete_model_parameter(
    param_id: str,
    current_user: User = Depends(get_current_active_user),
):
    """删除模型参数。"""
    try:
        ok = SystemModelParametersService(DATABASE).delete_param(param_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    if not ok:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="参数不存在")
    return {"deleted": True, "param_id": param_id}
