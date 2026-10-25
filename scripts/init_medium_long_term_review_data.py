"""
中长期交易复盘数据生成脚本

生成中长期交易复盘的模拟数据，用于前端展示和测试
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


# 基础负荷映射
BASE_DAILY_LOAD_MAP = {
    "CUST001": 3100.0,
    "CUST002": 1100.0,
    "CUST003": 2500.0
}


def generate_medium_long_term_transaction(
    customer_id: str,
    customer_name: str,
    transaction_type: str,
    transaction_date: date,
    effective_date: date,
    amount: float,
    price: float
) -> Dict[str, Any]:
    """生成单条中长期交易记录"""
    season_factor = get_seasonal_factor(effective_date.month)
    base_price = 380.0 * season_factor

    market_price_at_signing = base_price * random.uniform(0.95, 1.05)
    current_market_price = base_price * random.uniform(0.98, 1.02)

    price_advantage_at_signing = price - market_price_at_signing
    current_price_advantage = price - current_market_price

    transaction_id = f"MLT_{transaction_date.strftime('%Y%m%d')}_{customer_id}_{transaction_type.upper()}"

    return {
        "transaction_id": transaction_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "transaction_type": transaction_type,  # annual_contract, monthly_bid, contract_adjustment
        "transaction_date": datetime.combine(transaction_date, datetime.min.time()),
        "effective_date": datetime.combine(effective_date, datetime.min.time()),
        "expiry_date": datetime.combine(effective_date.replace(year=effective_date.year + 1), datetime.min.time()) - timedelta(days=1),
        "contract_id": f"CONTRACT_{effective_date.strftime('%Y')}_{customer_id}",
        "amount": amount,
        "price": price,
        "total_value": amount * price,
        "market_price_at_signing": market_price_at_signing,
        "price_advantage": price_advantage_at_signing,
        "current_market_price": current_market_price,
        "current_price_advantage": current_price_advantage,
        "actual_usage": 0,
        "remaining_amount": amount,
        "is_active": True,
        "created_by": "trader_001",
        "created_at": datetime.now(),
        "updated_at": datetime.now()
    }


def generate_medium_long_term_review(
    customer_id: str,
    customer_name: str,
    start_date: date,
    end_date: date
) -> Dict[str, Any]:
    """生成中长期交易复盘报告"""
    total_days = (end_date - start_date).days + 1
    season_factor = get_seasonal_factor(start_date.month)

    # 基础数据
    base_daily_load = (BASE_DAILY_LOAD_MAP.get(customer_id, 2000.0) / 365) * season_factor
    total_demand = base_daily_load * total_days

    # 执行指标
    planned_contract_coverage = random.uniform(0.80, 0.90)
    actual_contract_coverage = planned_contract_coverage * random.uniform(0.95, 1.05)
    execution_rate = 1.0 - abs(actual_contract_coverage - planned_contract_coverage) / planned_contract_coverage
    avg_deviation = random.uniform(0.02, 0.05)

    # 成本指标
    contract_price = 365.0 * season_factor
    spot_price = 380.0 * season_factor * random.uniform(1.0, 1.2)

    contract_cost = total_demand * actual_contract_coverage * contract_price
    spot_cost = total_demand * (1 - actual_contract_coverage) * spot_price
    total_cost = contract_cost + spot_cost
    blended_price = total_cost / total_demand

    market_cost = total_demand * spot_price * 1.05
    cost_savings = market_cost - total_cost
    savings_percentage = cost_savings / market_cost if market_cost > 0 else 0

    # 时机分析
    avg_days_before_effective = random.randint(30, 60)
    avg_price_advantage = random.uniform(10, 30)
    timing_accuracy = random.uniform(0.75, 0.90)

    # 策略对比
    strategy_comparison = [
        {
            "strategy": "actual",
            "contract_coverage": actual_contract_coverage,
            "total_cost": round(total_cost, 2),
            "risk_score": "medium"
        },
        {
            "strategy": "pure_spot",
            "contract_coverage": 0.0,
            "total_cost": round(total_demand * spot_price * 1.2, 2),
            "risk_score": "high"
        },
        {
            "strategy": "full_contract",
            "contract_coverage": 1.0,
            "total_cost": round(total_demand * contract_price, 2),
            "risk_score": "low"
        }
    ]

    # 异常交易
    anomalies = []
    if random.random() < 0.3:
        anomalies.append({
            "date": datetime.combine(start_date + timedelta(days=random.randint(0, total_days-1)), datetime.min.time()),
            "type": "spot_over_purchase",
            "description": "现货超量采购",
            "deviation": random.randint(100, 300),
            "impact_cost": random.randint(30000, 80000),
            "recommendation": "加强需求预测"
        })

    if random.random() < 0.3:
        anomalies.append({
            "date": datetime.combine(start_date + timedelta(days=random.randint(0, total_days-1)), datetime.min.time()),
            "type": "price_missed",
            "description": "价格错失",
            "deviation": 0,
            "impact_cost": -random.randint(20000, 50000),
            "recommendation": "灵活调整合同"
        })

    # 总结
    summary = {
        "highlights": [
            f"年度双边合同签订时机精准，平均价格优势 {avg_price_advantage:.0f}元/MWh",
            f"合同电量执行准确，平均偏差仅 {avg_deviation*100:.1f}%"
        ],
        "issues": [anomaly["description"] for anomaly in anomalies],
        "recommendations": [
            {
                "priority": 1,
                "action": "提高年度双边合同比例",
                "reason": f"平均价格优势 {avg_price_advantage:.0f}元/MWh",
                "suggestion": "从 70% 提升到 80%",
                "expected_benefit": "节省约 50万元"
            }
        ]
    }

    review_id = f"MLR_{start_date.strftime('%Y%m%d')}_to_{end_date.strftime('%Y%m%d')}_{customer_id}"

    return {
        "review_id": review_id,
        "customer_id": customer_id,
        "customer_name": customer_name,
        "review_period": {
            "start_date": datetime.combine(start_date, datetime.min.time()),
            "end_date": datetime.combine(end_date, datetime.min.time()),
            "type": "quarterly"
        },
        "execution_metrics": {
            "planned_contract_coverage": round(planned_contract_coverage, 3),
            "actual_contract_coverage": round(actual_contract_coverage, 3),
            "execution_rate": round(execution_rate, 3),
            "avg_deviation": round(avg_deviation, 3),
            "max_deviation_date": datetime.combine(start_date + timedelta(days=random.randint(0, total_days-1)), datetime.min.time()),
            "max_deviation_amount": round(random.uniform(100, 300), 1)
        },
        "cost_metrics": {
            "contract_cost": round(contract_cost, 2),
            "spot_cost": round(spot_cost, 2),
            "total_cost": round(total_cost, 2),
            "blended_price": round(blended_price, 2),
            "market_cost": round(market_cost, 2),
            "cost_savings": round(cost_savings, 2),
            "savings_percentage": round(savings_percentage, 4)
        },
        "timing_analysis": {
            "avg_days_before_effective": avg_days_before_effective,
            "avg_price_advantage_at_signing": round(avg_price_advantage, 2),
            "timing_accuracy": round(timing_accuracy, 3)
        },
        "strategy_comparison": strategy_comparison,
        "anomalies": anomalies,
        "summary": summary,
        "generated_at": datetime.now(),
        "generated_by": "system",
        "status": "active"
    }


def init_medium_long_term_review_data():
    """初始化中长期交易复盘数据"""
    print("=" * 60)
    print("开始生成中长期交易复盘数据")
    print("=" * 60)

    customers = [
        ("CUST001", "某某制造"),
        ("CUST002", "某某集团"),
        ("CUST003", "某某企业")
    ]

    # 生成2025年第一季度的复盘数据（1-3月）
    review_periods = [
        (date(2025, 1, 1), date(2025, 1, 31)),
        (date(2025, 2, 1), date(2025, 2, 28)),
        (date(2025, 3, 1), date(2025, 3, 31)),
        (date(2025, 4, 1), date(2025, 6, 30)),  # Q2
        (date(2025, 7, 1), date(2025, 9, 30)),  # Q3
        (date(2025, 10, 1), date(2025, 12, 31))  # Q4
    ]

    transactions_collection = DATABASE["medium_long_term_transactions"]
    reviews_collection = DATABASE["medium_long_term_reviews"]

    # 清空现有数据
    transactions_collection.delete_many({})
    reviews_collection.delete_many({})
    print("已清空现有数据\n")

    total_transactions = 0
    total_reviews = 0

    # 生成交易记录
    for customer_id, customer_name in customers:
        # 年度双边合同（每年11-12月签订）
        for year in [2024]:
            for month in [11, 12]:
                transaction_date = date(year, month, random.randint(1, 25))
                effective_date = date(2025, 1, 1)
                season_factor = get_seasonal_factor(effective_date.month)
                base_price = 365.0 * season_factor
                amount = (base_daily_load_map[customer_id] * 365) * 0.7  # 年度双边 70%

                transaction = generate_medium_long_term_transaction(
                    customer_id, customer_name, "annual_contract",
                    transaction_date, effective_date, amount, base_price
                )
                transactions_collection.insert_one(transaction)
                total_transactions += 1
                print(f"[OK] 生成交易: {transaction['transaction_id']}")

        # 月度竞价（每月20-25日签订下月）
        for year in [2024, 2025]:
            for month in range(1, 13):
                if month == 12:
                    continue
                transaction_date = date(year, month, random.randint(20, 25))
                effective_date = date(year if month < 12 else year + 1, month + 1, 1)
                season_factor = get_seasonal_factor(effective_date.month)
                base_price = 375.0 * season_factor
                amount = (base_daily_load_map[customer_id] * 30) * 0.15  # 月度竞价 15%

                transaction = generate_medium_long_term_transaction(
                    customer_id, customer_name, "monthly_bid",
                    transaction_date, effective_date, amount, base_price
                )
                transactions_collection.insert_one(transaction)
                total_transactions += 1
                print(f"[OK] 生成交易: {transaction['transaction_id']}")

    # 生成复盘报告
    for customer_id, customer_name in customers:
        for start_date, end_date in review_periods[:3]:  # 只生成Q1的季度复盘
            review = generate_medium_long_term_review(customer_id, customer_name, start_date, end_date)
            reviews_collection.insert_one(review)
            total_reviews += 1
            print(f"[OK] 生成复盘: {review['review_id']}")

    # 创建索引
    transactions_collection.create_index([("customer_id", 1), ("effective_date", 1)])
    transactions_collection.create_index([("transaction_id", 1)], unique=True)
    transactions_collection.create_index([("transaction_type", 1)])

    reviews_collection.create_index([("customer_id", 1), ("review_period.start_date", 1)])
    reviews_collection.create_index([("review_id", 1)], unique=True)
    reviews_collection.create_index([("status", 1)])

    print("\n" + "=" * 60)
    print(f"数据生成完成！")
    print(f"  - 交易记录: {total_transactions} 条")
    print(f"  - 复盘报告: {total_reviews} 条")
    print("=" * 60)

    return total_transactions, total_reviews


if __name__ == "__main__":
    # 定义基础负荷映射（需要在函数外部定义）
    base_daily_load_map = {
        "CUST001": 3100.0,
        "CUST002": 1100.0,
        "CUST003": 2500.0
    }

    init_medium_long_term_review_data()
