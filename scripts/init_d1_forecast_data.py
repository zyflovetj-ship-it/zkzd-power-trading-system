"""
生成D-1日前价格预测模拟数据
生成最近30天的D-1预测数据，包括预测结果和准确度统计
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random
from pymongo import ASCENDING

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from webapp.tools.mongo import DATABASE

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 配置参数
END_DATE = datetime.now() - timedelta(days=1)  # 昨天
START_DATE = END_DATE - timedelta(days=29)  # 最近30天


def generate_time_points(date: datetime) -> List[datetime]:
    """生成指定日期的96个时间点（15分钟粒度）"""
    points = []
    current = date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=15)
    end_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    while current <= end_of_day:
        points.append(current)
        current += timedelta(minutes=15)

    return points


def generate_d1_forecast_batch(forecast_date: datetime, actual_data: List[Dict]) -> List[Dict[str, Any]]:
    """生成 D-1 价格预测批次数据"""
    forecast_date_str = forecast_date.strftime("%Y-%m-%d")
    forecast_time = "09:00"  # 假设每天9点执行预测
    forecast_id = f"D1_{forecast_date.strftime('%Y%m%d')}_{forecast_time.replace(':', '')}"

    # 获取目标日期
    target_date = forecast_date + timedelta(days=1)
    target_date_str = target_date.strftime("%Y-%m-%d")

    # 生成时间点
    time_points = generate_time_points(target_date)

    # 季节因子
    month = target_date.month
    if month in [1, 2, 12]:  # 冬季
        seasonal_factor = 1.15
    elif month in [6, 7, 8]:  # 夏季
        seasonal_factor = 1.10
    else:
        seasonal_factor = 1.0

    # 周末因子
    weekday = target_date.weekday()
    if weekday >= 5:
        weekend_factor = 0.9
    else:
        weekend_factor = 1.0

    data = []
    for dt in time_points:
        hour = dt.hour

        # 基础价格
        if 0 <= hour < 6:
            base = 250 * seasonal_factor  # 深谷
        elif 6 <= hour < 8:
            base = 320 * seasonal_factor  # 早峰前爬坡
        elif 8 <= hour < 12:
            base = 450 * seasonal_factor  # 早高峰
        elif 12 <= hour < 16:
            base = 350 * seasonal_factor  # 午间平段
        elif 16 <= hour < 18:
            base = 380 * seasonal_factor  # 晚峰前爬坡
        elif 18 <= hour < 21:
            base = 520 * seasonal_factor  # 晚高峰
        else:
            base = 300 * seasonal_factor  # 晚间平段

        base *= weekend_factor

        # 如果有实际数据，基于实际价格生成预测（添加8-12%的误差）
        # 如果没有实际数据，使用模拟的基础价格
        if actual_data:
            time_label = dt.strftime("%H:%M")
            actual_point = next((p for p in actual_data if p["datetime"].strftime("%H:%M") == time_label), None)
            if actual_point:
                actual_price = actual_point["avg_clearing_price"]
                # 添加8-12%的预测误差
                error_factor = random.uniform(0.92, 1.08)
                predicted_price = actual_price * error_factor
            else:
                predicted_price = base * random.uniform(0.85, 1.15)
        else:
            predicted_price = base * random.uniform(0.85, 1.15)

        # 置信区间（D-1的置信区间通常比D-2窄一些）
        confidence_80_range = predicted_price * 0.12  # 80%置信区间 ±12%
        confidence_90_range = predicted_price * 0.16  # 90%置信区间 ±16%

        data.append({
            "forecast_id": forecast_id,
            "forecast_type": "d1_price",
            "forecast_date": datetime.strptime(forecast_date_str, "%Y-%m-%d"),
            "target_date": datetime.strptime(target_date_str, "%Y-%m-%d"),
            "datetime": dt,
            "predicted_price": round(predicted_price, 2),
            "confidence_80_lower": round(predicted_price - confidence_80_range, 2),
            "confidence_80_upper": round(predicted_price + confidence_80_range, 2),
            "confidence_90_lower": round(predicted_price - confidence_90_range, 2),
            "confidence_90_upper": round(predicted_price + confidence_90_range, 2),
            "model_type": "d1_price_model",
            "model_version": "v1.0.0",
            "created_at": datetime.strptime(f"{forecast_date_str} {forecast_time}", "%Y-%m-%d %H:%M"),
        })

    return data


def calculate_accuracy_metrics(target_date: datetime, forecast_id: str) -> Dict[str, Any]:
    """计算指定目标日期的预测准确度指标"""
    target_date_str = target_date.strftime("%Y-%m-%d")

    # 获取预测数据
    forecast_collection = DATABASE["price_forecast_results"]
    forecast_docs = list(forecast_collection.find({
        "forecast_id": forecast_id,
        "target_date": {
            "$gte": target_date.replace(hour=0, minute=0, second=0, microsecond=0),
            "$lt": target_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        }
    }).sort("datetime", ASCENDING))

    if not forecast_docs:
        logger.warning(f"未找到目标日期 {target_date_str} 的预测数据")
        return None

    # 获取实际价格
    actual_collection = DATABASE["day_ahead_spot_price"]
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    actual_docs = list(actual_collection.find({
        "datetime": {"$gte": start_of_day, "$lt": end_of_day}
    }).sort("datetime", ASCENDING))

    logger.info(f"  目标日期: {target_date_str}, 预测点数: {len(forecast_docs)}, 实际点数: {len(actual_docs)}")

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
        logger.warning(f"  目标日期 {target_date_str}: 没有匹配的预测和实际数据")
        return None

    # 计算指标
    mae = sum(abs_errors) / len(abs_errors)
    rmse = (sum(e ** 2 for e in abs_errors) / len(abs_errors)) ** 0.5

    # MAPE
    sum_abs_actual = sum(abs(actual) for actual in actual_prices.values())
    mape = (sum(abs_errors) / sum_abs_actual) * 100 if sum_abs_actual != 0 else 0

    # WMAPE准确度
    wmape_accuracy = max(0, 100 - mape)

    # 方向准确度
    if len(errors) > 1:
        correct_direction = sum(1 for i in range(1, len(errors)) if (errors[i] >= 0) == (errors[i-1] >= 0))
        direction_accuracy = (correct_direction / (len(errors) - 1)) * 100
    else:
        direction_accuracy = 0

    # 分时段准确度（根据时段划分）
    period_accuracy = {}
    time_to_period = {
        (0, 6): "低谷",
        (6, 8): "爬坡",
        (8, 12): "早高峰",
        (12, 16): "平段",
        (16, 18): "爬坡",
        (18, 21): "晚高峰",
        (21, 24): "晚间"
    }

    period_errors = {}  # 存储每个时段的误差
    for doc in forecast_docs:
        hour = doc["datetime"].hour
        time_label = doc["datetime"].strftime("%H:%M")
        predicted = doc["predicted_price"]
        actual = actual_prices.get(time_label)

        if actual is not None:
            for (start, end), period in time_to_period.items():
                if start <= hour < end:
                    if period not in period_errors:
                        period_errors[period] = []
                    period_errors[period].append(abs(actual - predicted))
                    break

    for period, errs in period_errors.items():
        if errs:
            period_mape = (sum(errs) / sum(abs(p) for p in [actual_prices.get(f"{h:02d}:00") for h in range(24)] if p)) * 100
            period_accuracy[period] = max(0, 100 - period_mape)

    # 统计特征
    if actual_prices:
        prices_list = list(actual_prices.values())
        stats = {
            "max_value": max(prices_list),
            "min_value": min(prices_list),
            "mean_value": sum(prices_list) / len(prices_list),
            "has_negative": any(p < 0 for p in prices_list)
        }
    else:
        stats = {}

    # 达标判断
    rate_90_pass = wmape_accuracy >= 90
    rate_85_pass = wmape_accuracy >= 85

    # R² Score (简化计算)
    y_mean = sum(abs(p) for p in actual_prices.values()) / len(actual_prices) if actual_prices else 1
    ss_tot = sum((abs(p) - y_mean) ** 2 for p in actual_prices.values()) if actual_prices else 1
    ss_res = sum((e ** 2 for e in errors))
    r2_score = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0

    return {
        "forecast_id": forecast_id,
        "target_date": target_date_str,
        "forecast_type": "d1_price",
        "customer_id": "system",
        "forecast_date": target_date - timedelta(days=1),
        "model_type": "d1_price_model",
        "model_version": "v1.0.0",
        "wmape_accuracy": round(wmape_accuracy, 2),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "mape": round(mape, 2),
        "direction_accuracy": round(direction_accuracy, 2),
        "period_accuracy": period_accuracy,
        "stats": stats,
        "rate_90_pass": rate_90_pass,
        "rate_85_pass": rate_85_pass,
        "r2_score": round(r2_score, 3),
        "calculated_at": datetime.now(),
    }


def init_d1_forecast_data():
    """初始化D-1价格预测数据"""
    logger.info(f"开始生成D-1价格预测数据：{START_DATE.strftime('%Y-%m-%d')} 到 {END_DATE.strftime('%Y-%m-%d')}")

    # 清空现有D-1预测数据
    logger.info("清空现有D-1预测数据...")
    DATABASE["price_forecast_results"].delete_many({"forecast_type": "d1_price"})
    DATABASE["forecast_accuracy_daily"].delete_many({
        "forecast_type": "d1_price",
        "customer_id": "system"
    })
    logger.info("数据清空完成")

    total_days = (END_DATE - START_DATE).days + 1
    processed_days = 0
    current_date = START_DATE

    # 1. 生成预测数据
    logger.info("\n[1/2] 生成D-1价格预测数据...")
    while current_date <= END_DATE:
        # 获取实际价格数据（用于生成更真实的预测）
        target_date = current_date + timedelta(days=1)
        actual_collection = DATABASE["day_ahead_spot_price"]
        actual_docs = list(actual_collection.find({
            "datetime": {
                "$gte": target_date.replace(hour=0, minute=0, second=0, microsecond=0),
                "$lt": target_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
            }
        }).sort("datetime", ASCENDING))

        try:
            forecast_data = generate_d1_forecast_batch(current_date, actual_docs)
            if forecast_data:
                DATABASE["price_forecast_results"].insert_many(forecast_data)
                logger.info(f"  预测日期: {current_date.strftime('%Y-%m-%d')}, 目标日期: {target_date.strftime('%Y-%m-%d')}, 插入 {len(forecast_data)} 条")
            processed_days += 1

            if processed_days % 10 == 0:
                logger.info(f"  进度: {processed_days}/{total_days}")
        except Exception as e:
            logger.error(f"生成预测数据失败: {current_date.strftime('%Y-%m-%d')}, 错误: {e}", exc_info=True)

        current_date += timedelta(days=1)

    logger.info(f"  预测数据生成完成: {DATABASE['price_forecast_results'].count_documents({'forecast_type': 'd1_price'})} 条")

    # 2. 生成准确度统计
    logger.info("\n[2/2] 生成准确度统计数据...")
    current_target = START_DATE + timedelta(days=1)  # 第一个有实际值的目标日期
    accuracy_records = []
    processed_accuracy = 0

    while current_target <= END_DATE:
        forecast_date = current_target - timedelta(days=1)
        forecast_id = f"D1_{forecast_date.strftime('%Y%m%d')}_0900"

        metrics = calculate_accuracy_metrics(current_target, forecast_id)
        if metrics:
            accuracy_records.append(metrics)
            processed_accuracy += 1

            if processed_accuracy % 10 == 0:
                logger.info(f"  进度: {current_target.strftime('%Y-%m-%d')} ({processed_accuracy}/{total_days})")

        current_target += timedelta(days=1)

    if accuracy_records:
        DATABASE["forecast_accuracy_daily"].insert_many(accuracy_records)
        logger.info(f"  准确度统计生成完成: {len(accuracy_records)} 条")

        # 计算平均准确度
        avg_accuracy = sum(r["wmape_accuracy"] for r in accuracy_records) / len(accuracy_records)
        best = max(accuracy_records, key=lambda x: x["wmape_accuracy"])
        worst = min(accuracy_records, key=lambda x: x["wmape_accuracy"])

        logger.info(f"  平均准确度: {avg_accuracy:.2f}%")
        logger.info(f"  最佳准确度: {best['wmape_accuracy']:.2f}% ({best['target_date']})")
        logger.info(f"  最低准确度: {worst['wmape_accuracy']:.2f}% ({worst['target_date']})")
    else:
        logger.warning("  未生成任何准确度统计记录")

    # 最终统计
    logger.info("\n" + "=" * 60)
    logger.info("D-1价格预测数据生成完成！")
    logger.info("=" * 60)
    logger.info("\n数据统计:")
    logger.info(f"  - price_forecast_results (d1_price): {DATABASE['price_forecast_results'].count_documents({'forecast_type': 'd1_price'})} 条")
    logger.info(f"  - forecast_accuracy_daily (d1_price): {DATABASE['forecast_accuracy_daily'].count_documents({'forecast_type': 'd1_price', 'customer_id': 'system'})} 条")


if __name__ == "__main__":
    init_d1_forecast_data()
