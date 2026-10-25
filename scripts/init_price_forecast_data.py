"""
初始化D-2价格预测测试数据
生成最近30天的价格预测结果和准确度统计数据
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random

from pymongo import ASCENDING
from webapp.tools.mongo import DATABASE

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# 配置参数
START_DATE = datetime.now() - timedelta(days=30)  # D-30
END_DATE = datetime.now() - timedelta(days=1)     # D-1


def generate_time_points(date: datetime) -> List[datetime]:
    """生成指定日期的96个时间点（15分钟粒度）"""
    points = []
    current = date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=15)
    end_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    while current <= end_of_day:
        points.append(current)
        current += timedelta(minutes=15)

    return points


def simulate_spot_price(time_points: List[datetime]) -> List[Dict[str, Any]]:
    """
    模拟现货价格曲线（元/MWh）
    特征：
    - 深谷（23:00-6:00）：200-300 元/MWh
    - 早高峰（8:00-12:00）：350-500 元/MWh
    - 晚高峰（18:00-21:00）：400-550 元/MWh
    - 平段（其他）：280-380 元/MWh
    """
    data = []
    for dt in time_points:
        hour = dt.hour

        # 基础价格
        if 0 <= hour < 6:
            base = 250  # 深谷
        elif 6 <= hour < 8:
            base = 320  # 早峰前爬坡
        elif 8 <= hour < 12:
            base = 420  # 早高峰
        elif 12 <= hour < 16:
            base = 350  # 午间平段
        elif 16 <= hour < 18:
            base = 380  # 晚峰前爬坡
        elif 18 <= hour < 21:
            base = 480  # 晚高峰
        else:
            base = 300  # 晚间平段

        # 添加随机波动（±15%）
        value = base * random.uniform(0.85, 1.15)

        data.append({
            "datetime": dt,
            "date_str": dt.strftime("%Y-%m-%d"),
            "time_str": dt.strftime("%H:%M"),
            "total_clearing_power": random.uniform(40000, 50000),
            "avg_clearing_price": round(value, 2),
        })

    return data


def generate_d2_forecast_batch(forecast_date: datetime) -> List[Dict[str, Any]]:
    """
    生成 D-2 价格预测批次数据
    预测未来10天（D ~ D+9）
    """
    forecast_date_str = forecast_date.strftime("%Y-%m-%d")
    forecast_id = f"D2_{forecast_date.strftime('%Y%m%d')}_0920"

    data = []
    for day_offset in range(10):
        target_date = forecast_date + timedelta(days=2 + day_offset)  # D-2预测D~D+9
        target_date_str = target_date.strftime("%Y-%m-%d")

        time_points = generate_time_points(target_date)
        actual_prices = simulate_spot_price(time_points)

        for i, dt in enumerate(time_points):
            # 预测价格与实际价格的偏差为 ±10%
            actual_price = actual_prices[i]["avg_clearing_price"]
            predicted_price = actual_price * random.uniform(0.90, 1.10)

            # 置信区间
            confidence_80_range = predicted_price * 0.15  # 80%置信区间 ±15%
            confidence_90_range = predicted_price * 0.20  # 90%置信区间 ±20%

            data.append({
                "forecast_id": forecast_id,
                "forecast_type": "d2_price",
                "forecast_date": datetime.strptime(forecast_date_str, "%Y-%m-%d"),
                "target_date": datetime.strptime(target_date_str, "%Y-%m-%d"),
                "datetime": dt,
                "predicted_price": round(predicted_price, 2),
                "confidence_80_lower": round(predicted_price - confidence_80_range, 2),
                "confidence_80_upper": round(predicted_price + confidence_80_range, 2),
                "confidence_90_lower": round(predicted_price - confidence_90_range, 2),
                "confidence_90_upper": round(predicted_price + confidence_90_range, 2),
                "model_type": "d2_near_term",
                "model_version": "v1.0.0",
                "created_at": datetime.now(),
            })

    return data


def calculate_accuracy_metrics(forecast_date: datetime, target_date: datetime) -> Dict[str, Any]:
    """
    计算预测准确度指标
    """
    # 获取预测数据
    forecast_collection = DATABASE["price_forecast_results"]
    target_date_str = target_date.strftime("%Y-%m-%d")

    # 查询该目标日期的预测（使用预测日期<=目标日期-2的最新预测）
    forecast_docs = list(forecast_collection.find({
        "forecast_type": "d2_price",
        "target_date": datetime.strptime(target_date_str, "%Y-%m-%d"),
        "forecast_date": {"$lte": forecast_date}
    }).sort("forecast_date", -1).limit(96))

    if not forecast_docs:
        return None

    # 获取实际价格
    actual_collection = DATABASE["day_ahead_spot_price"]
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    actual_docs = list(actual_collection.find({
        "datetime": {"$gt": start_of_day, "$lte": end_of_day}
    }).sort("datetime", ASCENDING))

    # 构建实际价格字典
    actual_prices = {}
    for doc in actual_docs:
        time_label = doc["datetime"].strftime("%H:%M")
        actual_prices[time_label] = doc["avg_clearing_price"]

    # 计算误差
    errors = []
    abs_errors = []
    for doc in forecast_docs:
        time_label = doc["datetime"].strftime("%H:%M")
        predicted = doc["predicted_price"]
        actual = actual_prices.get(time_label)

        if actual is not None:
            error = actual - predicted
            abs_error = abs(error)
            errors.append(error)
            abs_errors.append(abs_error)

    if not errors:
        return None

    # 计算指标
    mae = sum(abs_errors) / len(abs_errors)
    rmse = (sum(e ** 2 for e in abs_errors) / len(abs_errors)) ** 0.5

    # MAPE
    sum_actual = sum(abs(p) for p in [actual_prices.get(doc["datetime"].strftime("%H:%M")) for doc in forecast_docs])
    mape = (sum(abs_errors) / sum_actual) * 100 if sum_actual != 0 else 0

    # WMAPE准确度
    wmape_accuracy = max(0, 100 - mape)

    # 方向准确度（简化计算）
    correct_direction = sum(1 for i in range(1, len(errors)) if (errors[i] >= 0) == (errors[i-1] >= 0))
    direction_accuracy = (correct_direction / (len(errors) - 1)) * 100 if len(errors) > 1 else 0

    return {
        "target_date": target_date_str,
        "forecast_id": forecast_docs[0]["forecast_id"] if forecast_docs else "unknown",
        "forecast_type": "d2_price",
        "customer_id": "system",
        "forecast_date": forecast_date,
        "model_type": "d2_near_term",
        "model_version": "v1.0.0",
        "wmape_accuracy": round(wmape_accuracy, 2),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(mape, 2),
        "direction_accuracy": round(direction_accuracy, 2),
        "calculated_at": datetime.now(),
    }


def init_price_forecast_data():
    """初始化价格预测数据"""
    logger.info(f"开始生成D-2价格预测数据：{START_DATE.strftime('%Y-%m-%d')} 到 {END_DATE.strftime('%Y-%m-%d')}")

    # 清空现有数据
    logger.info("清空现有价格预测数据...")
    DATABASE["price_forecast_results"].delete_many({"forecast_type": "d2_price"})
    DATABASE["forecast_accuracy_daily"].delete_many({"forecast_type": "d2_price", "customer_id": "system"})
    logger.info("数据清空完成")

    current_date = START_DATE
    total_days = (END_DATE - START_DATE).days + 1
    processed_days = 0

    # 生成预测数据
    logger.info("生成价格预测结果...")
    while current_date <= END_DATE:
        date_str = current_date.strftime("%Y-%m-%d")
        logger.info(f"生成预测批次: {date_str} ({processed_days + 1}/{total_days})")

        try:
            # 生成预测批次（D-2执行，预测D~D+9）
            forecast_data = generate_d2_forecast_batch(current_date)
            if forecast_data:
                DATABASE["price_forecast_results"].insert_many(forecast_data)
                logger.info(f"  - price_forecast_results: {len(forecast_data)} 条")

            processed_days += 1

        except Exception as e:
            logger.error(f"生成预测批次失败: {date_str}, 错误: {e}", exc_info=True)

        current_date += timedelta(days=1)

    # 生成准确度统计数据
    logger.info("\n生成准确度统计数据...")
    accuracy_records = []

    # 对每个目标日期，计算准确度
    target_date_start = START_DATE + timedelta(days=2)  # 第一个有实际值的目标日期

    current_target = target_date_start
    while current_target <= END_DATE:
        try:
            # 使用该目标日期-2作为预测执行日期
            forecast_exec_date = current_target - timedelta(days=2)

            metrics = calculate_accuracy_metrics(forecast_exec_date, current_target)
            if metrics:
                accuracy_records.append(metrics)

        except Exception as e:
            logger.error(f"计算准确度失败: {current_target.strftime('%Y-%m-%d')}, 错误: {e}", exc_info=True)

        current_target += timedelta(days=1)

    if accuracy_records:
        DATABASE["forecast_accuracy_daily"].insert_many(accuracy_records)
        logger.info(f"  - forecast_accuracy_daily: {len(accuracy_records)} 条")

    logger.info(f"\n数据生成完成！共处理 {processed_days} 天预测，{len(accuracy_records)} 天准确度统计")

    # 统计数据量
    logger.info("\n数据统计:")
    logger.info(f"  - price_forecast_results (d2_price): {DATABASE['price_forecast_results'].count_documents({'forecast_type': 'd2_price'})} 条")
    logger.info(f"  - forecast_accuracy_daily (d2_price): {DATABASE['forecast_accuracy_daily'].count_documents({'forecast_type': 'd2_price', 'customer_id': 'system'})} 条")


if __name__ == "__main__":
    init_price_forecast_data()
