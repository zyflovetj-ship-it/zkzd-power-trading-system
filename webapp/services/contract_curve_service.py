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
        # 真实分解：合约电量 → 月 → 日 → 96 点（口径见 ContractDecomposeService）
        from webapp.services.contract_decompose_service import ContractDecomposeService

        curve = ContractDecomposeService(self.db).decompose(
            customer_id=customer_id,
            year=target_year,
            month=target_month,
            params=optimization_params or {},
        )
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
        elif scenario_type == "coverage_sensitivity":
            return self._calculate_coverage_sensitivity(curve)
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

    @staticmethod
    def _base(curve: Dict[str, Any]) -> Dict[str, float]:
        """取基准量：合约电量 / 需求 / 敞口 / 现货均价 / 合约均价。"""
        sm = curve.get("summary") or {}
        pos = float(sm.get("total_volume_mwh") or 0)
        demand = float(sm.get("total_demand") or 0)
        spot = float(sm.get("spot_avg_price") or 0)
        blended = float(sm.get("blended_cost") or 0)
        gap = float(sm.get("gap_energy_mwh"))
        if gap is None or gap == 0:
            gap = demand - pos
        contract_cost = pos * blended
        spot_cost = gap * spot
        return {"pos": pos, "demand": demand, "gap": gap, "spot": spot,
                "blended": blended, "contract_cost": contract_cost,
                "base_cost": contract_cost + spot_cost}

    def _calculate_price_sensitivity(self, curve: Dict[str, Any]) -> Dict[str, Any]:
        """现货价格敏感性：仅敞口部分随现货价变动重算。"""
        b = self._base(curve)
        out = []
        for dev in (-0.3, -0.2, -0.1, 0.0, 0.1, 0.2, 0.3):
            new_spot = b["spot"] * (1 + dev)
            spot_cost = b["gap"] * new_spot
            total = b["contract_cost"] + spot_cost
            out.append({
                "price_deviation": dev,
                "spot_price": round(new_spot, 2),
                "spot_cost": round(spot_cost, 2),
                "total_cost": round(total, 2),
                "cost_change": round(total - b["base_cost"], 2),
            })
        return {
            "scenario_type": "price_sensitivity",
            "base": {"spot_avg_price": round(b["spot"], 3), "gap_energy_mwh": round(b["gap"], 4),
                     "contract_cost": round(b["contract_cost"], 2),
                     "base_total_cost": round(b["base_cost"], 2)},
            "data": out,
        }

    def _calculate_load_sensitivity(self, curve: Dict[str, Any]) -> Dict[str, Any]:
        """负荷敏感性：负荷变动直接改变敞口电量，从而改变成本。"""
        b = self._base(curve)
        out = []
        for dev, name in ((-0.15, "低负荷"), (-0.10, "偏低负荷"), (0.0, "基准"),
                          (0.10, "偏高负荷"), (0.15, "高负荷")):
            new_demand = b["demand"] * (1 + dev)
            gap = new_demand - b["pos"]
            total = b["contract_cost"] + gap * b["spot"]
            out.append({
                "load_deviation": dev,
                "scenario_name": name,
                "total_demand": round(new_demand, 2),
                "gap_energy_mwh": round(gap, 2),
                "coverage_ratio": round(b["pos"] / new_demand, 4) if new_demand else None,
                "total_cost": round(total, 2),
                "cost_change": round(total - b["base_cost"], 2),
            })
        return {"scenario_type": "load_sensitivity",
                "base": {"total_demand": round(b["demand"], 2),
                         "position_mwh": round(b["pos"], 2),
                         "spot_avg_price": round(b["spot"], 3),
                         "blended_cost": round(b["blended"], 3)},
                "data": out}

    def _calculate_coverage_sensitivity(self, curve: Dict[str, Any]) -> Dict[str, Any]:
        """覆盖率敏感性：合约覆盖率 0%~120% 下的组合成本，并给出最低成本覆盖率。"""
        b = self._base(curve)
        demand = b["demand"]
        out = []
        best = None
        for cov in [0.0, 0.2, 0.4, 0.6, 0.8, 0.9, 1.0, 1.1, 1.2]:
            pos = demand * cov
            gap = demand - pos
            total = pos * b["blended"] + gap * b["spot"]
            row = {
                "coverage": cov,
                "position_mwh": round(pos, 2),
                "gap_energy_mwh": round(gap, 2),
                "total_cost": round(total, 2),
                "avg_price": round(total / demand, 3) if demand else None,
            }
            out.append(row)
            if best is None or row["total_cost"] < best["total_cost"]:
                best = row
        return {
            "scenario_type": "coverage_sensitivity",
            "base": {"total_demand": round(demand, 2),
                     "blended_cost": round(b["blended"], 3),
                     "spot_avg_price": round(b["spot"], 3)},
            "optimal": best,
            "data": out,
        }
