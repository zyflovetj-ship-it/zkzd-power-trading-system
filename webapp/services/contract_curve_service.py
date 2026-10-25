"""
合同曲线服务层
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pymongo.database import Database
from pymongo import ASCENDING

logger = logging.getLogger(__name__)


class ContractCurveService:
    """合同曲线服务"""

    def __init__(self, db: Database):
        self.db = db

    def generate_contract_curve(
        self,
        customer_id: str,
        target_year: int,
        target_month: int,
        optimization_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        生成合同曲线（调用优化算法）

        Args:
            customer_id: 客户ID
            target_year: 目标年份
            target_month: 目标月份
            optimization_params: 优化参数
                - objective: 优化目标 (cost_min, risk_min, balanced)
                - contract_coverage: 合同覆盖率 (0.5 - 1.0)
                - risk_aversion: 风险厌恶系数 (0-1)

        Returns:
            合同曲线数据
        """
        # 这里简化处理，实际应该调用优化算法
        # 暂时从数据库中查找已生成的合同曲线
        collection = self.db["contract_curves"]

        # 查找匹配的合同曲线
        curve = collection.find_one({
            "customer_id": customer_id,
            "contract_month.year": target_year,
            "contract_month.month": target_month,
            "optimization_params.objective": optimization_params.get("objective", "balanced"),
            "status": "active"
        }, sort=[("created_at", -1)])

        if not curve:
            raise ValueError(f"未找到客户 {customer_id} 在 {target_year}-{target_month:02d} 的合同曲线")

        return self._format_curve_response(curve)

    def get_contract_curve(
        self,
        curve_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取合同曲线详情

        Args:
            curve_id: 合同曲线ID

        Returns:
            合同曲线数据，如果不存在则返回 None
        """
        collection = self.db["contract_curves"]
        curve = collection.find_one({"curve_id": curve_id})

        if not curve:
            return None

        return self._format_curve_response(curve)

    def analyze_scenarios(
        self,
        curve_id: str,
        scenario_type: str = "price_sensitivity"
    ) -> Dict[str, Any]:
        """
        分析情景

        Args:
            curve_id: 合同曲线ID
            scenario_type: 情景类型 (price_sensitivity, load_sensitivity)

        Returns:
            情景分析数据
        """
        curve = self.get_contract_curve(curve_id)
        if not curve:
            raise ValueError(f"未找到合同曲线 {curve_id}")

        # 简化处理：直接返回计算好的情景数据
        if scenario_type == "price_sensitivity":
            return self._calculate_price_sensitivity(curve)
        elif scenario_type == "load_sensitivity":
            return self._calculate_load_sensitivity(curve)
        else:
            raise ValueError(f"不支持的情景类型: {scenario_type}")

    def get_customer_curves(
        self,
        customer_id: str,
        target_year: int,
        target_month: int
    ) -> List[Dict[str, Any]]:
        """
        获取客户的所有合同曲线（不同优化目标）

        Args:
            customer_id: 客户ID
            target_year: 目标年份
            target_month: 目标月份

        Returns:
            合同曲线列表
        """
        collection = self.db["contract_curves"]

        curves = list(collection.find({
            "customer_id": customer_id,
            "contract_month.year": target_year,
            "contract_month.month": target_month,
            "status": "active"
        }).sort("created_at", -1))

        return [
            {
                "curve_id": c["curve_id"],
                "customer_id": c["customer_id"],
                "customer_name": c["customer_name"],
                "contract_month": c["contract_month"],
                "optimization_params": c["optimization_params"],
                "summary": c["summary"],
                "created_at": c["created_at"]
            }
            for c in curves
        ]

    def _format_curve_response(self, curve: Dict[str, Any]) -> Dict[str, Any]:
        """格式化合同曲线响应"""
        return {
            "curve_id": curve["curve_id"],
            "customer_id": curve["customer_id"],
            "customer_name": curve["customer_name"],
            "contract_month": curve["contract_month"],
            "optimization_params": curve["optimization_params"],
            "daily_contracts": curve["daily_contracts"],
            "summary": curve["summary"],
            "created_at": curve["created_at"],
            "status": curve.get("status", "active")
        }

    def _calculate_price_sensitivity(self, curve: Dict[str, Any]) -> Dict[str, Any]:
        """计算价格敏感度"""
        base_cost = curve["summary"]["total_cost"]
        spot_cost = curve["summary"]["spot_cost"]

        price_sensitivity = []
        for deviation in [-0.2, -0.1, 0.0, 0.1, 0.2]:
            cost_change = deviation * spot_cost
            price_sensitivity.append({
                "price_deviation": deviation,
                "total_cost": round(base_cost + cost_change, 2),
                "cost_change": round(cost_change, 2)
            })

        return {"scenario_type": "price_sensitivity", "data": price_sensitivity}

    def _calculate_load_sensitivity(self, curve: Dict[str, Any]) -> Dict[str, Any]:
        """计算负荷敏感度"""
        base_cost = curve["summary"]["total_cost"]
        total_demand = curve["summary"]["total_demand"]
        blended_cost = curve["summary"]["blended_cost"]

        load_sensitivity = []
        for deviation, name in [(-0.15, "低负荷情景"), (0.0, "基准情景"), (0.15, "高负荷情景")]:
            load_change = total_demand * deviation
            cost_change = load_change * blended_cost
            load_sensitivity.append({
                "load_deviation": deviation,
                "scenario_name": name,
                "total_cost": round(base_cost + cost_change, 2),
                "cost_change": round(cost_change, 2)
            })

        return {"scenario_type": "load_sensitivity", "data": load_sensitivity}
