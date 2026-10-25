#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
为现货价格数据添加电源类型详细信息

为 day_ahead_spot_price 和 real_time_spot_price 集合添加以下字段：
- thermal_clearing_power（火电）
- hydro_clearing_power（水电）
- wind_clearing_power（风电）
- solar_clearing_power（光伏）
- pumped_storage_clearing_power（抽蓄）
- battery_storage_clearing_power（电池储能）

这些电源的出力总和应等于 total_clearing_power
"""

import sys
import random
from pathlib import Path
from datetime import datetime
from pymongo import UpdateOne

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from webapp.tools.mongo import DATABASE


def update_spot_price_with_generation_details(
    collection_name: str = "day_ahead_spot_price",
    clear_existing_details: bool = False
):
    """
    为现货价格数据添加电源类型详细信息

    Args:
        collection_name: 集合名称
        clear_existing_details: 是否清空现有的电源类型数据
    """
    print("="*80)
    print(f"为 {collection_name} 添加电源类型详细信息")
    print("="*80)

    collection = DATABASE[collection_name]

    # 检查是否已有电源类型数据
    has_generation_data = collection.count_documents({
        "thermal_clearing_power": {"$exists": True}
    })

    if has_generation_data > 0:
        print(f"\n现有数据: {has_generation_data} 条记录已包含电源类型数据")
        if clear_existing_details:
            print("[警告] 正在清空现有的电源类型数据...")
            collection.update_many(
                {"thermal_clearing_power": {"$exists": True}},
                {"$unset": {
                    "thermal_clearing_power": "",
                    "hydro_clearing_power": "",
                    "wind_clearing_power": "",
                    "solar_clearing_power": "",
                    "pumped_storage_clearing_power": "",
                    "battery_storage_clearing_power": ""
                }}
            )
            print("已清空")
        else:
            print("[错误] 部分数据已包含电源类型信息，请使用 --clear 选项清空后重新生成，或使用 --update 选项仅更新缺失的数据")
            return

    # 查询所有需要更新的数据
    total_docs = collection.count_documents({})
    query = {
        "$or": [
            {"thermal_clearing_power": {"$exists": False}},
            {"thermal_clearing_power": None}
        ]
    }
    docs_to_update = list(collection.find(query))

    print(f"\n需要更新的记录: {len(docs_to_update)}/{total_docs}")

    if len(docs_to_update) == 0:
        print("[成功] 所有数据已包含电源类型信息")
        return

    # 批量更新
    print("\n开始更新数据...")
    batch_size = 1000
    updated_count = 0

    for i in range(0, len(docs_to_update), batch_size):
        batch = docs_to_update[i:i + batch_size]
        bulk_operations = []

        for doc in batch:
            total_power = doc.get("total_clearing_power", 0)
            time_str = doc.get("time_str", "")

            # 解析时间用于确定光伏出力
            parts = time_str.split(":")
            hour = int(parts[0]) if len(parts) >= 2 else 0

            # 根据时间和总电量分配各电源出力
            # 基础比例（可根据实际情况调整）
            thermal_ratio = 0.5  # 火电占50%
            hydro_ratio = 0.15   # 水电占15%
            wind_ratio = 0.20    # 风电占20%
            solar_ratio = 0.10   # 光伏占10%（白天更高）
            pumped_ratio = 0.03  # 抽蓄占3%
            battery_ratio = 0.02 # 电池储能占2%

            # 根据时间调整光伏比例
            if 6 <= hour < 19:
                if 10 <= hour < 14:
                    # 中午光伏高峰
                    solar_ratio = 0.20
                    thermal_ratio = 0.40
                elif 6 <= hour < 10:
                    # 上午光伏爬坡
                    solar_factor = (hour - 6) / 4
                    solar_ratio = 0.05 + 0.10 * solar_factor
                    thermal_ratio = 0.50 - 0.05 * solar_factor
                else:
                    # 下午光伏回落
                    solar_factor = 1 - (hour - 14) / 5
                    solar_ratio = 0.05 + 0.15 * solar_factor
                    thermal_ratio = 0.50 - 0.05 * solar_factor
            else:
                solar_ratio = 0
                thermal_ratio = 0.55

            # 添加随机波动（±10%）
            def apply_variation(value):
                return value * random.uniform(0.9, 1.1)

            thermal = apply_variation(total_power * thermal_ratio)
            hydro = apply_variation(total_power * hydro_ratio)
            wind = apply_variation(total_power * wind_ratio)
            solar = apply_variation(total_power * solar_ratio) if solar_ratio > 0 else 0
            pumped = apply_variation(total_power * pumped_ratio)
            battery = apply_variation(total_power * battery_ratio)

            # 更新操作
            bulk_operations.append(
                UpdateOne(
                    {"_id": doc["_id"]},
                    {"$set": {
                        "thermal_clearing_power": round(thermal, 2),
                        "hydro_clearing_power": round(hydro, 2),
                        "wind_clearing_power": round(wind, 2),
                        "solar_clearing_power": round(solar, 2),
                        "pumped_storage_clearing_power": round(pumped, 2),
                        "battery_storage_clearing_power": round(battery, 2)
                    }}
                )
            )

        # 执行批量更新
        if bulk_operations:
            collection.bulk_write(bulk_operations)
            updated_count += len(bulk_operations)

        # 进度显示
        if (i + batch_size) % 5000 == 0 or (i + batch_size) >= len(docs_to_update):
            print(f"  已更新 {min(i + batch_size, len(docs_to_update))}/{len(docs_to_update)} 条记录...")

    print(f"\n[成功] 数据更新完成! 共更新 {updated_count} 条记录")


def verify_update(collection_name: str = "day_ahead_spot_price"):
    """验证更新结果"""
    print("\n" + "="*80)
    print("数据验证")
    print("="*80)

    collection = DATABASE[collection_name]

    # 统计包含电源类型数据的记录数
    has_generation = collection.count_documents({
        "thermal_clearing_power": {"$exists": True, "$ne": None}
    })

    total = collection.count_documents({})

    print(f"\n{collection_name}:")
    print(f"  总记录数: {total}")
    print(f"  包含电源类型数据: {has_generation}")
    print(f"  覆盖率: {has_generation/total*100:.1f}%")

    # 示例数据
    print(f"\n示例数据 (2024-01-15 12:00):")
    sample = collection.find_one({
        "date_str": "2024-01-15",
        "time_str": "12:00"
    })

    if sample:
        print(f"  总电量: {sample.get('total_clearing_power', 0):.2f} MWh")
        print(f"  火电: {sample.get('thermal_clearing_power', 0):.2f} MWh")
        print(f"  水电: {sample.get('hydro_clearing_power', 0):.2f} MWh")
        print(f"  风电: {sample.get('wind_clearing_power', 0):.2f} MWh")
        print(f"  光伏: {sample.get('solar_clearing_power', 0):.2f} MWh")
        print(f"  抽蓄: {sample.get('pumped_storage_clearing_power', 0):.2f} MWh")
        print(f"  电池储能: {sample.get('battery_storage_clearing_power', 0):.2f} MWh")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="为现货价格数据添加电源类型详细信息")
    parser.add_argument("--collection", default="day_ahead_spot_price",
                       choices=["day_ahead_spot_price", "real_time_spot_price", "both"],
                       help="要更新的集合名称")
    parser.add_argument("--clear", action="store_true", help="清空现有的电源类型数据")
    parser.add_argument("--update", action="store_true", help="仅更新缺失的数据（不清空现有数据）")

    args = parser.parse_args()

    try:
        collections_to_update = []
        if args.collection == "both":
            collections_to_update = ["day_ahead_spot_price", "real_time_spot_price"]
        else:
            collections_to_update = [args.collection]

        for collection_name in collections_to_update:
            update_spot_price_with_generation_details(
                collection_name=collection_name,
                clear_existing_details=args.clear
            )
            verify_update(collection_name)

        print("\n[成功] 更新完成！")
    except Exception as e:
        print(f"\n[失败] 更新失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
