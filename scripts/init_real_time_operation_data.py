#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
实时运行数据初始化脚本

生成 actual_operation 和 real_time_generation 集合的模拟数据：
- actual_operation: 实际运行数据（系统负荷、联络线潮流）
- real_time_generation: 实时发电数据（风电、光伏、水电、抽蓄、储能）
"""

import sys
import random
from pathlib import Path
from datetime import datetime, timedelta
from typing import List, Dict

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from webapp.tools.mongo import DATABASE


def generate_time_points(resolution: int = 96) -> List[str]:
    """生成时间点标签"""
    time_points = []
    minutes_per_point = 24 * 60 // resolution

    for i in range(resolution):
        total_minutes = i * minutes_per_point
        hour = total_minutes // 60
        minute = total_minutes % 60
        time_points.append(f"{hour:02d}:{minute:02d}")

    return time_points


def generate_actual_operation_date(date_str: str, resolution: int = 96) -> List[Dict]:
    """
    生成单日的实际运行数据

    Args:
        date_str: 日期字符串 YYYY-MM-DD
        resolution: 时间分辨率

    Returns:
        数据文档列表
    """
    time_points = generate_time_points(resolution)
    documents = []

    for time_str in time_points:
        # 解析时间
        parts = time_str.split(":")
        hour = int(parts[0])

        # 基础负荷水平（MW）- 略高于预测
        base_load = 50000

        # 日内负荷波动模式
        if 0 <= hour < 6:
            hour_factor = 0.62 + 0.1 * (hour / 6)
        elif 6 <= hour < 9:
            hour_factor = 0.82 + 0.25 * ((hour - 6) / 3)
        elif 9 <= hour < 17:
            if 11 <= hour < 13:
                hour_factor = 1.08
            else:
                hour_factor = 1.03 + 0.05 * ((hour - 9) / 8)
        elif 17 <= hour < 21:
            hour_factor = 1.18 + 0.1 * ((hour - 17) / 4)
        else:  # 21 <= hour < 24
            hour_factor = 1.03 - 0.2 * ((hour - 21) / 3)

        # 添加随机波动（±8%）
        random_factor = random.uniform(0.92, 1.08)

        # 系统负荷（MW）- 实际值可能与预测有偏差
        system_load = base_load * hour_factor * random_factor

        # 联络线潮流（MW）- 可以为正（输入）或负（输出）
        tieline_flow = random.uniform(-2500, 3200)

        documents.append({
            "date_str": date_str,
            "time_str": time_str,
            "system_load": round(system_load, 2),
            "tieline_flow": round(tieline_flow, 2)
        })

    return documents


def generate_real_time_generation_date(date_str: str, resolution: int = 96) -> List[Dict]:
    """
    生成单日的实时发电数据

    Args:
        date_str: 日期字符串 YYYY-MM-DD
        resolution: 时间分辨率

    Returns:
        数据文档列表
    """
    time_points = generate_time_points(resolution)
    documents = []

    for time_str in time_points:
        # 解析时间
        parts = time_str.split(":")
        hour = int(parts[0])

        # 风电（MW）- 随机波动
        wind_generation = random.uniform(1800, 8500)

        # 光伏（MW）- 白天有输出
        if 6 <= hour < 19:
            if 10 <= hour < 14:
                solar_factor = 1.0
            elif 6 <= hour < 10:
                solar_factor = 0.3 + 0.7 * ((hour - 6) / 4)
            else:  # 14 <= hour < 19
                solar_factor = 1.0 - 0.8 * ((hour - 14) / 5)
            solar_generation = 5200 * solar_factor * random.uniform(0.9, 1.1)
        else:
            solar_generation = 0

        # 水电（MW）
        hydro_generation = random.uniform(3000, 6000)

        # 抽蓄（MW）- 可以为正（发电）或负（抽水）
        if 0 <= hour < 6 or 22 <= hour < 24:
            # 夜间抽水（负值）
            pumped_storage = -random.uniform(1000, 2000)
        elif 11 <= hour < 14 or 17 <= hour < 21:
            # 高峰发电（正值）
            pumped_storage = random.uniform(500, 1500)
        else:
            # 其他时段小幅波动
            pumped_storage = random.uniform(-500, 500)

        # 电池储能（MW）- 可以为正（放电）或负（充电）
        if 0 <= hour < 5:
            # 夜间充电（负值）
            battery_storage = -random.uniform(200, 500)
        elif 10 <= hour < 15 or 18 <= hour < 21:
            # 高峰放电（正值）
            battery_storage = random.uniform(150, 400)
        else:
            battery_storage = random.uniform(-100, 100)

        documents.append({
            "date_str": date_str,
            "time_str": time_str,
            "wind_generation": round(wind_generation, 2),
            "solar_generation": round(solar_generation, 2),
            "hydro_generation": round(hydro_generation, 2),
            "pumped_storage_generation": round(pumped_storage, 2),
            "battery_storage_generation": round(battery_storage, 2)
        })

    return documents


def init_real_time_data(
    start_date: str = "2024-01-01",
    end_date: str = "2025-12-31",
    resolution: int = 96,
    clear_existing: bool = False,
    append_mode: bool = False
):
    """
    初始化实时运行数据

    Args:
        start_date: 开始日期
        end_date: 结束日期
        resolution: 时间分辨率
        clear_existing: 是否清空现有数据
        append_mode: 追加模式（在现有数据基础上添加）
    """
    print("="*80)
    print("实时运行数据初始化脚本")
    print("="*80)

    # 解析日期
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # 计算天数
    total_days = (end - start).days + 1
    print(f"\n生成数据范围: {start_date} ~ {end_date} (共 {total_days} 天)")
    print(f"时间分辨率: {resolution} 点/天")

    # 获取集合
    actual_op_collection = DATABASE["actual_operation"]
    rt_gen_collection = DATABASE["real_time_generation"]

    # 检查现有数据
    actual_op_count = actual_op_collection.count_documents({})
    rt_gen_count = rt_gen_collection.count_documents({})

    print(f"\n现有数据:")
    print(f"  actual_operation: {actual_op_count} 条")
    print(f"  real_time_generation: {rt_gen_count} 条")

    if actual_op_count > 0 or rt_gen_count > 0:
        if clear_existing:
            print("\n[警告] 正在清空现有数据...")
            actual_op_collection.delete_many({})
            rt_gen_collection.delete_many({})
            print("已清空")
        elif append_mode:
            print("\n[追加模式] 在现有数据基础上追加新数据")
            # 检查重叠
            existing_dates = set(actual_op_collection.distinct("date_str"))
            overlap = []
            current = start
            while current <= end:
                date_str = current.strftime("%Y-%m-%d")
                if date_str in existing_dates:
                    overlap.append(date_str)
                current += timedelta(days=1)
            if overlap:
                print(f"[警告] 以下日期的数据已存在，将被跳过: {overlap[:5]}{'...' if len(overlap) > 5 else ''}")
        else:
            print("\n[错误] 集合中已存在数据，请使用 --clear 选项清空后重新生成，或使用 --append 选项追加数据")
            return

    # 生成数据
    print(f"\n开始生成数据...")
    generated_actual = 0
    generated_rt_gen = 0
    skipped_days = 0

    current_date = start
    batch_size = 100
    actual_batch = []
    rt_gen_batch = []

    # 获取已存在的日期（用于追加模式）
    existing_dates = set(actual_op_collection.distinct("date_str")) if append_mode else set()

    for day_num in range(total_days):
        date_str = current_date.strftime("%Y-%m-%d")

        # 追加模式下跳过已存在的日期
        if append_mode and date_str in existing_dates:
            skipped_days += 1
            current_date += timedelta(days=1)
            continue

        # 生成数据
        actual_docs = generate_actual_operation_date(date_str, resolution)
        rt_gen_docs = generate_real_time_generation_date(date_str, resolution)

        actual_batch.extend(actual_docs)
        rt_gen_batch.extend(rt_gen_docs)
        generated_actual += len(actual_docs)
        generated_rt_gen += len(rt_gen_docs)

        # 批量插入
        if len(actual_batch) >= batch_size:
            actual_op_collection.insert_many(actual_batch)
            actual_batch.clear()

        if len(rt_gen_batch) >= batch_size:
            rt_gen_collection.insert_many(rt_gen_batch)
            rt_gen_batch.clear()

        # 进度显示
        if (day_num + 1) % 30 == 0:
            print(f"  已处理 {day_num + 1}/{total_days} 天...")

        current_date += timedelta(days=1)

    # 插入剩余数据
    if actual_batch:
        actual_op_collection.insert_many(actual_batch)
    if rt_gen_batch:
        rt_gen_collection.insert_many(rt_gen_batch)

    print(f"\n[成功] 数据生成完成!")
    print(f"  actual_operation: {generated_actual} 条")
    print(f"  real_time_generation: {generated_rt_gen} 条")
    if skipped_days > 0:
        print(f"  跳过已存在: {skipped_days} 天")

    # 创建索引
    print("\n创建索引...")
    actual_op_collection.create_index([("date_str", 1), ("time_str", 1)], unique=True)
    rt_gen_collection.create_index([("date_str", 1), ("time_str", 1)], unique=True)
    print("[成功] 索引创建完成")


def verify_data():
    """验证数据"""
    print("\n" + "="*80)
    print("数据验证")
    print("="*80)

    actual_op_collection = DATABASE["actual_operation"]
    rt_gen_collection = DATABASE["real_time_generation"]

    # 统计总数
    actual_total = actual_op_collection.count_documents({})
    rt_gen_total = rt_gen_collection.count_documents({})

    print(f"\nactual_operation: {actual_total} 条")
    print(f"real_time_generation: {rt_gen_total} 条")

    # 日期范围
    actual_dates = sorted(actual_op_collection.distinct("date_str"))
    rt_gen_dates = sorted(rt_gen_collection.distinct("date_str"))

    print(f"\nactual_operation 日期范围: {actual_dates[0] if actual_dates else '无'} ~ {actual_dates[-1] if actual_dates else '无'} ({len(actual_dates)} 天)")
    print(f"real_time_generation 日期范围: {rt_gen_dates[0] if rt_gen_dates else '无'} ~ {rt_gen_dates[-1] if rt_gen_dates else '无'} ({len(rt_gen_dates)} 天)")

    # 示例数据
    print(f"\n示例数据 (2024-01-15 12:00):")
    actual_sample = actual_op_collection.find_one({"date_str": "2024-01-15", "time_str": "12:00"})
    if actual_sample:
        print(f"  actual_operation: 系统负荷={actual_sample['system_load']:.2f}MW, 联络线={actual_sample['tieline_flow']:.2f}MW")

    rt_gen_sample = rt_gen_collection.find_one({"date_str": "2024-01-15", "time_str": "12:00"})
    if rt_gen_sample:
        print(f"  real_time_generation: 风电={rt_gen_sample['wind_generation']:.2f}MW, "
              f"光伏={rt_gen_sample['solar_generation']:.2f}MW, 水电={rt_gen_sample['hydro_generation']:.2f}MW")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="初始化实时运行数据")
    parser.add_argument("--start", default="2024-01-01", help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", default="2025-12-31", help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--resolution", type=int, default=96, choices=[24, 48, 96], help="时间分辨率")
    parser.add_argument("--clear", action="store_true", help="清空现有数据")
    parser.add_argument("--append", action="store_true", help="追加模式（在现有数据基础上添加）")

    args = parser.parse_args()

    try:
        init_real_time_data(
            start_date=args.start,
            end_date=args.end,
            resolution=args.resolution,
            clear_existing=args.clear,
            append_mode=args.append
        )
        verify_data()
        print("\n[成功] 初始化完成！")
    except Exception as e:
        print(f"\n[失败] 初始化失败: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
