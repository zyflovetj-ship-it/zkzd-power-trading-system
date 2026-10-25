"""
中长期趋势分析 - API路由
"""
from fastapi import APIRouter, Query, HTTPException, status
from datetime import datetime, timedelta
import logging

from webapp.tools.mongo import DATABASE
from webapp.services.contract_price_trend_service import ContractPriceTrendService
from webapp.models.contract_price_trend import ContractPriceTrendResponse, CurveAnalysisResponse, QuantityStructureResponse

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/contract-price-trend", tags=["contract-price-trend"])


def get_service():
    return ContractPriceTrendService(DATABASE)


@router.get(
    "/price-trend",
    response_model=ContractPriceTrendResponse,
    summary="获取中长期合同价格趋势分析数据",
    description="获取指定日期范围内的中长期合同与现货价格对比趋势"
)
def get_price_trend(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    spot_type: str = Query("day_ahead", description="基准现货类型: day_ahead(日前) 或 real_time(实时)")
):
    """
    获取中长期合同价格趋势分析数据
    
    返回：
    - daily_trends: 每日趋势数据（中长期均价、现货均价、价差、正负价差时段数）
    - spread_stats: 价差统计指标
    - spread_distribution: 价差分布直方图数据
    """
    logger.info(f"[API] get_price_trend: start={start_date}, end={end_date}, spot_type={spot_type}")
    
    try:
        # 验证日期格式
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        # 验证日期范围
        if start > end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="开始日期不能晚于结束日期"
            )
        
        # 验证 spot_type
        if spot_type not in ("day_ahead", "real_time"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="spot_type 必须是 'day_ahead' 或 'real_time'"
            )
        
        service = get_service()
        return service.get_price_trend(start, end, spot_type)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="日期格式无效，请使用 YYYY-MM-DD 格式"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_price_trend: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/curve-analysis",
    response_model=CurveAnalysisResponse,
    summary="获取曲线分析数据（按类型分组）",
    description="获取指定日期范围内按合同类型分组的日均价格曲线"
)
def get_curve_analysis(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD"),
    spot_type: str = Query("day_ahead", description="基准现货类型: day_ahead(日前) 或 real_time(实时)")
):
    """
    获取曲线分析数据
    
    返回按合同类型分组的日均价格曲线：
    - 市场化：整体、年度、月度、月内
    - 绿电：整体、年度、月度、月内
    - 代理购电：整体、年度、月度
    """
    logger.info(f"[API] get_curve_analysis: start={start_date}, end={end_date}, spot_type={spot_type}")
    
    try:
        # 验证日期格式
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        # 验证日期范围
        if start > end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="开始日期不能晚于结束日期"
            )
        
        # 验证 spot_type
        if spot_type not in ("day_ahead", "real_time"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="spot_type 必须是 'day_ahead' 或 'real_time'"
            )
        
        service = get_service()
        return service.get_curve_analysis(start, end, spot_type)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="日期格式无效，请使用 YYYY-MM-DD 格式"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_curve_analysis: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get(
    "/quantity-structure",
    response_model=QuantityStructureResponse,
    summary="获取电量结构分析数据",
    description="获取指定日期范围内每日电量组成"
)
def get_quantity_structure(
    start_date: str = Query(..., description="开始日期 YYYY-MM-DD"),
    end_date: str = Query(..., description="结束日期 YYYY-MM-DD")
):
    """
    获取电量结构分析数据
    
    返回每日电量组成：
    - 按周期：年度、月度、月内
    - 按类型：市场化、绿电、代理购电
    """
    logger.info(f"[API] get_quantity_structure: start={start_date}, end={end_date}")
    
    try:
        # 验证日期格式
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        # 验证日期范围
        if start > end:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="开始日期不能晚于结束日期"
            )
        
        service = get_service()
        return service.get_quantity_structure(start, end)
        
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="日期格式无效，请使用 YYYY-MM-DD 格式"
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in get_quantity_structure: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )
