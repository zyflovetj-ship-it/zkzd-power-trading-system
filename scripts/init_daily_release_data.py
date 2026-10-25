#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
日报发布数据初始化脚本

生成 daily_release 集合的模拟数据，包含：
- 系统负荷预测
- 风电预测
- 光伏预测
- 非市场化机组预测
- 联络线计划
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


def generate_daily_release_date(date_str: str, resolution: int = 96) -> List[Dict]:
    """
    生成单日的日报发布数据

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

        # 基础负荷水平（MW）
        base_load = 50000

        # 日内负荷波动模式
        if 0 <= hour < 6:
            # 夜间低谷
            hour_factor = 0.6 + 0.1 * (hour / 6)
        elif 6 <= hour < 9:
            # 早高峰爬坡
            hour_factor = 0.8 + 0.25 * ((hour - 6) / 3)
        elif 9 <= hour < 17:
            # 日间平段（有午间小高峰）
            if 11 <= hour < 13:
                hour_factor = 1.05
            else:
                hour_factor = 1.0 + 0.05 * ((hour - 9) / 8)
        elif 17 <= hour < 21:
            # 晚高峰
            hour_factor = 1.15 + 0.1 * ((hour - 17) / 4)
        else:  # 21 <= hour < 24
            # 夜间回落
            hour_factor = 1.0 - 0.2 * ((hour - 21) / 3)

        # 添加随机波动（±5%）
        random_factor = random.uniform(0.95, 1.05)

        # 系统负荷预测（MW）
        system_load_forecast = base_load * hour_factor * random_factor

        # 风电预测（MW）- 随机波动较大
        wind_forecast = random.uniform(2000, 8000) * random_factor

        # 光伏预测（MW）- 白天有输出
        if 6 <= hour < 19:
            # 光伏在中午达到峰值
            if 10 <= hour < 14:
                pv_factor = 1.0
            elif 6 <= hour < 10:
                pv_factor = 0.3 + 0.7 * ((hour - 6) / 4)
            else:  # 14 <= hour < 19
                pv_factor = 1.0 - 0.8 * ((hour - 14) / 5)
            pv_forecast = 5000 * pv_factor * random_factor
        else:
            pv_forecast = 0

        # 非市场化机组预测（MW）- 包括水电、抽蓄等
        nonmarket_unit_forecast = system_load_forecast * random.uniform(0.15, 0.25)

        # 联络线计划（MW）- 可以为正（输入）或负（输出）
        tieline_plan = random.uniform(-2000, 3000)

        documents.append({
            "date_str": date_str,
            "time_str": time_str,
            "system_load_forecast": round(system_load_forecast, 2),
            "wind_forecast": round(wind_forecast, 2),
            "pv_forecast": round(pv_forecast, 2),
            "nonmarket_unit_forecast": round(nonmarket_unit_forecast, 2),
            "tieline_plan": round(tieline_plan, 2)
        })

    return documents


def init_daily_release_data(
    start_date: str = "2024-01-01",
    end_date: str = "2025-12-31",
    resolution: int = 96,
    clear_existing: bool = False,
    append_mode: bool = False
):
    """
    初始化日报发布数据

    Args:
        start_date: 开始日期
        end_date: 结束日期
        resolution: 时间分辨率
        clear_existing: 是否清空现有数据
        append_mode: 追加模式（在现有数据基础上添加）
    """
    print("="*80)
    print("日报发布数据初始化脚本")
    print("="*80)

    # 解析日期
    start = datetime.strptime(start_date, "%Y-%m-%d")
    end = datetime.strptime(end_date, "%Y-%m-%d")

    # 计算天数
    total_days = (end - start).days + 1
    print(f"\n生成数据范围: {start_date} ~ {end_date} (共 {total_days} 天)")
    print(f"时间分辨率: {resolution} 点/天")

    # 获取集合
    collection = DATABASE["daily_release"]

    # 检查现有数据
    existing_count = collection.count_documents({})
    print(f"\n现有数据: {existing_count} 条")

    if existing_count > 0:
        if clear_existing:
            print("\n[警告] 正在清空现有数据...")
            collection.delete_many({})
            print("已清空")
        elif append_mode:
            print("\n[追加模式] 在现有数据基础上追加新数据")
            # 检查是否已有重叠数据
            existing_dates = collection.distinct("date_str")
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
    generated = 0
    skipped_days = 0

    current_date = start
    batch_size = 100
    batch = []

    # 获取已存在的日期（用于追加模式）
    existing_dates = set(collection.distinct("date_str")) if append_mode else set()

    for day_num in range(total_days):
        date_str = current_date.strftime("%Y-%m-%d")

        # 追加模式下跳过已存在的日期
        if append_mode and date_str in existing_dates:
            skipped_days += 1
            current_date += timedelta(days=1)
            continue

        # 生成数据
        docs = generate_daily_release_date(date_str, resolution)
        batch.extend(docs)
        generated += len(docs)

        # 批量插入
        if len(batch) >= batch_size:
            collection.insert_many(batch)
            batch.clear()

        # 进度显示
        if (day_num + 1) % 30 == 0:
            print(f"  已处理 {day_num + 1}/{total_days} 天...")

        current_date += timedelta(days=1)

    # 插入剩余数据
    if batch:
        collection.insert_many(batch)

    print(f"\n[成功] 数据生成完成! 共生成 {generated} 条数据")
    if skipped_days > 0:
        print(f"  跳过已存在: {skipped_days} 天")

    # 创建索引
    print("\n创建索引...")
    collection.create_index([("date_str", 1), ("time_str", 1)], unique=True)
    print("[成功] 索引创建完成")


def verify_data():
    """验证数据"""
    print("\n" + "="*80)
    print("数据验证")
    print("="*80)

    collection = DATABASE["daily_release"]

    # 统计总数
    total = collection.count_documents({})
    print(f"\n数据总量: {total} 条")

    # 日期范围
    dates = sorted(collection.distinct("date_str"))
    print(f"日期范围: {dates[0] if dates else '无'} ~ {dates[-1] if dates else '无'} ({len(dates)} 天)")

    # 示例数据
    print(f"\n示例数据 (2024-01-01):")
    sample = list(collection.find({"date_str": "2024-01-01"}).limit(5))
    for doc in sample:
        print(f"  {doc['time_str']}: 负荷={doc['system_load_forecast']:.2f}MW, "
              f"风电={doc['wind_forecast']:.2f}MW, 光伏={doc['pv_forecast']:.2f}MW, "
              f"非市场化={doc['nonmarket_unit_forecast']:.2f}MW, 联络线={doc['tieline_plan']:.2f}MW")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="初始化日报发布数据")
    parser.add_argument("--start", default="2024-01-01", help="开始日期 (YYYY-MM-DD)")
    parser.add_argument("--end", default="2025-12-31", help="结束日期 (YYYY-MM-DD)")
    parser.add_argument("--resolution", type=int, default=96, choices=[24, 48, 96], help="时间分辨率")
    parser.add_argument("--clear", action="store_true", help="清空现有数据")
    parser.add_argument("--append", action="store_true", help="追加模式（在现有数据基础上添加）")

    args = parser.parse_args()

    try:
        init_daily_release_data(
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
