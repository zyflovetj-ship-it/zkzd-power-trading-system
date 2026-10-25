"""
短期负荷预测服务层

遵循规范：docs/spec/后端开发规范.md
- Service 层抛出 ValueError，由 API 层转换为 HTTPException
- 使用 Long Format 时序数据存储（每个时间点独立记录）
- 24:00 处理：业务日第96个点存储为次日 00:00，查询使用左开右闭区间
- 后端负责时间标签格式化
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pymongo.database import Database
from pymongo.errors import OperationFailure

logger = logging.getLogger(__name__)


class ShortTermLoadForecastService:
    """短期负荷预测服务"""

    def __init__(self, db: Database):
        self.db = db
        self.collection = db["short_term_load_forecast"]
        self.actual_collection = db["user_load_data"]  # 实际负荷数据
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """
        确保查询需要的索引存在
        遵循规范：安全创建索引，避免冲突
        """
        try:
            # 检查 short_term_load_forecast 集合索引
            has_datetime_index = False
            for idx in self.collection.list_indexes():
                if "key" in idx and "datetime" in idx["key"]:
                    has_datetime_index = True
                    break
            if not has_datetime_index:
                try:
                    self.collection.create_index([("datetime", 1)], name="datetime_1")
                    self.collection.create_index(
                        [("forecast_date", 1), ("forecast_type", 1)],
                        name="forecast_date_type_1"
                    )
                except OperationFailure:
                    logger.debug("创建索引失败（可能已存在不同选项的索引）")
        except Exception:
            logger.debug("索引检查异常，已忽略", exc_info=True)

    def get_forecast_curve(
        self,
        forecast_date: datetime,
        forecast_type: str = "d+1"
    ) -> Dict[str, Any]:
        """
        获取指定预测日期和类型的96点预测曲线

        Args:
            forecast_date: 预测日期（业务日）
            forecast_type: 预测类型，可选值：d+1, d+2, d+3

        Returns:
            包含96点预测曲线的字典
        """
        if forecast_type not in ["d+1", "d+2", "d+3"]:
            raise ValueError(f"无效的预测类型: {forecast_type}，支持：d+1, d+2, d+3")

        # 计算预测目标日期
        days_ahead = int(forecast_type.split("+")[1])
        forecast_target_date = forecast_date + timedelta(days=days_ahead)

        # 查询预测数据
        # datetime 字段存储的是预测目标日期的时间点
        # 尝试用 forecast_target_date 范围查询，若无结果则用 forecast_date 范围查询（兼容旧数据）
        start_of_target = forecast_target_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_target = start_of_target + timedelta(days=1)
        start_of_forecast = forecast_date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_forecast = start_of_forecast + timedelta(days=1)

        query_base = {
            "forecast_date": forecast_date.replace(hour=0, minute=0, second=0, microsecond=0),
            "forecast_type": forecast_type,
        }
        projection = {"_id": 0, "datetime": 1, "forecast_value": 1}

        # 先尝试用目标日期范围查询
        cursor = self.collection.find(
            {**query_base, "datetime": {"$gt": start_of_target, "$lte": end_of_target}},
            projection
        ).sort("datetime", 1)
        docs = list(cursor)

        # 若无结果，用预测日期范围查询（兼容 datetime 等于 forecast_date 的旧数据）
        if not docs:
            cursor = self.collection.find(
                {**query_base, "datetime": {"$gt": start_of_forecast, "$lte": end_of_forecast}},
                projection
            ).sort("datetime", 1)
            docs = list(cursor)

        # 尝试获取实际值（如果是历史数据）
        actual_data = self._get_actual_load_data(forecast_target_date)
        has_actual = len(actual_data) > 0

        # 格式化数据点
        formatted: List[Dict[str, Any]] = []
        for doc in docs:
            rec = self._format_time_point(doc, "forecast_value", forecast_target_date, actual_data)
            if rec is not None:
                formatted.append(rec)

        total_points = len(formatted)
        completeness = round(total_points / 96 * 100, 2)

        return {
            "forecast_date": forecast_date.strftime("%Y-%m-%d"),
            "forecast_target_date": forecast_target_date.strftime("%Y-%m-%d"),
            "forecast_type": forecast_type,
            "data": formatted,
            "total_points": total_points,
            "completeness": completeness,
            "has_actual": has_actual,
        }

    def get_multiple_forecasts(
        self,
        forecast_date: datetime,
        forecast_types: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        获取指定预测日期的多个预测类型曲线

        Args:
            forecast_date: 预测日期（业务日）
            forecast_types: 预测类型列表，默认为 ["d+1", "d+2", "d+3"]
        """
        if forecast_types is None:
            forecast_types = ["d+1", "d+2", "d+3"]

        curves: List[Dict[str, Any]] = []
        for ftype in forecast_types:
            try:
                curve = self.get_forecast_curve(forecast_date, ftype)
                curves.append(curve)
            except ValueError as ve:
                logger.error("获取预测曲线失败: %s, 错误: %s", ftype, ve, exc_info=True)

        return {"forecast_date": forecast_date.strftime("%Y-%m-%d"), "curves": curves}

    def get_forecast_accuracy(
        self,
        forecast_date: datetime,
        forecast_type: str = "d+1"
    ) -> Dict[str, Any]:
        """
        计算预测精度指标

        Args:
            forecast_date: 预测日期（业务日）
            forecast_type: 预测类型

        Returns:
            包含 MAE, MAPE, RMSE 等精度指标的字典
        """
        curve_data = self.get_forecast_curve(forecast_date, forecast_type)

        if not curve_data["has_actual"]:
            raise ValueError(f"预测目标日期 {curve_data['forecast_target_date']} 尚无实际数据，无法计算精度")

        # 提取预测值和实际值
        forecast_values: List[float] = []
        actual_values: List[float] = []
        errors: List[Dict[str, Any]] = []

        for point in curve_data["data"]:
            if point.get("actual_value") is not None:
                fv = point["forecast_value"]
                av = point["actual_value"]
                forecast_values.append(fv)
                actual_values.append(av)
                error = abs(fv - av)
                errors.append({"time": point["time"], "error": error})

        if len(forecast_values) == 0:
            raise ValueError("没有有效的预测-实际数据对，无法计算精度")

        # 计算精度指标
        mae = sum(abs(f - a) for f, a in zip(forecast_values, actual_values)) / len(forecast_values)

        mape_values = [abs((f - a) / a * 100) for f, a in zip(forecast_values, actual_values) if a != 0]
        mape = sum(mape_values) / len(mape_values) if mape_values else None

        rmse = (sum((f - a) ** 2 for f, a in zip(forecast_values, actual_values)) / len(forecast_values)) ** 0.5

        max_error_item = max(errors, key=lambda x: x["error"])

        return {
            "forecast_date": forecast_date.strftime("%Y-%m-%d"),
            "forecast_target_date": curve_data["forecast_target_date"],
            "forecast_type": forecast_type,
            "mae": round(mae, 2),
            "mape": round(mape, 2) if mape is not None else None,
            "rmse": round(rmse, 2),
            "max_error": round(max_error_item["error"], 2),
            "max_error_time": max_error_item["time"],
        }

    def get_forecast_list(
        self,
        start_date: datetime,
        end_date: datetime
    ) -> List[Dict[str, Any]]:
        """
        获取指定日期范围内的预测列表

        Args:
            start_date: 起始日期
            end_date: 结束日期

        Returns:
            预测列表
        """
        # 聚合查询获取每个预测日期的可用预测类型
        pipeline = [
            {
                "$match": {
                    "forecast_date": {
                        "$gte": start_date.replace(hour=0, minute=0, second=0, microsecond=0),
                        "$lte": end_date.replace(hour=0, minute=0, second=0, microsecond=0)
                    }
                }
            },
            {
                "$group": {
                    "_id": "$forecast_date",
                    "forecast_types": {"$addToSet": "$forecast_type"},
                    "created_at": {"$first": "$created_at"}
                }
            },
            {"$sort": {"_id": -1}}
        ]

        results: List[Dict[str, Any]] = []
        for doc in self.collection.aggregate(pipeline):
            forecast_date = doc["_id"]
            # 检查是否有实际数据（检查 d+1 的目标日期）
            target_date = forecast_date + timedelta(days=1)
            actual_data = self._get_actual_load_data(target_date)

            results.append({
                "forecast_date": forecast_date.strftime("%Y-%m-%d"),
                "forecast_target_date": target_date.strftime("%Y-%m-%d"),
                "forecast_types": sorted(doc["forecast_types"]),
                "has_actual": len(actual_data) > 0,
                "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
            })

        return results

    # ========== 私有辅助方法 ==========

    def _get_actual_load_data(self, date: datetime) -> Dict[str, float]:
        """
        获取实际负荷数据（所有用户汇总）

        Args:
            date: 日期

        Returns:
            时间标签 -> 实际负荷值的字典
        """
        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        # 使用聚合管道按时间点汇总所有用户的负荷值
        pipeline = [
            {"$match": {"timestamp": {"$gt": start_of_day, "$lte": end_of_day}}},
            {"$group": {
                "_id": "$timestamp",
                "total_load": {"$sum": "$load_value"}
            }},
            {"$sort": {"_id": 1}}
        ]

        actual_data: Dict[str, float] = {}
        for doc in self.actual_collection.aggregate(pipeline):
            ts = doc["_id"]
            if not isinstance(ts, datetime):
                continue
            total_load = doc.get("total_load")
            if total_load is None:
                continue

            next_day = start_of_day + timedelta(days=1)
            time_label = "24:00" if (ts.hour == 0 and ts.minute == 0 and ts.date() == next_day.date()) else ts.strftime("%H:%M")

            actual_data[time_label] = float(total_load)

        return actual_data

    def _format_time_point(
        self,
        point: Dict[str, Any],
        field_name: str,
        query_date: datetime,
        actual_data: Dict[str, float]
    ) -> Optional[Dict[str, Any]]:
        """
        将数据库记录格式化为前端需要的结构

        Args:
            point: 数据库记录
            field_name: 值字段名
            query_date: 查询日期（用于判断24:00）
            actual_data: 实际数据字典

        Returns:
            格式化后的数据点，或 None（如果数据无效）
        """
        if not point:
            return None

        ts = point.get("datetime")
        if not isinstance(ts, datetime):
            return None

        raw_val = point.get(field_name)
        if raw_val is None:
            return None

        try:
            forecast_value = round(float(raw_val), 2)
        except (TypeError, ValueError):
            return None

        # 格式化时间标签（24:00 处理）
        next_day = query_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        time_label = "24:00" if (ts.hour == 0 and ts.minute == 0 and ts.date() == next_day.date()) else ts.strftime("%H:%M")

        # 获取实际值（如果有）
        actual_value = actual_data.get(time_label)

        result = {
            "time": time_label,
            "forecast_value": forecast_value,
            "timestamp": ts.isoformat()
        }

        if actual_value is not None:
            result["actual_value"] = round(actual_value, 2)

        return result
