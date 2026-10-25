"""
月度交易策略服务层
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo.database import Database
from pymongo import ASCENDING

logger = logging.getLogger(__name__)


class MonthlyTradingStrategyService:
    """月度交易策略服务"""

    def __init__(self, db: Database):
        self.db = db

    def generate_strategy(
        self,
        customer_id: str,
        target_year: int,
        target_month: int,
        strategy_config: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成月度交易策略

        Args:
            customer_id: 客户ID
            target_year: 目标年份
            target_month: 目标月份
            strategy_config: 策略配置
                - annual_contract_ratio: 年度双边比例
                - monthly_bid_ratio: 月度竞价比例
                - spot_ratio: 现货比例
                - optimization_objective: 优化目标 (cost, risk, balanced)

        Returns:
            交易策略数据
        """
        collection = self.db["monthly_trading_strategies"]

        # 确定优化目标
        objective = strategy_config.get("optimization_objective", "balanced")

        # 查找匹配的策略
        strategy = collection.find_one({
            "customer_id": customer_id,
            "target_month.year": target_year,
            "target_month.month": target_month,
            "strategy_config.optimization_objective": objective,
            "status": "active"
        }, sort=[("created_at", -1)])

        if not strategy:
            raise ValueError(f"未找到客户 {customer_id} 在 {target_year}-{target_month:02d} 的交易策略")

        return self._format_strategy_response(strategy)

    def get_strategy(
        self,
        strategy_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取交易策略详情

        Args:
            strategy_id: 策略ID

        Returns:
            交易策略数据，如果不存在则返回 None
        """
        collection = self.db["monthly_trading_strategies"]
        strategy = collection.find_one({"strategy_id": strategy_id})

        if not strategy:
            return None

        return self._format_strategy_response(strategy)

    def analyze_scenarios(
        self,
        strategy_id: str
    ) -> Dict[str, Any]:
        """
        获取情景分析

        Args:
            strategy_id: 策略ID

        Returns:
            情景分析数据
        """
        strategy = self.get_strategy(strategy_id)
        if not strategy:
            raise ValueError(f"未找到交易策略 {strategy_id}")

        # 返回情景分析数据
        return strategy.get("scenario_analysis", {})

    def get_price_trend(
        self,
        target_year: int,
        target_month: int,
        forecast_type: str = "monthly_price"
    ) -> Dict[str, Any]:
        """
        获取价格走势数据

        Args:
            target_year: 目标年份
            target_month: 目标月份
            forecast_type: 预测类型（默认 monthly_price）

        Returns:
            价格走势数据
        """
        collection = self.db["monthly_price_trends"]

        price_trend = collection.find_one({
            "target_month.year": target_year,
            "target_month.month": target_month
        })

        if not price_trend:
            raise ValueError(f"未找到 {target_year}-{target_month:02d} 的价格走势数据")

        return {
            "target_month": price_trend["target_month"],
            "daily_prices": price_trend["daily_prices"],
            "price_distribution": price_trend["price_distribution"]
        }

    def get_customer_strategies(
        self,
        customer_id: str,
        target_year: int,
        target_month: int
    ) -> List[Dict[str, Any]]:
        """
        获取客户的所有交易策略（不同优化目标）

        Args:
            customer_id: 客户ID
            target_year: 目标年份
            target_month: 目标月份

        Returns:
            交易策略列表
        """
        collection = self.db["monthly_trading_strategies"]

        strategies = list(collection.find({
            "customer_id": customer_id,
            "target_month.year": target_year,
            "target_month.month": target_month,
            "status": "active"
        }).sort("created_at", -1))

        return [
            {
                "strategy_id": s["strategy_id"],
                "customer_id": s["customer_id"],
                "customer_name": s["customer_name"],
                "target_month": s["target_month"],
                "strategy_config": s["strategy_config"],
                "optimization_results": s["optimization_results"],
                "created_at": s["created_at"]
            }
            for s in strategies
        ]

    def _format_strategy_response(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """格式化交易策略响应"""
        return {
            "strategy_id": strategy["strategy_id"],
            "customer_id": strategy["customer_id"],
            "customer_name": strategy["customer_name"],
            "target_month": strategy["target_month"],
            "strategy_config": strategy["strategy_config"],
            "optimization_results": strategy["optimization_results"],
            "timing_recommendations": strategy.get("timing_recommendations", []),
            "scenario_analysis": strategy.get("scenario_analysis", {}),
            "created_at": strategy["created_at"],
            "status": strategy.get("status", "active")
        }

    def _ensure_indexes(self):
        """确保数据库索引存在"""
        collection = self.db["monthly_trading_strategies"]
        collection.create_index([("customer_id", 1), ("target_month.year", 1), ("target_month.month", 1)])
        collection.create_index([("strategy_id", 1)], unique=True)
        collection.create_index([("status", 1)])

        price_trend_collection = self.db["monthly_price_trends"]
        price_trend_collection.create_index([("target_month.year", 1), ("target_month.month", 1)], unique=True)
