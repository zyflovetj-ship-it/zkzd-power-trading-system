import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pymongo.database import Database
from pymongo.errors import OperationFailure

# 说明：
# - 本服务实现“预测基础数据”模块的后端逻辑，包括：
#   1) 数据可用性矩阵查询（按12:00是否存在数据）
#   2) 96点曲线查询（将次日00:00显示为“24:00”，并按左开右闭查询区间）
# - 严格遵循 docs/spec/后端开发规范.md 要求：
#   * 使用 logging 记录异常，Service 抛出 ValueError 交由 API 层转换为 HTTPException
#   * 时序查询区间使用 (start_of_day, end_of_day]
#   * 24:00 规范化展示

logger = logging.getLogger(__name__)


# 数据项映射配置
# 1-5: weekly_forecast（需按 info_name 过滤，取 value 字段）
# 6-10: daily_release（取各自字段）
# 11-14: real_time_generation（取各自字段）
# 15: real_time_tieline（取 total_tieline_plan）
DATA_ITEM_CONFIG: Dict[int, Dict[str, Any]] = {
    # 周预测（weekly_forecast）
    1: {"name": "周系统负荷预测", "collection": "weekly_forecast", "field": "value", "filter": {"info_name": "系统负荷预测"}},
    2: {"name": "周统调光伏预测", "collection": "weekly_forecast", "field": "value", "filter": {"info_name": "统调光伏"}},
    3: {"name": "周统调风电预测", "collection": "weekly_forecast", "field": "value", "filter": {"info_name": "统调风电"}},
    4: {"name": "周水电(含抽蓄)预测", "collection": "weekly_forecast", "field": "value", "filter": {"info_name": "统调水电(含抽蓄)"}},
    5: {"name": "次周省间联络线可用容量", "collection": "weekly_forecast", "field": "value", "filter": {"info_name": "省间联络线容量"}},
    # 日前发布（daily_release）
    6: {"name": "短期系统负荷预测", "collection": "daily_release", "field": "system_load_forecast", "filter": {}},
    7: {"name": "短期光伏预测", "collection": "daily_release", "field": "pv_forecast", "filter": {}},
    8: {"name": "短期风电预测", "collection": "daily_release", "field": "wind_forecast", "filter": {}},
    9: {"name": "非市场化机组出力预测", "collection": "daily_release", "field": "nonmarket_unit_forecast", "filter": {}},
    10: {"name": "联络线总计划", "collection": "daily_release", "field": "tieline_plan", "filter": {}},
    # 实时发力（real_time_generation / actual_operation）
    11: {"name": "实际系统负荷", "collection": "actual_operation", "field": "system_load", "filter": {}},
    12: {"name": "实际风电出力", "collection": "real_time_generation", "field": "wind_generation", "filter": {}},
    13: {"name": "实际光电出力", "collection": "real_time_generation", "field": "solar_generation", "filter": {}},
    14: {"name": "实际水电(含抽蓄)出力", "collection": "real_time_generation", "field": "hydro_with_pumped_total_generation", "filter": {}},
    15: {"name": "联络线潮流", "collection": "actual_operation", "field": "tieline_flow", "filter": {}},
}


class ForecastBaseDataService:
    """预测基础数据服务"""

    def __init__(self, db: Database):
        self.db = db
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """
        确保查询需要的索引存在。
        安全策略：
        - 仅在未发现任何包含 'datetime' 键的索引时，尝试创建单字段索引 'datetime'
        - 捕获 OperationFailure，避免因既有索引选项冲突引发异常
        """
        try:
            for coll_name in {"weekly_forecast", "daily_release", "real_time_generation", "actual_operation"}:
                collection = self.db[coll_name]
                has_datetime_index = False
                for idx in collection.list_indexes():
                    # idx["key"] 是有序字典，检测是否包含 datetime 键
                    if "key" in idx and "datetime" in idx["key"]:
                        has_datetime_index = True
                        break
                if not has_datetime_index:
                    try:
                        collection.create_index([("datetime", 1)], name="datetime_1")
                    except OperationFailure:
                        logger.debug("创建索引失败（可能已存在不同选项的索引）: %s.datetime", coll_name)
        except Exception:
            # 索引检查不应阻断业务
            logger.debug("索引检查异常，已忽略", exc_info=True)

    def get_data_availability(self, base_date: datetime, date_range_type: str = "recent_3") -> Dict[str, Any]:
        """
        获取数据可用性矩阵。
        - 可用性判定：指定日期的12:00是否存在该数据项的数据点。
        """
        date_list = self._generate_date_list(base_date, date_range_type)
        availability_matrix: List[List[Dict[str, Any]]] = []

        for data_item_id in range(1, 16):
            config = DATA_ITEM_CONFIG[data_item_id]
            collection = self.db[config["collection"]]
            row: List[Dict[str, Any]] = []

            for date_str in date_list:
                try:
                    target_dt = datetime.strptime(date_str, "%Y-%m-%d").replace(hour=12, minute=0, second=0, microsecond=0)
                except ValueError as e:
                    raise ValueError(f"无效日期格式: {date_str}") from e

                query = {"datetime": target_dt}
                query.update(config["filter"])
                # 同时查询目标字段，判断其是否存在且非空
                field_name = config["field"]
                doc = collection.find_one(query, {"_id": 0, "datetime": 1, field_name: 1})
                # 可用性判断：文档存在 且 目标字段非空
                is_available = bool(doc and doc.get("datetime") and doc.get(field_name) is not None)
                row.append(
                    {
                        "data_item_id": data_item_id,
                        "data_item_name": config["name"],
                        "date": date_str,
                        "is_available": is_available,
                        "sample_timestamp": (doc.get("datetime").isoformat() if doc and doc.get("datetime") else None),
                    }
                )

            availability_matrix.append(row)

        return {
            "base_date": base_date.strftime("%Y-%m-%d"),
            "date_range": date_list,
            "availability_matrix": availability_matrix,
        }

    def get_curve_data(self, data_item_id: int, date: datetime) -> Dict[str, Any]:
        """
        获取指定数据项在指定日期的96点曲线。
        查询区间：左开右闭 (date 00:00, date+1 00:00]
        展示规则：次日00:00显示为“24:00”
        """
        if data_item_id not in DATA_ITEM_CONFIG:
            raise ValueError(f"无效的数据项ID: {data_item_id}")

        config = DATA_ITEM_CONFIG[data_item_id]
        collection = self.db[config["collection"]]
        field_name = config["field"]

        start_of_day = date.replace(hour=0, minute=0, second=0, microsecond=0)
        end_of_day = start_of_day + timedelta(days=1)

        query = {"datetime": {"$gt": start_of_day, "$lte": end_of_day}}
        query.update(config["filter"])
        projection = {"_id": 0, "datetime": 1, field_name: 1}

        cursor = collection.find(query, projection).sort("datetime", 1)

        formatted: List[Dict[str, Any]] = []
        for doc in cursor:
            rec = self._format_time_point(doc, field_name, date)
            if rec is not None:
                formatted.append(rec)

        total_points = len(formatted)
        completeness = round(total_points / 96 * 100, 2)

        return {
            "data_item_id": data_item_id,
            "data_item_name": config["name"],
            "date": date.strftime("%Y-%m-%d"),
            "data": formatted,
            "total_points": total_points,
            "completeness": completeness,
        }

    def get_multiple_curves(self, requests: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        批量获取曲线数据。
        参数示例: [{"data_item_id": 1, "date": "2025-01-10"}, ...]
        """
        curves: List[Dict[str, Any]] = []
        for req in requests:
            try:
                data_item_id = int(req["data_item_id"])
                date_str = str(req["date"])
                date = datetime.strptime(date_str, "%Y-%m-%d")
                curve = self.get_curve_data(data_item_id, date)
                curves.append(curve)
            except ValueError as ve:
                # 单条错误不阻断整体
                logger.error("解析请求或获取曲线失败: %s, 错误: %s", req, ve, exc_info=True)
            except Exception as e:
                logger.error("获取曲线出现异常: %s, 错误: %s", req, e, exc_info=True)
        return {"curves": curves}

    # ========== 私有辅助方法 ==========

    def _generate_date_list(self, base_date: datetime, range_type: str) -> List[str]:
        """根据范围类型生成日期列表"""
        if range_type == "recent_3":
            days = [base_date - timedelta(days=i) for i in range(2, -1, -1)]  # D-2, D-1, D
        elif range_type == "recent_7":
            days = [base_date - timedelta(days=i) for i in range(7, -1, -1)]  # D-7 ... D
        elif range_type == "historical_10":
            days = [base_date - timedelta(days=i) for i in range(10, 0, -1)]  # D-10 ... D-1
        elif range_type == "desktop_full_range":
            days = [base_date + timedelta(days=i) for i in range(-10, 3)]  # D-10 ... D-1, D, D+1, D+2
        else:
            raise ValueError(f"无效的日期范围类型: {range_type}")
        return [d.strftime("%Y-%m-%d") for d in days]

    def _format_time_point(self, point: Dict[str, Any], field_name: str, query_date: datetime) -> Optional[Dict[str, Any]]:
        """
        将数据库记录格式化为前端需要的结构。
        防御式实现：
        - point 为空、缺少 datetime、目标字段为空/非数值时直接跳过（返回 None）
        - 将次日00:00格式化为“24:00”
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
            val = round(float(raw_val), 2)
        except (TypeError, ValueError):
            return None

        next_day = query_date.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        time_label = "24:00" if (ts.hour == 0 and ts.minute == 0 and ts.date() == next_day.date()) else ts.strftime("%H:%M")

        return {"time": time_label, "value": val, "timestamp": ts.isoformat()}

