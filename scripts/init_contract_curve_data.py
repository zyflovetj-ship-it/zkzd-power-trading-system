"""
生成合同曲线模拟数据
为指定客户和月份生成优化的合同曲线，包括合同电量分配和情景分析
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random
from pymongo import ASCENDING, DESCENDING
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from webapp.tools.mongo import DATABASE

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置参数
START_MONTH = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=90)
END_MONTH = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) + timedelta(days=120)


def get_days_in_month(year: int, month: int) -> int:
    """获取指定月份的天数"""
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    this_month = datetime(year, month, 1)
    return (next_month - this_month).days


def generate_contract_curve(
    customer_id: str,
    customer_name: str,
    target_year: int,
    target_month: int,
    objective: str = "balanced",
    contract_coverage: float = 0.85
) -> Dict[str, Any]:
    """生成优化的合同曲线"""

    curve_id = f"CONTRACT_{target_year}{target_month:02d}_{customer_id}_{objective}_{random.randint(1, 3)}_v{random.randint(1, 2)}"

    # 获取目标月份的天数
    days_in_month = get_days_in_month(target_year, target_month)

    # 季节因子
    if target_month in [1, 2, 12]:
        seasonal_factor = 1.15
        base_price = 400
    elif target_month in [6, 7, 8]:
        seasonal_factor = 1.10
        base_price = 380
    else:
        seasonal_factor = 1.0
        base_price = 365

    # 生成每日数据
    daily_contracts = []
    total_contract_amount = 0
    total_spot_amount = 0

    for day in range(1, days_in_month + 1):
        date = datetime(target_year, target_month, day)
        weekday = date.weekday()

        # 周末因子
        weekend_factor = 0.9 if weekday >= 5 else 1.0

        # 小时负荷分布（简化）
        hour = 12  # 中午
        if 0 <= hour < 6:
            hour_factor = 0.6
        elif 6 <= hour < 8:
            hour_factor = 0.8
        elif 8 <= hour < 12:
            hour_factor = 1.2
        elif 12 <= hour < 16:
            hour_factor = 1.0
        elif 16 <= hour < 18:
            hour_factor = 1.1
        elif 18 <= hour < 21:
            hour_factor = 1.3
        else:
            hour_factor = 0.8

        # 预测负荷（MWh）
        base_load = 1000 * seasonal_factor * hour_factor * weekend_factor
        predicted_load = base_load * random.uniform(0.95, 1.05)

        # 合同价格（固定）
        contract_price = base_price * random.uniform(0.98, 1.02)

        # 预测现货价格（带波动）
        spot_price_base = base_price * random.uniform(0.85, 1.20)

        # 根据优化目标调整合同量
        if objective == "cost_min":
            # 成本最小化：高覆盖率
            actual_coverage = contract_coverage * random.uniform(0.95, 1.05)
        elif objective == "risk_min":
            # 风险最小化：更高覆盖率
            actual_coverage = min(0.98, contract_coverage * 1.05)
        else:  # balanced
            actual_coverage = contract_coverage

        # 计算合同电量和现货电量
        contract_amount = predicted_load * actual_coverage
        spot_amount = predicted_load - contract_amount

        # 记录
        total_contract_amount += contract_amount
        total_spot_amount += spot_amount

        # 成本计算
        contract_cost = contract_amount * contract_price
        spot_cost = spot_amount * spot_price_base
        total_cost = contract_cost + spot_cost

        daily_contracts.append({
            "date": date.strftime("%Y-%m-%d"),
            "predicted_load": round(predicted_load, 2),
            "contract_amount": round(contract_amount, 2),
            "spot_amount": round(spot_amount, 2),
            "contract_price": round(contract_price, 2),
            "predicted_spot_price": round(spot_price_base, 2),
            "contract_cost": round(contract_cost, 2),
            "predicted_spot_cost": round(spot_cost, 2),
            "total_cost": round(total_cost, 2)
        })

    # 计算汇总指标
    avg_contract_price = sum(d["contract_price"] for d in daily_contracts) / len(daily_contracts)
    total_cost = sum(d["total_cost"] for d in daily_contracts)
    contract_cost = sum(d["contract_cost"] for d in daily_contracts)
    spot_cost = sum(d["predicted_spot_cost"] for d in daily_contracts)
    blended_cost = total_cost / (total_contract_amount + total_spot_amount)

    # 计算基准对比
    # 纯现货（假设覆盖率0%）
    pure_spot_cost = sum(d["predicted_load"] * d["predicted_spot_price"] for d in daily_contracts)

    # 等额合同（假设100%合同覆盖，合同价格取平均）
    equal_contract_cost = sum(d["predicted_load"] * avg_contract_price for d in daily_contracts)

    # 风险指标（简化计算）
    price_variance = sum((d["predicted_spot_price"] - avg_contract_price) ** 2 for d in daily_contracts) / len(daily_contracts)
    value_at_risk_95 = abs(total_cost - pure_spot_cost) * 0.05  # 简化VaR
    sharpe_ratio = (pure_spot_cost - total_cost) / (price_variance ** 0.5) if price_variance > 0 else 0

    return {
        "curve_id": curve_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "contract_month": {
            "year": target_year,
            "month": target_month
        },
        "optimization_params": {
            "objective": objective,
            "contract_coverage": contract_coverage,
            "risk_aversion": 0.5 if objective == "balanced" else (0.2 if objective == "cost_min" else 0.8)
        },
        "daily_contracts": daily_contracts,
        "summary": {
            "total_contract_amount": round(total_contract_amount, 2),
            "total_spot_amount": round(total_spot_amount, 2),
            "total_demand": round(total_contract_amount + total_spot_amount, 2),
            "contract_coverage": round(total_contract_amount / (total_contract_amount + total_spot_amount), 3),
            "avg_contract_price": round(avg_contract_price, 2),
            "total_cost": round(total_cost, 2),
            "contract_cost": round(contract_cost, 2),
            "spot_cost": round(spot_cost, 2),
            "blended_cost": round(blended_cost, 2),
            "price_variance": round(price_variance, 2),
            "value_at_risk_95": round(value_at_risk_95, 2),
            "sharpe_ratio": round(sharpe_ratio, 3),
            "vs_pure_spot": {
                "cost_difference": round(pure_spot_cost - total_cost, 2),
                "cost_percentage": round(((pure_spot_cost - total_cost) / pure_spot_cost) * 100, 2)
            },
            "vs_equal_contract": {
                "cost_difference": round(equal_contract_cost - total_cost, 2),
                "cost_percentage": round(((equal_contract_cost - total_cost) / equal_contract_cost) * 100, 2)
            }
        },
        "created_by": "system",
        "created_at": datetime.now(),
        "status": "active",
        "version": 1
    }


def generate_scenarios(curve_data: Dict[str, Any]) -> Dict[str, Any]:
    """生成情景分析数据"""

    base_cost = curve_data["summary"]["total_cost"]

    # 价格敏感度分析
    price_sensitivity = []
    for deviation in [-0.2, -0.1, 0.0, 0.1, 0.2]:
        # 简化计算：价格偏差 × 现货采购量
        cost_change = deviation * curve_data["summary"]["spot_cost"]
        price_sensitivity.append({
            "price_deviation": deviation,
            "total_cost": round(base_cost + cost_change, 2),
            "cost_change": round(cost_change, 2)
        })

    # 负荷敏感度分析
    load_sensitivity = []
    total_demand = curve_data["summary"]["total_demand"]
    blended_cost = curve_data["summary"]["blended_cost"]

    for deviation in [-0.15, 0.0, 0.15]:
        load_change = total_demand * deviation
        cost_change = load_change * blended_cost
        load_sensitivity.append({
            "load_deviation": deviation,
            "scenario_name": "低负荷情景" if deviation < 0 else ("基准情景" if deviation == 0 else "高负荷情景"),
            "total_cost": round(base_cost + cost_change, 2),
            "cost_change": round(cost_change, 2)
        })

    return {
        "price_sensitivity": price_sensitivity,
        "load_sensitivity": load_sensitivity
    }


def init_contract_curve_data():
    """初始化合同曲线数据"""
    logger.info(f"开始生成合同曲线数据：{START_MONTH.strftime('%Y-%m')} 到 {END_MONTH.strftime('%Y-%m')}")

    # 清空现有数据
    logger.info("清空现有合同曲线数据...")
    DATABASE["contract_curves"].delete_many({})
    logger.info("数据清空完成")

    # 模拟客户列表
    customers = [
        {"customer_id": "CUST001", "customer_name": "某某制造企业"},
        {"customer_id": "CUST002", "customer_name": "某某商业综合体"},
        {"customer_id": "CUST003", "customer_name": "某某工业园区"},
    ]

    total_curves = 0
    current_month = START_MONTH

    # 生成合同曲线
    logger.info("\n[1/2] 生成合同曲线数据...")
    while current_month <= END_MONTH:
        target_year = current_month.year
        target_month = current_month.month

        for customer in customers:
            # 为每个客户生成3种优化目标的合同曲线
            for objective in ["cost_min", "balanced", "risk_min"]:
                # 随机选择覆盖率
                coverage = random.choice([0.75, 0.85, 0.90, 0.95])

                try:
                    curve_data = generate_contract_curve(
                        customer["customer_id"],
                        customer["customer_name"],
                        target_year,
                        target_month,
                        objective,
                        coverage
                    )

                    DATABASE["contract_curves"].insert_one(curve_data)
                    total_curves += 1

                    logger.info(
                        f"  客户: {customer['customer_name']}, "
                        f"月份: {target_year}-{target_month:02d}, "
                        f"目标: {objective}, "
                        f"覆盖率: {coverage:.0%}"
                    )
                except Exception as e:
                    logger.error(f"生成合同曲线失败: {e}", exc_info=True)

        current_month = (current_month.replace(day=1) + timedelta(days=32)).replace(day=1)

    logger.info(f"  合同曲线数据生成完成: {total_curves} 条")

    # 最终统计
    logger.info("\n" + "=" * 60)
    logger.info("合同曲线数据生成完成！")
    logger.info("=" * 60)
    logger.info("\n数据统计:")
    logger.info(f"  - contract_curves: {DATABASE['contract_curves'].count_documents({})} 条")


if __name__ == "__main__":
    init_contract_curve_data()
