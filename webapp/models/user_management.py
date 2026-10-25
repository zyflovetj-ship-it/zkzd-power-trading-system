from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime


class UserCreate(BaseModel):
    username: str = Field(..., min_length=2, description="用户名")
    full_name: Optional[str] = Field(None, description="全名")
    email: Optional[str] = Field(None, description="邮箱")
    department: Optional[str] = Field(None, description="部门")
    role: str = Field("交易员", description="角色: 管理员/交易员/风控/只读")
    password: str = Field(..., min_length=6, description="密码")


class UserUpdate(BaseModel):
    full_name: Optional[str] = Field(None, description="全名")
    email: Optional[str] = Field(None, description="邮箱")
    department: Optional[str] = Field(None, description="部门")
    role: Optional[str] = Field(None, description="角色")
    is_active: Optional[bool] = Field(None, description="是否启用")


class UserListItem(BaseModel):
    id: str
    username: str
    full_name: Optional[str] = None
    email: Optional[str] = None
    department: Optional[str] = None
    role: str
    is_active: bool = True
    last_login: Optional[str] = None
    created_at: Optional[datetime] = None


class UserListResponse(BaseModel):
    total: int = 0
    items: list[UserListItem] = []
