"""
模拟 RPA 结算读数数据生成脚本

用途：为 data-validation 的"结算曲线"完整度提供源数据。
      结算曲线与手工负荷曲线（load_curve）是两套独立数据源：
        - load_curve        ← user_load_data 96 点经 transform-manual-data 聚合
        - settlement_curve  ← RPA 计量系统读数经 import-rpa-data 聚合
      缺后者时完整度面板会因 min(load, settlement)=0 而恒为 critical。

字段要求（见 DataValidationService.import_rpa_data）：
    rpa_batch_id / customer_id / datetime / load_kw / meter_id /
    mp_id(或 metering_point_id) / allocation_percentage

生成后需调用：
    POST /api/v1/data-validation/import-rpa-data
    body: {"rpa_batch_id": "<批次号>", "source_collection": "rpa_load_data"}
"""

import logging
import math
import os
import random
import sys
from datetime import datetime, timedelta
from typing import Any, Dict, List

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..')))

from webapp.tools.mongo import DATABASE  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

SOURCE_COLLECTION = "rpa_load_data"
SIMULATION_FLAG = "system_simulation"
RPA_BATCH_ID = "SIM_RPA_2026_10"


def _build_day_docs(
    target_date: datetime,
    customer_id: str,
    account_id: str,
    mp_id: str,
    meter_id: str,
) -> List[Dict[str, Any]]:
    """为指定业务日生成 96 条 RPA 计量读数。"""
    documents: List[Dict[str, Any]] = []
    weekday_factor = 0.85 if target_date.weekday() >= 5 else 1.0

    for point_index in range(96):
        minutes = (point_index + 1) * 15
        hours = minutes // 60
        mins = minutes % 60
        if hours == 24:
            point_datetime = (target_date + timedelta(days=1)).replace(
                hour=0, minute=0, second=0, microsecond=0
            )
        else:
            point_datetime = target_date.replace(
                hour=hours, minute=mins, second=0, microsecond=0
            )

        time_factor = math.sin((point_index / 96) * 2 * math.pi - math.pi / 2)
        morning_peak = 40 * math.sin((point_index - 28) / 8 * math.pi) if 28 <= point_index <= 36 else 0
        evening_peak = 55 * math.sin((point_index - 68) / 12 * math.pi) if 68 <= point_index <= 80 else 0

        # 语义：该 15 分钟时段的平均功率(kW)，与 user_load_data 保持一致口径。
        # 量级取自零售合约：日均 ≈ 10.5 MWh => 平均功率 ≈ 450 kW。
        load_kw = (
            450 + 100 * time_factor + morning_peak + evening_peak
            + random.uniform(-30, 30)
        ) * weekday_factor
        load_kw = round(max(200, min(750, load_kw)), 2)

        documents.append({
            "rpa_batch_id": RPA_BATCH_ID,
            "customer_id": customer_id,
            "account_id": account_id,
            "mp_id": mp_id,
            "metering_point_id": mp_id,
            "meter_id": meter_id,
            "allocation_percentage": 100.0,
            "datetime": point_datetime,
            "load_kw": load_kw,
            "data_source": SIMULATION_FLAG,
        })

    return documents


def generate_rpa_data() -> None:
    """按客户实际的计量点生成 RPA 源数据。"""
    source = DATABASE[SOURCE_COLLECTION]

    removed = source.delete_many({"data_source": SIMULATION_FLAG})
    logger.info("清理旧 RPA 模拟数据 %d 条", removed.deleted_count)

    # 直接读客户档案里的计量点，保证与 add_metering_point 创建的结构一致
    customers = list(DATABASE["customers"].find({"status": "active"}))
    if not customers:
        logger.warning("无生效客户，跳过 RPA 数据生成")
        return

    documents: List[Dict[str, Any]] = []
    today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    dates = [today - timedelta(days=i) for i in range(89, -1, -1)]

    for customer in customers:
        customer_id = str(customer["_id"])
        accounts = customer.get("utility_accounts", [])
        if not accounts:
            logger.warning("客户 %s 无户号，跳过", customer_id)
            continue

        for account in accounts:
            account_id = account.get("account_id", "")
            points = account.get("metering_points", []) or [{"metering_point_id": "MP_DEFAULT"}]
            for mp in points:
                mp_id = mp.get("metering_point_id", "MP_DEFAULT")
                meter_id = (mp.get("meter") or {}).get("meter_id", "")
                for target_date in dates:
                    documents.extend(
                        _build_day_docs(target_date, customer_id, account_id, mp_id, meter_id)
                    )

    if not documents:
        logger.warning("未生成任何 RPA 数据")
        return

    source.insert_many(documents)
    logger.info(
        "插入 RPA 源数据 %d 条（%d 个客户, %d 天）",
        len(documents), len(customers), len(dates),
    )

    try:
        existing = list(source.list_indexes())
        existing_keys = {tuple(idx.get("key", {}).items()) for idx in existing}
        for keys in ([("rpa_batch_id", 1)], [("customer_id", 1), ("datetime", 1)]):
            if tuple(keys) not in existing_keys:
                source.create_index(keys)
        logger.info("索引就绪")
    except Exception as exc:
        logger.warning("索引创建失败（不影响数据）: %s", exc)


def verify_data() -> bool:
    total = SOURCE_COLLECTION and DATABASE[SOURCE_COLLECTION].count_documents(
        {"rpa_batch_id": RPA_BATCH_ID}
    )
    logger.info("RPA 批次 %s 共 %d 条", RPA_BATCH_ID, total)
    if total:
        sample = DATABASE[SOURCE_COLLECTION].find_one(
            {"rpa_batch_id": RPA_BATCH_ID}, {"_id": 0}
        )
        if sample:
            logger.info(
                "  样例: customer_id=%s datetime=%s load_kw=%s meter_id=%s",
                sample.get("customer_id"),
                sample.get("datetime"),
                sample.get("load_kw"),
                sample.get("meter_id"),
            )
    return bool(total)


if __name__ == "__main__":
    logger.info("=" * 60)
    logger.info("RPA 结算读数模拟数据生成脚本")
    logger.info("=" * 60)
    try:
        generate_rpa_data()
        if verify_data():
            logger.info("🎉 RPA 数据生成成功，可调用 import-rpa-data 导入结算曲线")
        else:
            logger.error("❌ RPA 数据验证失败")
            sys.exit(1)
    except Exception:
        logger.error("RPA 数据生成失败", exc_info=True)
        raise
