"""
生成2025年全年价格预测数据（用于测试）
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


# 配置参数 - 2025年全年数据
START_DATE = datetime(2025, 1, 1)  # 2025-01-01
END_DATE = datetime.now() - timedelta(days=1)  # 昨天为止


def generate_time_points(date: datetime) -> List[datetime]:
    """生成指定日期的96个时间点（15分钟粒度）"""
    points = []
    current = date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=15)
    end_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    while current <= end_of_day:
        points.append(current)
        current += timedelta(minutes=15)

    return points


def simulate_spot_price_data(date: datetime) -> List[Dict[str, Any]]:
    """模拟指定日期的日前现货价格数据"""
    time_points = generate_time_points(date)
    data = []

    # 根据季节调整价格（夏季和冬季价格更高）
    month = date.month
    if month in [1, 2, 12]:  # 冬季
        seasonal_factor = 1.15
    elif month in [6, 7, 8]:  # 夏季
        seasonal_factor = 1.10
    else:
        seasonal_factor = 1.0

    # 周末价格略低
    weekday = date.weekday()
    if weekday >= 5:  # 周六、周日
        weekend_factor = 0.9
    else:
        weekend_factor = 1.0

    for dt in time_points:
        hour = dt.hour

        # 基础价格
        if 0 <= hour < 6:
            base = 250 * seasonal_factor  # 深谷
        elif 6 <= hour < 8:
            base = 320 * seasonal_factor  # 早峰前爬坡
        elif 8 <= hour < 12:
            base = 450 * seasonal_factor  # 早高峰（夏季略高）
        elif 12 <= hour < 16:
            base = 350 * seasonal_factor  # 午间平段
        elif 16 <= hour < 18:
            base = 380 * seasonal_factor  # 晚峰前爬坡
        elif 18 <= hour < 21:
            base = 520 * seasonal_factor  # 晚高峰
        else:
            base = 300 * seasonal_factor  # 晚间平段

        # 应用周末因子
        base *= weekend_factor

        # 添加随机波动（±15%）
        value = base * random.uniform(0.85, 1.15)

        data.append({
            "datetime": dt,
            "date_str": dt.strftime("%Y-%m-%d"),
            "time_str": dt.strftime("%H:%M"),
            "total_clearing_power": round(random.uniform(40000, 50000), 4),
            "thermal_clearing_power": round(random.uniform(25000, 30000), 4),
            "hydro_clearing_power": round(random.uniform(8000, 12000), 4),
            "wind_clearing_power": round(random.uniform(6000, 9000), 4),
            "solar_clearing_power": round(random.uniform(3000, 10000), 4),
            "pumped_storage_clearing_power": round(random.uniform(-500, 1500), 4),
            "battery_storage_generation": round(random.uniform(0, 500), 4),
            "avg_clearing_price": round(value, 2),
        })

    return data


def generate_d2_forecast_batch(forecast_date: datetime) -> List[Dict[str, Any]]:
    """生成 D-2 价格预测批次数据"""
    forecast_date_str = forecast_date.strftime("%Y-%m-%d")
    forecast_id = f"D2_{forecast_date.strftime('%Y%m%d')}_0920"

    data = []
    for day_offset in range(10):
        target_date = forecast_date + timedelta(days=2 + day_offset)  # D-2预测D~D+9
        target_date_str = target_date.strftime("%Y-%m-%d")

        time_points = generate_time_points(target_date)

        # 获取该日期的季节因子
        month = target_date.month
        if month in [1, 2, 12]:  # 冬季
            seasonal_factor = 1.15
        elif month in [6, 7, 8]:  # 夏季
            seasonal_factor = 1.10
        else:
            seasonal_factor = 1.0

        for dt in time_points:
            hour = dt.hour

            # 基础价格
            if 0 <= hour < 6:
                base = 250 * seasonal_factor
            elif 6 <= hour < 8:
                base = 320 * seasonal_factor
            elif 8 <= hour < 12:
                base = 450 * seasonal_factor
            elif 12 <= hour < 16:
                base = 350 * seasonal_factor
            elif 16 <= hour < 18:
                base = 380 * seasonal_factor
            elif 18 <= hour < 21:
                base = 520 * seasonal_factor
            else:
                base = 300 * seasonal_factor

            # 预测价格与实际价格的偏差为 ±10%
            predicted_price = base * random.uniform(0.90, 1.10)

            # 置信区间
            confidence_80_range = predicted_price * 0.15
            confidence_90_range = predicted_price * 0.20

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


def calculate_accuracy_metrics(target_date: datetime) -> dict:
    """计算指定目标日期的预测准确度指标"""
    target_date_str = target_date.strftime("%Y-%m-%d")
    forecast_date = target_date - timedelta(days=2)

    # 获取预测数据
    forecast_collection = DATABASE["price_forecast_results"]
    forecast_docs = list(forecast_collection.find({
        "forecast_type": "d2_price",
        "target_date": datetime.strptime(target_date_str, "%Y-%m-%d"),
        "forecast_date": {"$lte": datetime.strptime(forecast_date.strftime("%Y-%m-%d"), "%Y-%m-%d")}
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
    sum_abs_actual = sum(abs(actual) for actual in actual_prices.values())
    mape = (sum(abs_errors) / sum_abs_actual) * 100 if sum_abs_actual != 0 else 0
    wmape_accuracy = max(0, 100 - mape)

    # 方向准确度
    if len(errors) > 1:
        correct_direction = sum(1 for i in range(1, len(errors)) if (errors[i] >= 0) == (errors[i-1] >= 0))
        direction_accuracy = (correct_direction / (len(errors) - 1)) * 100
    else:
        direction_accuracy = 0

    return {
        "target_date": target_date_str,
        "forecast_id": forecast_docs[0]["forecast_id"],
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


def init_2025_data():
    """初始化2025年全年数据"""
    logger.info(f"开始生成2025年数据：{START_DATE.strftime('%Y-%m-%d')} 到 {END_DATE.strftime('%Y-%m-%d')}")

    # 清空现有数据
    logger.info("清空现有2025年数据...")
    DATABASE["day_ahead_spot_price"].delete_many({
        "datetime": {"$gte": START_DATE, "$lte": END_DATE}
    })
    DATABASE["price_forecast_results"].delete_many({
        "forecast_type": "d2_price",
        "forecast_date": {"$gte": START_DATE, "$lte": END_DATE}
    })
    DATABASE["forecast_accuracy_daily"].delete_many({
        "forecast_type": "d2_price",
        "customer_id": "system",
        "target_date": {"$gte": START_DATE, "$lte": END_DATE}
    })
    logger.info("数据清空完成")

    total_days = (END_DATE - START_DATE).days + 1
    processed_days = 0
    current_date = START_DATE

    # 1. 生成实际价格数据
    logger.info("\n[1/3] 生成日前现货价格数据...")
    while current_date <= END_DATE:
        if processed_days % 30 == 0:
            logger.info(f"  进度: {current_date.strftime('%Y-%m-%d')} ({processed_days + 1}/{total_days})")

        try:
            price_data = simulate_spot_price_data(current_date)
            if price_data:
                DATABASE["day_ahead_spot_price"].insert_many(price_data)
            processed_days += 1
        except Exception as e:
            logger.error(f"生成价格数据失败: {current_date.strftime('%Y-%m-%d')}, 错误: {e}", exc_info=True)

        current_date += timedelta(days=1)

    logger.info(f"  实际价格数据生成完成: {DATABASE['day_ahead_spot_price'].count_documents({})} 条")

    # 2. 生成预测数据
    logger.info("\n[2/3] 生成D-2价格预测数据...")
    current_date = START_DATE
    processed_forecasts = 0

    while current_date <= END_DATE:
        # 只到 D-2，确保有实际数据对比
        if current_date <= END_DATE - timedelta(days=2):
            try:
                forecast_data = generate_d2_forecast_batch(current_date)
                if forecast_data:
                    DATABASE["price_forecast_results"].insert_many(forecast_data)
                processed_forecasts += 1

                if processed_forecasts % 30 == 0:
                    logger.info(f"  进度: {current_date.strftime('%Y-%m-%d')} ({processed_forecasts}/{total_days - 2})")
            except Exception as e:
                logger.error(f"生成预测数据失败: {current_date.strftime('%Y-%m-%d')}, 错误: {e}", exc_info=True)

        current_date += timedelta(days=1)

    logger.info(f"  预测数据生成完成: {DATABASE['price_forecast_results'].count_documents({'forecast_type': 'd2_price'})} 条")

    # 3. 生成准确度统计
    logger.info("\n[3/3] 生成准确度统计数据...")
    current_target = START_DATE + timedelta(days=2)  # 第一个有预测和实际数据的目标日期
    accuracy_records = []
    processed_accuracy = 0

    while current_target <= END_DATE:
        metrics = calculate_accuracy_metrics(current_target)
        if metrics:
            accuracy_records.append(metrics)
            processed_accuracy += 1

            if processed_accuracy % 30 == 0:
                logger.info(f"  进度: {current_target.strftime('%Y-%m-%d')} ({processed_accuracy}/{total_days - 2})")

        current_target += timedelta(days=1)

    if accuracy_records:
        DATABASE["forecast_accuracy_daily"].insert_many(accuracy_records)

        # 计算平均准确度
        avg_accuracy = sum(r["wmape_accuracy"] for r in accuracy_records) / len(accuracy_records)
        best = max(accuracy_records, key=lambda x: x["wmape_accuracy"])
        worst = min(accuracy_records, key=lambda x: x["wmape_accuracy"])

        logger.info(f"  准确度统计完成: {len(accuracy_records)} 条")
        logger.info(f"  平均准确度: {avg_accuracy:.2f}%")
        logger.info(f"  最佳准确度: {best['wmape_accuracy']:.2f}% ({best['target_date']})")
        logger.info(f"  最低准确度: {worst['wmape_accuracy']:.2f}% ({worst['target_date']})")
    else:
        logger.warning("  未生成任何准确度统计记录")

    # 最终统计
    logger.info("\n" + "=" * 60)
    logger.info("2025年数据生成完成！")
    logger.info("=" * 60)
    logger.info("\n数据统计:")
    logger.info(f"  - day_ahead_spot_price: {DATABASE['day_ahead_spot_price'].count_documents({})} 条")
    logger.info(f"  - price_forecast_results (d2_price): {DATABASE['price_forecast_results'].count_documents({'forecast_type': 'd2_price'})} 条")
    logger.info(f"  - forecast_accuracy_daily (d2_price): {DATABASE['forecast_accuracy_daily'].count_documents({'forecast_type': 'd2_price', 'customer_id': 'system'})} 条")


if __name__ == "__main__":
    init_2025_data()
