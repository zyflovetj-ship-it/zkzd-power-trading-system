"""
中长期交易复盘服务层
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional

from pymongo.database import Database

logger = logging.getLogger(__name__)


class MediumLongTermReviewService:
    """中长期交易复盘服务"""

    def __init__(self, db: Database):
        self.db = db

    def generate_review(
        self,
        customer_id: str,
        start_date: date,
        end_date: date,
        compare_baselines: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        生成中长期交易复盘报告

        Args:
            customer_id: 客户ID
            start_date: 开始日期
            end_date: 结束日期
            compare_baselines: 对比基准列表 (pure_spot, fixed_price, market_avg)

        Returns:
            复盘报告数据
        """
        collection = self.db["medium_long_term_reviews"]

        # 将 date 转换为 datetime 以便 MongoDB 查询
        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.min.time())

        # 查找匹配的复盘报告
        review = collection.find_one({
            "customer_id": customer_id,
            "review_period.start_date": start_datetime,
            "review_period.end_date": end_datetime,
            "status": "active"
        }, sort=[("generated_at", -1)])

        if not review:
            raise ValueError(
                f"未找到客户 {customer_id} 在 {start_date.isoformat()} 至 {end_date.isoformat()} 的复盘报告"
            )

        return self._format_review_response(review)

    def get_execution_data(
        self,
        customer_id: str,
        start_date: date,
        end_date: date,
        granularity: str = "day"
    ) -> Dict[str, Any]:
        """
        获取合同执行数据（计划 vs 实际）

        Args:
            customer_id: 客户ID
            start_date: 开始日期
            end_date: 结束日期
            granularity: 粒度 (day, week, month)

        Returns:
            合同执行详细数据
        """
        transactions_collection = self.db["medium_long_term_transactions"]
        reviews_collection = self.db["medium_long_term_reviews"]

        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.min.time())

        # 获取复盘报告
        review = reviews_collection.find_one({
            "customer_id": customer_id,
            "review_period.start_date": start_datetime,
            "review_period.end_date": end_datetime,
            "status": "active"
        })

        if not review:
            raise ValueError(
                f"未找到客户 {customer_id} 在 {start_date.isoformat()} 至 {end_date.isoformat()} 的复盘报告"
            )

        # 获取交易记录
        transactions = list(transactions_collection.find({
            "customer_id": customer_id,
            "effective_date": {"$gte": start_datetime, "$lte": end_datetime},
            "is_active": True
        }).sort("effective_date", 1))

        return {
            "customer_id": customer_id,
            "period": {
                "start_date": start_datetime,
                "end_date": end_datetime,
                "granularity": granularity
            },
            "execution_metrics": review.get("execution_metrics", {}),
            "transactions": [
                {
                    "transaction_id": t.get("transaction_id"),
                    "transaction_type": t.get("transaction_type"),
                    "transaction_date": t.get("transaction_date"),
                    "effective_date": t.get("effective_date"),
                    "amount": t.get("amount"),
                    "price": t.get("price"),
                    "total_value": t.get("total_value"),
                    "price_advantage": t.get("price_advantage"),
                    "current_price_advantage": t.get("current_price_advantage"),
                    "actual_usage": t.get("actual_usage"),
                    "remaining_amount": t.get("remaining_amount")
                }
                for t in transactions
            ]
        }

    def get_cost_benefit(
        self,
        customer_id: str,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        获取成本效益分析

        Args:
            customer_id: 客户ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            成本效益分析数据
        """
        collection = self.db["medium_long_term_reviews"]

        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.min.time())

        review = collection.find_one({
            "customer_id": customer_id,
            "review_period.start_date": start_datetime,
            "review_period.end_date": end_datetime,
            "status": "active"
        })

        if not review:
            raise ValueError(
                f"未找到客户 {customer_id} 在 {start_date.isoformat()} 至 {end_date.isoformat()} 的复盘报告"
            )

        cost_metrics = review.get("cost_metrics", {})
        strategy_comparison = review.get("strategy_comparison", [])

        # 构建累计节省曲线数据
        cumulative_savings = self._generate_cumulative_savings_data(
            start_date, end_date, cost_metrics, strategy_comparison
        )

        return {
            "customer_id": customer_id,
            "period": {
                "start_date": start_datetime,
                "end_date": end_datetime
            },
            "cost_metrics": cost_metrics,
            "strategy_comparison": strategy_comparison,
            "cumulative_savings": cumulative_savings
        }

    def get_timing_analysis(
        self,
        customer_id: str,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        获取时机分析

        Args:
            customer_id: 客户ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            时机分析数据
        """
        transactions_collection = self.db["medium_long_term_transactions"]
        reviews_collection = self.db["medium_long_term_reviews"]

        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.min.time())

        # 获取复盘报告
        review = reviews_collection.find_one({
            "customer_id": customer_id,
            "review_period.start_date": start_datetime,
            "review_period.end_date": end_datetime,
            "status": "active"
        })

        if not review:
            raise ValueError(
                f"未找到客户 {customer_id} 在 {start_date.isoformat()} 至 {end_date.isoformat()} 的复盘报告"
            )

        # 获取交易记录（签订时机）
        transactions = list(transactions_collection.find({
            "customer_id": customer_id,
            "transaction_date": {
                "$gte": start_datetime - timedelta(days=365),
                "$lte": end_datetime
            },
            "is_active": True
        }).sort("transaction_date", 1))

        timing_analysis = review.get("timing_analysis", {})

        # 构建签订时机回顾表
        signing_timing_table = [
            {
                "contract_type": t.get("transaction_type"),
                "signing_date": t.get("transaction_date"),
                "effective_date": t.get("effective_date"),
                "days_before": (t.get("effective_date") - t.get("transaction_date")).days
                if t.get("effective_date") and t.get("transaction_date") else 0,
                "signing_price": t.get("price"),
                "market_price_at_signing": t.get("market_price_at_signing"),
                "price_advantage_at_signing": t.get("price_advantage"),
                "current_price_advantage": t.get("current_price_advantage")
            }
            for t in transactions
        ]

        return {
            "customer_id": customer_id,
            "period": {
                "start_date": start_datetime,
                "end_date": end_datetime
            },
            "timing_analysis": timing_analysis,
            "signing_timing_table": signing_timing_table
        }

    def get_strategy_comparison(
        self,
        customer_id: str,
        start_date: date,
        end_date: date
    ) -> Dict[str, Any]:
        """
        获取策略对比

        Args:
            customer_id: 客户ID
            start_date: 开始日期
            end_date: 结束日期

        Returns:
            策略对比数据
        """
        collection = self.db["medium_long_term_reviews"]

        start_datetime = datetime.combine(start_date, datetime.min.time())
        end_datetime = datetime.combine(end_date, datetime.min.time())

        review = collection.find_one({
            "customer_id": customer_id,
            "review_period.start_date": start_datetime,
            "review_period.end_date": end_datetime,
            "status": "active"
        })

        if not review:
            raise ValueError(
                f"未找到客户 {customer_id} 在 {start_date.isoformat()} 至 {end_date.isoformat()} 的复盘报告"
            )

        strategy_comparison = review.get("strategy_comparison", [])
        summary = review.get("summary", {})

        return {
            "customer_id": customer_id,
            "period": {
                "start_date": start_datetime,
                "end_date": end_datetime
            },
            "strategy_comparison": strategy_comparison,
            "recommendations": summary.get("recommendations", [])
        }

    def _format_review_response(self, review: Dict[str, Any]) -> Dict[str, Any]:
        """格式化复盘报告响应"""
        return {
            "review_id": review.get("review_id"),
            "customer_id": review.get("customer_id"),
            "customer_name": review.get("customer_name"),
            "review_period": review.get("review_period"),
            "execution_metrics": review.get("execution_metrics"),
            "cost_metrics": review.get("cost_metrics"),
            "timing_analysis": review.get("timing_analysis"),
            "strategy_comparison": review.get("strategy_comparison"),
            "anomalies": review.get("anomalies"),
            "summary": review.get("summary"),
            "generated_at": review.get("generated_at"),
            "status": review.get("status")
        }

    def _generate_cumulative_savings_data(
        self,
        start_date: date,
        end_date: date,
        cost_metrics: Dict[str, Any],
        strategy_comparison: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """生成累计节省曲线数据"""
        total_days = (end_date - start_date).days + 1
        dates = [start_date + timedelta(days=i) for i in range(total_days)]

        # 从策略对比中提取基准成本
        pure_spot_cost = 0
        fixed_price_cost = 0

        for strategy in strategy_comparison:
            if strategy.get("strategy") == "pure_spot":
                pure_spot_cost = strategy.get("total_cost", 0)
            elif strategy.get("strategy") == "full_contract":
                fixed_price_cost = strategy.get("total_cost", 0)

        actual_cost = cost_metrics.get("total_cost", 0)

        # 按天分配成本
        daily_actual = actual_cost / total_days
        daily_spot = pure_spot_cost / total_days
        daily_fixed = fixed_price_cost / total_days

        cumulative_vs_spot = []
        cumulative_vs_fixed = []
        cumulative_savings = 0

        for i, d in enumerate(dates):
            day_savings_vs_spot = (daily_spot - daily_actual) * (i + 1)
            day_savings_vs_fixed = (daily_fixed - daily_actual) * (i + 1)
            cumulative_savings = day_savings_vs_spot

            cumulative_vs_spot.append({
                "date": d.isoformat(),
                "cumulative_savings": round(day_savings_vs_spot, 2)
            })
            cumulative_vs_fixed.append({
                "date": d.isoformat(),
                "cumulative_savings": round(day_savings_vs_fixed, 2)
            })

        return {
            "vs_pure_spot": cumulative_vs_spot,
            "vs_fixed_price": cumulative_vs_fixed,
            "total_savings": round(cumulative_savings, 2)
        }

    def _ensure_indexes(self):
        """确保数据库索引存在"""
        transactions_collection = self.db["medium_long_term_transactions"]
        reviews_collection = self.db["medium_long_term_reviews"]

        transactions_collection.create_index([("customer_id", 1), ("effective_date", 1)])
        transactions_collection.create_index([("transaction_id", 1)], unique=True)
        transactions_collection.create_index([("transaction_type", 1)])

        reviews_collection.create_index([("customer_id", 1), ("review_period.start_date", 1)])
        reviews_collection.create_index([("review_id", 1)], unique=True)
        reviews_collection.create_index([("status", 1)])
