#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""检查价格数据集合情况"""

import sys
from pathlib import Path

# 添加项目根目录到 Python 路径
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

import json
from webapp.tools.mongo import DATABASE

def main():
    # 获取所有集合名称
    collections = DATABASE.list_collection_names()

    # 筛选价格相关的集合
    price_collections = [c for c in collections if 'price' in c.lower() or 'spot' in c.lower()]

    print('价格相关集合及文档数量:')
    print('='*60)
    for col in price_collections:
        count = DATABASE[col].count_documents({})
        print(f'{col}: {count} documents')

    # 查看日前和实时现货价格的数据样本
    print()
    print('='*60)
    print('日前现货价格数据样本 (day_ahead_spot_price):')
    sample_da = DATABASE['day_ahead_spot_price'].find_one()
    if sample_da:
        print(json.dumps(sample_da, indent=2, ensure_ascii=False, default=str))
        # 统计日期范围
        dates = DATABASE['day_ahead_spot_price'].distinct('date_str')
        print(f'日期范围: {min(dates) if dates else "无"} ~ {max(dates) if dates else "无"}')
        print(f'覆盖天数: {len(dates)} 天')
    else:
        print('无数据')

    print()
    print('='*60)
    print('实时现货价格数据样本 (real_time_spot_price):')
    sample_rt = DATABASE['real_time_spot_price'].find_one()
    if sample_rt:
        print(json.dumps(sample_rt, indent=2, ensure_ascii=False, default=str))
        # 统计日期范围
        dates = DATABASE['real_time_spot_price'].distinct('date_str')
        print(f'日期范围: {min(dates) if dates else "无"} ~ {max(dates) if dates else "无"}')
        print(f'覆盖天数: {len(dates)} 天')
    else:
        print('无数据')

    print()
    print('='*60)
    print('国网代购电价数据样本 (price_sgcc):')
    sample_sgcc = DATABASE['price_sgcc'].find_one()
    if sample_sgcc:
        # 只显示主要字段
        display = {k:v for k,v in sample_sgcc.items() if k not in ['pdf_binary_data', 'full_data']}
        print(json.dumps(display, indent=2, ensure_ascii=False, default=str))
        # 统计月份范围
        months = DATABASE['price_sgcc'].distinct('_id')
        print(f'月份范围: {min(months) if months else "无"} ~ {max(months) if months else "无"}')
        print(f'覆盖月数: {len(months)} 月')
    else:
        print('无数据')

if __name__ == '__main__':
    main()
