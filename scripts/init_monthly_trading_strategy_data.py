"""
月度交易策略数据生成脚本

生成月度交易策略的模拟数据，用于前端展示和测试
"""

from datetime import datetime, timedelta
from typing import Any, Dict, List
import random
import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from webapp.tools.mongo import DATABASE


def get_seasonal_factor(month: int) -> float:
    """获取季节因子（影响负荷和价格）"""
    if month in [1, 2, 12]:
        return 1.15  # 冬季高峰
    elif month in [7, 8]:
        return 1.10  # 夏季高峰
    elif month in [3, 4, 5]:
        return 0.95  # 春季平水期
    elif month in [6, 9, 10, 11]:
        return 0.90  # 秋季平水期
    else:
        return 1.0


def generate_monthly_strategy(
    customer_id: str,
    customer_name: str,
    target_year: int,
    target_month: int,
    annual_contract_ratio: float = 0.70,
    monthly_bid_ratio: float = 0.20,
    spot_ratio: float = 0.10,
    optimization_objective: str = "balanced"
) -> Dict[str, Any]:
    """
    生成月度交易策略数据

    Args:
        customer_id: 客户ID
        customer_name: 客户名称
        target_year: 目标年份
        target_month: 目标月份
        annual_contract_ratio: 年度双边比例
        monthly_bid_ratio: 月度竞价比例
        spot_ratio: 现货比例
        optimization_objective: 优化目标 (cost, risk, balanced)

    Returns:
        月度交易策略数据
    """
    season_factor = get_seasonal_factor(target_month)

    # 基础负荷（根据客户和季节变化）
    base_demand_map = {
        "CUST001": 1000000,  # MWh/年
        "CUST002": 350000,   # MWh/年
        "CUST003": 800000    # MWh/年
    }
    annual_demand = base_demand_map.get(customer_id, 500000) * season_factor
    monthly_demand = annual_demand / 12

    # 价格基准（元/MWh）
    base_annual_price = 365.0
    base_monthly_price = 380.0
    base_spot_price = 420.0

    # 根据优化目标调整价格
    if optimization_objective == "cost":
        annual_price = base_annual_price - 10
        monthly_price = base_monthly_price - 5
        spot_price = base_spot_price + 20
    elif optimization_objective == "risk":
        annual_price = base_annual_price + 15
        monthly_price = base_monthly_price + 10
        spot_price = base_spot_price - 10
    else:  # balanced
        annual_price = base_annual_price
        monthly_price = base_monthly_price
        spot_price = base_spot_price

    # 计算交易组合
    annual_contract_amount = monthly_demand * annual_contract_ratio
    monthly_bid_amount = monthly_demand * monthly_bid_ratio
    spot_amount = monthly_demand * spot_ratio

    # 计算成本
    annual_contract_cost = annual_contract_amount * annual_price
    monthly_bid_cost = monthly_bid_amount * monthly_price
    spot_cost = spot_amount * spot_price
    total_cost = annual_contract_cost + monthly_bid_cost + spot_cost

    # 综合成本（加权平均）
    blended_cost = total_cost / monthly_demand

    # 对比基准
    pure_spot_cost = monthly_demand * spot_price
    full_contract_cost = monthly_demand * annual_price
    cost_savings_vs_spot = pure_spot_cost - total_cost
    savings_percentage = (cost_savings_vs_spot / pure_spot_cost * 100) if pure_spot_cost > 0 else 0

    cost_increase_vs_contract = total_cost - full_contract_cost

    # 风险指标
    price_variance = (spot_price - annual_price) ** 2 * monthly_demand * 0.1
    value_at_risk_95 = price_variance * 0.15
    sharpe_ratio = 1.5 + random.uniform(-0.3, 0.3)
    flexibility_score = spot_ratio * 5  # 现货比例越高，灵活性越高

    # 生成交易时机建议
    timing_recommendations = []

    # 年度双边协商建议
    timing_recommendations.append({
        "date": f"{target_year - 1}-{12 - target_month % 3:02d}-20",
        "type": "annual_contract",
        "recommended_amount": round(annual_contract_amount / 12, 1),
        "recommended_price_range": [annual_price - 15, annual_price + 15],
        "reasoning": "年度协商窗口期，价格处于历史低位，建议锁定长期合同"
    })

    # 月度竞价建议（分批）
    bid_batches = 2
    for i in range(bid_batches):
        batch_date = f"{target_year - 1}-{12:02d}-{15 + i * 5:02d}"
        timing_recommendations.append({
            "date": batch_date,
            "type": "monthly_bid",
            "recommended_amount": round(monthly_bid_amount / bid_batches, 1),
            "recommended_price_range": [monthly_price - 20, monthly_price + 20],
            "reasoning": f"月度竞价第{i+1}批，预计价格温和上涨，建议分批采购"
        })

    # 现货调整建议
    timing_recommendations.append({
        "date": f"{target_year}-{target_month:02d}-01",
        "type": "spot_adjustment",
        "recommended_amount": round(spot_amount / 30, 1),
        "recommended_price_range": [spot_price - 50, spot_price + 50],
        "reasoning": "现货滚动调整开始，每日根据最新预测微调采购量"
    })

    # 生成情景分析
    base_case_cost = total_cost

    # 高价情景（价格+20%）
    high_price_cost = total_cost * 1.15  # 现货影响更大
    high_price_increase = high_price_cost - base_case_cost

    # 低价情景（价格-20%）
    low_price_cost = total_cost * 0.85
    low_price_decrease = low_price_cost - base_case_cost

    # 高负荷情景（负荷+15%）
    high_load_cost = total_cost * 1.12
    high_load_increase = high_load_cost - base_case_cost

    # 低负荷情景（负荷-15%）
    low_load_cost = total_cost * 0.88
    low_load_decrease = low_load_cost - base_case_cost

    strategy_id = f"MONTHLY_STRATEGY_{target_year}{target_month:02d}_{customer_id}_{optimization_objective}_v1"

    return {
        "strategy_id": strategy_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "target_month": {
            "year": target_year,
            "month": target_month
        },
        "strategy_config": {
            "annual_contract_ratio": annual_contract_ratio,
            "monthly_bid_ratio": monthly_bid_ratio,
            "spot_ratio": spot_ratio,
            "optimization_objective": optimization_objective,
            "risk_aversion": 0.5 if optimization_objective == "balanced" else (0.2 if optimization_objective == "cost" else 0.8)
        },
        "optimization_results": {
            "trading_mix": {
                "annual_contract": {
                    "amount": round(annual_contract_amount, 1),
                    "ratio": annual_contract_ratio,
                    "avg_price": round(annual_price, 2),
                    "total_cost": round(annual_contract_cost, 2)
                },
                "monthly_bid": {
                    "amount": round(monthly_bid_amount, 1),
                    "ratio": monthly_bid_ratio,
                    "avg_price": round(monthly_price, 2),
                    "total_cost": round(monthly_bid_cost, 2)
                },
                "spot": {
                    "amount": round(spot_amount, 1),
                    "ratio": spot_ratio,
                    "avg_price": round(spot_price, 2),
                    "total_cost": round(spot_cost, 2)
                }
            },
            "total_demand": round(monthly_demand, 1),
            "blended_cost": round(blended_cost, 2),
            "total_cost": round(total_cost, 2),
            "vs_pure_spot": {
                "cost_savings": round(cost_savings_vs_spot, 2),
                "savings_percentage": round(savings_percentage, 1)
            },
            "vs_full_contract": {
                "cost_increase": round(cost_increase_vs_contract, 2),
                "risk_reduction": round(flexibility_score * 40, 1)  # 模拟风险降低百分比
            },
            "risk_metrics": {
                "cost_variance": round(price_variance, 2),
                "value_at_risk_95": round(value_at_risk_95, 2),
                "sharpe_ratio": round(sharpe_ratio, 2),
                "flexibility_score": round(flexibility_score, 2)
            }
        },
        "timing_recommendations": timing_recommendations,
        "scenario_analysis": {
            "base_case": {
                "total_cost": round(base_case_cost, 2),
                "var_95": round(value_at_risk_95, 2)
            },
            "high_price": {
                "price_deviation": 0.20,
                "total_cost": round(high_price_cost, 2),
                "cost_increase": round(high_price_increase, 2)
            },
            "low_price": {
                "price_deviation": -0.20,
                "total_cost": round(low_price_cost, 2),
                "cost_decrease": round(low_price_decrease, 2)
            },
            "high_load": {
                "load_deviation": 0.15,
                "total_cost": round(high_load_cost, 2),
                "cost_increase": round(high_load_increase, 2)
            },
            "low_load": {
                "load_deviation": -0.15,
                "total_cost": round(low_load_cost, 2),
                "cost_decrease": round(low_load_decrease, 2)
            }
        },
        "created_by": "system",
        "created_at": datetime.now(),
        "status": "active",
        "version": 1
    }


def generate_price_trend_data(
    target_year: int,
    target_month: int
) -> Dict[str, Any]:
    """
    生成价格走势数据

    Args:
        target_year: 目标年份
        target_month: 目标月份

    Returns:
        价格走势数据
    """
    import calendar

    days_in_month = calendar.monthrange(target_year, target_month)[1]
    season_factor = get_seasonal_factor(target_month)

    # 基础价格
    base_price = 380.0 * season_factor

    daily_prices = []
    for day in range(1, days_in_month + 1):
        # 模拟价格波动（工作日价格更高）
        weekday = datetime(target_year, target_month, day).weekday()
        weekday_factor = 1.0 if weekday < 5 else 0.9  # 周末价格略低

        # 月初月末价格波动
        if day <= 5:
            month_factor = 0.95  # 月初价格较低
        elif day >= 25:
            month_factor = 1.05  # 月末价格较高
        else:
            month_factor = 1.0

        # 随机波动
        random_factor = random.uniform(0.95, 1.05)

        predicted_price = base_price * weekday_factor * month_factor * random_factor
        confidence_lower = predicted_price * 0.9
        confidence_upper = predicted_price * 1.1

        daily_prices.append({
            "date": f"{target_year}-{target_month:02d}-{day:02d}",
            "predicted_price": round(predicted_price, 2),
            "confidence_lower": round(confidence_lower, 2),
            "confidence_upper": round(confidence_upper, 2)
        })

    # 计算价格分布统计
    all_prices = [p["predicted_price"] for p in daily_prices]
    all_prices.sort()

    n = len(all_prices)
    price_distribution = {
        "min": round(min(all_prices), 2),
        "max": round(max(all_prices), 2),
        "mean": round(sum(all_prices) / n, 2),
        "std": round((sum((x - sum(all_prices) / n) ** 2 for x in all_prices) / n) ** 0.5, 2),
        "percentiles": {
            "p10": round(all_prices[int(n * 0.1)], 2),
            "p25": round(all_prices[int(n * 0.25)], 2),
            "p50": round(all_prices[int(n * 0.5)], 2),
            "p75": round(all_prices[int(n * 0.75)], 2),
            "p90": round(all_prices[int(n * 0.9)], 2)
        }
    }

    return {
        "target_month": {
            "year": target_year,
            "month": target_month
        },
        "daily_prices": daily_prices,
        "price_distribution": price_distribution
    }


def init_monthly_trading_strategy_data():
    """初始化月度交易策略数据"""
    print("=" * 60)
    print("开始生成月度交易策略数据")
    print("=" * 60)

    # 客户列表
    customers = [
        ("CUST001", "某某企业"),
        ("CUST002", "某某集团"),
        ("CUST003", "某某制造")
    ]

    # 目标月份（未来7个月）
    from datetime import datetime
    current_date = datetime.now()
    target_months = []
    for i in range(1, 8):
        year = current_date.year + (current_date.month + i - 1) // 12
        month = (current_date.month + i - 1) % 12 + 1
        target_months.append((year, month))

    # 优化目标
    objectives = ["cost", "risk", "balanced"]

    # 交易组合配置（不同优化目标对应不同配置）
    strategy_configs = {
        "cost": (0.80, 0.15, 0.05),  # 成本优先：更多年度双边
        "risk": (0.60, 0.25, 0.15),  # 风险优先：更多现货灵活性
        "balanced": (0.70, 0.20, 0.10)  # 平衡策略
    }

    collection = DATABASE["monthly_trading_strategies"]
    price_trend_collection = DATABASE["monthly_price_trends"]

    # 清空现有数据
    collection.delete_many({})
    price_trend_collection.delete_many({})
    print("已清空现有数据\n")

    total_strategies = 0
    total_price_trends = 0

    # 生成交易策略数据
    for customer_id, customer_name in customers:
        for year, month in target_months:
            for objective in objectives:
                annual_ratio, monthly_ratio, spot_ratio = strategy_configs[objective]

                strategy = generate_monthly_strategy(
                    customer_id=customer_id,
                    customer_name=customer_name,
                    target_year=year,
                    target_month=month,
                    annual_contract_ratio=annual_ratio,
                    monthly_bid_ratio=monthly_ratio,
                    spot_ratio=spot_ratio,
                    optimization_objective=objective
                )

                collection.insert_one(strategy)
                total_strategies += 1

                print(f"[OK] 生成策略: {strategy['strategy_id']}")

    # 生成价格走势数据
    for year, month in target_months:
        price_trend = generate_price_trend_data(year, month)
        price_trend_collection.insert_one(price_trend)
        total_price_trends += 1

        print(f"[OK] 生成价格走势: {year}-{month:02d}")

    # 创建索引
    collection.create_index([("customer_id", 1), ("target_month.year", 1), ("target_month.month", 1)])
    collection.create_index([("strategy_id", 1)], unique=True)
    collection.create_index([("status", 1)])

    price_trend_collection.create_index([("target_month.year", 1), ("target_month.month", 1)], unique=True)

    print("\n" + "=" * 60)
    print(f"数据生成完成！")
    print(f"  - 交易策略记录: {total_strategies} 条")
    print(f"  - 价格走势记录: {total_price_trends} 条")
    print("=" * 60)

    return total_strategies, total_price_trends


if __name__ == "__main__":
    init_monthly_trading_strategy_data()
