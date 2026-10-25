import logging
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from webapp.tools.mongo import DATABASE
from webapp.models.user_management import UserCreate, UserUpdate
from webapp.services.system_users_service import SystemUsersService
from webapp.tools.security import get_current_active_user, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["system-users"])


@router.get("/", summary="获取用户列表")
async def list_users(
    keyword: Optional[str] = Query(None, description="搜索关键词"),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_active_user),
):
    service = SystemUsersService(DATABASE)
    return service.get_users(keyword=keyword, page=page, page_size=page_size)


@router.post("/", summary="创建用户", status_code=status.HTTP_201_CREATED)
async def create_user(
    user: UserCreate,
    current_user: User = Depends(get_current_active_user),
):
    service = SystemUsersService(DATABASE)
    try:
        return service.create_user(user.model_dump(), operator=current_user.username)
    except ValueError as e:
        msg = str(e)
        if "已存在" in msg:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.put("/{user_id}", summary="更新用户")
async def update_user(
    user_id: str,
    user: UserUpdate,
    current_user: User = Depends(get_current_active_user),
):
    service = SystemUsersService(DATABASE)
    try:
        return service.update_user(user_id, user.model_dump(exclude_unset=True), operator=current_user.username)
    except ValueError as e:
        msg = str(e)
        if "不存在" in msg:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=msg)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)


@router.delete("/{user_id}", summary="删除用户", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: str,
    current_user: User = Depends(get_current_active_user),
):
    service = SystemUsersService(DATABASE)
    try:
        service.delete_user(user_id)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))


@router.post("/{user_id}/reset-password", summary="重置用户密码")
async def reset_password(
    user_id: str,
    body: dict,
    current_user: User = Depends(get_current_active_user),
):
    password = body.get("password", "")
    if not password or len(password) < 6:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="密码长度至少6位")
    service = SystemUsersService(DATABASE)
    try:
        service.reset_password(user_id, password)
        return {"message": "密码重置成功"}
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
