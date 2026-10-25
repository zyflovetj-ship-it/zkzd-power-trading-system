"""
日前价格预测服务层

适配 price_forecast_results 集合的实际数据格式：
  {date, time_str, datetime, actual_price, d2_forecast, da_forecast}

每个目标日期只有一组 da_forecast 数据，因此预测版本固定返回一个。
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pymongo.database import Database
from pymongo import ASCENDING

logger = logging.getLogger(__name__)


class DayAheadPriceForecastService:
    """日前价格预测服务"""

    def __init__(self, db: Database):
        self.db = db

    # ------------------------------------------------------------------
    # 1. 获取预测版本列表
    #    实际数据中每个 date 只有一组 da_forecast，返回单一版本。
    # ------------------------------------------------------------------
    def get_forecast_versions(
        self,
        target_date: datetime,
        forecast_type: str = "d1_price",
    ) -> List[Dict[str, Any]]:
        target_date_str = target_date.strftime("%Y-%m-%d")
        collection = self.db["price_forecast_results"]

        count = collection.count_documents({"date": target_date_str})
        if count == 0:
            return []

        return [
            {
                "forecast_id": f"da_{target_date_str}",
                "forecast_type": "d1_price",
                "model_type": "日前预测",
                "model_version": "v1.0",
                "created_at": target_date_str,
                "target_date": target_date_str,
            }
        ]

    # ------------------------------------------------------------------
    # 2. 获取图表数据（预测曲线 + 实际曲线）
    # ------------------------------------------------------------------
    def get_chart_data(
        self, forecast_id: str, target_date: datetime
    ) -> Dict[str, Any]:
        target_date_str = target_date.strftime("%Y-%m-%d")
        collection = self.db["price_forecast_results"]

        docs = list(
            collection.find({"date": target_date_str}).sort("datetime", ASCENDING)
        )

        if not docs:
            raise ValueError(
                f"未找到目标日期 {target_date_str} 的日前预测数据"
            )

        chart_data = []
        has_actual = False
        for doc in docs:
            time_label = doc.get("time_str", doc["datetime"].strftime("%H:%M"))
            predicted = doc.get("da_forecast")
            actual = doc.get("actual_price")

            if actual is not None:
                has_actual = True

            pred_val = predicted if predicted is not None else 0
            data_point = {
                "datetime": doc["datetime"].isoformat(),
                "time": time_label,
                "predicted": pred_val,
                "actual": actual,
                "confidence_80_lower": pred_val * 0.92,
                "confidence_80_upper": pred_val * 1.08,
                "confidence_90_lower": pred_val * 0.88,
                "confidence_90_upper": pred_val * 1.12,
            }

            if actual is not None and predicted is not None:
                data_point["error"] = round(actual - predicted, 2)

            chart_data.append(data_point)

        return {
            "forecast_id": forecast_id,
            "target_date": target_date_str,
            "data": chart_data,
            "has_actual": has_actual,
        }

    # ------------------------------------------------------------------
    # 3. 获取准确度评估详情
    #    forecast_id 格式为 da_YYYY-MM-DD，从中提取目标日期，
    #    逐点计算精度指标。
    # ------------------------------------------------------------------
    def get_accuracy_details(
        self, forecast_id: str
    ) -> Optional[Dict[str, Any]]:
        target_date_str = forecast_id.replace("da_", "", 1)
        collection = self.db["price_forecast_results"]

        docs = list(
            collection.find({"date": target_date_str}).sort("datetime", ASCENDING)
        )

        if not docs:
            return None

        errors: List[float] = []
        predicted_list: List[float] = []
        actual_list: List[float] = []
        direction_correct = 0
        direction_total = 0

        for i, doc in enumerate(docs):
            predicted = doc.get("da_forecast")
            actual = doc.get("actual_price")
            if predicted is None or actual is None:
                continue
            diff = actual - predicted
            errors.append(abs(diff))
            predicted_list.append(predicted)
            actual_list.append(actual)

            if i > 0:
                prev_actual = docs[i - 1].get("actual_price")
                prev_pred = docs[i - 1].get("da_forecast")
                if prev_actual is not None and prev_pred is not None:
                    actual_dir = actual - prev_actual
                    pred_dir = predicted - prev_pred
                    if actual_dir != 0:
                        direction_total += 1
                        if (actual_dir > 0 and pred_dir > 0) or (
                            actual_dir < 0 and pred_dir < 0
                        ):
                            direction_correct += 1

        if not errors:
            return None

        mae = sum(errors) / len(errors)
        rmse = (sum(e ** 2 for e in errors) / len(errors)) ** 0.5
        mape_vals = [
            abs(e) / p * 100 for e, p in zip(errors, predicted_list) if p != 0
        ]
        mape = sum(mape_vals) / len(mape_vals) if mape_vals else 0
        wmape = max(0, 100 - mape)
        direction_accuracy = (
            (direction_correct / direction_total * 100) if direction_total else 0
        )

        mean_actual = sum(actual_list) / len(actual_list)
        ss_res = sum((a - p) ** 2 for a, p in zip(actual_list, predicted_list))
        ss_tot = sum((a - mean_actual) ** 2 for a in actual_list)
        r2 = 1 - ss_res / ss_tot if ss_tot != 0 else 0

        return {
            "forecast_id": forecast_id,
            "target_date": target_date_str,
            "forecast_type": "d1_price",
            "customer_id": "system",
            "forecast_date": target_date_str,
            "model_type": "日前预测",
            "model_version": "v1.0",
            "wmape_accuracy": round(wmape, 2),
            "mae": round(mae, 2),
            "rmse": round(rmse, 2),
            "mape": round(mape, 2),
            "direction_accuracy": round(direction_accuracy, 2),
            "period_accuracy": {},
            "stats": {},
            "rate_90_pass": wmape >= 90,
            "rate_85_pass": wmape >= 85,
            "r2_score": round(r2, 4),
            "calculated_at": datetime.now().isoformat(),
        }
