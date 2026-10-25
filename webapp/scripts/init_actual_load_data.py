"""
模拟历史真实负荷数据生成脚本

生成最近7天的实际负荷数据（96点/天），用于精度计算
实际数据基于预测数据加上随机偏差生成
"""

import logging
import math
import random
import sys
import os
from datetime import datetime, timedelta
from typing import Any, Dict, List

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from webapp.tools.mongo import DATABASE
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 模拟数据标记：清理与验证一律按它过滤
SIMULATION_FLAG = "system_simulation"
# 96→48 点转换批次号，供 /api/v1/data-validation/transform-manual-data 使用
SIMULATION_BATCH_ID = "SIM_LOAD_2026_10"


def _resolve_customer_ids() -> List[str]:
    """解析负荷数据要挂到哪些客户下。

    结算、利润、风险敞口等接口都按 ``customer_id`` 过滤负荷数据，
    若负荷不关联真实客户，这些接口即使有数据也恒为 0。

    优先使用 customers 集合中状态为 active 的客户；
    一个都没有时回落到 system_simulation（保持脚本在空库上也能独立运行）。
    """
    active = list(DATABASE["customers"].find({"status": "active"}, {"_id": 1}))
    if active:
        ids = [str(doc["_id"]) for doc in active]
        logger.info("关联到 %d 个生效客户: %s", len(ids), ids)
        return ids
    logger.warning("customers 集合无生效客户，负荷数据将挂到 system_simulation")
    return ["system_simulation"]


def generate_actual_load_data():
    """生成实际负荷模拟数据"""

    collection = DATABASE["user_load_data"]

    # 清空现有数据（可选，根据需求决定是否清空）
    # logger.info("清空现有实际负荷数据...")
    # collection.delete_many({})

    # 生成最近7天的实际数据
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    dates = [today - timedelta(days=i) for i in range(89, -1, -1)]

    documents = []

    for target_date in dates:
        logger.info(f"生成日期: {target_date.strftime('%Y-%m-%d')} 的实际负荷数据")

        # 为每一天生成96个时间点
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

            # 生成实际负荷值（与预测数据类似的模式，但添加不同偏差）
            base_load = 450  # 基础负荷 (kW)，单客户日均 ≈ 10.8 MWh，与零售合约量级自洽
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

            # 周末负荷降低
            weekday_factor = 0.85 if target_date.weekday() >= 5 else 1.0

            # 实际值的随机偏差（比预测的偏差更大，模拟实际情况）
            actual_noise = random.uniform(-80, 80)

            actual_value = (
                base_load
                + amplitude * time_factor
                + morning_peak
                + evening_peak
                + actual_noise
            ) * weekday_factor

            # 确保负荷值在合理范围内
            actual_value = max(200, min(750, actual_value))

            # 创建文档
            #
            # 字段契约（重要）：
            #   - 规范字段（docs/spec/后端开发规范.md §5.1.1 强制）：timestamp / value
            #     —— profit / retail / wholesale 结算、预测精度、风险敞口、客户聚类、仪表盘等
            #        8 个服务按此查询
            #   - 历史字段：datetime / load
            #     —— short_term_load_forecast、spot_review 按此查询
            # 此处**同时写入两套**，使两方都能读到数据，避免因字段命名不一致导致
            # 同一份数据在部分接口里"查得到、部分接口恒为 0"。
            # TODO: 待读取方全部统一到 timestamp/value 后，删除 datetime/load 冗余字段。
            point_value = round(actual_value, 2)
            doc = {
                # 规范字段（§5.1.1）
                "timestamp": point_datetime,
                "value": point_value,
                # 历史兼容字段
                "datetime": point_datetime,
                "load": point_value,
                # 业务标识
                "customer_id": "system_simulation",
                "user_id": "system_simulation",
                "user_name": "系统模拟数据",
                "meter_id": "simulation_meter_01",
                # 模拟数据标记：清理/验证一律按它过滤（customer_id 会被改写成真实客户）
                "data_source": SIMULATION_FLAG,
                # 转换批次号：data-validation 的 96→48 点转换按此字段筛选数据
                # （POST /api/v1/data-validation/transform-manual-data）
                "import_batch_id": SIMULATION_BATCH_ID,
                # 时间标签（便于调试）
                "time_str": "24:00" if hours == 24 else f"{hours:02d}:{mins:02d}",
                "date_str": target_date.strftime("%Y-%m-%d")
            }

            documents.append(doc)

    # 按客户展开：每个生效客户都拿到完整的 7 天 × 96 点负荷，
    # 使按 customer_id 过滤的结算/利润/风险接口能取到数据。
    customer_ids = _resolve_customer_ids()
    expanded: List[Dict[str, Any]] = []
    for customer_id in customer_ids:
        for base_doc in documents:
            doc = dict(base_doc)
            doc["customer_id"] = customer_id
            doc["user_id"] = customer_id
            expanded.append(doc)

    # 批量插入数据
    logger.info(
        "插入 %d 条记录到数据库（%d 个客户 × %d 个时点）...",
        len(expanded), len(customer_ids), len(documents),
    )
    collection.insert_many(expanded)
    documents = expanded

    logger.info("✅ 实际负荷模拟数据生成完成！")
    logger.info(f"   - 日期数量: {len(dates)}")
    logger.info(f"   - 总记录数: {len(documents)}")

    # 创建索引
    logger.info("创建索引...")
    try:
        collection.create_index([("datetime", 1)])
        collection.create_index([("user_id", 1), ("meter_id", 1)])
        collection.create_index([("date_str", 1)])
        logger.info("✅ 索引创建成功")
    except Exception as e:
        logger.warning(f"索引创建失败（可能已存在）: {e}")

    # 显示统计信息
    logger.info("\n数据统计:")
    for target_date in dates:
        start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)
        count = collection.count_documents({
            "datetime": {"$gt": start_of_day, "$lte": end_of_day}
        })
        logger.info(f"  {target_date.strftime('%Y-%m-%d')}: {count} 条")


def verify_data():
    """验证数据是否正确插入"""
    collection = DATABASE["user_load_data"]

    logger.info("\n验证数据...")
    # 只统计模拟数据
    total_count = collection.count_documents({"data_source": SIMULATION_FLAG})
    logger.info(f"✅ 模拟数据总记录数: {total_count}")

    if total_count > 0:
        # 查询一条样例数据
        sample = collection.find_one({"data_source": SIMULATION_FLAG}, {"_id": 0})
        if sample:
            logger.info("\n样例数据:")
            logger.info(f"  时间点: {sample.get('timestamp')}")
            logger.info(f"  负荷值: {sample.get('value')} kW")
            logger.info(f"  客户ID: {sample.get('customer_id')}")
            logger.info(f"  电表ID: {sample.get('meter_id')}")
            # 双字段一致性抽查
            if sample.get("timestamp") != sample.get("datetime"):
                logger.error("  ❌ timestamp 与 datetime 不一致")
                return False
            if sample.get("value") != sample.get("load"):
                logger.error("  ❌ value 与 load 不一致")
                return False

    return total_count > 0


def clear_existing_simulation_data():
    """清空已有的模拟数据（保留真实数据）"""
    collection = DATABASE["user_load_data"]

    logger.info("清空旧的模拟数据...")
    # 兼容两种历史标记：新数据用 data_source，早期版本用 user_id
    result = collection.delete_many({
        "$or": [
            {"data_source": SIMULATION_FLAG},
            {"user_id": SIMULATION_FLAG},
        ]
    })
    logger.info(f"✅ 删除了 {result.deleted_count} 条旧记录")


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("实际负荷数据模拟生成脚本")
    logger.info("=" * 60)

    try:
        # 先清空旧的模拟数据
        clear_existing_simulation_data()

        # 生成新数据
        generate_actual_load_data()

        if verify_data():
            logger.info("\n" + "=" * 60)
            logger.info("🎉 数据生成和验证成功！")
            logger.info("=" * 60)
            logger.info("\n现在可以测试 /accuracy 接口了")
            logger.info("示例日期（实际数据存在）: " + (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d"))
        else:
            logger.error("\n❌ 数据验证失败")

    except Exception as e:
        logger.error(f"\n❌ 数据生成失败: {e}", exc_info=True)
        raise
