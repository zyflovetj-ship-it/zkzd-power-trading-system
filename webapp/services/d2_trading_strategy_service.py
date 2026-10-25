"""
D-2 交易策略服务层
"""

import logging
from datetime import datetime, date
from typing import Any, Dict, List, Optional

from pymongo.database import Database

logger = logging.getLogger(__name__)


class D2TradingStrategyService:
    """D-2 交易策略服务"""

    def __init__(self, db: Database):
        self.db = db

    def generate_d2_strategy(
        self,
        customer_id: str,
        target_date: date,
        compare_with: List[str] = None
    ) -> Dict[str, Any]:
        """
        生成 D-2 交易策略

        Args:
            customer_id: 客户ID
            target_date: 目标日期
            compare_with: 对比基准列表

        Returns:
            D-2 交易策略数据
        """
        collection = self.db["d2_trading_strategies"]

        # 查找匹配的策略
        strategy = collection.find_one({
            "customer_id": customer_id,
            "target_date": datetime.combine(target_date, datetime.min.time()),
            "status": "active"
        }, sort=[("created_at", -1)])

        if not strategy:
            raise ValueError(f"未找到客户 {customer_id} 在 {target_date.isoformat()} 的 D-2 交易策略")

        return self._format_strategy_response(strategy)

    def get_d2_strategy(
        self,
        strategy_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取 D-2 交易策略详情

        Args:
            strategy_id: 策略ID

        Returns:
            D-2 交易策略数据，如果不存在则返回 None
        """
        collection = self.db["d2_trading_strategies"]
        strategy = collection.find_one({"strategy_id": strategy_id})

        if not strategy:
            return None

        return self._format_strategy_response(strategy)

    def get_risk_alerts(
        self,
        target_date: date,
        customer_id: str
    ) -> List[Dict[str, Any]]:
        """
        获取风险预警

        Args:
            target_date: 目标日期
            customer_id: 客户ID

        Returns:
            风险预警列表
        """
        strategy = self.generate_d2_strategy(customer_id, target_date)
        return strategy.get("risk_alerts", [])

    def get_backtesting_results(
        self,
        customer_id: str,
        period_days: int = 30
    ) -> Dict[str, Any]:
        """
        获取回测结果

        Args:
            customer_id: 客户ID
            period_days: 回测周期天数

        Returns:
            回测结果数据
        """
        collection = self.db["d2_trading_strategies"]

        # 获取最近的策略
        strategy = collection.find_one({
            "customer_id": customer_id,
            "status": "active"
        }, sort=[("target_date", -1)])

        if not strategy:
            raise ValueError(f"未找到客户 {customer_id} 的 D-2 交易策略")

        # 返回回测数据
        return strategy.get("backtesting", {})

    def _format_strategy_response(self, strategy: Dict[str, Any]) -> Dict[str, Any]:
        """格式化 D-2 交易策略响应"""
        return {
            "strategy_id": strategy["strategy_id"],
            "customer_id": strategy["customer_id"],
            "customer_name": strategy["customer_name"],
            "target_date": strategy["target_date"],
            "d2_forecast": strategy["d2_forecast"],
            "current_contract": strategy["current_contract"],
            "load_forecast": strategy["load_forecast"],
            "strategy_recommendations": strategy["strategy_recommendations"],
            "risk_alerts": strategy.get("risk_alerts", []),
            "backtesting": strategy.get("backtesting", {}),
            "created_at": strategy["created_at"],
            "status": strategy.get("status", "active")
        }

    def _ensure_indexes(self):
        """确保数据库索引存在"""
        collection = self.db["d2_trading_strategies"]
        collection.create_index([("customer_id", 1), ("target_date", 1)])
        collection.create_index([("strategy_id", 1)], unique=True)
        collection.create_index([("status", 1)])
