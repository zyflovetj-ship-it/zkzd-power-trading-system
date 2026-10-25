import logging
import math
from datetime import datetime, timedelta
from typing import Any, Dict, List

from pymongo.database import Database

from webapp.models.forecast_accuracy import ForecastAccuracyData, AccuracyMetric, ForecastAccuracyItem

logger = logging.getLogger(__name__)


class ForecastAccuracyService:

    def __init__(self, db: Database) -> None:
        self.db = db
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        try:
            for coll_name in ["short_term_load_forecast", "medium_long_term_load_forecast", "price_forecast"]:
                coll = self.db[coll_name]
                existing = {idx.get('name') for idx in coll.list_indexes()}
                if f'idx_{coll_name}_date' not in existing:
                    coll.create_index([('date', 1)], name=f'idx_{coll_name}_date')
        except Exception as exc:
            logger.warning("创建预测精度索引时出错: %s", exc)

    def get_accuracy(self, forecast_type: str, days: int = 30) -> Dict[str, Any]:
        if forecast_type == "short_term_load":
            actual_coll = self.db.user_load_data
            forecast_coll = self.db.short_term_load_forecast
            time_field = "timestamp"
        elif forecast_type == "medium_long_term_load":
            actual_coll = self.db.user_load_data
            forecast_coll = self.db.medium_long_term_load_forecast
            time_field = "timestamp"
        elif forecast_type == "price":
            actual_coll = self.db.day_ahead_spot_price
            forecast_coll = self.db.price_forecast
            time_field = "timestamp"
        else:
            raise ValueError(f"不支持的预测类型: {forecast_type}")

        end_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        start_date = end_date - timedelta(days=days)

        trend: List[ForecastAccuracyItem] = []
        scatter: List[dict] = []
        total_ae = 0.0
        total_ape = 0.0
        total_se = 0.0
        total_count = 0

        for day_offset in range(days):
            day = start_date + timedelta(days=day_offset)

            # 先取预测：预测文档的 date 是"生成日"，而 timestamp 指向"目标日"
            # （d+1/d+2/d+3 可能相差 1~3 天）。
            forecast_docs = list(forecast_coll.find(
                {"date": day.strftime("%Y-%m-%d")},
                {"value": 1, "timestamp": 1, "_id": 0}
            ))
            if not forecast_docs:
                continue

            # 实际数据必须按预测的 timestamp（目标日）取，
            # 否则实际窗口会比目标日早 N 天，按时间戳 join 时全部落空，
            # 导致 MAE/MAPE/RMSE 恒为 0 且 trend 为空。
            ts_list = [d["timestamp"] for d in forecast_docs if d.get("timestamp") is not None]
            if not ts_list:
                logger.warning(
                    "%s %s 的预测记录缺少 timestamp，无法与实际值配对",
                    forecast_type, day.strftime("%Y-%m-%d"),
                )
                continue

            actual_docs = list(actual_coll.find(
                {time_field: {"$gte": min(ts_list), "$lte": max(ts_list)}},
                {time_field: 1, "value": 1, "_id": 0}
            ))
            if not actual_docs:
                continue

            # 按时间戳配对：原实现按列表下标配对且两侧均未排序，
            # 任一侧缺点/顺序不一致都会让 MAE/MAPE/RMSE 整体错位。
            actual_by_ts = {
                doc[time_field]: doc.get("value", 0)
                for doc in actual_docs
                if time_field in doc
            }
            pairs: List[tuple] = []
            unmatched = 0
            for fc in forecast_docs:
                ts = fc.get("timestamp")
                if ts is not None and ts in actual_by_ts:
                    pairs.append((actual_by_ts[ts], fc.get("value", 0)))
                else:
                    unmatched += 1

            if unmatched:
                logger.warning(
                    "%s %s 有 %d/%d 条预测记录找不到对应实际值，已跳过",
                    forecast_type, day.strftime("%Y-%m-%d"), unmatched, len(forecast_docs),
                )
            if not pairs:
                continue

            day_ae = 0.0
            day_ape = 0.0
            day_se = 0.0
            day_count = len(pairs)

            for actual_val, forecast_val in pairs:
                ae = abs(actual_val - forecast_val)
                day_ae += ae
                day_se += (actual_val - forecast_val) ** 2
                if abs(actual_val) > 1e-6:
                    day_ape += ae / abs(actual_val) * 100
                if day_offset >= days - 10:
                    scatter.append({"actual": round(actual_val, 2), "forecast": round(forecast_val, 2)})

            if day_count > 0:
                mae = round(day_ae / day_count, 4)
                mape = round(day_ape / day_count, 4)
                rmse = round(math.sqrt(day_se / day_count), 4)
                trend.append(ForecastAccuracyItem(
                    date=day.strftime("%Y-%m-%d"),
                    mae=mae, mape=mape, rmse=rmse
                ))
                total_ae += day_ae
                total_ape += day_ape
                total_se += day_se
                total_count += day_count

        metrics = AccuracyMetric()
        if total_count > 0:
            metrics = AccuracyMetric(
                mae=round(total_ae / total_count, 4),
                mape=round(total_ape / total_count, 4),
                rmse=round(math.sqrt(total_se / total_count), 4)
            )

        return ForecastAccuracyData(
            forecast_type=forecast_type,
            metrics=metrics,
            trend=trend,
            scatter=scatter
        ).model_dump()
