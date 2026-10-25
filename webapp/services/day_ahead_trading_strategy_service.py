"""
日前交易策略服务层
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, Optional

from pymongo.database import Database

logger = logging.getLogger(__name__)


class DayAheadTradingStrategyService:
    """日前交易策略服务"""

    def __init__(self, db: Database):
        self.db = db

    def generate_day_ahead_plan(
        self,
        customer_id: str,
        target_date: date,
        strategy_type: str = "balanced"
    ) -> Dict[str, Any]:
        """
        生成日前交易方案

        Args:
            customer_id: 客户ID
            target_date: 目标日期
            strategy_type: 策略类型 (conservative, balanced, aggressive)

        Returns:
            日前交易方案数据
        """
        collection = self.db["day_ahead_trading_plans"]

        # 将 date 转换为 datetime 以便 MongoDB 查询
        target_datetime = datetime.combine(target_date, datetime.min.time())

        # 查找匹配的方案
        plan = collection.find_one({
            "customer_id": customer_id,
            "target_date": target_datetime,
            "status": "active"
        }, sort=[("created_at", -1)])

        if not plan:
            raise ValueError(f"未找到客户 {customer_id} 在 {target_date.isoformat()} 的日前交易方案")

        return self._format_plan_response(plan)

    def get_day_ahead_plan(
        self,
        plan_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取日前交易方案详情

        Args:
            plan_id: 方案ID

        Returns:
            日前交易方案数据
        """
        collection = self.db["day_ahead_trading_plans"]
        plan = collection.find_one({"plan_id": plan_id})

        if not plan:
            return None

        return self._format_plan_response(plan)

    def get_priority_recommendations(
        self,
        customer_id: str,
        target_date: date
    ) -> list:
        """
        获取高优先级交易建议

        Args:
            customer_id: 客户ID
            target_date: 目标日期

        Returns:
            高优先级建议列表
        """
        plan = self.generate_day_ahead_plan(customer_id, target_date)
        return plan.get("priority_recommendations", [])

    def _format_plan_response(self, plan: Dict[str, Any]) -> Dict[str, Any]:
        """格式化日前交易方案响应"""
        return {
            "plan_id": plan.get("plan_id", plan.get("strategy_id", "")),
            "customer_id": plan["customer_id"],
            "customer_name": plan["customer_name"],
            "target_date": plan["target_date"],
            "plan_config": plan.get("plan_config", {}),
            "d1_forecast": plan["d2_forecast"],  # 复用d2_forecast
            "load_forecast": plan["load_forecast"],
            "hourly_trading_plan": plan.get("hourly_trading_plan", []),
            "strategy_recommendations": plan["strategy_recommendations"],
            "priority_recommendations": plan.get("priority_recommendations", []),
            "risk_alerts": plan.get("risk_alerts", []),
            "created_at": plan["created_at"],
            "status": plan.get("status", "active")
        }

    def _ensure_indexes(self):
        """确保数据库索引存在"""
        collection = self.db["day_ahead_trading_plans"]
        collection.create_index([("customer_id", 1), ("target_date", 1)])
        collection.create_index([("plan_id", 1)], unique=True)
        collection.create_index([("status", 1)])
