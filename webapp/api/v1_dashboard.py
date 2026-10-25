from fastapi import APIRouter, Depends

from webapp.services.dashboard_service import DashboardService
from webapp.tools.mongo import DATABASE
from webapp.tools.security import get_current_active_user, User

router = APIRouter()


@router.get("", response_model=dict, summary="获取交易总览数据")
async def get_dashboard(
    current_user: User = Depends(get_current_active_user),
):
    service = DashboardService(DATABASE)
    return service.get_dashboard_data()