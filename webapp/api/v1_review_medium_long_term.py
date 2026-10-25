"""
中长期交易复盘 API 路由
"""

from datetime import date
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from webapp.tools.security import get_current_active_user
from webapp.services.medium_long_term_review_service import MediumLongTermReviewService
from webapp.tools.mongo import DATABASE

router = APIRouter()


# 请求模型
class GenerateReviewRequest(BaseModel):
    """生成复盘报告请求"""
    customer_id: str = Field(..., description="客户ID")
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)")
    compare_baselines: Optional[List[str]] = Field(
        default=None,
        description="对比基准列表 (pure_spot, fixed_price, market_avg)"
    )


class ExecutionDataRequest(BaseModel):
    """获取执行数据请求"""
    customer_id: str = Field(..., description="客户ID")
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)")
    granularity: str = Field(default="day", description="粒度 (day, week, month)")


class CostBenefitRequest(BaseModel):
    """获取成本效益分析请求"""
    customer_id: str = Field(..., description="客户ID")
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)")


class TimingAnalysisRequest(BaseModel):
    """获取时机分析请求"""
    customer_id: str = Field(..., description="客户ID")
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)")


class StrategyComparisonRequest(BaseModel):
    """获取策略对比请求"""
    customer_id: str = Field(..., description="客户ID")
    start_date: str = Field(..., description="开始日期 (YYYY-MM-DD)")
    end_date: str = Field(..., description="结束日期 (YYYY-MM-DD)")


# 响应模型
class ReviewResponse(BaseModel):
    """复盘报告响应"""
    review_id: str
    customer_id: str
    customer_name: str
    review_period: Dict[str, Any]
    execution_metrics: Dict[str, Any]
    cost_metrics: Dict[str, Any]
    timing_analysis: Dict[str, Any]
    strategy_comparison: List[Dict[str, Any]]
    anomalies: List[Dict[str, Any]]
    summary: Dict[str, Any]
    generated_at: Any
    status: str


# API 端点
@router.post("/generate", response_model=ReviewResponse)
async def generate_review(
    request: GenerateReviewRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    生成中长期交易复盘报告

    Args:
        request: 复盘报告生成请求
        current_user: 当前用户（由依赖注入）

    Returns:
        完整的复盘报告数据
    """
    try:
        service = MediumLongTermReviewService(DATABASE)

        # 解析日期
        start_date = date.fromisoformat(request.start_date)
        end_date = date.fromisoformat(request.end_date)

        # 生成复盘报告
        review = service.generate_review(
            customer_id=request.customer_id,
            start_date=start_date,
            end_date=end_date,
            compare_baselines=request.compare_baselines
        )

        return review
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"生成复盘报告失败: {str(e)}")


@router.post("/execution")
async def get_execution_data(
    request: ExecutionDataRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    获取合同执行数据（计划 vs 实际）

    Args:
        request: 执行数据请求
        current_user: 当前用户（由依赖注入）

    Returns:
        合同执行详细数据
    """
    try:
        service = MediumLongTermReviewService(DATABASE)

        # 解析日期
        start_date = date.fromisoformat(request.start_date)
        end_date = date.fromisoformat(request.end_date)

        # 获取执行数据
        execution_data = service.get_execution_data(
            customer_id=request.customer_id,
            start_date=start_date,
            end_date=end_date,
            granularity=request.granularity
        )

        return execution_data
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取执行数据失败: {str(e)}")


@router.post("/cost-benefit")
async def get_cost_benefit(
    request: CostBenefitRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    获取成本效益分析

    Args:
        request: 成本效益分析请求
        current_user: 当前用户（由依赖注入）

    Returns:
        成本效益分析数据
    """
    try:
        service = MediumLongTermReviewService(DATABASE)

        # 解析日期
        start_date = date.fromisoformat(request.start_date)
        end_date = date.fromisoformat(request.end_date)

        # 获取成本效益分析
        cost_benefit = service.get_cost_benefit(
            customer_id=request.customer_id,
            start_date=start_date,
            end_date=end_date
        )

        return cost_benefit
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取成本效益分析失败: {str(e)}")


@router.post("/timing")
async def get_timing_analysis(
    request: TimingAnalysisRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    获取时机分析

    Args:
        request: 时机分析请求
        current_user: 当前用户（由依赖注入）

    Returns:
        时机分析数据
    """
    try:
        service = MediumLongTermReviewService(DATABASE)

        # 解析日期
        start_date = date.fromisoformat(request.start_date)
        end_date = date.fromisoformat(request.end_date)

        # 获取时机分析
        timing_analysis = service.get_timing_analysis(
            customer_id=request.customer_id,
            start_date=start_date,
            end_date=end_date
        )

        return timing_analysis
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取时机分析失败: {str(e)}")


@router.post("/strategy-comparison")
async def get_strategy_comparison(
    request: StrategyComparisonRequest,
    current_user: dict = Depends(get_current_active_user)
):
    """
    获取策略对比

    Args:
        request: 策略对比请求
        current_user: 当前用户（由依赖注入）

    Returns:
        策略对比数据
    """
    try:
        service = MediumLongTermReviewService(DATABASE)

        # 解析日期
        start_date = date.fromisoformat(request.start_date)
        end_date = date.fromisoformat(request.end_date)

        # 获取策略对比
        strategy_comparison = service.get_strategy_comparison(
            customer_id=request.customer_id,
            start_date=start_date,
            end_date=end_date
        )

        return strategy_comparison
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"获取策略对比失败: {str(e)}")


@router.get("/list")
async def list_reviews(
    customer_id: Optional[str] = Query(None, description="客户ID"),
    limit: int = Query(10, ge=1, le=100, description="返回数量限制"),
    current_user: dict = Depends(get_current_active_user)
):
    """
    列出复盘报告

    Args:
        customer_id: 客户ID（可选）
        limit: 返回数量限制
        current_user: 当前用户（由依赖注入）

    Returns:
        复盘报告列表
    """
    try:
        collection = DATABASE["medium_long_term_reviews"]

        query = {"status": "active"}
        if customer_id:
            query["customer_id"] = customer_id

        reviews = list(
            collection.find(query)
            .sort("generated_at", -1)
            .limit(limit)
        )

        return {
            "total": len(reviews),
            "reviews": [
                {
                    "review_id": r.get("review_id"),
                    "customer_id": r.get("customer_id"),
                    "customer_name": r.get("customer_name"),
                    "review_period": r.get("review_period"),
                    "cost_metrics": r.get("cost_metrics"),
                    "generated_at": r.get("generated_at")
                }
                for r in reviews
            ]
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"列出复盘报告失败: {str(e)}")
