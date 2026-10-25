"""
中长期负荷预测服务

提供中长期负荷预测数据的CRUD操作和模拟数据生成功能。
"""

import logging
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from dateutil.relativedelta import relativedelta

from webapp.tools.mongo import DATABASE
from webapp.models.medium_long_term_load_forecast import (
    MonthlyForecastPoint,
    MediumLongTermLoadForecastResponse,
    MediumLongTermLoadForecastCreate,
)

logger = logging.getLogger(__name__)


class MediumLongTermLoadForecastService:
    """中长期负荷预测服务类"""

    COLLECTION_NAME = "medium_long_term_load_forecast"

    def __init__(self):
        """初始化服务，确保索引存在"""
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """确保数据库索引存在"""
        try:
            DATABASE[self.COLLECTION_NAME].create_index([("forecast_date", -1)])
            DATABASE[self.COLLECTION_NAME].create_index([("data.month", 1)])
            logger.info(f"{self.COLLECTION_NAME} 集合索引创建成功")
        except Exception as e:
            logger.error(f"创建 {self.COLLECTION_NAME} 集合索引失败: {e}", exc_info=True)
            raise

    def create_forecast(
        self,
        forecast_data: MediumLongTermLoadForecastCreate
    ) -> MediumLongTermLoadForecastResponse:
        """
        创建中长期负荷预测

        Args:
            forecast_data: 预测数据创建请求

        Returns:
            MediumLongTermLoadForecastResponse: 创建的预测数据

        Raises:
            ValueError: 如果创建失败
        """
        try:
            # 验证 forecast_date 格式
            forecast_dt = datetime.strptime(forecast_data.forecast_date, "%Y-%m-%d")

            # 生成月度预测数据
            monthly_data = self._generate_monthly_forecast(
                base_date=forecast_dt,
                horizon_months=forecast_data.forecast_horizon_months,
                base_load_value=forecast_data.base_load_value,
                confidence_interval_ratio=forecast_data.confidence_interval_ratio,
            )

            # 构建文档
            doc = {
                "forecast_date": forecast_data.forecast_date,
                "forecast_horizon_months": forecast_data.forecast_horizon_months,
                "data": [point.model_dump() for point in monthly_data],
                "created_at": datetime.now().isoformat(),
            }

            # 插入数据库
            result = DATABASE[self.COLLECTION_NAME].insert_one(doc)
            if not result.inserted_id:
                raise ValueError("插入数据失败")

            # 返回响应
            return MediumLongTermLoadForecastResponse(
                forecast_date=forecast_data.forecast_date,
                forecast_horizon_months=forecast_data.forecast_horizon_months,
                data=monthly_data,
                total_months=len(monthly_data),
            )

        except ValueError as e:
            logger.error(f"创建预测数据失败: {e}", exc_info=True)
            raise
        except Exception as e:
            logger.error(f"创建预测数据时发生错误: {e}", exc_info=True)
            raise ValueError(f"创建预测数据失败: {e}")

    def _generate_monthly_forecast(
        self,
        base_date: datetime,
        horizon_months: int,
        base_load_value: float,
        confidence_interval_ratio: float,
    ) -> List[MonthlyForecastPoint]:
        """
        生成月度预测数据

        Args:
            base_date: 基准日期
            horizon_months: 预测月数
            base_load_value: 基础负荷值
            confidence_interval_ratio: 置信区间比例

        Returns:
            List[MonthlyForecastPoint]: 月度预测数据列表
        """
        monthly_data = []

        for i in range(1, horizon_months + 1):
            # 计算目标月份（从基准日期的下个月开始）
            target_date = base_date + relativedelta(months=+i)
            month_str = target_date.strftime("%Y-%m")
            timestamp = target_date.isoformat()

            # 模拟季节性波动（夏季和冬季负荷高）
            month_factor = self._get_seasonal_factor(target_date.month)

            # 模拟增长趋势（每月小幅增长）
            growth_factor = 1 + (i * 0.005)  # 每月增长0.5%

            # 添加随机波动
            import random
            random_factor = 1 + (random.random() - 0.5) * 0.1  # ±5%波动

            # 计算预测值
            forecast_value = base_load_value * month_factor * growth_factor * random_factor

            # 计算置信区间
            upper_bound = forecast_value * (1 + confidence_interval_ratio)
            lower_bound = forecast_value * (1 - confidence_interval_ratio)

            monthly_data.append(
                MonthlyForecastPoint(
                    month=month_str,
                    forecast_value=round(forecast_value, 2),
                    upper_bound=round(upper_bound, 2),
                    lower_bound=round(lower_bound, 2),
                    timestamp=timestamp,
                )
            )

        return monthly_data

    def _get_seasonal_factor(self, month: int) -> float:
        """
        获取季节性系数

        夏季（7-8月）和冬季（12-1月）负荷较高

        Args:
            month: 月份（1-12）

        Returns:
            float: 季节性系数
        """
        seasonal_factors = {
            1: 1.15,   # 1月：冬季高峰
            2: 1.10,   # 2月：冬季
            3: 0.95,   # 3月：春季
            4: 0.90,   # 4月：春季
            5: 0.88,   # 5月：春季
            6: 0.92,   # 6月：初夏
            7: 1.18,   # 7月：夏季高峰
            8: 1.20,   # 8月：夏季高峰
            9: 1.05,   # 9月：秋季
            10: 0.95,  # 10月：秋季
            11: 0.98,  # 11月：晚秋
            12: 1.12,  # 12月：冬季
        }
        return seasonal_factors.get(month, 1.0)

    def get_latest_forecast(self) -> Optional[MediumLongTermLoadForecastResponse]:
        """
        获取最新的预测数据

        Returns:
            Optional[MediumLongTermLoadForecastResponse]: 最新的预测数据，如果不存在则返回None
        """
        try:
            collection = DATABASE[self.COLLECTION_NAME]

            # 检查数据格式：如果有嵌套 data 字段的复合文档
            doc = collection.find_one(
                {"data": {"$exists": True}},
                sort=[("forecast_date", -1)]
            )

            if doc and "data" in doc:
                monthly_data = [
                    MonthlyForecastPoint(**point) for point in doc.get("data", [])
                ]

                return MediumLongTermLoadForecastResponse(
                    forecast_date=doc["forecast_date"],
                    forecast_horizon_months=doc["forecast_horizon_months"],
                    data=monthly_data,
                    total_months=len(monthly_data),
                )

            # 适配简单记录格式：从所有记录中聚合生成响应
            docs = list(collection.find().sort("forecast_date", -1))
            if not docs:
                return None

            # 按 forecast_month 分组
            from collections import defaultdict
            monthly_map = defaultdict(list)
            for d in docs:
                month_key = d.get("forecast_month", d["forecast_date"].strftime("%Y-%m"))
                monthly_map[month_key].append(d.get("forecast_value", 0))

            monthly_data = []
            for month_key in sorted(monthly_map.keys()):
                values = monthly_map[month_key]
                avg_value = sum(values) / len(values) if values else 0
                monthly_data.append(MonthlyForecastPoint(
                    month=month_key,
                    forecast_value=round(avg_value, 2),
                    upper_bound=round(avg_value * 1.1, 2),
                    lower_bound=round(avg_value * 0.9, 2),
                    timestamp=docs[0]["forecast_date"].isoformat(),
                ))

            if not monthly_data:
                return None

            return MediumLongTermLoadForecastResponse(
                forecast_date=docs[0]["forecast_date"].strftime("%Y-%m-%d"),
                forecast_horizon_months=len(monthly_data),
                data=monthly_data,
                total_months=len(monthly_data),
            )

        except Exception as e:
            logger.error(f"获取最新预测数据失败: {e}", exc_info=True)
            raise ValueError(f"获取最新预测数据失败: {e}")

    def get_forecast_by_date(
        self, forecast_date: str
    ) -> Optional[MediumLongTermLoadForecastResponse]:
        """
        根据预测发布日期获取预测数据

        Args:
            forecast_date: 预测发布日期，格式 YYYY-MM-DD

        Returns:
            Optional[MediumLongTermLoadForecastResponse]: 预测数据，如果不存在则返回None
        """
        try:
            doc = DATABASE[self.COLLECTION_NAME].find_one(
                {"forecast_date": forecast_date}
            )

            if not doc:
                return None

            # 转换数据
            monthly_data = [
                MonthlyForecastPoint(**point) for point in doc.get("data", [])
            ]

            return MediumLongTermLoadForecastResponse(
                forecast_date=doc["forecast_date"],
                forecast_horizon_months=doc["forecast_horizon_months"],
                data=monthly_data,
                total_months=len(monthly_data),
            )

        except Exception as e:
            logger.error(f"获取预测数据失败: {e}", exc_info=True)
            raise ValueError(f"获取预测数据失败: {e}")

    def get_all_forecasts(self) -> List[Dict[str, Any]]:
        """
        获取所有预测数据的摘要列表

        Returns:
            List[Dict[str, Any]]: 预测数据摘要列表
        """
        try:
            cursor = DATABASE[self.COLLECTION_NAME].find(
                {}, {"forecast_date": 1, "forecast_horizon_months": 1, "created_at": 1}
            ).sort("forecast_date", -1)

            return list(cursor)

        except Exception as e:
            logger.error(f"获取所有预测数据失败: {e}", exc_info=True)
            raise ValueError(f"获取所有预测数据失败: {e}")

    def delete_forecast(self, forecast_date: str) -> bool:
        """
        删除指定日期的预测数据

        Args:
            forecast_date: 预测发布日期，格式 YYYY-MM-DD

        Returns:
            bool: 是否删除成功
        """
        try:
            result = DATABASE[self.COLLECTION_NAME].delete_one(
                {"forecast_date": forecast_date}
            )
            return result.deleted_count > 0

        except Exception as e:
            logger.error(f"删除预测数据失败: {e}", exc_info=True)
            raise ValueError(f"删除预测数据失败: {e}")

    def delete_all_forecasts(self) -> int:
        """
        删除所有预测数据

        Returns:
            int: 删除的文档数量
        """
        try:
            result = DATABASE[self.COLLECTION_NAME].delete_many({})
            return result.deleted_count

        except Exception as e:
            logger.error(f"删除所有预测数据失败: {e}", exc_info=True)
            raise ValueError(f"删除所有预测数据失败: {e}")
