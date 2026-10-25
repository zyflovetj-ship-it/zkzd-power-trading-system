"""
现货交易复盘服务层

提供96点精细化交易复盘、预测精度评估、交易时机分析、
成本优化建议、风险事件回溯等功能。
"""
import logging
import math
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple

from bson import ObjectId
from pymongo.database import Database

from webapp.services.tou_service import get_tou_rule_by_date

logger = logging.getLogger(__name__)


class SpotReviewService:
    """现货交易复盘服务"""

    def __init__(self, db: Database):
        self.db = db
        # 索引创建应在构造时执行一次；原实现把它放在 generate_review() 内，
        # 每次复盘都额外发起 5 次 create_index 往返，且失败会直接中断业务。
        try:
            self._ensure_indexes()
        except Exception as exc:
            logger.warning("创建现货复盘索引时出错: %s", exc)

    def _ensure_indexes(self):
        """确保数据库索引存在（失败不阻断业务，见规范 §4.2）"""
        try:
            tx_col = self.db["spot_transactions"]
            review_col = self.db["spot_trading_reviews"]

            tx_col.create_index([("customer_id", 1), ("date", 1), ("spot_type", 1)])
            tx_col.create_index([("date", 1)])
            tx_col.create_index([("spot_type", 1)])

            review_col.create_index([("customer_id", 1), ("review_date", -1)])
            review_col.create_index([("review_type", 1), ("review_date", -1)])
        except Exception as exc:
            logger.warning("创建现货复盘索引时出错: %s", exc)

    # ========== 核心方法：生成复盘报告 ==========

    def generate_review(
        self,
        customer_id: str,
        review_date: str,
        review_type: str = "daily",
        operator: str = ""
    ) -> Dict[str, Any]:
        """
        生成复盘报告

        流程：查询交易数据 → 计算概览统计 → 时段分析 → 预测精度 → 识别风险事件 → 生成优化建议 → 存入spot_trading_reviews
        """
        customer_name = self._get_customer_name(customer_id)

        date_range = self._get_date_range(review_date, review_type)

        actual_data = self._query_spot_data(
            customer_id, date_range, spot_type="day_ahead", source="actual"
        )
        forecast_data = self._query_spot_data(
            customer_id, date_range, spot_type="day_ahead", source="forecast"
        )

        if not actual_data and not forecast_data:
            raise ValueError(
                f"客户 {customer_id} 在 {review_date} 无交易数据，无法生成复盘报告"
            )

        overview = self._calc_overview(actual_data, date_range)

        tou_map = self._get_tou_map(review_date)
        time_slot_analysis = self._calc_time_slot_analysis(actual_data, tou_map)

        forecast_accuracy = self._calc_forecast_accuracy(actual_data, forecast_data)

        special_events = self._identify_special_events(actual_data, forecast_data)

        optimization_suggestions = self._generate_optimization_suggestions(
            actual_data, forecast_data, time_slot_analysis, overview
        )

        review_doc = {
            "customer_id": customer_id,
            "customer_name": customer_name,
            "review_date": review_date,
            "review_type": review_type,
            "overview": overview,
            "time_slot_analysis": time_slot_analysis,
            "forecast_accuracy": forecast_accuracy,
            "special_events": special_events,
            "optimization_suggestions": optimization_suggestions,
            "created_at": datetime.now(),
            "created_by": operator,
        }

        review_col = self.db["spot_trading_reviews"]
        existing = review_col.find_one({
            "customer_id": customer_id,
            "review_date": review_date,
            "review_type": review_type,
        })
        if existing:
            review_col.replace_one({"_id": existing["_id"]}, review_doc)
            review_doc["_id"] = existing["_id"]
        else:
            insert_result = review_col.insert_one(review_doc)
            review_doc["_id"] = insert_result.inserted_id

        return self._format_review(review_doc)

    # ========== 96点复盘数据 ==========

    def get_96_point_data(
        self,
        customer_id: str,
        review_date: str
    ) -> Dict[str, Any]:
        """获取96点复盘数据：实际交易数据+预测数据+偏差"""
        date_range = [review_date]

        actual_data = self._query_spot_data(
            customer_id, date_range, spot_type="day_ahead", source="actual"
        )
        forecast_data = self._query_spot_data(
            customer_id, date_range, spot_type="day_ahead", source="forecast"
        )

        actual_by_time = {d["time_str"]: d for d in actual_data}
        forecast_by_time = {d["time_str"]: d for d in forecast_data}

        all_times = sorted(set(list(actual_by_time.keys()) + list(forecast_by_time.keys())))

        points = []
        for time_str in all_times:
            actual = actual_by_time.get(time_str)
            forecast = forecast_by_time.get(time_str)

            item: Dict[str, Any] = {"time": time_str}

            if actual:
                item["actual_volume"] = round(actual.get("volume_mwh", 0), 4)
                item["actual_price"] = round(actual.get("price_yuan_mwh", 0), 2)
                item["actual_cost"] = round(actual.get("cost_yuan", 0), 2)
            if forecast:
                item["forecast_volume"] = round(forecast.get("volume_mwh", 0), 4)
                item["forecast_price"] = round(forecast.get("price_yuan_mwh", 0), 2)
                item["forecast_cost"] = round(forecast.get("cost_yuan", 0), 2)

            if actual and forecast:
                a_vol = actual.get("volume_mwh", 0)
                f_vol = forecast.get("volume_mwh", 0)
                a_price = actual.get("price_yuan_mwh", 0)
                f_price = forecast.get("price_yuan_mwh", 0)

                vol_dev = a_vol - f_vol
                item["volume_deviation"] = round(vol_dev, 4)
                item["volume_deviation_rate"] = round(
                    (vol_dev / f_vol * 100) if f_vol != 0 else 0, 2
                )
                item["price_deviation"] = round(a_price - f_price, 2)
            elif actual and not forecast:
                item["volume_deviation"] = None
                item["volume_deviation_rate"] = None
                item["price_deviation"] = None

            points.append(item)

        return {
            "customer_id": customer_id,
            "review_date": review_date,
            "data": points,
        }

    # ========== 时段分析 ==========

    def get_time_slot_analysis(
        self,
        customer_id: str,
        review_date: str
    ) -> Dict[str, Any]:
        """获取时段分析：各时段(峰/平/谷)的交易量占比/成本占比/均价"""
        date_range = [review_date]
        actual_data = self._query_spot_data(
            customer_id, date_range, spot_type="day_ahead", source="actual"
        )

        if not actual_data:
            raise ValueError(
                f"客户 {customer_id} 在 {review_date} 无实际交易数据"
            )

        tou_map = self._get_tou_map(review_date)
        time_slot_analysis = self._calc_time_slot_analysis(actual_data, tou_map)

        return {
            "customer_id": customer_id,
            "review_date": review_date,
            "time_slot_analysis": time_slot_analysis,
        }

    # ========== 预测精度 ==========

    def get_forecast_accuracy(
        self,
        customer_id: str,
        review_date: str
    ) -> Dict[str, Any]:
        """获取预测精度：MAE/MAPE/RMSE/5%内命中率"""
        date_range = [review_date]
        actual_data = self._query_spot_data(
            customer_id, date_range, spot_type="day_ahead", source="actual"
        )
        forecast_data = self._query_spot_data(
            customer_id, date_range, spot_type="day_ahead", source="forecast"
        )

        forecast_accuracy = self._calc_forecast_accuracy(actual_data, forecast_data)

        return {
            "customer_id": customer_id,
            "review_date": review_date,
            "forecast_accuracy": forecast_accuracy,
        }

    # ========== 风险事件 ==========

    def get_special_events(
        self,
        customer_id: str,
        review_date: str
    ) -> Dict[str, Any]:
        """获取风险事件：异常价格事件/极端偏差事件"""
        date_range = [review_date]
        actual_data = self._query_spot_data(
            customer_id, date_range, spot_type="day_ahead", source="actual"
        )
        forecast_data = self._query_spot_data(
            customer_id, date_range, spot_type="day_ahead", source="forecast"
        )

        special_events = self._identify_special_events(actual_data, forecast_data)

        return {
            "customer_id": customer_id,
            "review_date": review_date,
            "special_events": special_events,
        }

    # ========== 内部方法 ==========

    def _get_customer_name(self, customer_id: str) -> str:
        """从 customers 集合获取客户名称。

        原实现有两处字段错误：按 ``customer_id`` 查询、按 ``customer_name`` 取值，
        而 customers 集合实际是 ``_id`` + ``user_name``，因此永远回落为原始 ID。
        """
        try:
            col = self.db["customers"]
            query: Dict[str, Any]
            if ObjectId.is_valid(customer_id):
                query = {"_id": ObjectId(customer_id)}
            else:
                # 兼容调用方传入业务标识的场景
                query = {"customer_id": customer_id}

            doc = col.find_one(query, {"user_name": 1, "_id": 0})
            if doc and doc.get("user_name"):
                return doc["user_name"]
            return customer_id
        except Exception as exc:
            logger.warning("查询客户名称失败（customer_id=%s）: %s", customer_id, exc, exc_info=True)
            return customer_id

    def _get_date_range(self, review_date: str, review_type: str) -> List[str]:
        """根据复盘类型计算日期范围"""
        d = date.fromisoformat(review_date)
        if review_type == "daily":
            return [review_date]
        elif review_type == "weekly":
            start = d - timedelta(days=d.weekday())
            return [(start + timedelta(days=i)).isoformat() for i in range(7)]
        elif review_type == "monthly":
            start = d.replace(day=1)
            if d.month == 12:
                end = d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
            else:
                end = d.replace(month=d.month + 1, day=1) - timedelta(days=1)
            days = (end - start).days + 1
            return [(start + timedelta(days=i)).isoformat() for i in range(days)]
        return [review_date]

    def _query_spot_data(
        self,
        customer_id: str,
        date_range: List[str],
        spot_type: str = "day_ahead",
        source: str = "actual"
    ) -> List[Dict[str, Any]]:
        """
        查询现货交易数据

        优先从spot_transactions集合查询，若无数据则从原始集合(day_ahead_spot_price/real_time_spot_price)查询
        """
        tx_col = self.db["spot_transactions"]
        tx_data = list(tx_col.find({
            "customer_id": customer_id,
            "date": {"$in": date_range},
            "spot_type": spot_type,
            "source": source,
        }).sort("datetime", 1))

        if tx_data:
            return [self._format_tx_point(d) for d in tx_data]

        return self._query_from_price_collections(
            customer_id, date_range, spot_type, source
        )

    def _query_from_price_collections(
        self,
        customer_id: str,
        date_range: List[str],
        spot_type: str,
        source: str
    ) -> List[Dict[str, Any]]:
        """从原始价格集合和负荷集合查询数据"""
        price_col_name = "day_ahead_spot_price" if spot_type == "day_ahead" else "real_time_spot_price"
        price_col = self.db[price_col_name]

        price_data = list(price_col.find({
            "date_str": {"$in": date_range},
        }).sort("time_str", 1))

        if not price_data:
            return []

        load_col = self.db["user_load_data"]
        start_dt = datetime.fromisoformat(date_range[0] + "T00:00:00")
        end_dt = datetime.fromisoformat(date_range[-1] + "T23:59:59")
        load_data = list(load_col.find({
            "customer_id": customer_id,
            "datetime": {"$gt": start_dt, "$lte": end_dt + timedelta(minutes=15)},
        }).sort("datetime", 1))
        load_by_time = {}
        for ld in load_data:
            ts = ld.get("datetime")
            if ts:
                key = ts.strftime("%H:%M") if ts.hour != 0 or ts.minute != 0 else "24:00"
                d_key = ts.strftime("%Y-%m-%d")
                if ts.hour == 0 and ts.minute == 0:
                    prev_day = (ts - timedelta(days=1)).strftime("%Y-%m-%d")
                    if prev_day in date_range:
                        d_key = prev_day
                        key = "24:00"
                # 兼容多种负荷数据源字段：
                #   load_kwh —— 已按 kWh 计量的数据源（保留原有口径）
                #   value / load —— 功率读数(kW)，15 分钟时段电量(MWh) = kW × 0.25h / 1000
                raw_kwh = ld.get("load_kwh")
                if raw_kwh is None:
                    power_kw = ld.get("value", ld.get("load", 0)) or 0
                    vol_mwh = float(power_kw) * 0.25 / 1000.0
                else:
                    vol_mwh = float(raw_kwh) / 1000.0 * 0.25
                load_by_time[f"{d_key}_{key}"] = vol_mwh

        result = []
        for pd in price_data:
            price = pd.get("avg_clearing_price", 0) or 0
            time_str = pd.get("time_str", "")
            date_str = pd.get("date_str", "")
            load_key = f"{date_str}_{time_str}"
            # load_by_time 中已是 MWh，直接取用（不再二次换算）
            volume_mwh = load_by_time.get(load_key, 0)

            result.append({
                "time_str": time_str,
                "date_str": date_str,
                "price_yuan_mwh": round(price, 2),
                "volume_mwh": round(volume_mwh, 4),
                "cost_yuan": round(price * volume_mwh, 2),
            })

        return result

    def _format_tx_point(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """格式化spot_transactions中的数据点"""
        ts = doc.get("datetime")
        if ts:
            if ts.hour == 0 and ts.minute == 0:
                time_str = "24:00"
            else:
                time_str = ts.strftime("%H:%M")
        else:
            time_str = ""

        return {
            "time_str": time_str,
            "date_str": doc.get("date", ""),
            "price_yuan_mwh": doc.get("price_yuan_mwh", 0),
            "volume_mwh": doc.get("volume_mwh", 0),
            "cost_yuan": doc.get("cost_yuan", 0),
        }

    def _get_tou_map(self, review_date: str) -> Dict[str, str]:
        """获取分时电价时段映射"""
        d = datetime.fromisoformat(review_date + "T00:00:00")
        return get_tou_rule_by_date(d)

    def _calc_overview(
        self,
        actual_data: List[Dict[str, Any]],
        date_range: List[str]
    ) -> Dict[str, Any]:
        """计算概览统计"""
        if not actual_data:
            return {
                "total_cost": 0,
                "total_volume": 0,
                "avg_price": 0,
                "market_avg_price": 0,
                "cost_saving": 0,
                "saving_rate": 0,
            }

        total_cost = sum(d.get("cost_yuan", 0) for d in actual_data)
        total_volume = sum(d.get("volume_mwh", 0) for d in actual_data)

        weighted_prices = []
        for d in actual_data:
            vol = d.get("volume_mwh", 0)
            price = d.get("price_yuan_mwh", 0)
            if vol > 0:
                weighted_prices.append(price * vol)

        avg_price = (sum(weighted_prices) / total_volume) if total_volume > 0 else 0

        market_avg_price = self._calc_market_avg_price(date_range)

        cost_saving = 0
        saving_rate = 0
        if market_avg_price > 0 and total_volume > 0:
            market_cost = market_avg_price * total_volume
            cost_saving = market_cost - total_cost
            saving_rate = (cost_saving / market_cost * 100) if market_cost > 0 else 0

        return {
            "total_cost": round(total_cost, 2),
            "total_volume": round(total_volume, 4),
            "avg_price": round(avg_price, 2),
            "market_avg_price": round(market_avg_price, 2),
            "cost_saving": round(cost_saving, 2),
            "saving_rate": round(saving_rate, 2),
        }

    def _calc_market_avg_price(self, date_range: List[str]) -> float:
        """计算市场平均价格（日前市场）"""
        col = self.db["day_ahead_spot_price"]
        pipeline = [
            {"$match": {"date_str": {"$in": date_range}}},
            {"$group": {
                "_id": None,
                "avg_price": {"$avg": "$avg_clearing_price"},
            }},
        ]
        result = list(col.aggregate(pipeline))
        if result and result[0].get("avg_price") is not None:
            return round(result[0]["avg_price"], 2)
        return 0.0

    def _calc_time_slot_analysis(
        self,
        actual_data: List[Dict[str, Any]],
        tou_map: Dict[str, str]
    ) -> List[Dict[str, Any]]:
        """计算时段分析（峰/平/谷）"""
        slot_data: Dict[str, Dict[str, float]] = {}

        for d in actual_data:
            time_str = d.get("time_str", "")
            slot_name = tou_map.get(time_str, "平段")

            if slot_name not in slot_data:
                slot_data[slot_name] = {"volume": 0, "cost": 0, "weighted_price": 0}

            vol = d.get("volume_mwh", 0)
            cost = d.get("cost_yuan", 0)
            price = d.get("price_yuan_mwh", 0)

            slot_data[slot_name]["volume"] += vol
            slot_data[slot_name]["cost"] += cost
            if vol > 0:
                slot_data[slot_name]["weighted_price"] += price * vol

        total_volume = sum(s["volume"] for s in slot_data.values())
        total_cost = sum(s["cost"] for s in slot_data.values())

        result = []
        for slot_name, data in slot_data.items():
            vol_ratio = (data["volume"] / total_volume * 100) if total_volume > 0 else 0
            cost_ratio = (data["cost"] / total_cost * 100) if total_cost > 0 else 0
            avg_price = (data["weighted_price"] / data["volume"]) if data["volume"] > 0 else 0

            result.append({
                "slot_name": slot_name,
                "volume_ratio": round(vol_ratio, 2),
                "cost_ratio": round(cost_ratio, 2),
                "avg_price": round(avg_price, 2),
            })

        return sorted(result, key=lambda x: x["avg_price"], reverse=True)

    def _calc_forecast_accuracy(
        self,
        actual_data: List[Dict[str, Any]],
        forecast_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """计算预测精度指标：MAE/MAPE/RMSE/5%内命中率"""
        actual_by_time = {d["time_str"]: d for d in actual_data}
        forecast_by_time = {d["time_str"]: d for d in forecast_data}

        common_times = sorted(set(actual_by_time.keys()) & set(forecast_by_time.keys()))

        if not common_times:
            return {"mae": 0, "mape": 0, "rmse": 0, "within_5pct_rate": 0}

        abs_errors = []
        pct_errors = []
        sq_errors = []
        within_5pct_count = 0

        for t in common_times:
            a_vol = actual_by_time[t].get("volume_mwh", 0)
            f_vol = forecast_by_time[t].get("volume_mwh", 0)

            abs_err = abs(a_vol - f_vol)
            abs_errors.append(abs_err)

            if f_vol != 0:
                pct_err = abs_err / abs(f_vol) * 100
                pct_errors.append(pct_err)
                if pct_err <= 5:
                    within_5pct_count += 1

            sq_errors.append(abs_err ** 2)

        n = len(common_times)
        mae = sum(abs_errors) / n
        mape = (sum(pct_errors) / len(pct_errors)) if pct_errors else 0
        rmse = math.sqrt(sum(sq_errors) / n)
        within_5pct_rate = (within_5pct_count / n * 100) if n > 0 else 0

        return {
            "mae": round(mae, 4),
            "mape": round(mape, 2),
            "rmse": round(rmse, 4),
            "within_5pct_rate": round(within_5pct_rate, 2),
        }

    def _identify_special_events(
        self,
        actual_data: List[Dict[str, Any]],
        forecast_data: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """识别风险事件：价格异常(偏离均值2σ以上) + 极端偏差(偏差率>10%)"""
        events = []

        # --- 价格异常检测 ---
        prices = [d.get("price_yuan_mwh", 0) for d in actual_data if d.get("price_yuan_mwh") is not None]
        if len(prices) >= 2:
            mean_price = sum(prices) / len(prices)
            var_price = sum((p - mean_price) ** 2 for p in prices) / len(prices)
            std_price = math.sqrt(var_price)

            if std_price > 0:
                for d in actual_data:
                    price = d.get("price_yuan_mwh", 0)
                    deviation = abs(price - mean_price)
                    if deviation > 2 * std_price:
                        time_str = d.get("time_str", "")
                        direction = "高于" if price > mean_price else "低于"
                        impact = d.get("cost_yuan", 0) - mean_price * d.get("volume_mwh", 0)
                        events.append({
                            "event_time": time_str,
                            "event_type": "price_anomaly",
                            "description": (
                                f"价格{direction}均值{deviation / std_price:.1f}倍标准差"
                                f"（价格{price:.2f}元/MWh，均值{mean_price:.2f}元/MWh）"
                            ),
                            "impact_cost": round(impact, 2),
                        })

        # --- 极端偏差检测 ---
        actual_by_time = {d["time_str"]: d for d in actual_data}
        forecast_by_time = {d["time_str"]: d for d in forecast_data}
        common_times = sorted(set(actual_by_time.keys()) & set(forecast_by_time.keys()))

        for t in common_times:
            a_vol = actual_by_time[t].get("volume_mwh", 0)
            f_vol = forecast_by_time[t].get("volume_mwh", 0)
            a_price = actual_by_time[t].get("price_yuan_mwh", 0)

            if f_vol != 0:
                deviation_rate = abs(a_vol - f_vol) / abs(f_vol) * 100
                if deviation_rate > 10:
                    impact = (a_vol - f_vol) * a_price
                    events.append({
                        "event_time": t,
                        "event_type": "deviation_extreme",
                        "description": (
                            f"电量偏差率达{deviation_rate:.1f}%"
                            f"（实际{a_vol:.4f}MWh，预测{f_vol:.4f}MWh）"
                        ),
                        "impact_cost": round(impact, 2),
                    })

        events.sort(key=lambda x: abs(x.get("impact_cost", 0)), reverse=True)
        return events

    def _generate_optimization_suggestions(
        self,
        actual_data: List[Dict[str, Any]],
        forecast_data: List[Dict[str, Any]],
        time_slot_analysis: List[Dict[str, Any]],
        overview: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """基于历史数据模式生成优化建议"""
        suggestions = []

        # 建议1: 高价时段负荷转移
        high_price_slots = [s for s in time_slot_analysis if s.get("avg_price", 0) > overview.get("avg_price", 0)]
        low_price_slots = [s for s in time_slot_analysis if s.get("avg_price", 0) < overview.get("avg_price", 0)]

        if high_price_slots and low_price_slots:
            high_slot = high_price_slots[0]
            low_slot = low_price_slots[-1]
            price_diff = high_slot["avg_price"] - low_slot["avg_price"]
            total_vol = overview.get("total_volume", 0)
            shift_vol = total_vol * 0.05
            estimated_saving = shift_vol * price_diff

            suggestions.append({
                "category": "负荷转移",
                "description": (
                    f"建议将{high_slot['slot_name']}时段5%负荷({shift_vol:.2f}MWh)"
                    f"转移至{low_slot['slot_name']}时段，"
                    f"价差{price_diff:.2f}元/MWh"
                ),
                "estimated_saving": round(estimated_saving, 2),
            })

        # 建议2: 预测精度提升
        if forecast_data and actual_data:
            common_times = set(d["time_str"] for d in actual_data) & set(d["time_str"] for d in forecast_data)
            if common_times:
                actual_by_time = {d["time_str"]: d for d in actual_data}
                forecast_by_time = {d["time_str"]: d for d in forecast_data}
                total_dev = 0
                dev_count = 0
                for t in common_times:
                    a = actual_by_time[t].get("volume_mwh", 0)
                    f = forecast_by_time[t].get("volume_mwh", 0)
                    if f != 0:
                        total_dev += abs(a - f) / abs(f) * 100
                        dev_count += 1
                if dev_count > 0:
                    avg_dev_rate = total_dev / dev_count
                    if avg_dev_rate > 5:
                        improvement_pct = min(avg_dev_rate * 0.3, 10)
                        estimated_saving = overview.get("total_cost", 0) * improvement_pct / 100
                        suggestions.append({
                            "category": "预测优化",
                            "description": (
                                f"当前平均偏差率{avg_dev_rate:.1f}%，"
                                f"提升预测精度可降低偏差率约{improvement_pct:.1f}%"
                            ),
                            "estimated_saving": round(estimated_saving, 2),
                        })

        # 建议3: 低谷时段增购
        for slot in time_slot_analysis:
            if slot.get("avg_price", 0) < overview.get("avg_price", 0) * 0.8:
                low_vol = overview.get("total_volume", 0) * 0.03
                saving = low_vol * (overview.get("avg_price", 0) - slot["avg_price"])
                suggestions.append({
                    "category": "低谷增购",
                    "description": (
                        f"{slot['slot_name']}时段均价仅{slot['avg_price']:.2f}元/MWh，"
                        f"建议增购{low_vol:.2f}MWh"
                    ),
                    "estimated_saving": round(saving, 2),
                })
                break

        return suggestions

    def _format_review(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """格式化复盘报告响应"""
        return {
            "id": str(doc.get("_id", "")),
            "customer_id": doc.get("customer_id", ""),
            "customer_name": doc.get("customer_name", ""),
            "review_date": doc.get("review_date", ""),
            "review_type": doc.get("review_type", ""),
            "overview": doc.get("overview", {}),
            "time_slot_analysis": doc.get("time_slot_analysis", []),
            "forecast_accuracy": doc.get("forecast_accuracy", {}),
            "special_events": doc.get("special_events", []),
            "optimization_suggestions": doc.get("optimization_suggestions", []),
            "created_at": doc.get("created_at"),
        }
