"""
初始化预测基础数据模拟数据
生成最近30天的数据（D-30 到 D-1）
数据粒度：15分钟，每天96个点（00:15 - 24:00）
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
    """
    生成指定日期的96个时间点（15分钟粒度）
    返回：[date 00:15, date 00:30, ..., date 23:45, date+1 00:00]
    """
    points = []
    current = date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(minutes=15)
    end_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)

    while current <= end_of_day:
        points.append(current)
        current += timedelta(minutes=15)

    return points


def simulate_system_load(time_points: List[datetime], base_date: datetime) -> List[Dict[str, Any]]:
    """
    模拟系统负荷曲线（MW）
    特征：
    - 早高峰（8:00-12:00）：40000-45000 MW
    - 晚高峰（18:00-21:00）：42000-47000 MW
    - 深谷（23:00-6:00）：28000-32000 MW
    - 平段（其他）：35000-40000 MW
    """
    data = []
    for dt in time_points:
        hour = dt.hour
        minute = dt.minute

        # 基础负荷
        if 0 <= hour < 6:
            base = 30000  # 深谷
        elif 6 <= hour < 8:
            base = 35000  # 早峰前爬坡
        elif 8 <= hour < 12:
            base = 43000  # 早高峰
        elif 12 <= hour < 16:
            base = 38000  # 午间平段
        elif 16 <= hour < 18:
            base = 40000  # 晚峰前爬坡
        elif 18 <= hour < 21:
            base = 45000  # 晚高峰
        else:
            base = 33000  # 晚间平段

        # 添加随机波动（±5%）
        value = base * random.uniform(0.95, 1.05)

        data.append({
            "datetime": dt,
            "date_str": dt.strftime("%Y-%m-%d"),
            "time_str": dt.strftime("%H:%M"),
            "value": round(value, 4)
        })

    return data


def simulate_pv_forecast(time_points: List[datetime]) -> List[Dict[str, Any]]:
    """
    模拟光伏预测（MW）
    特征：
    - 夜间（19:00-6:00）：0 MW
    - 日出后逐渐上升
    - 中午（11:00-14:00）达到峰值：8000-12000 MW
    - 日落前下降
    """
    data = []
    for dt in time_points:
        hour = dt.hour
        minute = dt.minute

        # 光伏只在白天有出力
        if hour < 6 or hour >= 19:
            value = 0
        elif 6 <= hour < 9:
            # 日出爬坡：0 -> 3000
            progress = (hour - 6) + (minute / 60)
            value = 3000 * (progress / 3)
        elif 9 <= hour < 11:
            # 上午爬坡：3000 -> 10000
            progress = (hour - 9) + (minute / 60)
            value = 3000 + 7000 * (progress / 2)
        elif 11 <= hour < 14:
            # 中午峰值：10000 ± 2000
            value = 10000 + random.uniform(-2000, 2000)
        elif 14 <= hour < 17:
            # 下午下降：10000 -> 3000
            progress = (hour - 14) + (minute / 60)
            value = 10000 - 7000 * (progress / 3)
        else:  # 17 <= hour < 19
            # 日落下降：3000 -> 0
            progress = (hour - 17) + (minute / 60)
            value = 3000 * (1 - progress / 2)

        data.append({
            "datetime": dt,
            "date_str": dt.strftime("%Y-%m-%d"),
            "time_str": dt.strftime("%H:%M"),
            "value": round(max(0, value), 4)
        })

    return data


def simulate_wind_forecast(time_points: List[datetime]) -> List[Dict[str, Any]]:
    """
    模拟风电预测（MW）
    特征：
    - 随机性较强，但有一定持续性
    - 典型范围：2000-8000 MW
    - 夜间通常高于白天
    """
    data = []
    # 每天随机选择一个基准值（4000-7000）
    daily_base = random.uniform(4000, 7000)

    for dt in time_points:
        hour = dt.hour
        # 夜间（20:00-6:00）稍高
        if hour >= 20 or hour < 6:
            hourly_factor = 1.2
        else:
            hourly_factor = 0.9

        # 添加平滑随机波动
        value = daily_base * hourly_factor * random.uniform(0.85, 1.15)

        data.append({
            "datetime": dt,
            "date_str": dt.strftime("%Y-%m-%d"),
            "time_str": dt.strftime("%H:%M"),
            "value": round(value, 4)
        })

    return data


def simulate_hydro_with_pumped(time_points: List[datetime]) -> List[Dict[str, Any]]:
    """
    模拟水电（含抽蓄）出力（MW）
    特征：
    - 相对稳定，高峰时增加出力
    - 典型范围：8000-15000 MW
    """
    data = []
    for dt in time_points:
        hour = dt.hour

        # 基础出力
        base = 10000

        # 高峰时段增加出力
        if 8 <= hour < 12 or 18 <= hour < 21:
            hourly_factor = random.uniform(1.2, 1.5)
        elif 0 <= hour < 6:
            # 深夜抽蓄蓄能，出力降低
            hourly_factor = random.uniform(0.6, 0.8)
        else:
            hourly_factor = random.uniform(0.9, 1.1)

        value = base * hourly_factor * random.uniform(0.95, 1.05)

        data.append({
            "datetime": dt,
            "date_str": dt.strftime("%Y-%m-%d"),
            "time_str": dt.strftime("%H:%M"),
            "value": round(value, 4)
        })

    return data


def simulate_tieline_capacity(time_points: List[datetime]) -> List[Dict[str, Any]]:
    """
    模拟省间联络线可用容量（MW）
    特征：
    - 相对稳定，每日变化不大
    - 典型值：5000-8000 MW
    """
    data = []
    # 每天随机选择一个基准值
    daily_base = random.uniform(6000, 7500)

    for dt in time_points:
        # 添加小幅波动
        value = daily_base * random.uniform(0.98, 1.02)

        data.append({
            "datetime": dt,
            "date_str": dt.strftime("%Y-%m-%d"),
            "time_str": dt.strftime("%H:%M"),
            "value": round(value, 4)
        })

    return data


def generate_weekly_forecast_data(date: datetime) -> List[Dict[str, Any]]:
    """生成周预测数据（5种信息类型）"""
    time_points = generate_time_points(date)

    info_configs = [
        ("系统负荷预测", simulate_system_load(time_points, date)),
        ("统调光伏", simulate_pv_forecast(time_points)),
        ("统调风电", simulate_wind_forecast(time_points)),
        ("统调水电(含抽蓄)", simulate_hydro_with_pumped(time_points)),
        ("省间联络线容量", simulate_tieline_capacity(time_points)),
    ]

    data = []
    for info_name, values in info_configs:
        for i, dt in enumerate(time_points):
            data.append({
                "datetime": dt,
                "info_name": info_name,
                "date_str": dt.strftime("%Y-%m-%d"),
                "time_str": dt.strftime("%H:%M"),
                "value": values[i]["value"]
            })

    return data


def generate_daily_release_data(date: datetime) -> List[Dict[str, Any]]:
    """生成每日预测数据（5个字段）"""
    time_points = generate_time_points(date)

    # 生成各种预测数据
    load_data = simulate_system_load(time_points, date)
    pv_data = simulate_pv_forecast(time_points)
    wind_data = simulate_wind_forecast(time_points)
    hydro_data = simulate_hydro_with_pumped(time_points)
    tieline_data = simulate_tieline_capacity(time_points)

    data = []
    for i, dt in enumerate(time_points):
        data.append({
            "datetime": dt,
            "date_str": dt.strftime("%Y-%m-%d"),
            "time_str": dt.strftime("%H:%M"),
            "system_load_forecast": round(load_data[i]["value"] * 0.98, 4),  # 短期预测略低于周预测
            "pv_forecast": round(pv_data[i]["value"] * 1.02, 4),
            "wind_forecast": round(wind_data[i]["value"] * 1.05, 4),
            "nonmarket_unit_forecast": round(load_data[i]["value"] * random.uniform(0.08, 0.12), 4),  # 非市场化机组约8-12%
            "tieline_plan": round(tieline_data[i]["value"] * 0.95, 4),
        })

    return data


def generate_actual_operation_data(date: datetime) -> List[Dict[str, Any]]:
    """生成实际运行数据"""
    time_points = generate_time_points(date)

    # 实际负荷与预测略有差异
    load_data = simulate_system_load(time_points, date)
    tieline_data = simulate_tieline_capacity(time_points)

    data = []
    for i, dt in enumerate(time_points):
        hour = dt.hour

        # 系统负荷（实际值）
        system_load = round(load_data[i]["value"] * random.uniform(0.97, 1.03), 4)

        # 正备用（约5-10%负荷）
        positive_reserve = round(system_load * random.uniform(0.05, 0.10), 4)

        # 负备用（约3-7%负荷）
        negative_reserve = round(system_load * random.uniform(0.03, 0.07), 4)

        # 联络线潮流（与计划有偏差）
        tieline_flow = round(tieline_data[i]["value"] * random.uniform(0.90, 1.10), 4)

        data.append({
            "datetime": dt,
            "date_str": dt.strftime("%Y-%m-%d"),
            "time_str": dt.strftime("%H:%M"),
            "system_load": system_load,
            "positive_reserve": positive_reserve,
            "negative_reserve": negative_reserve,
            "tieline_flow": tieline_flow,
        })

    return data


def generate_real_time_generation_data(date: datetime) -> List[Dict[str, Any]]:
    """生成实时发电出力数据"""
    time_points = generate_time_points(date)

    # 各类电源出力
    wind_data = simulate_wind_forecast(time_points)
    solar_data = simulate_pv_forecast(time_points)
    hydro_data = simulate_hydro_with_pumped(time_points)

    data = []
    for i, dt in enumerate(time_points):
        hour = dt.hour

        # 风电实际出力
        wind_gen = round(wind_data[i]["value"] * random.uniform(0.95, 1.05), 4)

        # 光伏实际出力
        solar_gen = round(solar_data[i]["value"] * random.uniform(0.98, 1.02), 4)

        # 水电实际出力
        hydro_gen = round(hydro_data[i]["value"] * random.uniform(0.97, 1.03), 4)

        # 其他电源（火电等）
        system_load = wind_gen + solar_gen + hydro_gen + 20000  # 假设火电基荷20000
        thermal_gen = round(system_load * random.uniform(0.55, 0.65), 4)

        # 抽蓄（可能为负，表示抽水状态）
        if 0 <= hour < 6 or 23 <= hour:
            # 深夜抽水
            pumped_storage = round(random.uniform(-2000, -500), 4)
        else:
            # 白天发电
            pumped_storage = round(random.uniform(200, 1500), 4)

        # 储能（新兴技术，规模较小）
        battery_storage = round(random.uniform(0, 500), 4)

        # 汇总
        total_generation = wind_gen + solar_gen + hydro_gen + thermal_gen + pumped_storage + battery_storage
        total_generation_energy = round(total_generation / 4, 4)  # 15分钟电量 = MW / 4

        data.append({
            "datetime": dt,
            "date_str": dt.strftime("%Y-%m-%d"),
            "time_str": dt.strftime("%H:%M"),
            "total_generation": total_generation,
            "total_generation_energy": total_generation_energy,
            "thermal_generation": thermal_gen,
            "thermal_generation_energy": round(thermal_gen / 4, 4),
            "hydro_generation": hydro_gen,
            "hydro_generation_energy": round(hydro_gen / 4, 4),
            "pumped_storage_generation": pumped_storage,
            "pumped_storage_generation_energy": round(pumped_storage / 4, 4),
            "wind_generation": wind_gen,
            "wind_generation_energy": round(wind_gen / 4, 4),
            "solar_generation": solar_gen,
            "solar_generation_energy": round(solar_gen / 4, 4),
            "battery_storage_generation": battery_storage,
            "battery_storage_generation_energy": round(battery_storage / 4, 4),
            "non_market_total_generation": round(thermal_gen * 0.1, 4),
            "renewable_total_generation": round(wind_gen + solar_gen, 4),
            "hydro_with_pumped_total_generation": round(hydro_gen + pumped_storage, 4),
        })

    return data


def init_forecast_base_data():
    """初始化预测基础数据"""
    logger.info(f"开始生成预测基础数据：{START_DATE.strftime('%Y-%m-%d')} 到 {END_DATE.strftime('%Y-%m-%d')}")

    # 清空现有数据
    logger.info("清空现有数据...")
    DATABASE["weekly_forecast"].delete_many({})
    DATABASE["daily_release"].delete_many({})
    DATABASE["actual_operation"].delete_many({})
    DATABASE["real_time_generation"].delete_many({})
    logger.info("数据清空完成")

    current_date = START_DATE
    total_days = (END_DATE - START_DATE).days + 1
    processed_days = 0

    while current_date <= END_DATE:
        date_str = current_date.strftime("%Y-%m-%d")
        logger.info(f"生成数据: {date_str} ({processed_days + 1}/{total_days})")

        try:
            # 1. 生成周预测数据
            weekly_data = generate_weekly_forecast_data(current_date)
            if weekly_data:
                DATABASE["weekly_forecast"].insert_many(weekly_data)
                logger.info(f"  - weekly_forecast: {len(weekly_data)} 条")

            # 2. 生成每日预测数据
            daily_data = generate_daily_release_data(current_date)
            if daily_data:
                DATABASE["daily_release"].insert_many(daily_data)
                logger.info(f"  - daily_release: {len(daily_data)} 条")

            # 3. 生成实际运行数据
            operation_data = generate_actual_operation_data(current_date)
            if operation_data:
                DATABASE["actual_operation"].insert_many(operation_data)
                logger.info(f"  - actual_operation: {len(operation_data)} 条")

            # 4. 生成实时发电出力数据
            generation_data = generate_real_time_generation_data(current_date)
            if generation_data:
                DATABASE["real_time_generation"].insert_many(generation_data)
                logger.info(f"  - real_time_generation: {len(generation_data)} 条")

            processed_days += 1

        except Exception as e:
            logger.error(f"生成数据失败: {date_str}, 错误: {e}", exc_info=True)

        current_date += timedelta(days=1)

    logger.info(f"数据生成完成！共处理 {processed_days} 天")

    # 统计数据量
    logger.info("\n数据统计:")
    logger.info(f"  - weekly_forecast: {DATABASE['weekly_forecast'].count_documents({})} 条")
    logger.info(f"  - daily_release: {DATABASE['daily_release'].count_documents({})} 条")
    logger.info(f"  - actual_operation: {DATABASE['actual_operation'].count_documents({})} 条")
    logger.info(f"  - real_time_generation: {DATABASE['real_time_generation'].count_documents({})} 条")


if __name__ == "__main__":
    init_forecast_base_data()
