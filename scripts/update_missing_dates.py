"""
补充 2025-12-24 和 2025-12-25 的数据
"""
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any
import random
from pymongo import ASCENDING
import sys
import os

# 添加项目路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from webapp.tools.mongo import DATABASE

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


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
    """模拟指定日期的日前现货价格数据"""
    time_points = generate_time_points(date)
    data = []

    # 根据季节调整价格
    month = date.month
    if month in [1, 2, 12]:  # 冬季
        seasonal_factor = 1.15
    elif month in [6, 7, 8]:  # 夏季
        seasonal_factor = 1.10
    else:
        seasonal_factor = 1.0

    # 周末价格略低
    weekday = date.weekday()
    if weekday >= 5:  # 周六、周日
        weekend_factor = 0.9
    else:
        weekend_factor = 1.0

    for dt in time_points:
        hour = dt.hour

        # 基础价格
        if 0 <= hour < 6:
            base = 250 * seasonal_factor  # 深谷
        elif 6 <= hour < 8:
            base = 320 * seasonal_factor  # 早峰前爬坡
        elif 8 <= hour < 12:
            base = 450 * seasonal_factor  # 早高峰
        elif 12 <= hour < 16:
            base = 350 * seasonal_factor  # 午间平段
        elif 16 <= hour < 18:
            base = 380 * seasonal_factor  # 晚峰前爬坡
        elif 18 <= hour < 21:
            base = 520 * seasonal_factor  # 晚高峰
        else:
            base = 300 * seasonal_factor  # 晚间平段

        # 应用周末因子
        base *= weekend_factor

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


def generate_d2_forecast_batch(forecast_date: datetime) -> List[Dict[str, Any]]:
    """生成 D-2 价格预测批次数据"""
    forecast_date_str = forecast_date.strftime("%Y-%m-%d")
    forecast_id = f"D2_{forecast_date.strftime('%Y%m%d')}_0920"

    data = []
    for day_offset in range(10):
        target_date = forecast_date + timedelta(days=2 + day_offset)  # D-2预测D~D+9
        target_date_str = target_date.strftime("%Y-%m-%d")

        time_points = generate_time_points(target_date)

        # 获取该日期的季节因子
        month = target_date.month
        if month in [1, 2, 12]:  # 冬季
            seasonal_factor = 1.15
        elif month in [6, 7, 8]:  # 夏季
            seasonal_factor = 1.10
        else:
            seasonal_factor = 1.0

        for dt in time_points:
            hour = dt.hour

            # 基础价格
            if 0 <= hour < 6:
                base = 250 * seasonal_factor
            elif 6 <= hour < 8:
                base = 320 * seasonal_factor
            elif 8 <= hour < 12:
                base = 450 * seasonal_factor
            elif 12 <= hour < 16:
                base = 350 * seasonal_factor
            elif 16 <= hour < 18:
                base = 380 * seasonal_factor
            elif 18 <= hour < 21:
                base = 520 * seasonal_factor
            else:
                base = 300 * seasonal_factor

            # 预测价格与实际价格的偏差为 ±10%
            predicted_price = base * random.uniform(0.90, 1.10)

            # 置信区间
            confidence_80_range = predicted_price * 0.15
            confidence_90_range = predicted_price * 0.20

            data.append({
                "forecast_id": forecast_id,
                "forecast_type": "d2_price",
                "forecast_date": datetime.strptime(forecast_date_str, "%Y-%m-%d"),
                "target_date": datetime.strptime(target_date_str, "%Y-%m-%d"),
                "datetime": dt,
                "predicted_price": round(predicted_price, 2),
                "confidence_80_lower": round(predicted_price - confidence_80_range, 2),
                "confidence_80_upper": round(predicted_price + confidence_80_range, 2),
                "confidence_90_lower": round(predicted_price - confidence_90_range, 2),
                "confidence_90_upper": round(predicted_price + confidence_90_range, 2),
                "model_type": "d2_near_term",
                "model_version": "v1.0.0",
                "created_at": datetime.now(),
            })

    return data


def update_missing_dates():
    """补充 2025-12-24 和 2025-12-25 的数据"""
    logger.info("开始补充 2025-12-24 和 2025-12-25 的数据")

    # 需要补充的日期
    dates_to_add = [
        datetime(2025, 12, 24),
        datetime(2025, 12, 25)
    ]

    for date in dates_to_add:
        date_str = date.strftime("%Y-%m-%d")
        logger.info(f"\n处理日期: {date_str}")

        # 1. 生成实际价格数据
        logger.info(f"  [1/2] 生成实际价格数据...")
        try:
            price_data = simulate_spot_price_data(date)
            DATABASE["day_ahead_spot_price"].insert_many(price_data)
            logger.info(f"      插入 {len(price_data)} 条实际价格记录")
        except Exception as e:
            logger.warning(f"      实际价格数据可能已存在: {e}")

        # 2. 生成预测数据（D-2预测，所以用 date-2 作为预测日期）
        forecast_date = date - timedelta(days=2)
        logger.info(f"  [2/2] 生成预测数据 (forecast_date={forecast_date.strftime('%Y-%m-%d')})...")
        try:
            forecast_data = generate_d2_forecast_batch(forecast_date)
            DATABASE["price_forecast_results"].insert_many(forecast_data)
            logger.info(f"      插入 {len(forecast_data)} 条预测记录")
        except Exception as e:
            logger.warning(f"      预测数据可能已存在: {e}")

    # 统计
    logger.info("\n" + "=" * 60)
    logger.info("数据补充完成！")
    logger.info("=" * 60)
    logger.info("\n数据统计:")
    logger.info(f"  - day_ahead_spot_price: {DATABASE['day_ahead_spot_price'].count_documents({})} 条")
    logger.info(f"  - price_forecast_results (d2_price): {DATABASE['price_forecast_results'].count_documents({'forecast_type': 'd2_price'})} 条")

    # 检查 2025-12-24 的预测数据
    date_check = datetime(2025, 12, 24)
    forecast_date_check = date_check - timedelta(days=2)
    count = DATABASE['price_forecast_results'].count_documents({
        'forecast_type': 'd2_price',
        'forecast_date': forecast_date_check
    })
    logger.info(f"\n验证: forecast_date={forecast_date_check.strftime('%Y-%m-%d')} 有 {count} 条预测记录")


if __name__ == "__main__":
    update_missing_dates()
