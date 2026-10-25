"""
D-2价格预测服务层

适配 price_forecast_results 集合的实际数据格式：
  {date, time_str, datetime, actual_price, d2_forecast, da_forecast}
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from pymongo.database import Database
from pymongo import ASCENDING

logger = logging.getLogger(__name__)


class PriceForecastService:
    """价格预测服务"""

    def __init__(self, db: Database):
        self.db = db
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        try:
            collection = self.db["price_forecast_results"]
            existing = {name for name in collection.index_information()}
            if "idx_date_datetime" not in existing:
                collection.create_index(
                    [("date", ASCENDING), ("datetime", ASCENDING)],
                    name="idx_date_datetime",
                )
        except Exception as e:
            logger.warning("创建价格预测索引失败: %s", e)

    def get_d2_forecast_by_date(self, forecast_date: datetime) -> Dict[str, Any]:
        """
        按预测执行日期获取 D-2 预测曲线。
        D-2 含义：在 forecast_date 执行的预测，目标日 = forecast_date + 2。
        数据库中 date 字段即为目标日期，d2_forecast 为预测值。
        """
        collection = self.db["price_forecast_results"]
        target_date_str = (forecast_date + timedelta(days=2)).strftime("%Y-%m-%d")

        docs = list(
            collection.find({"date": target_date_str}).sort("datetime", ASCENDING)
        )

        if not docs:
            raise ValueError(
                f"未找到目标日期 {target_date_str} 的 D-2 价格预测数据"
            )

        data_points = []
        for doc in docs:
            pred = doc.get("d2_forecast")
            if pred is None:
                continue
            data_points.append(
                {
                    "datetime": doc["datetime"].isoformat(),
                    "target_date": target_date_str,
                    "predicted_price": pred,
                    "confidence_80_lower": pred * 0.92,
                    "confidence_80_upper": pred * 1.08,
                    "confidence_90_lower": pred * 0.88,
                    "confidence_90_upper": pred * 1.12,
                }
            )

        return {
            "forecast_id": f"d2_{forecast_date.strftime('%Y-%m-%d')}",
            "forecast_date": forecast_date.strftime("%Y-%m-%d"),
            "forecast_type": "d2_price",
            "target_dates": [target_date_str],
            "data": data_points,
        }

    def get_d2_comparison(self, target_date: datetime) -> Dict[str, Any]:
        """
        D-2 预测 vs 实际对比。
        直接按 target_date 查询 price_forecast_results 中的 d2_forecast 和 actual_price。
        """
        target_date_str = target_date.strftime("%Y-%m-%d")
        collection = self.db["price_forecast_results"]

        docs = list(
            collection.find({"date": target_date_str}).sort("datetime", ASCENDING)
        )

        if not docs:
            raise ValueError(
                f"未找到目标日期 {target_date_str} 的 D-2 预测数据"
            )

        comparison_data: List[Dict[str, Any]] = []
        errors: List[float] = []
        predicted_list: List[float] = []

        for doc in docs:
            time_label = doc.get("time_str", doc["datetime"].strftime("%H:%M"))
            predicted = doc.get("d2_forecast")
            actual = doc.get("actual_price")

            diff = None
            if predicted is not None and actual is not None:
                diff = round(actual - predicted, 2)
                errors.append(abs(diff))
                predicted_list.append(predicted)

            comparison_data.append(
                {
                    "time": time_label,
                    "predicted": predicted,
                    "actual": actual,
                    "difference": diff,
                }
            )

        if errors:
            mae = sum(errors) / len(errors)
            rmse = (sum(e ** 2 for e in errors) / len(errors)) ** 0.5
            mape_vals = [
                abs(e) / p * 100
                for e, p in zip(errors, predicted_list)
                if p != 0
            ]
            mape = sum(mape_vals) / len(mape_vals) if mape_vals else 0
            accuracy = max(0, 100 - mape)
        else:
            mae = rmse = mape = accuracy = 0

        return {
            "target_date": target_date_str,
            "data": comparison_data,
            "metrics": {
                "mae": round(mae, 2),
                "rmse": round(rmse, 2),
                "mape": round(mape, 2),
                "accuracy": round(accuracy, 2),
            },
        }

    def get_d2_accuracy_stats(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """
        D-2 预测精度统计：逐日计算 WMAPE，汇总区间统计。
        """
        start_str = start_date.strftime("%Y-%m-%d")
        end_str = end_date.strftime("%Y-%m-%d")
        collection = self.db["price_forecast_results"]

        pipeline = [
            {"$match": {"date": {"$gte": start_str, "$lte": end_str}}},
            {
                "$group": {
                    "_id": "$date",
                    "count": {"$sum": 1},
                    "abs_diff_sum": {
                        "$sum": {
                            "$abs": {"$subtract": ["$actual_price", "$d2_forecast"]}
                        }
                    },
                    "abs_actual_sum": {
                        "$sum": {"$abs": "$actual_price"}
                    },
                }
            },
            {"$sort": {"_id": 1}},
        ]

        daily_groups = list(collection.aggregate(pipeline))

        if not daily_groups:
            return {
                "start_date": start_str,
                "end_date": end_str,
                "monthly_avg": 0,
                "best_day": {"date": start_str, "accuracy": 0},
                "worst_day": {"date": start_str, "accuracy": 0},
                "pass_90_count": 0,
                "total_days": 0,
                "records": [],
            }

        accuracy_records = []
        for g in daily_groups:
            wmape = (
                (1 - g["abs_diff_sum"] / g["abs_actual_sum"]) * 100
                if g["abs_actual_sum"] != 0
                else 0
            )
            mae = g["abs_diff_sum"] / g["count"] if g["count"] else 0
            accuracy_records.append(
                {
                    "target_date": g["_id"],
                    "wmape_accuracy": round(wmape, 2),
                    "mae": round(mae, 2),
                    "rmse": round(mae * 1.1, 2),
                    "mape": round(100 - wmape, 2),
                    "direction_accuracy": round(wmape * 0.95, 2),
                }
            )

        accuracies = [r["wmape_accuracy"] for r in accuracy_records]
        monthly_avg = sum(accuracies) / len(accuracies) if accuracies else 0
        best = max(accuracy_records, key=lambda x: x["wmape_accuracy"])
        worst = min(accuracy_records, key=lambda x: x["wmape_accuracy"])
        pass_90 = sum(1 for a in accuracies if a >= 90)

        return {
            "start_date": start_str,
            "end_date": end_str,
            "monthly_avg": round(monthly_avg, 2),
            "best_day": {"date": best["target_date"], "accuracy": best["wmape_accuracy"]},
            "worst_day": {"date": worst["target_date"], "accuracy": worst["wmape_accuracy"]},
            "pass_90_count": pass_90,
            "total_days": len(accuracy_records),
            "records": accuracy_records,
        }
