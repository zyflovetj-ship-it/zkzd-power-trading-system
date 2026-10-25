#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
国网代购电价数据初始化脚本

生成国网代购电价的模拟数据，包含：
- 代理购电价格
- 平均上网电价
- 代理购电规模
- 历史偏差折价
- 上网环节线损
- 系统运行费折价
- 价格构成详情
- PDF附件（可选）
"""

import sys
import random
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from webapp.tools.mongo import DATABASE


def generate_price_composition(purchase_price: float, avg_on_grid_price: float) -> List[List]:
    """
    生成价格构成详情表格

    Args:
        purchase_price: 代理购电价格
        avg_on_grid_price: 平均上网电价

    Returns:
        价格构成二维数组
    """
    # 价格构成项（模拟真实电价构成）
    composition = [
        ["项目", "金额（元/千瓦时）"],
        ["一、代理购电价格", f"{purchase_price:.4f}"],
        ["  1. 平均上网电价", f"{avg_on_grid_price:.4f}"],
        ["  2. 上网环节线损费用", f"{avg_on_grid_price * 0.065:.4f}"],
        ["  3. 抽水蓄能容量电费", f"{0.008:.4f}"],
        ["  4. 输配电价（含交叉补贴）", f"{0.152:.4f}"],
        ["  5. 政府性基金及附加", f"{0.0086:.4f}"],
    ]

    return composition


def generate_sgcc_price_month(
    year: int,
    month: int,
    include_pdf: bool = False
) -> Dict:
    """
    生成单月的国网代购电价数据

    Args:
        year: 年份
        month: 月份
        include_pdf: 是否包含PDF附件

    Returns:
        数据文档
    """
    # 月份ID
    month_id = f"{year}-{month:02d}"

    # 基础价格水平（元/kWh，转换为元/MWh需乘1000）
    base_price = 0.45  # 0.45元/kWh

    # 季节性调整（冬季较高，夏季较低）
    if month in [12, 1, 2]:
        season_factor = 1.1
    elif month in [6, 7, 8]:
        season_factor = 0.9
    else:
        season_factor = 1.0

    # 随机波动
    random_factor = random.uniform(0.95, 1.05)

    # 计算代理购电价格（元/kWh）
    purchase_price = base_price * season_factor * random_factor

    # 平均上网电价（约为代理购电价格的70%）
    avg_on_grid_price = purchase_price * random.uniform(0.68, 0.72)

    # 代理购电规模（MWh）
    base_scale = 1000000  # 100万MWh基础规模
    purchase_scale_kwh = base_scale * random.uniform(0.8, 1.2) * (1.2 if month in [1, 7, 8] else 1.0)

    # 历史偏差折价（元/MWh）
    historical_deviation_discount = random.uniform(-5, 5)

    # 上网环节线损（元/MWh，约为上网电价的6.5%）
    network_loss_price = avg_on_grid_price * 1000 * 0.065

    # 系统运行费折价（元/MWh）
    system_op_cost_discount = random.uniform(-2, 2)

    # 生成价格构成详情
    price_composition = generate_price_composition(purchase_price, avg_on_grid_price)

    # 附件名称
    attachment_name = f"{year}年{month}月电网代理购电价格公告.pdf"

    # 构建文档
    document = {
        "_id": month_id,
        "purchase_price": round(purchase_price * 1000, 2),  # 转换为元/MWh
        "avg_on_grid_price": round(avg_on_grid_price * 1000, 2),  # 转换为元/MWh
        "purchase_scale_kwh": round(purchase_scale_kwh, 2),
        "historical_deviation_discount": round(historical_deviation_discount, 2),
        "network_loss_price": round(network_loss_price, 2),
        "system_op_cost_discount": round(system_op_cost_discount, 2),
        "attachment_name": attachment_name,
        "full_data": {
            "price_composition": price_composition
        }
    }

    # 可选：添加PDF附件（模拟的二进制数据）
    if include_pdf:
        # 模拟PDF数据（实际使用时应从真实PDF文件读取）
        pdf_content = f"模拟PDF内容 - {attachment_name}".encode('utf-8')
        document["pdf_binary_data"] = pdf_content

    return document


def init_sgcc_price_data(
    start_year: int = 2023,
    end_year: int = 2024,
    include_pdf: bool = False,
    clear_existing: bool = False,
    append_mode: bool = False
):
    """
    初始化国网代购电价数据

    Args:
        start_year: 开始年份
        end_year: 结束年份
        include_pdf: 是否包含PDF附件
        clear_existing: 是否清空现有数据
        append_mode: 追加模式（在现有数据基础上添加）
    """
    print("="*80)
    print("国网代购电价数据初始化脚本")
    print("="*80)

    # 计算月数
    total_months = (end_year - start_year + 1) * 12
    print(f"\n生成数据范围: {start_year}-01 ~ {end_year}-12 (共 {total_months} 个月)")
    print(f"包含PDF附件: {'是' if include_pdf else '否'}")

    # 获取集合
    collection = DATABASE["price_sgcc"]

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
            existing_months = set(collection.distinct("_id"))
            overlap = []
            for year in range(start_year, end_year + 1):
                for month in range(1, 13):
                    month_id = f"{year}-{month:02d}"
                    if month_id in existing_months:
                        overlap.append(month_id)
            if overlap:
                print(f"[警告] 以下月份的数据已存在，将被跳过: {overlap[:5]}{'...' if len(overlap) > 5 else ''}")
        else:
            print("\n[错误] 集合中已存在数据，请使用 --clear 选项清空后重新生成，或使用 --append 选项追加数据")
            return

    # 生成数据
    print(f"\n开始生成数据...")

    documents = []
    skipped_months = 0

    # 获取已存在的月份（用于追加模式）
    existing_months = set(collection.distinct("_id")) if append_mode else set()

    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            month_id = f"{year}-{month:02d}"

            # 追加模式下跳过已存在的月份
            if append_mode and month_id in existing_months:
                skipped_months += 1
                continue

            doc = generate_sgcc_price_month(year, month, include_pdf)
            documents.append(doc)

    # 插入数据
    if documents:
        collection.insert_many(documents)

    print(f"[成功] 数据生成完成! 共生成 {len(documents)} 条数据")
    if skipped_months > 0:
        print(f"  跳过已存在: {skipped_months} 个月")

    # 创建索引
    print("\n创建索引...")
    # _id 字段默认已有唯一索引，无需手动创建
    collection.create_index("purchase_price")
    collection.create_index("avg_on_grid_price")
    print("[成功] 索引创建完成")


def verify_data():
    """验证数据"""
    print("\n" + "="*80)
    print("数据验证")
    print("="*80)

    collection = DATABASE["price_sgcc"]

    # 统计总数
    total = collection.count_documents({})
    print(f"\n数据总量: {total} 条")

    # 月份范围
    months = sorted(collection.distinct("_id"))
    print(f"月份范围: {months[0] if months else '无'} ~ {months[-1] if months else '无'}")

    # 统计价格范围
    price_stats = list(collection.aggregate([
        {"$group": {
            "_id": None,
            "min_purchase_price": {"$min": "$purchase_price"},
            "max_purchase_price": {"$max": "$purchase_price"},
            "avg_purchase_price": {"$avg": "$purchase_price"},
            "min_on_grid_price": {"$min": "$avg_on_grid_price"},
            "max_on_grid_price": {"$max": "$avg_on_grid_price"},
            "avg_on_grid_price": {"$avg": "$avg_on_grid_price"}
        }}
    ]))

    print(f"\n价格统计 (元/MWh):")
    if price_stats:
        stats = price_stats[0]
        print(f"  代理购电价格: 最小={stats['min_purchase_price']:.2f}, 最大={stats['max_purchase_price']:.2f}, 平均={stats['avg_purchase_price']:.2f}")
        print(f"  平均上网电价: 最小={stats['min_on_grid_price']:.2f}, 最大={stats['max_on_grid_price']:.2f}, 平均={stats['avg_on_grid_price']:.2f}")

    # 示例数据
    print(f"\n示例数据 (最近3个月):")
    sample_data = list(collection.find({}, {"pdf_binary_data": 0}).sort("_id", -1).limit(3))

    for doc in sample_data:
        print(f"\n  月份: {doc['_id']}")
        print(f"    代理购电价格: {doc['purchase_price']:.2f} 元/MWh")
        print(f"    平均上网电价: {doc['avg_on_grid_price']:.2f} 元/MWh")
        print(f"    代理购电规模: {doc['purchase_scale_kwh']:.2f} MWh")
        print(f"    历史偏差折价: {doc['historical_deviation_discount']:.2f} 元/MWh")
        print(f"    上网环节线损: {doc['network_loss_price']:.2f} 元/MWh")
        print(f"    系统运行费折价: {doc['system_op_cost_discount']:.2f} 元/MWh")
        print(f"    附件名称: {doc['attachment_name']}")

        # 显示价格构成
        if "full_data" in doc and "price_composition" in doc["full_data"]:
            print(f"    价格构成:")
            for row in doc["full_data"]["price_composition"]:
                print(f"      {row[0]:20s}: {row[1]}")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="初始化国网代购电价数据")
    parser.add_argument("--start-year", type=int, default=2023, help="开始年份")
    parser.add_argument("--end-year", type=int, default=2024, help="结束年份")
    parser.add_argument("--include-pdf", action="store_true", help="是否包含PDF附件（模拟数据）")
    parser.add_argument("--clear", action="store_true", help="清空现有数据")
    parser.add_argument("--append", action="store_true", help="追加模式（在现有数据基础上添加）")

    args = parser.parse_args()

    try:
        init_sgcc_price_data(
            start_year=args.start_year,
            end_year=args.end_year,
            include_pdf=args.include_pdf,
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
