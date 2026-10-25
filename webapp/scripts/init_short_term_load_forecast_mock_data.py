"""
短期负荷预测模拟数据生成脚本

生成最近7天的短期负荷预测数据，包括 d+1, d+2, d+3 三种预测类型
每种预测类型包含96个时间点（15分钟间隔）
"""

import logging
import math
import random
import sys
import os
from datetime import datetime, timedelta

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from webapp.tools.mongo import DATABASE

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def generate_forecast_data():
    """生成短期负荷预测模拟数据"""

    collection = DATABASE["short_term_load_forecast"]

    # 清空现有数据
    logger.info("清空现有短期负荷预测数据...")
    collection.delete_many({})

    # 生成最近7天的预测数据
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    forecast_dates = [today - timedelta(days=i) for i in range(89, -1, -1)]

    forecast_types = ["d+1"]  # 仅 d+1，避免同一 target_date 多套预测造成引擎取数歧义
    documents = []

    for forecast_date in forecast_dates:
        logger.info(f"生成预测日期: {forecast_date.strftime('%Y-%m-%d')} 的数据")

        for forecast_type in forecast_types:
            # 计算预测目标日期
            days_ahead = int(forecast_type.split("+")[1])
            target_date = forecast_date + timedelta(days=days_ahead)

            # 为每个预测类型生成96个时间点
            for point_index in range(96):
                # 计算时间点（15分钟间隔）
                minutes = (point_index + 1) * 15
                hours = minutes // 60
                mins = minutes % 60

                # 处理24:00的情况（第96个点）
                if hours == 24:
                    point_datetime = target_date + timedelta(days=1)
                    point_datetime = point_datetime.replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    point_datetime = target_date.replace(hour=hours, minute=mins, second=0, microsecond=0)

                # 生成模拟的负荷预测值
                # 基于正弦函数模拟日负荷曲线 + 随机噪声
                base_load = 450  # 基础负荷 (kW)，与零售合约量级自洽
                amplitude = 100  # 振幅

                # 日负荷曲线：白天高峰，夜间低谷
                time_factor = math.sin((point_index / 96) * 2 * math.pi - math.pi / 2)

                # 添加早高峰和晚高峰
                morning_peak = 0
                if 28 <= point_index <= 36:  # 07:00-09:00
                    morning_peak = 40 * math.sin((point_index - 28) / 8 * math.pi)

                evening_peak = 0
                if 68 <= point_index <= 80:  # 17:00-20:00
                    evening_peak = 55 * math.sin((point_index - 68) / 12 * math.pi)

                # 预测类型差异（d+1 最准确，d+3 误差最大）
                type_noise = {
                    "d+1": random.uniform(-50, 50),
                    "d+2": random.uniform(-100, 100),
                    "d+3": random.uniform(-150, 150)
                }

                forecast_value = (
                    base_load
                    + amplitude * time_factor
                    + morning_peak
                    + evening_peak
                    + type_noise[forecast_type]
                    + random.uniform(-30, 30)  # 随机噪声
                )

                # 确保负荷值在合理范围内
                forecast_value = max(200, min(750, forecast_value))

                # 创建文档
                #
                # 字段契约（与 init_actual_load_data.py 同理）：
                #   - 规范/通用字段：date / timestamp / value
                #     —— forecast_accuracy_service 按此查询：
                #        find({"date": "YYYY-MM-DD"}, {"value": 1, "timestamp": 1})
                #   - 历史字段：forecast_date / datetime / forecast_value
                #     —— short_term_load_forecast_service 的曲线接口按此查询
                # 同时写入两套，使精度统计与预测曲线两条链路都能取到数据。
                # TODO: 待读取方统一后删除冗余字段。
                point_value = round(forecast_value, 2)
                doc = {
                    "forecast_date": forecast_date,
                    "forecast_type": forecast_type,
                    "datetime": point_datetime,
                    "forecast_value": point_value,
                    # 兼容 forecast_accuracy_service
                    "date": forecast_date.strftime("%Y-%m-%d"),
                    "timestamp": point_datetime,
                    "value": point_value,
                    "created_at": forecast_date.replace(hour=12, minute=0, second=0, microsecond=0)
                }

                documents.append(doc)

    # 批量插入数据
    logger.info(f"插入 {len(documents)} 条记录到数据库...")
    collection.insert_many(documents)

    logger.info("✅ 短期负荷预测模拟数据生成完成！")
    logger.info(f"   - 预测日期数量: {len(forecast_dates)}")
    logger.info(f"   - 预测类型: {', '.join(forecast_types)}")
    logger.info(f"   - 总记录数: {len(documents)}")

    # 创建索引
    logger.info("创建索引...")
    try:
        collection.create_index([("datetime", 1)])
        collection.create_index([("forecast_date", 1), ("forecast_type", 1)])
        logger.info("✅ 索引创建成功")
    except Exception as e:
        logger.warning(f"索引创建失败（可能已存在）: {e}")

    # 显示统计信息
    logger.info("\n数据统计:")
    for forecast_date in forecast_dates:
        for forecast_type in forecast_types:
            count = collection.count_documents({
                "forecast_date": forecast_date,
                "forecast_type": forecast_type
            })
            logger.info(f"  {forecast_date.strftime('%Y-%m-%d')} {forecast_type}: {count} 条")


def verify_data():
    """验证数据是否正确插入"""
    collection = DATABASE["short_term_load_forecast"]

    logger.info("\n验证数据...")
    total_count = collection.count_documents({})
    logger.info(f"✅ 总记录数: {total_count}")

    # 查询一条样例数据
    sample = collection.find_one({}, {"_id": 0})
    if sample:
        logger.info("\n样例数据:")
        logger.info(f"  预测日期: {sample['forecast_date']}")
        logger.info(f"  预测类型: {sample['forecast_type']}")
        logger.info(f"  时间点: {sample['datetime']}")
        logger.info(f"  预测值: {sample['forecast_value']} kW")
        logger.info(f"  创建时间: {sample['created_at']}")

    return total_count > 0


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("短期负荷预测模拟数据生成脚本")
    logger.info("=" * 60)

    try:
        generate_forecast_data()

        if verify_data():
            logger.info("\n" + "=" * 60)
            logger.info("🎉 数据生成和验证成功！")
            logger.info("=" * 60)
        else:
            logger.error("\n❌ 数据验证失败")

    except Exception as e:
        logger.error(f"\n❌ 数据生成失败: {e}", exc_info=True)
        raise
