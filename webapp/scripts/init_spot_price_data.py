"""
模拟日前/实时现货电价数据生成脚本

生成最近 7 天、每天 96 点的电价数据，写入：
    - day_ahead_spot_price （日前）
    - real_time_spot_price  （实时）

用途：结算、利润、风险敞口、趋势分析、合同价格对比等接口都依赖电价，
     缺电价时这些接口虽然能查到电量，但金额恒为 0。

字段契约（与 init_actual_load_data.py 同理，双写）：
    - 规范字段（docs/spec/后端开发规范.md §5.1.1）：timestamp / value
      —— forecast_accuracy、profit_analysis、retail/wholesale_settlement、
         risk_exposure、trend_analysis 按此查询
    - 历史字段：datetime / avg_clearing_price / date_str / time_str
      —— contract_price_trend、price_forecast、spot_price、spot_review、
         monthly/day_ahead_price_forecast 按此查询
    TODO: 待读取方全部统一到 timestamp/value 后，删除冗余字段。

24:00 处理（规范 §5.3）：业务日第 96 个点存为次日 00:00，
time_str 仍标记为 "24:00" 以表达业务含义。
"""

import logging
import math
import os
import random
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List

# 添加项目根目录到 Python 路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from webapp.tools.mongo import DATABASE  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 模拟数据标识，便于与未来导入的真实数据区分
SIMULATION_FLAG = "system_simulation"

# 价格区间（元/MWh），围绕基准价上下波动
BASE_PRICE = 420.0
PRICE_AMPLITUDE = 120.0


def _build_day_prices(target_date: datetime) -> List[Dict[str, Any]]:
    """为指定业务日生成 96 个电价点。

    :param target_date: 业务日（00:00）
    :return: 96 条文档
    """
    documents: List[Dict[str, Any]] = []
    date_str = target_date.strftime("%Y-%m-%d")
    weekday_factor = 1.08 if target_date.weekday() >= 5 else 1.0

    for point_index in range(96):
        # 与负荷脚本一致：第 96 个点（24:00）存为次日 00:00
        minutes = (point_index + 1) * 15
        hours = minutes // 60
        mins = minutes % 60
        if hours == 24:
            point_datetime = (target_date + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            time_str = "24:00"
        else:
            point_datetime = target_date.replace(
                hour=hours, minute=mins, second=0, microsecond=0
            )
            time_str = f"{hours:02d}:{mins:02d}"

        # 电价与负荷正相关：早晚高峰价格高，深夜低谷价格低
        time_factor = math.sin((point_index / 96) * 2 * math.pi - math.pi / 2)
        morning_peak = 0.0
        if 28 <= point_index <= 36:  # 07:00-09:00
            morning_peak = 45 * math.sin((point_index - 28) / 8 * math.pi)
        evening_peak = 0.0
        if 68 <= point_index <= 80:  # 17:00-20:00
            evening_peak = 60 * math.sin((point_index - 68) / 12 * math.pi)

        price = (
            BASE_PRICE
            + PRICE_AMPLITUDE * time_factor * weekday_factor
            + morning_peak
            + evening_peak
            + random.uniform(-15, 15)
        )
        price = round(max(180.0, min(780.0, price)), 2)

        common = {
            # 规范字段（§5.1.1）
            "timestamp": point_datetime,
            "value": price,
            # 历史兼容字段
            "datetime": point_datetime,
            "avg_clearing_price": price,
            # 业务标识
            "date_str": date_str,
            "time_str": time_str,
            "data_source": SIMULATION_FLAG,
        }
        documents.append(common)

    return documents


def generate_spot_price_data(days: int = 90) -> None:
    """生成最近 N 天的日前与实时电价数据。"""
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    dates = [today - timedelta(days=i) for i in range(days - 1, -1, -1)]

    for collection_name, price_type in (
        ("day_ahead_spot_price", "day_ahead"),
        ("real_time_spot_price", "real_time"),
    ):
        collection = DATABASE[collection_name]

        # 只清理模拟数据，避免误删未来导入的真实数据
        removed = collection.delete_many({"data_source": SIMULATION_FLAG})
        logger.info("[%s] 清理旧模拟数据 %d 条", collection_name, removed.deleted_count)

        documents: List[Dict[str, Any]] = []
        for target_date in dates:
            day_docs = _build_day_prices(target_date)
            for doc in day_docs:
                doc["price_type"] = price_type
            documents.extend(day_docs)

        logger.info("[%s] 插入 %d 条记录", collection_name, len(documents))
        collection.insert_many(documents)

        # 索引：按键判断，避免 IndexOptionsConflict（重跑脚本时不再报错）
        try:
            existing = list(collection.list_indexes())
            existing_keys = {
                tuple(idx.get("key", {}).items()) for idx in existing
            }
            for keys in (
                [("timestamp", 1)],
                [("datetime", 1)],
                [("date_str", 1)],
            ):
                if tuple(keys) not in existing_keys:
                    collection.create_index(keys)
                    existing_keys.add(tuple(keys))
            logger.info("[%s] 索引就绪", collection_name)
        except Exception as exc:
            logger.warning("[%s] 索引创建失败（不影响数据）: %s", collection_name, exc)


def verify_data() -> bool:
    """验证数据是否写入成功。"""
    ok = True
    for collection_name in ("day_ahead_spot_price", "real_time_spot_price"):
        collection = DATABASE[collection_name]
        total = collection.count_documents({"data_source": SIMULATION_FLAG})
        logger.info("[%s] 模拟数据 %d 条", collection_name, total)
        if total == 0:
            ok = False
            continue

        sample = collection.find_one(
            {"data_source": SIMULATION_FLAG}, {"_id": 0}
        )
        if sample:
            logger.info(
                "  样例: timestamp=%s value=%s date_str=%s time_str=%s",
                sample.get("timestamp"),
                sample.get("value"),
                sample.get("date_str"),
                sample.get("time_str"),
            )

        # 双字段一致性抽查
        if sample and sample.get("timestamp") != sample.get("datetime"):
            logger.error("  ❌ timestamp 与 datetime 不一致")
            ok = False
        if sample and sample.get("value") != sample.get("avg_clearing_price"):
            logger.error("  ❌ value 与 avg_clearing_price 不一致")
            ok = False

    return ok


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("现货电价模拟数据生成脚本")
    logger.info("=" * 60)

    try:
        generate_spot_price_data(days=90)
        if verify_data():
            logger.info("🎉 电价数据生成并验证成功")
        else:
            logger.error("❌ 电价数据验证失败")
            sys.exit(1)
    except Exception:
        logger.error("电价数据生成失败", exc_info=True)
        raise
