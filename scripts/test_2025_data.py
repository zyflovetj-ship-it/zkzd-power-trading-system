#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""测试2025年价格数据"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from webapp.tools.mongo import DATABASE


def main():
    print("="*80)
    print("2025年价格数据验证")
    print("="*80)

    # 检查现货价格数据
    da_collection = DATABASE["day_ahead_spot_price"]
    rt_collection = DATABASE["real_time_spot_price"]

    # 2025年日前现货数据统计
    da_2025_count = da_collection.count_documents({"date_str": {"$regex": "^2025-"}})
    rt_2025_count = rt_collection.count_documents({"date_str": {"$regex": "^2025-"}})

    print(f"\n2025年现货价格数据:")
    print(f"  日前现货: {da_2025_count} 条 (预期: 365天 × 96点/天 = 35040 条)")
    print(f"  实时现货: {rt_2025_count} 条 (预期: 365天 × 96点/天 = 35040 条)")

    # 验证日期范围
    da_2025_dates = sorted(da_collection.distinct("date_str", {"date_str": {"$regex": "^2025-"}}))
    rt_2025_dates = sorted(rt_collection.distinct("date_str", {"date_str": {"$regex": "^2025-"}}))

    print(f"\n2025年日期范围:")
    print(f"  日前现货: {da_2025_dates[0] if da_2025_dates else '无'} ~ {da_2025_dates[-1] if da_2025_dates else '无'} ({len(da_2025_dates)} 天)")
    print(f"  实时现货: {rt_2025_dates[0] if rt_2025_dates else '无'} ~ {rt_2025_dates[-1] if rt_2025_dates else '无'} ({len(rt_2025_dates)} 天)")

    # 价格统计
    da_2025_stats = list(da_collection.aggregate([
        {"$match": {"date_str": {"$regex": "^2025-"}}},
        {"$group": {
            "_id": None,
            "min_price": {"$min": "$avg_clearing_price"},
            "max_price": {"$max": "$avg_clearing_price"},
            "avg_price": {"$avg": "$avg_clearing_price"}
        }}
    ]))

    rt_2025_stats = list(rt_collection.aggregate([
        {"$match": {"date_str": {"$regex": "^2025-"}}},
        {"$group": {
            "_id": None,
            "min_price": {"$min": "$avg_clearing_price"},
            "max_price": {"$max": "$avg_clearing_price"},
            "avg_price": {"$avg": "$avg_clearing_price"}
        }}
    ]))

    print(f"\n2025年价格统计 (元/MWh):")
    if da_2025_stats:
        stats = da_2025_stats[0]
        print(f"  日前现货: 最小={stats['min_price']:.2f}, 最大={stats['max_price']:.2f}, 平均={stats['avg_price']:.2f}")
    if rt_2025_stats:
        stats = rt_2025_stats[0]
        print(f"  实时现货: 最小={stats['min_price']:.2f}, 最大={stats['max_price']:.2f}, 平均={stats['avg_price']:.2f}")

    # 检查国网代购电价数据
    sgcc_collection = DATABASE["price_sgcc"]
    sgcc_2025_count = sgcc_collection.count_documents({"_id": {"$regex": "^2025-"}})
    sgcc_2025_months = sorted(sgcc_collection.distinct("_id", {"_id": {"$regex": "^2025-"}}))

    print(f"\n2025年国网代购电价数据:")
    print(f"  记录数: {sgcc_2025_count} 条 (预期: 12个月)")
    print(f"  月份范围: {sgcc_2025_months[0] if sgcc_2025_months else '无'} ~ {sgcc_2025_months[-1] if sgcc_2025_months else '无'}")

    # 示例数据
    if sgcc_2025_months:
        sample = sgcc_collection.find_one({"_id": sgcc_2025_months[0]})
        print(f"\n2025年1月示例数据:")
        print(f"  代理购电价格: {sample['purchase_price']:.2f} 元/MWh")
        print(f"  平均上网电价: {sample['avg_on_grid_price']:.2f} 元/MWh")

    # 验证总结
    print("\n" + "="*80)
    print("验证总结")
    print("="*80)

    checks = [
        (da_2025_count == 35040, f"日前现货数据完整: {da_2025_count}/35040 条"),
        (rt_2025_count == 35040, f"实时现货数据完整: {rt_2025_count}/35040 条"),
        (len(da_2025_dates) == 365, f"日前现货日期完整: {len(da_2025_dates)}/365 天"),
        (len(rt_2025_dates) == 365, f"实时现货日期完整: {len(rt_2025_dates)}/365 天"),
        (sgcc_2025_count == 12, f"国网代购电价完整: {sgcc_2025_count}/12 个月")
    ]

    all_passed = True
    for passed, message in checks:
        status = "[✓]" if passed else "[✗]"
        print(f"{status} {message}")
        if not passed:
            all_passed = False

    if all_passed:
        print("\n[成功] 2025年价格数据验证全部通过！")
    else:
        print("\n[警告] 2025年价格数据验证存在问题，请检查！")


if __name__ == "__main__":
    main()
