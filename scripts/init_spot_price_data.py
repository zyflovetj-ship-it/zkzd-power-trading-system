"""
生成日前现货价格数据（用于测试D-2价格预测）
生成最近30天的实际价格数据
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random

from webapp.tools.mongo import DATABASE

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


# 配置参数
START_DATE = datetime.now() - timedelta(days=30)  # D-30
END_DATE = datetime.now() - timedelta(days=1)     # D-1


def generate_time_points(date: datetime) -> List[datetime]:
    """生成指定日期的96个时间点（15分钟粒度）"""
    points = []
    current = date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=15)
    end_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    while current <= end_of_day:
        points.append(current)
        current += timedelta(minutes=15)

    return points


def simulate_spot_price_data(date: datetime) -> List[Dict[str, Any]]:
    """模拟指定日期的现货价格数据"""
    time_points = generate_time_points(date)
    data = []

    for dt in time_points:
        hour = dt.hour

        # 基础价格
        if 0 <= hour < 6:
            base = 250  # 深谷
        elif 6 <= hour < 8:
            base = 320  # 早峰前爬坡
        elif 8 <= hour < 12:
            base = 420  # 早高峰
        elif 12 <= hour < 16:
            base = 350  # 午间平段
        elif 16 <= hour < 18:
            base = 380  # 晚峰前爬坡
        elif 18 <= hour < 21:
            base = 480  # 晚高峰
        else:
            base = 300  # 晚间平段

        # 添加随机波动（±15%）
        value = base * random.uniform(0.85, 1.15)

        data.append({
            "datetime": dt,
            "date_str": dt.strftime("%Y-%m-%d"),
            "time_str": dt.strftime("%H:%M"),
            "total_clearing_power": round(random.uniform(40000, 50000), 4),
            "thermal_clearing_power": round(random.uniform(25000, 30000), 4),
            "hydro_clearing_power": round(random.uniform(8000, 12000), 4),
            "wind_clearing_power": round(random.uniform(6000, 9000), 4),
            "solar_clearing_power": round(random.uniform(3000, 10000), 4),
            "pumped_storage_clearing_power": round(random.uniform(-500, 1500), 4),
            "battery_storage_generation": round(random.uniform(0, 500), 4),
            "avg_clearing_price": round(value, 2),
        })

    return data


def init_spot_price_data():
    """初始化现货价格数据"""
    logger.info(f"开始生成日前现货价格数据：{START_DATE.strftime('%Y-%m-%d')} 到 {END_DATE.strftime('%Y-%m-%d')}")

    # 清空现有数据
    logger.info("清空现有日前现货价格数据...")
    DATABASE["day_ahead_spot_price"].delete_many({})
    logger.info("数据清空完成")

    current_date = START_DATE
    total_days = (END_DATE - START_DATE).days + 1
    processed_days = 0

    while current_date <= END_DATE:
        date_str = current_date.strftime("%Y-%m-%d")
        logger.info(f"生成数据: {date_str} ({processed_days + 1}/{total_days})")

        try:
            price_data = simulate_spot_price_data(current_date)
            if price_data:
                DATABASE["day_ahead_spot_price"].insert_many(price_data)
                logger.info(f"  - day_ahead_spot_price: {len(price_data)} 条")

            processed_days += 1

        except Exception as e:
            logger.error(f"生成数据失败: {date_str}, 错误: {e}", exc_info=True)

        current_date += timedelta(days=1)

    logger.info(f"\n数据生成完成！共处理 {processed_days} 天")

    # 统计数据量
    logger.info("\n数据统计:")
    logger.info(f"  - day_ahead_spot_price: {DATABASE['day_ahead_spot_price'].count_documents({})} 条")


if __name__ == "__main__":
    init_spot_price_data()
