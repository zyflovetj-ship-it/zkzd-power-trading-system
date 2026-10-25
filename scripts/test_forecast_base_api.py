"""
测试预测基础数据 API
"""

import sys
sys.path.insert(0, '.')

from datetime import datetime, timedelta
from webapp.tools.mongo import DATABASE
from webapp.services.forecast_base_data_service import ForecastBaseDataService

def test_forecast_base_data_api():
    """测试预测基础数据 API"""
    print("=" * 60)
    print("测试预测基础数据 API")
    print("=" * 60)

    service = ForecastBaseDataService(DATABASE)

    # 测试 1: 数据可用性查询（最近3天）
    print("\n[测试 1] 获取数据可用性矩阵（最近3天）")
    base_date = datetime.now()
    try:
        result = service.get_data_availability(base_date, "recent_3")
        print(f"[OK] 基准日期: {result['base_date']}")
        print(f"[OK] 日期范围: {result['date_range']}")
        print(f"[OK] 数据项数量: {len(result['availability_matrix'])} 行")
        print(f"[OK] 每行日期数: {len(result['availability_matrix'][0])} 列")

        # 统计可用性
        total_cells = 15 * len(result['date_range'])
        available_cells = sum(
            1 for row in result['availability_matrix']
            for cell in row
            if cell['is_available']
        )
        print(f"[OK] 数据可用性: {available_cells}/{total_cells} ({available_cells*100//total_cells}%)")
    except Exception as e:
        print(f"[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()

    # 测试 2: 单条曲线查询
    print("\n[测试 2] 获取单条曲线数据（短期系统负荷预测）")
    test_date = datetime.now() - timedelta(days=1)  # 使用昨天的日期
    try:
        curve = service.get_curve_data(6, test_date)  # 短期系统负荷预测
        print(f"[OK] 数据项ID: {curve['data_item_id']}")
        print(f"[OK] 数据项名称: {curve['data_item_name']}")
        print(f"[OK] 日期: {curve['date']}")
        print(f"[OK] 数据点数: {curve['total_points']}/96")
        print(f"[OK] 完整度: {curve['completeness']}%")
        if curve['data']:
            print(f"[OK] 首点数据: {curve['data'][0]}")
            print(f"[OK] 末点数据: {curve['data'][-1]}")
    except Exception as e:
        print(f"[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()

    # 测试 3: 多条曲线查询
    print("\n[测试 3] 批量获取曲线数据")
    requests = [
        {"data_item_id": 1, "date": test_date.strftime("%Y-%m-%d")},
        {"data_item_id": 6, "date": test_date.strftime("%Y-%m-%d")},
        {"data_item_id": 11, "date": test_date.strftime("%Y-%m-%d")},
    ]
    try:
        curves = service.get_multiple_curves(requests)
        print(f"[OK] 获取曲线数: {len(curves['curves'])}")
        for curve in curves['curves']:
            print(f"  - [{curve['data_item_id']}] {curve['data_item_name']}: {curve['total_points']}/96 点, 完整度 {curve['completeness']}%")
    except Exception as e:
        print(f"[ERROR] 错误: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print("测试完成！")
    print("=" * 60)


if __name__ == "__main__":
    test_forecast_base_data_api()
