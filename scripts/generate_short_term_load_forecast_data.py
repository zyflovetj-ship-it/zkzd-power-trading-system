#!/usr/bin/env python3
"""
短期负荷预测数据生成脚本

基于 webapp/api/v1_short_term_load_forecast.py 接口的实现逻辑，
在 MongoDB 数据库中生成模拟的短期负荷预测数据。

遵循规范：docs/spec/后端开发规范.md
- 使用 Long Format 时序数据存储（每个时间点独立记录）
- 24:00 处理：业务日第96个点存储为次日 00:00，查询使用左开右闭区间
- 后端负责时间标签格式化
"""

import logging
import random
from datetime import datetime, timedelta
from pymongo import MongoClient
from pymongo.errors import OperationFailure
from bson import ObjectId

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class ShortTermLoadForecastDataGenerator:
    """短期负荷预测数据生成器"""

    def __init__(self, mongodb_uri="mongodb://localhost:27017", database_name="exds"):
        """
        初始化数据库连接

        Args:
            mongodb_uri: MongoDB 连接字符串
            database_name: 数据库名称
        """
        self.client = MongoClient(mongodb_uri)
        self.db = self.client[database_name]
        self.collection = self.db["short_term_load_forecast"]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """确保查询需要的索引存在"""
        try:
            # 创建复合索引
            self.collection.create_index(
                [("forecast_date", 1), ("forecast_type", 1), ("datetime", 1)],
                name="forecast_date_type_datetime_1"
            )
            self.collection.create_index([("datetime", 1)], name="datetime_1")
            logger.info("数据库索引创建完成")
        except OperationFailure as e:
            logger.warning(f"索引创建失败（可能已存在）: {e}")
        except Exception as e:
            logger.error(f"索引创建异常: {e}")

    def generate_realistic_load_pattern(self, target_date: datetime, i: int) -> float:
        """
        生成真实的负荷模式

        Args:
            target_date: 目标日期
            i: 时间点索引（0-95）

        Returns:
            负荷值 (MW)
        """
        time_obj = target_date + timedelta(minutes=15 * i)
        hour = time_obj.hour
        minute = time_obj.minute

        # 定义不同时段的基础负荷模式
        base_load_profile = {
            # 深夜时段 (00:00-06:00): 低负荷
            "night_base": 650,
            # 早高峰 (06:00-09:00): 快速上升
            "morning_peak": 1200,
            # 日间平稳 (09:00-17:00): 相对稳定
            "day_stable": 950,
            # 晚高峰 (17:00-21:00): 最高负荷
            "evening_peak": 1350,
            # 夜间回落 (21:00-24:00): 逐步下降
            "evening_decline": 800
        }

        # 根据时段确定基础负荷
        if hour >= 0 and hour < 6:
            base_load = base_load_profile["night_base"]
        elif hour >= 6 and hour < 9:
            # 早高峰过渡
            progress = (hour - 6) + (minute / 60)
            base_load = base_load_profile["night_base"] + \
                      (base_load_profile["morning_peak"] - base_load_profile["night_base"]) * progress / 3
        elif hour >= 9 and hour < 17:
            base_load = base_load_profile["day_stable"]
        elif hour >= 17 and hour < 21:
            # 晚高峰过渡
            progress = (hour - 17) + (minute / 60)
            base_load = base_load_profile["day_stable"] + \
                      (base_load_profile["evening_peak"] - base_load_profile["day_stable"]) * progress / 4
        else:
            # 夜间回落
            progress = (hour - 21) + (minute / 60)
            base_load = base_load_profile["evening_peak"] - \
                      (base_load_profile["evening_peak"] - base_load_profile["evening_decline"]) * progress / 3

        # 添加随机波动和季节性因素
        random_factor = 0.95 + random.random() * 0.1  # ±5% 随机波动
        seasonal_factor = 1 + 0.1 * (i / 96) * 2 * 3.14159  # 日周期性
        weekend_factor = 0.85 if target_date.weekday() >= 5 else 1  # 周末负荷降低

        forecast_value = round(base_load * random_factor * seasonal_factor * weekend_factor)
        return max(100, min(2000, forecast_value))  # 限制在合理范围内

    def generate_forecast_data_for_date(self, forecast_date: datetime, forecast_type: str):
        """
        为指定预测日期和类型生成96点预测数据

        Args:
            forecast_date: 预测日期（业务日）
            forecast_type: 预测类型 (d+1, d+2, d+3)
        """
        if forecast_type not in ["d+1", "d+2", "d+3"]:
            raise ValueError(f"无效的预测类型: {forecast_type}，支持：d+1, d+2, d+3")

        # 计算预测目标日期
        days_ahead = int(forecast_type.split("+")[1])
        forecast_target_date = forecast_date + timedelta(days=days_ahead)

        logger.info(f"为 {forecast_date.date()} ({forecast_type}) 生成预测数据，目标日期: {forecast_target_date.date()}")

        # 删除现有数据（避免重复）
        start_of_day = forecast_target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        delete_query = {
            "forecast_date": forecast_date.replace(hour=0, minute=0, second=0, microsecond=0),
            "forecast_type": forecast_type,
            "datetime": {"$gte": start_of_day, "$lt": end_of_day}
        }

        deleted_count = self.collection.delete_many(delete_query)
        if deleted_count.deleted_count > 0:
            logger.info(f"删除了 {deleted_count.deleted_count} 条现有数据")

        # 生成96个时间点的数据
        documents = []
        for i in range(96):
            # 计算时间戳
            timestamp = start_of_day + timedelta(minutes=15 * i)

            # 特殊处理24:00点（存储为次日00:00）
            if i == 95:  # 最后一个点
                timestamp = end_of_day  # 次日00:00
                time_str = "24:00"
            else:
                time_str = timestamp.strftime("%H:%M")

            # 生成预测值
            forecast_value = self.generate_realistic_load_pattern(forecast_target_date, i)

            document = {
                "forecast_date": forecast_date.replace(hour=0, minute=0, second=0, microsecond=0),
                "forecast_type": forecast_type,
                "datetime": timestamp,
                "time": time_str,
                "forecast_value": forecast_value,
                "confidence_level": self._calculate_confidence_level(forecast_type),
                "created_at": datetime.now(),
                "updated_at": datetime.now(),
                "model_version": "v1.0",
                "data_source": "simulated"
            }

            documents.append(document)

        # 批量插入数据
        if documents:
            self.collection.insert_many(documents)
            logger.info(f"成功生成 {len(documents)} 条预测数据点")

    def _calculate_confidence_level(self, forecast_type: str) -> str:
        """根据预测类型计算置信水平"""
        confidence_map = {
            "d+1": "高",
            "d+2": "中",
            "d+3": "低"
        }
        return confidence_map.get(forecast_type, "中")

    def generate_historical_data(self, start_date: datetime, end_date: datetime):
        """
        为指定日期范围生成历史预测数据（包含实际值）

        Args:
            start_date: 开始日期
            end_date: 结束日期
        """
        current_date = start_date
        forecast_types = ["d+1", "d+2", "d+3"]

        while current_date <= end_date:
            logger.info(f"生成 {current_date.date()} 的历史预测数据")

            for forecast_type in forecast_types:
                # 生成预测数据
                self.generate_forecast_data_for_date(current_date, forecast_type)

                # 为较老的日期随机添加一些实际值（模拟历史数据）
                if current_date < datetime.now() - timedelta(days=7):
                    self._add_actual_values_for_date(current_date, forecast_type)

            current_date += timedelta(days=1)

    def _add_actual_values_for_date(self, forecast_date: datetime, forecast_type: str):
        """为指定日期的预测数据添加实际值"""
        days_ahead = int(forecast_type.split("+")[1])
        target_date = forecast_date + timedelta(days=days_ahead)

        # 如果目标日期在过去，有概率添加实际值
        if target_date < datetime.now() - timedelta(days=1):
            if random.random() < 0.7:  # 70%概率有实际值
                start_of_day = target_date.replace(hour=0, minute=0, second=0, microsecond=0)
                end_of_day = start_of_day + timedelta(days=1)

                # 随机选择要更新的时间点
                num_points_to_update = random.randint(48, 96)  # 50%-100%的点有实际值
                points_to_update = random.sample(range(96), num_points_to_update)

                for i in points_to_update:
                    timestamp = start_of_day + timedelta(minutes=15 * i)
                    if i == 95:  # 24:00处理
                        timestamp = end_of_day

                    # 生成实际值（在预测值基础上添加误差）
                    forecast_query = {
                        "forecast_date": forecast_date.replace(hour=0, minute=0, second=0, microsecond=0),
                        "forecast_type": forecast_type,
                        "datetime": timestamp
                    }

                    forecast_doc = self.collection.find_one(forecast_query)
                    if forecast_doc:
                        # 添加误差：MAPE约3-8%
                        error_rate = 0.03 + random.random() * 0.05  # 3%-8%误差
                        error_direction = 1 if random.random() > 0.5 else -1
                        actual_value = forecast_doc["forecast_value"] * (1 + error_direction * error_rate)

                        update = {
                            "$set": {
                                "actual_value": round(actual_value),
                                "actual_timestamp": timestamp,
                                "updated_at": datetime.now()
                            }
                        }

                        self.collection.update_one(forecast_query, update)

    def generate_data_for_recent_days(self, days: int = 30):
        """
        为最近N天生成预测数据

        Args:
            days: 生成数据的天数
        """
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days-1)

        logger.info(f"为最近 {days} 天生成预测数据 ({start_date.date()} 到 {end_date.date()})")
        self.generate_historical_data(start_date, end_date)

    def get_data_summary(self):
        """获取数据生成摘要"""
        total_docs = self.collection.count_documents({})

        # 按预测类型统计
        type_stats = {}
        for forecast_type in ["d+1", "d+2", "d+3"]:
            count = self.collection.count_documents({"forecast_type": forecast_type})
            type_stats[forecast_type] = count

        # 获取日期范围
        first_doc = self.collection.find_one({}, sort=[("forecast_date", 1)])
        last_doc = self.collection.find_one({}, sort=[("forecast_date", -1)])

        summary = {
            "total_documents": total_docs,
            "by_forecast_type": type_stats,
            "date_range": {
                "start": first_doc["forecast_date"].date() if first_doc else None,
                "end": last_doc["forecast_date"].date() if last_doc else None
            }
        }

        return summary


def main():
    """主函数"""
    generator = ShortTermLoadForecastDataGenerator()

    # 生成最近30天的数据
    generator.generate_data_for_recent_days(days=30)

    # 获取数据摘要
    summary = generator.get_data_summary()
    logger.info("数据生成完成！")
    logger.info(f"数据摘要: {summary}")


if __name__ == "__main__":
    main()