"""
生成D-2价格预测准确度统计数据
基于已有的价格预测结果和实际价格数据
"""

import logging
from datetime import datetime, timedelta
from pymongo import ASCENDING

from webapp.tools.mongo import DATABASE

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


def calculate_accuracy_metrics(target_date: datetime) -> dict:
    """
    计算指定目标日期的预测准确度指标
    """
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
        logger.warning(f"未找到目标日期 {target_date_str} 的预测数据")
        return None

    # 获取实际价格
    actual_collection = DATABASE["day_ahead_spot_price"]
    start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
    end_of_day = start_of_day + timedelta(days=1)

    actual_docs = list(actual_collection.find({
        "datetime": {"$gt": start_of_day, "$lte": end_of_day}
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
    predicted_values = []

    for doc in forecast_docs:
        time_label = doc["datetime"].strftime("%H:%M")
        predicted = doc["predicted_price"]
        predicted_values.append(predicted)
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

    # 方向准确度（简化计算）
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


def generate_accuracy_stats():
    """生成准确度统计数据"""
    logger.info("开始生成D-2价格预测准确度统计")

    # 清空现有准确度数据
    DATABASE["forecast_accuracy_daily"].delete_many({
        "forecast_type": "d2_price",
        "customer_id": "system"
    })

    # 确定日期范围
    end_date = datetime.now() - timedelta(days=1)
    start_date = end_date - timedelta(days=28)  # 生成最近29天的准确度统计

    logger.info(f"统计范围: {start_date.strftime('%Y-%m-%d')} 到 {end_date.strftime('%Y-%m-%d')}")

    accuracy_records = []
    current_date = start_date
    processed = 0

    while current_date <= end_date:
        metrics = calculate_accuracy_metrics(current_date)
        if metrics:
            accuracy_records.append(metrics)
            processed += 1

        current_date += timedelta(days=1)

    if accuracy_records:
        DATABASE["forecast_accuracy_daily"].insert_many(accuracy_records)
        logger.info(f"\n准确度统计生成完成！共 {processed} 天")

        # 计算平均准确度
        avg_accuracy = sum(r["wmape_accuracy"] for r in accuracy_records) / len(accuracy_records)
        logger.info(f"平均准确度: {avg_accuracy:.2f}%")

        # 最佳和最差
        best = max(accuracy_records, key=lambda x: x["wmape_accuracy"])
        worst = min(accuracy_records, key=lambda x: x["wmape_accuracy"])
        logger.info(f"最佳准确度: {best['wmape_accuracy']:.2f}% ({best['target_date']})")
        logger.info(f"最低准确度: {worst['wmape_accuracy']:.2f}% ({worst['target_date']})")
    else:
        logger.warning("未生成任何准确度统计记录")


if __name__ == "__main__":
    generate_accuracy_stats()
