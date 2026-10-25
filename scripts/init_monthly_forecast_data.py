"""
生成月度价格预测模拟数据
生成最近6个月的月度预测数据，包括预测结果和准确度统计
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
START_MONTH = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) - timedelta(days=150)  # 5个月前
END_MONTH = datetime.now().replace(day=1, hour=0, minute=0, second=0, microsecond=0) + timedelta(days=90)  # 3个月后


def get_days_in_month(year: int, month: int) -> int:
    """获取指定月份的天数"""
    if month == 12:
        next_month = datetime(year + 1, 1, 1)
    else:
        next_month = datetime(year, month + 1, 1)
    this_month = datetime(year, month, 1)
    return (next_month - this_month).days


def generate_monthly_forecast_batch(
    forecast_date: datetime,
    target_year: int,
    target_month: int,
    version_suffix: str
) -> Dict[str, Any]:
    """生成月度价格预测批次数据"""
    forecast_id = f"MONTHLY_{forecast_date.strftime('%Y%m%d')}_{version_suffix}"

    # 获取目标月份的天数
    days_in_month = get_days_in_month(target_year, target_month)

    # 季节因子
    if target_month in [1, 2, 12]:  # 冬季
        seasonal_factor = 1.15
    elif target_month in [6, 7, 8]:  # 夏季
        seasonal_factor = 1.10
    else:
        seasonal_factor = 1.0

    # 生成每日预测数据
    daily_predictions = []
    for day in range(1, days_in_month + 1):
        date = datetime(target_year, target_month, day)

        # 基础价格（添加随机波动）
        base_mean = 380 * seasonal_factor * random.uniform(0.9, 1.1)
        base_max = base_mean * random.uniform(1.4, 1.8)
        base_min = base_mean * random.uniform(0.3, 0.6)
        base_peak = base_mean * random.uniform(1.2, 1.5)
        base_valley = base_mean * random.uniform(0.6, 0.8)

        # 添加周末因子
        weekday = date.weekday()
        if weekday >= 5:
            weekend_factor = 0.9
        else:
            weekend_factor = 1.0

        price_mean = base_mean * weekend_factor
        price_max = base_max * weekend_factor
        price_min = base_min * weekend_factor
        price_peak = base_peak * weekend_factor
        price_valley = base_valley * weekend_factor

        # 置信区间
        confidence_80_range = price_mean * 0.15  # 80%置信区间 ±15%
        confidence_90_range = price_mean * 0.20  # 90%置信区间 ±20%

        daily_predictions.append({
            "date": date.strftime("%Y-%m-%d"),
            "datetime": date,
            "price_max": round(price_max, 2),
            "price_min": round(price_min, 2),
            "price_mean": round(price_mean, 2),
            "price_peak": round(price_peak, 2),
            "price_valley": round(price_valley, 2),
            "confidence_80_lower": round(price_mean - confidence_80_range, 2),
            "confidence_80_upper": round(price_mean + confidence_80_range, 2),
            "confidence_90_lower": round(price_mean - confidence_90_range, 2),
            "confidence_90_upper": round(price_mean + confidence_90_range, 2),
        })

    return {
        "forecast_id": forecast_id,
        "forecast_type": "monthly_price",
        "forecast_date": forecast_date,
        "target_month": {
            "year": target_year,
            "month": target_month
        },
        "daily_predictions": daily_predictions,
        "model_type": "monthly_xgboost_v2",
        "model_version": "v2.1.0",
        "created_at": forecast_date,
        "created_by": "system",
        "status": "active"
    }


def calculate_monthly_accuracy(
    forecast_id: str,
    target_year: int,
    target_month: int
) -> Dict[str, Any]:
    """计算月度预测准确度指标"""
    # 获取预测数据
    forecast_collection = DATABASE["monthly_price_forecast"]
    forecast_doc = forecast_collection.find_one({"forecast_id": forecast_id})

    if not forecast_doc:
        logger.warning(f"未找到预测记录: {forecast_id}")
        return None

    # 获取目标月份的实际价格数据
    actual_collection = DATABASE["day_ahead_spot_price"]
    start_of_month = datetime(target_year, target_month, 1)
    days_in_month = get_days_in_month(target_year, target_month)
    end_of_month = datetime(target_year, target_month, days_in_month, 23, 59, 59)

    actual_docs = list(actual_collection.find({
        "datetime": {"$gte": start_of_month, "$lte": end_of_month}
    }).sort("datetime", ASCENDING))

    if not actual_docs:
        logger.warning(f"未找到 {target_year}-{target_month:02d} 的实际价格数据")
        return None

    # 聚合实际价格为日度统计
    actual_daily_stats = {}
    for doc in actual_docs:
        date_str = doc["datetime"].strftime("%Y-%m-%d")
        price = doc["avg_clearing_price"]

        if date_str not in actual_daily_stats:
            actual_daily_stats[date_str] = {
                "prices": [],
                "max": price,
                "min": price,
                "sum": 0,
                "count": 0
            }

        stats = actual_daily_stats[date_str]
        stats["prices"].append(price)
        stats["max"] = max(stats["max"], price)
        stats["min"] = min(stats["min"], price)
        stats["sum"] += price
        stats["count"] += 1

    # 计算每日实际均值
    for date_str, stats in actual_daily_stats.items():
        stats["mean"] = stats["sum"] / stats["count"]

    # 匹配预测和实际数据，计算误差
    errors = []
    abs_errors = []
    period_errors = {"高峰": [], "平段": [], "低谷": []}

    for pred_day in forecast_doc["daily_predictions"]:
        pred_date_str = pred_day["date"]
        actual_stats = actual_daily_stats.get(pred_date_str)

        if actual_stats:
            pred_mean = pred_day["price_mean"]
            actual_mean = actual_stats["mean"]

            error = actual_mean - pred_mean
            abs_error = abs(error)
            errors.append(error)
            abs_errors.append(abs_error)

            # 分时段准确度（简化版本，使用小时判断）
            hour = datetime.strptime(pred_date_str, "%Y-%m-%d").hour
            if 8 <= hour < 12 or 18 <= hour < 21:
                period_errors["高峰"].append(abs_error)
            elif 0 <= hour < 6 or 21 <= hour < 24:
                period_errors["低谷"].append(abs_error)
            else:
                period_errors["平段"].append(abs_error)

    if not errors:
        logger.warning(f"{target_year}-{target_month:02d}: 没有匹配的预测和实际数据")
        return None

    # 计算整体指标
    mae = sum(abs_errors) / len(abs_errors)
    rmse = (sum(e ** 2 for e in abs_errors) / len(abs_errors)) ** 0.5

    sum_abs_actual = sum(abs(s["mean"]) for s in actual_daily_stats.values())
    mape = (sum(abs_errors) / sum_abs_actual) * 100 if sum_abs_actual != 0 else 0
    wmape_accuracy = max(0, 100 - mape)

    # 方向准确率
    if len(errors) > 1:
        correct_direction = sum(1 for i in range(1, len(errors)) if (errors[i] >= 0) == (errors[i-1] >= 0))
        direction_accuracy = (correct_direction / (len(errors) - 1)) * 100
    else:
        direction_accuracy = 0

    # 分时段准确度
    period_accuracy = {}
    for period, errs in period_errors.items():
        if errs:
            period_mape = (sum(errs) / sum_abs_actual) * 100
            period_accuracy[period] = max(0, 100 - period_mape)

    # 统计特征
    all_prices = []
    for stats in actual_daily_stats.values():
        all_prices.extend(stats["prices"])

    stats = {
        "max_value": max(all_prices) if all_prices else 0,
        "min_value": min(all_prices) if all_prices else 0,
        "mean_value": sum(all_prices) / len(all_prices) if all_prices else 0,
        "has_negative": any(p < 0 for p in all_prices),
        "volatility": (max(all_prices) - min(all_prices)) / sum(all_prices) * len(all_prices) if all_prices and sum(all_prices) != 0 else 0
    }

    # 日度误差分布
    daily_errors = []
    for pred_day in forecast_doc["daily_predictions"]:
        pred_date_str = pred_day["date"]
        actual_stats = actual_daily_stats.get(pred_date_str)

        if actual_stats:
            pred_mean = pred_day["price_mean"]
            actual_mean = actual_stats["mean"]
            daily_mape = abs((actual_mean - pred_mean) / actual_mean) * 100 if actual_mean != 0 else 0
            daily_errors.append({
                "date": pred_date_str,
                "mape": round(daily_mape, 2)
            })

    # 达标判断
    rate_90_pass = wmape_accuracy >= 90
    rate_85_pass = wmape_accuracy >= 85

    # R² Score
    if all_prices:
        y_mean = sum(all_prices) / len(all_prices)
        ss_tot = sum((p - y_mean) ** 2 for p in all_prices)
        ss_res = sum(e ** 2 for e in errors)
        r2_score = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
    else:
        r2_score = 0

    return {
        "forecast_id": forecast_id,
        "forecast_type": "monthly_price",
        "customer_id": "system",
        "target_month": {
            "year": target_year,
            "month": target_month
        },
        "mape": round(mape, 2),
        "wmape_accuracy": round(wmape_accuracy, 2),
        "mae": round(mae, 2),
        "rmse": round(rmse, 2),
        "direction_accuracy": round(direction_accuracy, 2),
        "period_accuracy": period_accuracy,
        "stats": stats,
        "rate_90_pass": rate_90_pass,
        "rate_85_pass": rate_85_pass,
        "r2_score": round(r2_score, 3),
        "daily_errors": daily_errors,
        "calculated_at": datetime.now()
    }


def init_monthly_forecast_data():
    """初始化月度价格预测数据"""
    logger.info(f"开始生成月度价格预测数据")

    # 清空现有数据
    logger.info("清空现有月度预测数据...")
    DATABASE["monthly_price_forecast"].delete_many({})
    DATABASE["forecast_accuracy_monthly"].delete_many({})
    logger.info("数据清空完成")

    # 生成月份范围
    current_month = START_MONTH
    forecast_count = 0
    accuracy_count = 0

    # 1. 生成预测数据
    logger.info("\n[1/2] 生成月度价格预测数据...")
    while current_month <= END_MONTH:
        target_year = current_month.year
        target_month = current_month.month

        # 每个月生成 2-3 个版本
        num_versions = random.randint(2, 3)
        for i in range(num_versions):
            # 预测日期：月初前 7-3 天
            forecast_date = current_month - timedelta(days=random.randint(3, 7))
            version_suffix = f"v{i}_0" if i == 0 else f"v{i}_{random.randint(0, 2)}"

            forecast_data = generate_monthly_forecast_batch(
                forecast_date,
                target_year,
                target_month,
                version_suffix
            )

            DATABASE["monthly_price_forecast"].insert_one(forecast_data)
            forecast_count += 1

            logger.info(
                f"  目标月份: {target_year}-{target_month:02d}, "
                f"版本: {forecast_data['forecast_id']}"
            )

        current_month = (current_month.replace(day=1) + timedelta(days=32)).replace(day=1)

    logger.info(f"  预测数据生成完成: {forecast_count} 条")

    # 2. 生成准确度统计（只为已过去的月份）
    logger.info("\n[2/2] 生成准确度统计数据...")
    current_month = START_MONTH
    now = datetime.now()

    while current_month < now.replace(day=1):
        target_year = current_month.year
        target_month = current_month.month

        # 获取该月份的最新预测版本
        forecast_docs = list(DATABASE["monthly_price_forecast"].find({
            "target_month.year": target_year,
            "target_month.month": target_month
        }).sort("forecast_date", -1).limit(1))

        if forecast_docs:
            forecast_id = forecast_docs[0]["forecast_id"]
            accuracy_data = calculate_monthly_accuracy(
                forecast_id,
                target_year,
                target_month
            )

            if accuracy_data:
                DATABASE["forecast_accuracy_monthly"].insert_one(accuracy_data)
                accuracy_count += 1

                logger.info(
                    f"  目标月份: {target_year}-{target_month:02d}, "
                    f"MAPE: {accuracy_data['mape']:.2f}%, "
                    f"准确度: {accuracy_data['wmape_accuracy']:.2f}%"
                )

        current_month = (current_month.replace(day=1) + timedelta(days=32)).replace(day=1)

    logger.info(f"  准确度统计生成完成: {accuracy_count} 条")

    if accuracy_count > 0:
        # 计算平均准确度
        accuracy_docs = list(DATABASE["forecast_accuracy_monthly"].find())
        avg_accuracy = sum(d["wmape_accuracy"] for d in accuracy_docs) / len(accuracy_docs)
        best = max(accuracy_docs, key=lambda x: x["wmape_accuracy"])
        worst = min(accuracy_docs, key=lambda x: x["wmape_accuracy"])

        logger.info(f"\n  平均准确度: {avg_accuracy:.2f}%")
        logger.info(f"  最佳准确度: {best['wmape_accuracy']:.2f}% ({best['target_month']['year']}-{best['target_month']['month']:02d})")
        logger.info(f"  最低准确度: {worst['wmape_accuracy']:.2f}% ({worst['target_month']['year']}-{worst['target_month']['month']:02d})")

    # 最终统计
    logger.info("\n" + "=" * 60)
    logger.info("月度价格预测数据生成完成！")
    logger.info("=" * 60)
    logger.info("\n数据统计:")
    logger.info(f"  - monthly_price_forecast: {DATABASE['monthly_price_forecast'].count_documents({})} 条")
    logger.info(f"  - forecast_accuracy_monthly: {DATABASE['forecast_accuracy_monthly'].count_documents({})} 条")


if __name__ == "__main__":
    init_monthly_forecast_data()
