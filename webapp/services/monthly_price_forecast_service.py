"""
月度价格预测服务层
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pymongo.database import Database
from pymongo import ASCENDING

logger = logging.getLogger(__name__)


class MonthlyPriceForecastService:
    """月度价格预测服务"""

    def __init__(self, db: Database):
        self.db = db

    def get_forecast_versions(
        self,
        target_year: int,
        target_month: int,
        forecast_type: str = "monthly_price"
    ) -> List[Dict[str, Any]]:
        """
        获取指定目标月份的所有预测版本

        Args:
            target_year: 目标年份
            target_month: 目标月份
            forecast_type: 预测类型

        Returns:
            预测版本列表
        """
        collection = self.db["monthly_price_forecast"]

        # 查询该月份的所有预测版本
        results = list(collection.find({
            "forecast_type": forecast_type,
            "target_month.year": target_year,
            "target_month.month": target_month
        }).sort("forecast_date", -1))

        # 转换为响应格式
        versions = []
        for doc in results:
            versions.append({
                "forecast_id": doc["forecast_id"],
                "forecast_type": doc["forecast_type"],
                "model_type": doc.get("model_type", "unknown"),
                "model_version": doc.get("model_version", "unknown"),
                "created_at": doc["created_at"],
                "status": doc.get("status", "active")
            })

        return versions

    def get_chart_data(
        self,
        forecast_id: str,
        chart_type: str = "mean_trend"
    ) -> Dict[str, Any]:
        """
        获取图表数据

        Args:
            forecast_id: 预测批次ID
            chart_type: 图表类型 (mean_trend, price_spread, peak_valley)

        Returns:
            图表数据
        """
        # 获取预测数据
        forecast_collection = self.db["monthly_price_forecast"]
        forecast_doc = forecast_collection.find_one({"forecast_id": forecast_id})

        if not forecast_doc:
            raise ValueError(f"未找到预测批次 {forecast_id}")

        target_year = forecast_doc["target_month"]["year"]
        target_month = forecast_doc["target_month"]["month"]

        # 获取目标月份的实际价格数据（如果存在）
        actual_collection = self.db["day_ahead_spot_price"]
        start_of_month = datetime(target_year, target_month, 1)
        days_in_month = self._get_days_in_month(target_year, target_month)
        end_of_month = datetime(target_year, target_month, days_in_month, 23, 59, 59)

        actual_docs = list(actual_collection.find({
            "datetime": {"$gte": start_of_month, "$lte": end_of_month}
        }).sort("datetime", ASCENDING))

        # 聚合实际价格为日度统计
        actual_daily_stats = self._aggregate_actual_prices(actual_docs)

        # 获取上月均价（参考线）
        last_month_avg = self._get_last_month_avg(target_year, target_month)

        # 组合数据
        chart_data = []
        for pred_day in forecast_doc["daily_predictions"]:
            date_str = pred_day["date"]
            actual_stats = actual_daily_stats.get(date_str, {})

            data_point = {
                "date": date_str,
                "day": int(date_str.split("-")[2]),  # 日期数字（1-31）
                "price_max": pred_day["price_max"],
                "price_min": pred_day["price_min"],
                "price_mean": pred_day["price_mean"],
                "price_peak": pred_day["price_peak"],
                "price_valley": pred_day["price_valley"],
                "confidence_80_lower": pred_day.get("confidence_80_lower"),
                "confidence_80_upper": pred_day.get("confidence_80_upper"),
                "confidence_90_lower": pred_day.get("confidence_90_lower"),
                "confidence_90_upper": pred_day.get("confidence_90_upper"),
                "actual_mean": actual_stats.get("mean"),
                "actual_max": actual_stats.get("max"),
                "actual_min": actual_stats.get("min"),
            }

            # 计算价差
            data_point["price_spread"] = pred_day["price_max"] - pred_day["price_min"]
            if actual_stats.get("max") and actual_stats.get("min"):
                data_point["actual_spread"] = actual_stats["max"] - actual_stats["min"]

            chart_data.append(data_point)

        return {
            "forecast_id": forecast_id,
            "target_month": {
                "year": target_year,
                "month": target_month
            },
            "chart_type": chart_type,
            "data": chart_data,
            "has_actual": len(actual_docs) > 0,
            "last_month_avg": last_month_avg
        }

    def get_accuracy_details(
        self,
        forecast_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        获取准确度评估详情

        Args:
            forecast_id: 预测批次ID

        Returns:
            准确度数据，如果不存在则返回 None
        """
        collection = self.db["forecast_accuracy_monthly"]

        doc = collection.find_one({"forecast_id": forecast_id})

        if not doc:
            return None

        # 转换为响应格式
        return {
            "forecast_id": doc["forecast_id"],
            "target_month": doc["target_month"],
            "forecast_type": doc.get("forecast_type", ""),
            "customer_id": doc.get("customer_id", "system"),
            "mape": doc.get("mape", 0),
            "wmape_accuracy": doc.get("wmape_accuracy", 0),
            "mae": doc.get("mae", 0),
            "rmse": doc.get("rmse", 0),
            "direction_accuracy": doc.get("direction_accuracy", 0),
            "period_accuracy": doc.get("period_accuracy", {}),
            "stats": doc.get("stats", {}),
            "rate_90_pass": doc.get("rate_90_pass", False),
            "rate_85_pass": doc.get("rate_85_pass", False),
            "r2_score": doc.get("r2_score", 0),
            "daily_errors": doc.get("daily_errors", []),
            "calculated_at": doc.get("calculated_at")
        }

    def _get_days_in_month(self, year: int, month: int) -> int:
        """获取指定月份的天数"""
        if month == 12:
            next_month = datetime(year + 1, 1, 1)
        else:
            next_month = datetime(year, month + 1, 1)
        this_month = datetime(year, month, 1)
        return (next_month - this_month).days

    def _aggregate_actual_prices(self, actual_docs: List[Dict]) -> Dict[str, Dict[str, float]]:
        """聚合实际价格为日度统计"""
        actual_daily_stats = {}

        for doc in actual_docs:
            date_str = doc["datetime"].strftime("%Y-%m-%d")
            price = doc["avg_clearing_price"]

            if date_str not in actual_daily_stats:
                actual_daily_stats[date_str] = {
                    "prices": [],
                    "max": price,
                    "min": price,
                    "sum": 0,
                    "count": 0
                }

            stats = actual_daily_stats[date_str]
            stats["prices"].append(price)
            stats["max"] = max(stats["max"], price)
            stats["min"] = min(stats["min"], price)
            stats["sum"] += price
            stats["count"] += 1

        # 计算每日均值
        for stats in actual_daily_stats.values():
            stats["mean"] = stats["sum"] / stats["count"] if stats["count"] > 0 else 0

        return actual_daily_stats

    def _get_last_month_avg(self, target_year: int, target_month: int) -> Optional[float]:
        """获取上月均价"""
        if target_month == 1:
            last_month_year = target_year - 1
            last_month = 12
        else:
            last_month_year = target_year
            last_month = target_month - 1

        start_of_month = datetime(last_month_year, last_month, 1)
        days_in_month = self._get_days_in_month(last_month_year, last_month)
        end_of_month = datetime(last_month_year, last_month, days_in_month, 23, 59, 59)

        actual_collection = self.db["day_ahead_spot_price"]
        docs = list(actual_collection.find({
            "datetime": {"$gte": start_of_month, "$lte": end_of_month}
        }))

        if not docs:
            return None

        total = sum(doc["avg_clearing_price"] for doc in docs)
        return round(total / len(docs), 2) if docs else None
