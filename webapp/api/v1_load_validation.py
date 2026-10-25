import logging
from fastapi import APIRouter, Depends, HTTPException, status
from webapp.tools.mongo import DATABASE
from webapp.services.load_validation_service import LoadValidationService
from webapp.tools.security import get_current_active_user

logger = logging.getLogger(__name__)

router = APIRouter(tags=["load-validation"])


@router.get("/")
async def get_load_validation(current_user: dict = Depends(get_current_active_user)):
    """获取负荷数据校验记录"""
    try:
        return LoadValidationService(DATABASE).get_records()
    except Exception as e:
        logger.error("获取负荷数据校验失败: %s", e)
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
