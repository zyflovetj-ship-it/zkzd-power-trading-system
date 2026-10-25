"""
D-2 交易策略数据生成脚本

生成 D-2 交易策略的模拟数据，用于前端展示和测试
"""

from datetime import datetime, timedelta, date
from typing import Any, Dict, List
import random
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from webapp.tools.mongo import DATABASE


def get_seasonal_factor(month: int) -> float:
    """获取季节因子"""
    if month in [1, 2, 12]:
        return 1.15
    elif month in [7, 8]:
        return 1.10
    elif month in [3, 4, 5]:
        return 0.95
    else:
        return 0.90


def generate_hourly_prices(base_price: float, volatility: float = 0.15) -> List[Dict[str, Any]]:
    """
    生成96点（15分钟间隔）的小时价格数据

    Args:
        base_price: 基础价格
        volatility: 波动率

    Returns:
        96个时间点的价格数据
    """
    hourly_prices = []

    # 定义时段模式（低谷、早峰、平段、晚峰）
    period_factors = {
        "valley": (0, 24, 0.7),   # 0:00-6:00 低谷
        "morning": (32, 48, 1.3),  # 8:00-12:00 早峰
        "noon": (48, 64, 1.0),     # 12:00-16:00 平段
        "evening": (72, 84, 1.5)   # 18:00-21:00 晚峰
    }

    for i in range(96):
        time_hour = i // 4
        time_minute = (i % 4) * 15
        time_str = f"{time_hour:02d}:{time_minute:02d}"

        # 确定当前时段
        period_factor = 1.0
        for period_name, (start_idx, end_idx, factor) in period_factors.items():
            if start_idx <= i < end_idx:
                period_factor = factor
                break

        # 随机波动
        random_factor = random.uniform(0.85, 1.15)

        # 偶尔出现负电价（低谷时段）
        if period_factor < 0.8 and random.random() < 0.05:
            predicted_price = -random.uniform(10, 50)
        else:
            predicted_price = base_price * period_factor * random_factor

        # 偶尔出现价格尖峰（晚峰时段）
        if period_factor > 1.3 and random.random() < 0.08:
            predicted_price *= 1.8

        confidence_lower = predicted_price * 0.9
        confidence_upper = predicted_price * 1.1

        hourly_prices.append({
            "time": time_str,
            "predicted_price": round(predicted_price, 2),
            "confidence_lower": round(confidence_lower, 2),
            "confidence_upper": round(confidence_upper, 2)
        })

    return hourly_prices


def generate_d2_strategy(
    customer_id: str,
    customer_name: str,
    target_date: date
) -> Dict[str, Any]:
    """
    生成 D-2 交易策略数据

    Args:
        customer_id: 客户ID
        customer_name: 客户名称
        target_date: 目标日期

    Returns:
        D-2 交易策略数据
    """
    season_factor = get_seasonal_factor(target_date.month)

    # 基础负荷和价格
    base_daily_load_map = {
        "CUST001": 3100.0,   # MWh/天
        "CUST002": 1100.0,
        "CUST003": 2500.0
    }
    base_daily_load = base_daily_load_map.get(customer_id, 2000.0) * season_factor
    base_price = 380.0 * season_factor

    # 合同价格（通常略低于市场均价）
    contract_price = base_price * 0.95

    # 当前合同量（覆盖约90%负荷）
    contract_amount = base_daily_load * 0.90

    # 生成96点价格数据
    hourly_prices = generate_hourly_prices(base_price)

    # 计算价格统计
    all_prices = [p["predicted_price"] for p in hourly_prices]
    avg_price = sum(all_prices) / len(all_prices)
    min_price = min(all_prices)
    max_price = max(all_prices)
    std_price = (sum((x - avg_price) ** 2 for x in all_prices) / len(all_prices)) ** 0.5

    # 生成负荷预测数据
    hourly_loads = []
    for i in range(96):
        time_hour = i // 4
        time_minute = (i % 4) * 15
        time_str = f"{time_hour:02d}:{time_minute:02d}"

        # 时段负荷因子
        if 0 <= time_hour < 6:
            load_factor = 0.6  # 低谷
        elif 8 <= time_hour < 12:
            load_factor = 1.2  # 早峰
        elif 12 <= time_hour < 16:
            load_factor = 1.0  # 平段
        elif 18 <= time_hour < 21:
            load_factor = 1.3  # 晚峰
        else:
            load_factor = 0.9  # 其他时段

        base_hourly_load = base_daily_load / 96
        predicted_load = base_hourly_load * load_factor * random.uniform(0.95, 1.05)

        hourly_loads.append({
            "time": time_str,
            "predicted_load": round(predicted_load, 2)
        })

    # 生成当前合同数据
    hourly_amounts = []
    for i in range(96):
        time_hour = i // 4
        time_minute = (i % 4) * 15
        time_str = f"{time_hour:02d}:{time_minute:02d}"

        base_hourly_contract = contract_amount / 96
        contract_amount_val = base_hourly_contract * random.uniform(0.98, 1.02)

        hourly_amounts.append({
            "time": time_str,
            "contract_amount": round(contract_amount_val, 2),
            "contract_price": round(contract_price, 2)
        })

    # 生成合同覆盖率分析
    hourly_coverage = []
    for i in range(96):
        contract_amt = hourly_amounts[i]["contract_amount"]
        predicted_load = hourly_loads[i]["predicted_load"]
        coverage = contract_amt / predicted_load if predicted_load > 0 else 0

        hourly_coverage.append({
            "time": hourly_prices[i]["time"],
            "contract_amount": contract_amt,
            "predicted_load": predicted_load,
            "coverage": round(coverage, 3)
        })

    overall_coverage = contract_amount / base_daily_load

    # 生成时段调整建议
    period_adjustments = []

    # 低谷时段 (0-6h)
    valley_prices = [p for p in hourly_prices if 0 <= int(p["time"].split(":")[0]) < 6]
    valley_avg_price = sum(p["predicted_price"] for p in valley_prices) / len(valley_prices)
    valley_coverage = sum(h["coverage"] for h in hourly_coverage if 0 <= int(h["time"].split(":")[0]) < 6) / 24

    period_adjustments.append({
        "period": "低谷",
        "hours": "00:00-06:00",
        "predicted_avg_price": round(valley_avg_price, 2),
        "contract_price": round(contract_price, 2),
        "price_spread": round(valley_avg_price - contract_price, 2),
        "coverage": round(valley_coverage, 3),
        "recommendation": "maintain" if valley_coverage > 0.85 else "decrease_contract",
        "amount": round(base_daily_load * 0.05, 1) if valley_coverage > 0.85 else 0,
        "expected_savings": round(abs(valley_avg_price - contract_price) * base_daily_load * 0.05, 2),
        "reasoning": "预测价低于合同价，建议保持或减少合同"
    })

    # 早峰时段 (8-12h)
    morning_prices = [p for p in hourly_prices if 8 <= int(p["time"].split(":")[0]) < 12]
    morning_avg_price = sum(p["predicted_price"] for p in morning_prices) / len(morning_prices)
    morning_coverage = sum(h["coverage"] for h in hourly_coverage if 8 <= int(h["time"].split(":")[0]) < 12) / 16

    if morning_avg_price > contract_price + 50 and morning_coverage < 0.9:
        morning_recommendation = "increase_contract"
        morning_amount = round(base_daily_load * 0.1, 1)
    else:
        morning_recommendation = "maintain"
        morning_amount = 0

    period_adjustments.append({
        "period": "早峰",
        "hours": "08:00-12:00",
        "predicted_avg_price": round(morning_avg_price, 2),
        "contract_price": round(contract_price, 2),
        "price_spread": round(morning_avg_price - contract_price, 2),
        "coverage": round(morning_coverage, 3),
        "recommendation": morning_recommendation,
        "amount": round(morning_amount, 1),
        "expected_savings": round(max(0, (morning_avg_price - contract_price) * morning_amount), 2),
        "reasoning": "预测价高于合同价且覆盖率不足，建议增加合同"
    })

    # 平段时段 (12-16h)
    noon_prices = [p for p in hourly_prices if 12 <= int(p["time"].split(":")[0]) < 16]
    noon_avg_price = sum(p["predicted_price"] for p in noon_prices) / len(noon_prices)
    noon_coverage = sum(h["coverage"] for h in hourly_coverage if 12 <= int(h["time"].split(":")[0]) < 16) / 16

    period_adjustments.append({
        "period": "平段",
        "hours": "12:00-16:00",
        "predicted_avg_price": round(noon_avg_price, 2),
        "contract_price": round(contract_price, 2),
        "price_spread": round(noon_avg_price - contract_price, 2),
        "coverage": round(noon_coverage, 3),
        "recommendation": "maintain",
        "amount": 0,
        "expected_savings": 0,
        "reasoning": "预测价接近合同价，建议保持"
    })

    # 晚峰时段 (18-21h)
    evening_prices = [p for p in hourly_prices if 18 <= int(p["time"].split(":")[0]) < 21]
    evening_avg_price = sum(p["predicted_price"] for p in evening_prices) / len(evening_prices)
    evening_coverage = sum(h["coverage"] for h in hourly_coverage if 18 <= int(h["time"].split(":")[0]) < 21) / 12

    if evening_avg_price > contract_price + 50 and evening_coverage < 0.9:
        evening_recommendation = "increase_contract"
        evening_amount = round(base_daily_load * 0.15, 1)
    else:
        evening_recommendation = "maintain"
        evening_amount = 0

    period_adjustments.append({
        "period": "晚峰",
        "hours": "18:00-21:00",
        "predicted_avg_price": round(evening_avg_price, 2),
        "contract_price": round(contract_price, 2),
        "price_spread": round(evening_avg_price - contract_price, 2),
        "coverage": round(evening_coverage, 3),
        "recommendation": evening_recommendation,
        "amount": round(evening_amount, 1),
        "expected_savings": round(max(0, (evening_avg_price - contract_price) * evening_amount), 2),
        "reasoning": "预测价显著高于合同价且覆盖率不足，强烈建议增加合同"
    })

    # 总体建议
    total_expected_savings = sum(p["expected_savings"] for p in period_adjustments)
    total_adjustment_amount = sum(p["amount"] for p in period_adjustments)

    if total_adjustment_amount > 0:
        overall_action = "increase_contract"
        overall_reasoning = "D-2预测价格显著高于合同价格，建议增加合同覆盖"
    elif total_adjustment_amount < 0:
        overall_action = "decrease_contract"
        overall_reasoning = "D-2预测价格低于合同价格，建议减少合同"
    else:
        overall_action = "maintain"
        overall_reasoning = "D-2预测价格接近合同价格，建议保持当前策略"

    # 生成风险预警
    risk_alerts = []

    # 检查负电价
    negative_prices = [p for p in hourly_prices if p["predicted_price"] < 0]
    if negative_prices:
        most_negative = min(negative_prices, key=lambda x: x["predicted_price"])
        risk_alerts.append({
            "type": "negative_price",
            "severity": "high",
            "time_range": f"{most_negative['time']}-05:00",
            "predicted_price": round(most_negative["predicted_price"], 2),
            "recommendation": "减少合同，增加现货采购",
            "potential_loss": round(abs(most_negative["predicted_price"]) * base_daily_load * 0.05, 2)
        })

    # 检查价格尖峰
    if max_price > contract_price * 1.5:
        spike_prices = [p for p in hourly_prices if p["predicted_price"] > contract_price * 1.5]
        if spike_prices:
            highest_spike = max(spike_prices, key=lambda x: x["predicted_price"])
            risk_alerts.append({
                "type": "price_spike",
                "severity": "high",
                "time_range": f"{highest_spike['time']}",
                "predicted_price": round(highest_spike["predicted_price"], 2),
                "recommendation": "增加合同覆盖，避免现货采购",
                "potential_loss": round((highest_spike["predicted_price"] - contract_price) * base_daily_load * 0.05, 2)
            })

    # 检查高波动
    if std_price > 100:
        risk_alerts.append({
            "type": "high_volatility",
            "severity": "medium",
            "time_range": "全天",
            "std": round(std_price, 2),
            "recommendation": "提高合同覆盖率至90%"
        })

    # 生成回测结果
    backtesting = {
        "period": f"{(target_date - timedelta(days=30)).isoformat()} to {target_date.isoformat()}",
        "d2_strategy": {
            "total_cost": round(base_daily_load * avg_price * 30 * 0.98, 2),
            "daily_volatility": round(base_daily_load * std_price * 0.3, 2),
            "max_loss": -round(base_daily_load * std_price * 0.5, 2),
            "sharpe_ratio": round(1.2 + random.uniform(-0.2, 0.3), 2)
        },
        "fixed_contract": {
            "total_cost": round(base_daily_load * contract_price * 30, 2),
            "daily_volatility": 0,
            "max_loss": 0,
            "sharpe_ratio": 0
        },
        "pure_spot": {
            "total_cost": round(base_daily_load * avg_price * 30 * 1.05, 2),
            "daily_volatility": round(base_daily_load * std_price * 1.5, 2),
            "max_loss": -round(base_daily_load * std_price * 2.5, 2),
            "sharpe_ratio": round(0.8 + random.uniform(-0.1, 0.1), 2)
        }
    }

    strategy_id = f"D2_STRATEGY_{target_date.strftime('%Y%m%d')}_{customer_id}"

    return {
        "strategy_id": strategy_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "target_date": datetime.combine(target_date, datetime.min.time()),
        "d2_forecast": {
            "forecast_id": f"D2_{target_date.strftime('%Y%m%d')}_0900",
            "avg_price": round(avg_price, 2),
            "price_range": [round(min_price, 2), round(max_price, 2)],
            "hourly_prices": hourly_prices,
            "price_distribution": {
                "min": round(min_price, 2),
                "max": round(max_price, 2),
                "mean": round(avg_price, 2),
                "std": round(std_price, 2)
            }
        },
        "current_contract": {
            "total_amount": round(contract_amount, 2),
            "avg_price": round(contract_price, 2),
            "hourly_amounts": hourly_amounts
        },
        "load_forecast": {
            "total_load": round(base_daily_load, 2),
            "hourly_loads": hourly_loads
        },
        "strategy_recommendations": {
            "contract_coverage": {
                "overall": round(overall_coverage, 3),
                "hourly_coverage": hourly_coverage
            },
            "overall_recommendation": {
                "action": overall_action,
                "amount": round(abs(total_adjustment_amount), 2),
                "expected_cost_savings": round(total_expected_savings, 2),
                "reasoning": overall_reasoning
            },
            "period_adjustments": period_adjustments
        },
        "risk_alerts": risk_alerts,
        "backtesting": backtesting,
        "created_by": "system",
        "created_at": datetime.now(),
        "status": "active"
    }


def init_day_ahead_trading_strategy_data():
    """初始化日前交易策略数据（复用D-2数据结构）"""
    print("=" * 60)
    print("开始生成日前交易策略数据")
    print("=" * 60)

    customers = [
        ("CUST001", "某某企业"),
        ("CUST002", "某某集团"),
        ("CUST003", "某某制造")
    ]

    # 生成未来14天的数据
    current_date = date.today()
    target_dates = [current_date + timedelta(days=i) for i in range(1, 15)]

    collection = DATABASE["day_ahead_trading_plans"]

    # 清空现有数据
    collection.delete_many({})
    print("已清空现有数据\n")

    total_plans = 0

    for customer_id, customer_name in customers:
        for target_date in target_dates:
            # 复用D-2策略生成逻辑，修改策略ID前缀
            strategy = generate_d2_strategy(customer_id, customer_name, target_date)

            # 修改为日前交易方案的格式
            strategy["plan_id"] = strategy["strategy_id"].replace("D2_STRATEGY", "DA_PLAN")
            strategy["plan_config"] = {
                "strategy_type": "balanced",
                "contract_coverage_ratio": strategy["strategy_recommendations"]["contract_coverage"]["overall"],
                "day_ahead_coverage_ratio": 1 - strategy["strategy_recommendations"]["contract_coverage"]["overall"],
                "spot_ratio": 0.0
            }

            # 添加96点交易方案
            hourly_plan = []
            for i in range(96):
                time_str = strategy["d2_forecast"]["hourly_prices"][i]["time"]
                pred_load = strategy["load_forecast"]["hourly_loads"][i]["predicted_load"]
                contract_amt = strategy["current_contract"]["hourly_amounts"][i]["contract_amount"]
                contract_price = strategy["current_contract"]["hourly_amounts"][i]["contract_price"]
                day_ahead_price = strategy["d2_forecast"]["hourly_prices"][i]["predicted_price"]

                day_ahead_amount = max(0, pred_load - contract_amt)
                coverage = contract_amt / pred_load if pred_load > 0 else 0

                hourly_plan.append({
                    "time": time_str,
                    "predicted_load": pred_load,
                    "contract_amount": contract_amt,
                    "contract_price": contract_price,
                    "day_ahead_amount": day_ahead_amount,
                    "day_ahead_predicted_price": day_ahead_price,
                    "coverage": coverage,
                    "strategy": "day_ahead_purchase" if day_ahead_amount > 0 else "contract",
                    "contract_cost": contract_amt * contract_price,
                    "day_ahead_cost": day_ahead_amount * day_ahead_price,
                    "total_cost": contract_amt * contract_price + day_ahead_amount * day_ahead_price,
                    "vs_contract_only_savings": -day_ahead_amount * (day_ahead_price - contract_price),
                    "vs_spot_only_savings": (pred_load * day_ahead_price) - (contract_amt * contract_price + day_ahead_amount * day_ahead_price)
                })

            strategy["hourly_trading_plan"] = hourly_plan

            # 生成高优先级建议
            base_daily_load_map = {
                "CUST001": 3100.0,
                "CUST002": 1100.0,
                "CUST003": 2500.0
            }

            priority_recs = []
            for adj in strategy["strategy_recommendations"]["period_adjustments"]:
                if adj["recommendation"] == "increase_contract" and adj["expected_savings"] > 5000:
                    priority_recs.append({
                        "time_slot": adj["hours"],
                        "priority": len(priority_recs) + 1,
                        "predicted_load": base_daily_load_map.get(customer_id, 2000.0) * 0.3,
                        "contract_amount": base_daily_load_map.get(customer_id, 2000.0) * 0.2,
                        "day_ahead_amount": adj["amount"],
                        "predicted_price": adj["predicted_avg_price"],
                        "strategy": "day_ahead_purchase",
                        "reasoning": adj["reasoning"],
                        "expected_savings": adj["expected_savings"]
                    })

            strategy["priority_recommendations"] = priority_recs[:3]

            collection.insert_one(strategy)
            total_plans += 1

            print(f"[OK] 生成方案: {strategy['plan_id']}")

    # 创建索引
    collection.create_index([("customer_id", 1), ("target_date", 1)])
    collection.create_index([("plan_id", 1)], unique=True)
    collection.create_index([("status", 1)])

    print("\n" + "=" * 60)
    print(f"数据生成完成！")
    print(f"  - 日前交易方案记录: {total_plans} 条")
    print("=" * 60)

    return total_plans


def init_d2_trading_strategy_data():
    """初始化 D-2 交易策略数据"""
    print("=" * 60)
    print("开始生成 D-2 交易策略数据")
    print("=" * 60)

    customers = [
        ("CUST001", "某某企业"),
        ("CUST002", "某某集团"),
        ("CUST003", "某某制造")
    ]

    # 生成未来14天的数据
    current_date = date.today()
    target_dates = [current_date + timedelta(days=i) for i in range(2, 16)]

    collection = DATABASE["d2_trading_strategies"]

    # 清空现有数据
    collection.delete_many({})
    print("已清空现有数据\n")

    total_strategies = 0

    for customer_id, customer_name in customers:
        for target_date in target_dates:
            strategy = generate_d2_strategy(customer_id, customer_name, target_date)
            collection.insert_one(strategy)
            total_strategies += 1

            print(f"[OK] 生成策略: {strategy['strategy_id']}")

    # 创建索引
    collection.create_index([("customer_id", 1), ("target_date", 1)])
    collection.create_index([("strategy_id", 1)], unique=True)
    collection.create_index([("status", 1)])

    print("\n" + "=" * 60)
    print(f"数据生成完成！")
    print(f"  - D-2 交易策略记录: {total_strategies} 条")
    print("=" * 60)

    return total_strategies


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "day-ahead":
        init_day_ahead_trading_strategy_data()
    else:
        init_d2_trading_strategy_data()
