"""
负荷数据校验 API 路由

提供负荷数据校验相关的 API 端点：
1. POST /transform-manual-data - 96点手工数据转48点
2. POST /import-rpa-data - RPA数据聚合到结算曲线
3. POST /analyze-completeness - 分析数据完整性
4. GET /completeness-report/{customer_id} - 获取完整性报告
5. GET /completeness-dashboard - 完整性概览仪表板
6. POST /validate-curves - 执行数据校核
7. GET /curve-comparison - 曲线对比数据
8. POST /regenerate-load-curve - 重新生成负荷曲线
"""
import logging
from datetime import date
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from webapp.models.data_validation import (
    TransformManualDataRequest,
    ImportRpaDataRequest,
    AnalyzeCompletenessRequest,
    ValidateCurvesRequest,
    RegenerateLoadCurveRequest,
    CompletenessDashboardResponse,
    CurveComparisonResponse,
)
from webapp.services.data_validation_service import DataValidationService
from webapp.tools.mongo import DATABASE
from webapp.tools.security import get_current_active_user, User

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/data-validation", tags=["Data Validation"])


@router.post(
    "/transform-manual-data",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="96点手工数据转48点负荷曲线",
    description="将user_load_data中的96点手工数据聚合为48点用户级负荷曲线并存入load_curve_user"
)
async def transform_manual_data(
    request: TransformManualDataRequest,
    current_user: User = Depends(get_current_active_user)
):
    """96点手工数据转48点负荷曲线"""
    service = DataValidationService(DATABASE)
    try:
        result = service.transform_manual_data(
            import_batch_id=request.import_batch_id,
            operator=current_user.username
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("手工数据转换失败: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"手工数据转换失败: {str(e)}"
        )


@router.post(
    "/import-rpa-data",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="RPA数据聚合到结算曲线",
    description="从RPA源集合聚合数据到settlement_curve_user"
)
async def import_rpa_data(
    request: ImportRpaDataRequest,
    current_user: User = Depends(get_current_active_user)
):
    """RPA数据聚合到结算曲线"""
    service = DataValidationService(DATABASE)
    try:
        result = service.import_rpa_data(
            rpa_batch_id=request.rpa_batch_id,
            source_collection=request.source_collection,
            operator=current_user.username
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("RPA数据导入失败: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RPA数据导入失败: {str(e)}"
        )


@router.post(
    "/analyze-completeness",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="分析数据完整性",
    description="分析指定客户的负荷曲线和结算曲线数据完整性"
)
async def analyze_completeness(
    request: AnalyzeCompletenessRequest,
    current_user: User = Depends(get_current_active_user)
):
    """分析数据完整性"""
    service = DataValidationService(DATABASE)
    try:
        result = service.analyze_completeness(
            customer_id=request.customer_id,
            operator=current_user.username
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("完整性分析失败: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"完整性分析失败: {str(e)}"
        )


@router.get(
    "/completeness-report/{customer_id}",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="获取完整性报告",
    description="获取指定客户的最新或历史完整性报告"
)
async def get_completeness_report(
    customer_id: str,
    latest: bool = Query(True, description="是否只获取最新报告"),
    current_user: User = Depends(get_current_active_user)
):
    """获取完整性报告"""
    service = DataValidationService(DATABASE)
    result = service.get_completeness_report(customer_id, latest)
    if not result:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"客户 {customer_id} 无完整性报告"
        )
    return result


@router.get(
    "/completeness-dashboard",
    response_model=CompletenessDashboardResponse,
    status_code=status.HTTP_200_OK,
    summary="完整性概览仪表板",
    description="获取所有客户的数据完整性概览，包含健康/预警/严重分级"
)
async def get_completeness_dashboard(
    current_user: User = Depends(get_current_active_user)
):
    """完整性概览仪表板"""
    service = DataValidationService(DATABASE)
    return service.get_completeness_dashboard()


@router.post(
    "/validate-curves",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="执行数据校核",
    description="比较负荷曲线与结算曲线的偏差，支持深入分析阈值配置"
)
async def validate_curves(
    request: ValidateCurvesRequest,
    current_user: User = Depends(get_current_active_user)
):
    """执行数据校核"""
    service = DataValidationService(DATABASE)
    try:
        result = service.validate_curves(
            customer_id=request.customer_id,
            validation_date=request.validation_date,
            deep_analysis_threshold=request.deep_analysis_threshold,
            operator=current_user.username
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("曲线校核失败: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"曲线校核失败: {str(e)}"
        )


@router.get(
    "/curve-comparison",
    response_model=CurveComparisonResponse,
    status_code=status.HTTP_200_OK,
    summary="曲线对比数据",
    description="获取指定客户和日期的48点负荷曲线与结算曲线对比数据"
)
async def get_curve_comparison(
    customer_id: str = Query(..., description="客户ID"),
    comparison_date: date = Query(..., description="对比日期(YYYY-MM-DD)"),
    current_user: User = Depends(get_current_active_user)
):
    """获取曲线对比数据"""
    service = DataValidationService(DATABASE)
    try:
        return service.get_curve_comparison(customer_id, comparison_date)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except Exception as e:
        logger.error("曲线对比查询失败: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"曲线对比查询失败: {str(e)}"
        )


@router.post(
    "/regenerate-load-curve",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="重新生成负荷曲线",
    description="基于当前分配系数重新计算用户级负荷曲线"
)
async def regenerate_load_curve(
    request: RegenerateLoadCurveRequest,
    current_user: User = Depends(get_current_active_user)
):
    """重新生成负荷曲线"""
    service = DataValidationService(DATABASE)
    try:
        result = service.regenerate_load_curve(
            customer_id=request.customer_id,
            operator=current_user.username
        )
        return result
    except ValueError as e:
        error_msg = str(e)
        if "不存在" in error_msg or "无" in error_msg:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=error_msg
            )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=error_msg
        )
    except Exception as e:
        logger.error("负荷曲线重新生成失败: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"负荷曲线重新生成失败: {str(e)}"
        )
