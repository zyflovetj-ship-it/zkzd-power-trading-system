"""
负荷数据校验服务层

提供负荷数据校验的核心业务逻辑：
1. 96点手工数据转48点负荷曲线
2. RPA数据聚合到结算曲线
3. 数据完整性分析
4. 曲线校核与偏差计算
5. 负荷曲线重新生成
"""
import logging
import time
from datetime import datetime, timedelta, date
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from bson import ObjectId
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

logger = logging.getLogger(__name__)

#: 96 点源数据的语义是**该 15 分钟时段的平均功率(kW)**，不是累计示数，
#: 也不是时段电量。已用零售合约交叉校验：
#:   user_load_data 平均 437 kW × 0.25h × 96 点 ≈ 10.5 MWh/日
#:   零售合约 1,000,000 kWh / 92 天 ≈ 10.87 MWh/日  —— 两者吻合。
#:
#: 注意：字段命名即语义契约 —— load_kw / value / load / load_value 视为功率(kW)，
#: 需乘 0.25 换算；若接入真正的电表电量源，字段必须命名为 load_kwh，
#: 由 _power_to_kwh() 按字段名区分处理，不做二次换算。
#:
#: 因此 96 点合并为 48 点时必须做功率→电量换算：
#:   30 分钟电量(kWh) = (v1 + v2) / 2 × 0.5h = (v1 + v2) × 0.25
#: 原实现写成纯求和（假定源为时段电量），与数据语义不符，
#: 会把 30 分钟电量放大 4 倍、日电量放大 4 倍（实测 42 MWh vs 真实 10.5 MWh）。
KWH_PER_KW_POINT = 0.25


class DataValidationService:
    """负荷数据校验服务"""

    LOAD_CURVE_USER_COLLECTION = "load_curve_user"
    SETTLEMENT_CURVE_USER_COLLECTION = "settlement_curve_user"
    DATA_QUALITY_REPORT_COLLECTION = "data_quality_report"
    USER_LOAD_DATA_COLLECTION = "user_load_data"
    CUSTOMERS_COLLECTION = "customers"

    def __init__(self, db: Database) -> None:
        self.db = db
        self.load_curve_collection = self.db[self.LOAD_CURVE_USER_COLLECTION]
        self.settlement_curve_collection = self.db[self.SETTLEMENT_CURVE_USER_COLLECTION]
        self.report_collection = self.db[self.DATA_QUALITY_REPORT_COLLECTION]
        self.user_load_collection = self.db[self.USER_LOAD_DATA_COLLECTION]
        self.customers_collection = self.db[self.CUSTOMERS_COLLECTION]
        self._ensure_indexes()

    def _ensure_indexes(self) -> None:
        """确保数据库索引存在"""
        try:
            # load_curve_user 索引
            existing_lc = {idx.get('name') for idx in self.load_curve_collection.list_indexes()}
            lc_indexes = [
                ([('customer_id', 1), ('datetime', 1)], {'name': 'idx_customer_datetime', 'unique': True}),
                ([('datetime', 1)], {'name': 'idx_datetime'}),
                ([('created_at', -1)], {'name': 'idx_created_at'}),
                ([('import_batch_id', 1)], {'name': 'idx_import_batch_id'}),
            ]
            for keys, options in lc_indexes:
                if options['name'] not in existing_lc:
                    self.load_curve_collection.create_index(keys, **options)

            # settlement_curve_user 索引
            existing_sc = {idx.get('name') for idx in self.settlement_curve_collection.list_indexes()}
            sc_indexes = [
                ([('customer_id', 1), ('datetime', 1)], {'name': 'idx_customer_datetime', 'unique': True}),
                ([('datetime', 1)], {'name': 'idx_datetime'}),
                ([('created_at', -1)], {'name': 'idx_created_at'}),
                ([('rpa_batch_id', 1)], {'name': 'idx_rpa_batch_id'}),
            ]
            for keys, options in sc_indexes:
                if options['name'] not in existing_sc:
                    self.settlement_curve_collection.create_index(keys, **options)

            # data_quality_report 索引
            existing_rpt = {idx.get('name') for idx in self.report_collection.list_indexes()}
            rpt_indexes = [
                ([('customer_id', 1), ('generated_at', -1)], {'name': 'idx_customer_generated'}),
                ([('customer_id', 1), ('report_type', 1), ('generated_at', -1)], {'name': 'idx_customer_type_generated'}),
                ([('report_type', 1), ('generated_at', -1)], {'name': 'idx_type_generated'}),
            ]
            for keys, options in rpt_indexes:
                if options['name'] not in existing_rpt:
                    self.report_collection.create_index(keys, **options)

        except Exception as exc:
            logger.warning("创建数据校验索引时出错: %s", exc)

    # ========== 辅助方法 ==========

    def _get_customer_info(self, customer_id: str) -> Optional[Dict[str, Any]]:
        """获取客户信息（名称和分配系数）"""
        customer = self.customers_collection.find_one({"_id": ObjectId(customer_id)})
        if not customer:
            customer = self.customers_collection.find_one({"user_name": customer_id})
        return customer

    def _get_customer_name(self, customer_id: str) -> str:
        """获取客户名称"""
        customer = self._get_customer_info(customer_id)
        if customer:
            return customer.get("user_name", customer_id)
        return customer_id

    def _get_metering_points_with_allocation(self, customer_id: str) -> List[Dict[str, Any]]:
        """
        获取客户所有计量点及其分配系数
        返回: [{mp_id, meter_id, allocation_percentage, account_id}, ...]
        """
        customer = self._get_customer_info(customer_id)
        if not customer:
            return []

        mp_list = []
        for account in customer.get("utility_accounts", []):
            account_id = account.get("account_id", "")
            for mp in account.get("metering_points", []):
                mp_list.append({
                    "mp_id": mp.get("metering_point_id", ""),
                    "meter_id": mp.get("meter", {}).get("meter_id", ""),
                    "allocation_percentage": mp.get("allocation_percentage", 0.0),
                    "account_id": account_id,
                })
        return mp_list

    def _format_time_label(self, dt: datetime, day_start: datetime) -> str:
        """
        将时间戳格式化为业务时间标签
        次日00:00 → "24:00"，其他 → "HH:MM"
        """
        next_day_start = day_start + timedelta(days=1)
        if dt == next_day_start:
            return "24:00"
        return dt.strftime("%H:%M")

    def _get_48point_datetimes(self, target_date: date) -> List[datetime]:
        """
        生成48点时间点列表（30分钟间隔）
        第1点: 00:30, 第2点: 01:00, ..., 第48点: 次日00:00(即24:00)
        """
        start = datetime(target_date.year, target_date.month, target_date.day)
        return [start + timedelta(minutes=30 * i) for i in range(1, 49)]

    # ========== 1. 96点手工数据转48点 ==========

    def transform_manual_data(self, import_batch_id: str, operator: str) -> Dict[str, Any]:
        """
        将user_load_data中的96点手工数据转换为48点用户级负荷曲线

        流程：
        1. 从user_load_data按batch_id查询96点数据
        2. 30分钟聚合（相邻两点合并）
        3. 示数转差值（如果是累计示数）
        4. 按分配系数聚合到用户级
        5. 存入load_curve_user
        6. 触发完整度分析
        """
        start_time = time.time()
        logger.info("开始转换手工数据, import_batch_id=%s", import_batch_id)

        # 查询该批次所有数据
        raw_data = list(self.user_load_collection.find(
            {"import_batch_id": import_batch_id},
            {"_id": 0}
        ).sort("timestamp", 1))

        if not raw_data:
            raise ValueError(f"未找到批次 {import_batch_id} 的手工数据")

        # 按日期+客户分组
        grouped: Dict[str, List[Dict]] = defaultdict(list)
        for doc in raw_data:
            customer_id = doc.get("customer_id", doc.get("user_id", ""))
            dt = doc.get("timestamp", doc.get("datetime"))
            if dt is None:
                continue
            day_key = self._business_day(dt)
            group_key = f"{customer_id}_{day_key.isoformat()}"
            grouped[group_key].append(doc)

        total_inserted = 0
        customers_processed = set()

        for group_key, docs in grouped.items():
            # 从分组key解析customer_id
            parts = group_key.rsplit("_", 1)
            customer_id = parts[0] if len(parts) == 2 else docs[0].get("customer_id", docs[0].get("user_id", ""))
            customers_processed.add(customer_id)

            customer_name = self._get_customer_name(customer_id)
            mp_list = self._get_metering_points_with_allocation(customer_id)

            # 按日期分组（处理跨日数据）
            by_date: Dict[datetime, List[Dict]] = defaultdict(list)
            for d in docs:
                dt = d.get("timestamp", d.get("datetime"))
                day_start = self._business_day(dt)
                by_date[day_start].append(d)

            for day_start, day_docs in by_date.items():
                # 96点按15分钟排序
                day_docs.sort(key=lambda x: x.get("timestamp", x.get("datetime")))

                # 30分钟聚合：相邻两点合并
                aggregated_48 = self._aggregate_96_to_48(day_docs, day_start)

                if not aggregated_48:
                    continue

                # 按分配系数聚合到用户级
                user_level_data = self._aggregate_to_user_level(
                    aggregated_48, customer_id, mp_list
                )

                # 写入load_curve_user（upsert语义）
                for point in user_level_data:
                    now = datetime.now()
                    doc = {
                        "customer_id": customer_id,
                        "customer_name": customer_name,
                        "datetime": point["datetime"],
                        "load_kwh": point["load_kwh"],
                        "data_source": "manual_import",
                        "import_batch_id": import_batch_id,
                        "aggregation_meta": point.get("aggregation_meta"),
                        "created_at": now,
                    }
                    self.load_curve_collection.update_one(
                        {"customer_id": customer_id, "datetime": point["datetime"]},
                        {"$set": doc},
                        upsert=True
                    )
                    total_inserted += 1

        elapsed = time.time() - start_time
        logger.info("手工数据转换完成, 插入%d条, 耗时%.2fs", total_inserted, elapsed)

        # 对涉及的每个客户触发完整度分析
        completeness_results = []
        for cid in customers_processed:
            try:
                result = self.analyze_completeness(cid, operator)
                completeness_results.append(result)
            except Exception as e:
                logger.warning("客户 %s 完整度分析失败: %s", cid, e)

        return {
            "import_batch_id": import_batch_id,
            "total_inserted": total_inserted,
            "customers_processed": list(customers_processed),
            "completeness_analysis": completeness_results,
        }

    @staticmethod
    def _business_day(dt: datetime) -> datetime:
        """把时间点归入其所属的业务日（返回该业务日的 00:00）。

        规范 §5.3：业务日第 96 个点（24:00）**存储为次日 00:00**，
        因此 `次日 00:00` 属于**前一个**业务日，而不是它自然落下的那一天。

        业务日的点从 00:15 开始（不含自身的 00:00），所以判断
        `hour==0 and minute==0` 即可安全地把它归回前一天 ——
        否则分组会把每天的 24:00 点甩到次日，造成首日少一点、
        末尾多出孤儿点、48 点时间标签整体错位。
        """
        if dt.hour == 0 and dt.minute == 0 and dt.second == 0:
            return (dt - timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
        return dt.replace(hour=0, minute=0, second=0, microsecond=0)

    @staticmethod
    def _pick_numeric(doc: Dict[str, Any], *keys: str) -> float:
        """按优先级从文档中取数值字段。

        96 点源数据存在多套字段命名（规范 §5.1.1 是 ``value``，
        历史实现用 ``load`` / ``load_value`` / ``load_kwh``），
        原实现只认 ``load_value``/``load_kwh``，取不到就静默变成 0 ——
        表现为"完整度 100% 但 48 点数值全为 0"。
        """
        for key in keys:
            val = doc.get(key)
            if val is None:
                continue
            try:
                return float(val)
            except (TypeError, ValueError):
                continue
        return 0.0

    @staticmethod
    def _point_energy_kwh(doc: Dict[str, Any]) -> float:
        """把单个 15 分钟采集点换算为时段电量(kWh)。

        字段名即语义契约：
          - load_kwh：已是时段电量，原样返回
          - load_kw / value / load / load_value：平均功率(kW)，× 0.25h
        """
        if doc.get("load_kwh") is not None:
            return DataValidationService._pick_numeric(doc, "load_kwh")
        power_kw = DataValidationService._pick_numeric(doc, "load_kw", "load_value", "value", "load")
        return power_kw * KWH_PER_KW_POINT

    def _aggregate_96_to_48(self, docs: List[Dict], day_start: datetime) -> List[Dict[str, Any]]:
        """
        将96点（15分钟间隔）聚合为48点（30分钟间隔）

        数据语义：源数据为每个 15 分钟采集点的**平均功率(kW)**，
        合并为 30 分钟时段时取两点均值再乘 0.5h，即 (v1+v2)×0.25 kWh。

        注意：早期文档（技术方案 v1.0 / v1.1）曾描述为"示数转差值"或"取均值"，
        与代码及实际数据不符。实际入库的 96 点数据为时段电量
        （见 scripts/init_actual_load_data.py 生成的带正负噪声的曲线值），
        若按示数做差分或按均值合并都会导致日电量失真。
        """
        result = []
        for i in range(0, min(len(docs), 96), 2):
            if i + 1 < len(docs):
                val1 = self._point_energy_kwh(docs[i])
                val2 = self._point_energy_kwh(docs[i + 1])
                # 两点均为 15 分钟时段电量，直接相加即为 30 分钟电量
                combined_value = val1 + val2
            else:
                combined_value = self._point_energy_kwh(docs[i])

            # 48点的时间点：第1点=00:30, 第2点=01:00, ..., 第48点=24:00(次日00:00)
            point_index = i // 2  # 0-based
            minutes = (point_index + 1) * 30
            hours = minutes // 60
            mins = minutes % 60

            if hours == 24:
                point_dt = day_start + timedelta(days=1)
            else:
                point_dt = day_start.replace(hour=hours, minute=mins, second=0, microsecond=0)

            meter_id = docs[i].get("meter_id", "")
            customer_id = docs[i].get("customer_id", docs[i].get("user_id", ""))

            result.append({
                "datetime": point_dt,
                "load_kwh": combined_value,
                "meter_id": meter_id,
                "customer_id": customer_id,
            })

        return result

    def _aggregate_to_user_level(
        self,
        aggregated_48: List[Dict],
        customer_id: str,
        mp_list: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        按分配系数将计量点级数据聚合为用户级数据
        如果有分配系数，按分配系数加权；否则直接求和
        """
        if not mp_list:
            # 无分配系数信息，直接使用原始数据
            return [{
                "datetime": p["datetime"],
                "load_kwh": p["load_kwh"],
                "aggregation_meta": {
                    "mp_count": 1,
                    "mp_contributions": [{
                        "mp_id": "",
                        "meter_id": p.get("meter_id", ""),
                        "load_kwh": p["load_kwh"],
                        "allocation_percentage": 100.0,
                    }],
                },
            } for p in aggregated_48]

        # 按时间点聚合
        result = []
        for point in aggregated_48:
            meter_id = point.get("meter_id", "")
            # 找到对应计量点的分配系数
            allocation = 100.0
            mp_id = ""
            for mp in mp_list:
                if mp["meter_id"] == meter_id:
                    allocation = mp["allocation_percentage"]
                    mp_id = mp["mp_id"]
                    break

            # 用户级负荷 = 计量点负荷 * (分配系数 / 100)
            # 如果只有一个计量点，分配系数就是100%
            user_load = point["load_kwh"] * (allocation / 100.0)

            result.append({
                "datetime": point["datetime"],
                "load_kwh": round(user_load, 4),
                "aggregation_meta": {
                    "mp_count": len(mp_list),
                    "mp_contributions": [{
                        "mp_id": mp_id,
                        "meter_id": meter_id,
                        "load_kwh": point["load_kwh"],
                        "allocation_percentage": allocation,
                    }],
                },
            })

        return result

    # ========== 2. RPA数据导入 ==========

    def import_rpa_data(
        self,
        rpa_batch_id: str,
        source_collection: str,
        operator: str
    ) -> Dict[str, Any]:
        """
        从RPA源集合聚合数据到settlement_curve_user

        流程：
        1. 从source_collection查询rpa_batch_id对应的数据
        2. 按customer_id + datetime聚合
        3. 存入settlement_curve_user
        """
        start_time = time.time()
        logger.info("开始导入RPA数据, rpa_batch_id=%s, source=%s", rpa_batch_id, source_collection)

        source_coll = self.db[source_collection]
        raw_data = list(source_coll.find(
            {"rpa_batch_id": rpa_batch_id},
            {"_id": 0}
        ).sort("datetime", 1))

        if not raw_data:
            raise ValueError(f"未找到批次 {rpa_batch_id} 的RPA数据（集合: {source_collection}）")

        # 按 customer_id + 计量点 + 业务日 分组（RPA 源为 96 点/15分钟，
        # 必须与手工侧的 48 点/30分钟对齐，否则校核时两条曲线粒度不一致，
        # 96 个比对点里约一半是单边缺失，平均偏差率会虚高一倍）。
        grouped: Dict[Tuple[str, str, datetime], List[Dict]] = defaultdict(list)
        for doc in raw_data:
            cid = doc.get("customer_id", "")
            dt = doc.get("datetime")
            if not cid or dt is None:
                continue
            meter_id = doc.get("meter_id", "") or ""
            day_start = self._business_day(dt)
            grouped[(cid, meter_id, day_start)].append(doc)

        total_inserted = 0
        now = datetime.now()

        # 先按 (客户, 业务日) 归集各计量点聚合后的 48 点曲线，
        # 再在同一时间点上按分配系数加权求和得到用户级结算曲线。
        by_customer_day: Dict[Tuple[str, datetime], Dict[str, Any]] = {}

        for (customer_id, meter_id, day_start), docs in grouped.items():
            docs.sort(key=lambda x: x.get("datetime") or datetime.min)

            # 96 点 -> 48 点（该计量点自身的时段电量求和，保持电量守恒）
            aggregated_48 = self._aggregate_96_to_48(docs, day_start)
            if not aggregated_48:
                continue

            # 取该计量点的分配系数（同一计量点内取首条的系数）
            allocation = 100.0
            mp_id = ""
            for d in docs:
                if d.get("allocation_percentage") is not None:
                    allocation = float(d.get("allocation_percentage") or 0.0)
                    break
            for d in docs:
                if d.get("mp_id") or d.get("metering_point_id"):
                    mp_id = d.get("mp_id") or d.get("metering_point_id")
                    break

            bucket = by_customer_day.setdefault(
                (customer_id, day_start),
                {"points": {}, "names": {}}
            )

            for point in aggregated_48:
                dt_key = point["datetime"]
                slot = bucket["points"].setdefault(
                    dt_key, {"load_kwh": 0.0, "contributions": []}
                )
                # 用户级 = 该计量点时段电量 × 分配系数
                slot["load_kwh"] += point["load_kwh"] * (allocation / 100.0)
                slot["contributions"].append({
                    "mp_id": mp_id,
                    "meter_id": meter_id,
                    "load_kwh": point["load_kwh"],
                    "allocation_percentage": allocation,
                })

        for (customer_id, day_start), bucket in by_customer_day.items():
            customer_name = self._get_customer_name(customer_id)

            for dt_key in sorted(bucket["points"].keys()):
                slot = bucket["points"][dt_key]
                contributions = slot["contributions"]

                aggregation_meta = {
                    "mp_count": len(contributions),
                    "mp_contributions": contributions,
                }

                doc = {
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "datetime": dt_key,
                    "load_kwh": round(slot["load_kwh"], 4),
                    "data_source": "rpa_settlement",
                    "rpa_batch_id": rpa_batch_id,
                    "aggregation_meta": aggregation_meta,
                    "created_at": now,
                }
                self.settlement_curve_collection.update_one(
                    {"customer_id": customer_id, "datetime": dt_key},
                    {"$set": doc},
                    upsert=True
                )
                total_inserted += 1

        elapsed = time.time() - start_time
        logger.info("RPA数据导入完成, 插入%d条, 耗时%.2fs", total_inserted, elapsed)

        return {
            "rpa_batch_id": rpa_batch_id,
            "source_collection": source_collection,
            "total_inserted": total_inserted,
        }

    # ========== 3. 数据完整性分析 ==========

    def analyze_completeness(self, customer_id: str, operator: str) -> Dict[str, Any]:
        """
        分析指定客户的数据完整性

        完整性计算：
        - 负荷曲线：expected_end_date = today - 1
        - 结算曲线：expected_end_date = today - 2
        - 完整度 = actual_days / total_days * 100
        """
        start_time = time.time()
        logger.info("开始分析客户 %s 的数据完整性", customer_id)

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        customer_name = self._get_customer_name(customer_id)

        load_completeness = self._analyze_curve_completeness(
            customer_id, self.load_curve_collection, today - timedelta(days=1)
        )
        settlement_completeness = self._analyze_curve_completeness(
            customer_id, self.settlement_curve_collection, today - timedelta(days=2)
        )
        overlap = self._analyze_overlap(customer_id, load_completeness, settlement_completeness)

        completeness_analysis = {
            "load_curve": load_completeness,
            "settlement_curve": settlement_completeness,
            "overlap_analysis": overlap,
        }

        elapsed_ms = (time.time() - start_time) * 1000

        report = {
            "customer_id": customer_id,
            "customer_name": customer_name,
            "report_type": "completeness",
            "generated_at": datetime.now(),
            "completeness_analysis": completeness_analysis,
            "metadata": {
                "analysis_duration_ms": round(elapsed_ms, 2),
                "triggered_by": "api",
                "trigger_user": operator,
            },
        }

        self.report_collection.insert_one(report)
        report["_id"] = str(report.pop("_id"))

        logger.info("客户 %s 完整度分析完成, 负荷曲线%.1f%%, 结算曲线%.1f%%",
                     customer_id,
                     load_completeness.get("completeness_rate", 0),
                     settlement_completeness.get("completeness_rate", 0))

        return report

    def _analyze_curve_completeness(
        self,
        customer_id: str,
        collection,
        expected_end_date: datetime
    ) -> Dict[str, Any]:
        """分析单条曲线的完整度"""
        # 查询该客户所有数据日期
        pipeline = [
            {"$match": {"customer_id": customer_id}},
            {"$project": {"date_str": {"$dateToString": {"format": "%Y-%m-%d", "date": "$datetime"}}}},
            {"$group": {"_id": "$date_str"}},
            {"$sort": {"_id": 1}},
        ]
        available_dates = [doc["_id"] for doc in collection.aggregate(pipeline)]

        if not available_dates:
            return {
                "start_date": None,
                "end_date": None,
                "expected_end_date": expected_end_date.strftime("%Y-%m-%d"),
                "total_days": 0,
                "actual_days": 0,
                "missing_days": 0,
                "missing_dates": [],
                "completeness_rate": 0.0,
            }

        start_date_str = available_dates[0]
        end_date_str = available_dates[-1]

        start_dt = datetime.strptime(start_date_str, "%Y-%m-%d")
        end_dt = datetime.strptime(end_date_str, "%Y-%m-%d")

        # 总天数 = 从start到expected_end的日历天数
        total_days = (expected_end_date - start_dt).days + 1
        if total_days <= 0:
            total_days = 0

        # 实际天数
        actual_dates_set = set(available_dates)

        # 期望日期范围
        expected_dates = []
        current = start_dt
        while current <= expected_end_date:
            expected_dates.append(current.strftime("%Y-%m-%d"))
            current += timedelta(days=1)

        missing_dates = [d for d in expected_dates if d not in actual_dates_set]
        actual_days = len(expected_dates) - len(missing_dates)

        completeness_rate = (actual_days / total_days * 100) if total_days > 0 else 0.0

        return {
            "start_date": start_date_str,
            "end_date": end_date_str,
            "expected_end_date": expected_end_date.strftime("%Y-%m-%d"),
            "total_days": total_days,
            "actual_days": actual_days,
            "missing_days": len(missing_dates),
            "missing_dates": missing_dates,
            "completeness_rate": round(completeness_rate, 2),
        }

    def _analyze_overlap(
        self,
        customer_id: str,
        load_completeness: Dict,
        settlement_completeness: Dict
    ) -> Dict[str, Any]:
        """分析两条曲线的重叠区间"""
        load_start = load_completeness.get("start_date")
        load_end = load_completeness.get("end_date")
        settlement_start = settlement_completeness.get("start_date")
        settlement_end = settlement_completeness.get("end_date")

        if not all([load_start, load_end, settlement_start, settlement_end]):
            return {
                "overlap_start_date": None,
                "overlap_end_date": None,
                "overlap_days": 0,
                "daily_deviations": [],
            }

        load_start_dt = datetime.strptime(load_start, "%Y-%m-%d")
        load_end_dt = datetime.strptime(load_end, "%Y-%m-%d")
        settlement_start_dt = datetime.strptime(settlement_start, "%Y-%m-%d")
        settlement_end_dt = datetime.strptime(settlement_end, "%Y-%m-%d")

        overlap_start = max(load_start_dt, settlement_start_dt)
        overlap_end = min(load_end_dt, settlement_end_dt)

        if overlap_start > overlap_end:
            return {
                "overlap_start_date": None,
                "overlap_end_date": None,
                "overlap_days": 0,
                "daily_deviations": [],
            }

        overlap_days = (overlap_end - overlap_start).days + 1

        # 计算每日偏差
        daily_deviations = []
        current = overlap_start
        while current <= overlap_end:
            date_str = current.strftime("%Y-%m-%d")
            day_start = current
            day_end = current + timedelta(days=1)

            load_total = self._get_daily_total(customer_id, self.load_curve_collection, day_start, day_end)
            settlement_total = self._get_daily_total(customer_id, self.settlement_curve_collection, day_start, day_end)

            deviation = load_total - settlement_total
            deviation_rate = (deviation / settlement_total * 100) if settlement_total != 0 else 0.0

            daily_deviations.append({
                "date": date_str,
                "load_total": round(load_total, 4),
                "settlement_total": round(settlement_total, 4),
                "deviation": round(deviation, 4),
                "deviation_rate": round(deviation_rate, 2),
            })

            current += timedelta(days=1)

        return {
            "overlap_start_date": overlap_start.strftime("%Y-%m-%d"),
            "overlap_end_date": overlap_end.strftime("%Y-%m-%d"),
            "overlap_days": overlap_days,
            "daily_deviations": daily_deviations,
        }

    def _get_daily_total(
        self,
        customer_id: str,
        collection,
        day_start: datetime,
        day_end: datetime
    ) -> float:
        """获取指定客户某日的电量总和"""
        pipeline = [
            {
                "$match": {
                    "customer_id": customer_id,
                    "datetime": {"$gt": day_start, "$lte": day_end},
                }
            },
            {"$group": {"_id": None, "total": {"$sum": "$load_kwh"}}},
        ]
        result = list(collection.aggregate(pipeline))
        return result[0]["total"] if result else 0.0

    # ========== 4. 获取完整性报告 ==========

    def get_completeness_report(self, customer_id: str, latest: bool = True) -> Optional[Dict[str, Any]]:
        """获取指定客户的完整性报告"""
        query = {"customer_id": customer_id, "report_type": "completeness"}
        cursor = self.report_collection.find(query, {"_id": 0}).sort("generated_at", -1)

        if latest:
            report = next(cursor, None)
            if report:
                report["id"] = str(report.get("_id", ""))
            return report
        else:
            reports = list(cursor.limit(10))
            for r in reports:
                r["id"] = str(r.get("_id", ""))
            return {"reports": reports}

    # ========== 5. 完整性概览仪表板 ==========

    def get_completeness_dashboard(self) -> Dict[str, Any]:
        """获取所有客户的数据完整性概览"""
        # 获取所有活跃客户
        customers = list(self.customers_collection.find(
            {"status": {"$in": ["active", "pending"]}},
            {"_id": 1, "user_name": 1, "short_name": 1}
        ))

        if not customers:
            return {
                "total_customers": 0,
                "healthy_customers": 0,
                "warning_customers": 0,
                "critical_customers": 0,
                "customers": [],
            }

        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        customer_results = []
        healthy = warning = critical = 0

        for customer in customers:
            cid = str(customer["_id"])
            cname = customer.get("user_name", customer.get("short_name", ""))

            # 获取最新的完整性报告
            report = self.report_collection.find_one(
                {"customer_id": cid, "report_type": "completeness"},
                {"_id": 0},
                sort=[("generated_at", -1)]
            )

            if report and report.get("completeness_analysis"):
                ca = report["completeness_analysis"]
                lc = ca.get("load_curve", {})
                sc = ca.get("settlement_curve", {})
                load_rate = lc.get("completeness_rate", 0)
                settlement_rate = sc.get("completeness_rate", 0)
                min_rate = min(load_rate, settlement_rate)
            else:
                load_rate = 0.0
                settlement_rate = 0.0
                min_rate = 0.0

            if min_rate >= 90:
                status_label = "healthy"
                healthy += 1
            elif min_rate >= 70:
                status_label = "warning"
                warning += 1
            else:
                status_label = "critical"
                critical += 1

            customer_results.append({
                "customer_id": cid,
                "customer_name": cname,
                "load_curve_completeness": load_rate,
                "settlement_curve_completeness": settlement_rate,
                "min_completeness": min_rate,
                "status": status_label,
            })

        return {
            "total_customers": len(customers),
            "healthy_customers": healthy,
            "warning_customers": warning,
            "critical_customers": critical,
            "customers": customer_results,
        }

    # ========== 6. 曲线校核 ==========

    def validate_curves(
        self,
        customer_id: str,
        validation_date: date,
        deep_analysis_threshold: float,
        operator: str
    ) -> Dict[str, Any]:
        """
        执行数据校核：比较负荷曲线与结算曲线的偏差

        流程：
        1. 查询两条曲线在validation_date的48点数据
        2. 计算用户级偏差统计
        3. 判断是否需要深入分析（偏差率超过阈值）
        4. 如需深入则计算计量点级偏差
        5. 存入data_quality_report
        """
        start_time = time.time()
        logger.info("开始校核客户 %s 日期 %s 的曲线数据", customer_id, validation_date)

        customer_name = self._get_customer_name(customer_id)
        day_start = datetime(validation_date.year, validation_date.month, validation_date.day)
        day_end = day_start + timedelta(days=1)

        # 查询两条曲线
        load_data = list(self.load_curve_collection.find(
            {"customer_id": customer_id, "datetime": {"$gt": day_start, "$lte": day_end}},
            {"_id": 0}
        ).sort("datetime", 1))

        settlement_data = list(self.settlement_curve_collection.find(
            {"customer_id": customer_id, "datetime": {"$gt": day_start, "$lte": day_end}},
            {"_id": 0}
        ).sort("datetime", 1))

        if not load_data and not settlement_data:
            raise ValueError(f"客户 {customer_id} 在 {validation_date} 无负荷曲线和结算曲线数据")

        # 构建时间点映射
        load_map = {doc["datetime"]: doc.get("load_kwh", 0) for doc in load_data}
        settlement_map = {doc["datetime"]: doc.get("load_kwh", 0) for doc in settlement_data}

        all_datetimes = sorted(set(list(load_map.keys()) + list(settlement_map.keys())))

        # 计算对比数据
        comparison_data = []
        deviations = []
        deviation_rates = []

        for dt in all_datetimes:
            time_label = self._format_time_label(dt, day_start)
            load_val = load_map.get(dt)
            settle_val = settlement_map.get(dt)

            if load_val is not None and settle_val is not None and settle_val != 0:
                deviation = load_val - settle_val
                deviation_rate = (deviation / settle_val) * 100
                deviations.append(deviation)
                deviation_rates.append(deviation_rate)
            elif load_val is not None and settle_val is not None:
                deviation = load_val - settle_val
                deviation_rate = 0.0 if load_val == settle_val else float('inf')
                deviations.append(deviation)
            else:
                deviation = None
                deviation_rate = None

            comparison_data.append({
                "time": time_label,
                "load_value": load_val,
                "settlement_value": settle_val,
                "deviation": round(deviation, 4) if deviation is not None else None,
            })

        # 计算用户级统计
        user_stats = None
        if deviations:
            finite_deviation_rates = [r for r in deviation_rates if r is not None and r != float('inf') and r != float('-inf')]
            mean_dev = sum(deviations) / len(deviations)
            mean_dev_rate = sum(finite_deviation_rates) / len(finite_deviation_rates) if finite_deviation_rates else 0.0
            max_pos_dev = max(deviations)
            max_neg_dev = min(deviations)

            user_stats = {
                "mean_deviation": round(mean_dev, 4),
                "mean_deviation_rate": round(mean_dev_rate, 4),
                "max_positive_deviation": round(max_pos_dev, 4),
                "max_negative_deviation": round(max_neg_dev, 4),
            }

        # 判断是否需要深入分析
        deep_required = False
        mp_analysis = []
        if user_stats and abs(user_stats["mean_deviation_rate"]) > deep_analysis_threshold:
            deep_required = True
            mp_analysis = self._deep_analysis_metering_points(
                customer_id, day_start, day_end, settlement_data
            )

        elapsed_ms = (time.time() - start_time) * 1000

        validation_result = {
            "analysis_period": validation_date.isoformat(),
            "data_points_compared": len(comparison_data),
            "user_level_statistics": user_stats,
            "deep_analysis_required": deep_required,
            "metering_point_analysis": mp_analysis,
            "curve_comparison_data": comparison_data,
        }

        report = {
            "customer_id": customer_id,
            "customer_name": customer_name,
            "report_type": "validation",
            "generated_at": datetime.now(),
            "validation_result": validation_result,
            "metadata": {
                "analysis_duration_ms": round(elapsed_ms, 2),
                "triggered_by": "api",
                "trigger_user": operator,
            },
        }

        self.report_collection.insert_one(report)
        report["_id"] = str(report.pop("_id"))

        logger.info("校核完成, 对比%d点, 平均偏差率%.2f%%, 深入分析=%s",
                     len(comparison_data),
                     user_stats.get("mean_deviation_rate", 0) if user_stats else 0,
                     deep_required)

        return report

    def _deep_analysis_metering_points(
        self,
        customer_id: str,
        day_start: datetime,
        day_end: datetime,
        settlement_data: List[Dict]
    ) -> List[Dict[str, Any]]:
        """深入分析：计量点级偏差"""
        mp_list = self._get_metering_points_with_allocation(customer_id)
        if not mp_list:
            return []

        settlement_total = sum(d.get("load_kwh", 0) for d in settlement_data)

        results = []
        for mp in mp_list:
            # 查询该计量点在user_load_data中的数据
            mp_data = list(self.user_load_collection.find(
                {
                    "meter_id": mp["meter_id"],
                    "timestamp": {"$gt": day_start, "$lte": day_end},
                },
                {"_id": 0}
            ))

            if not mp_data:
                continue

            mp_total = sum(d.get("load_value", d.get("load_kwh", 0)) for d in mp_data)
            mp_allocation = mp["allocation_percentage"]
            expected_contribution = settlement_total * (mp_allocation / 100.0)

            if expected_contribution != 0:
                mean_dev_rate = ((mp_total - expected_contribution) / expected_contribution) * 100
            else:
                mean_dev_rate = 0.0

            results.append({
                "mp_id": mp["mp_id"],
                "meter_id": mp["meter_id"],
                "current_allocation": mp_allocation,
                "mean_deviation_rate": round(mean_dev_rate, 4),
            })

        return results

    # ========== 7. 曲线对比查询 ==========

    def get_curve_comparison(
        self,
        customer_id: str,
        comparison_date: date
    ) -> Dict[str, Any]:
        """获取两条曲线的对比数据"""
        day_start = datetime(comparison_date.year, comparison_date.month, comparison_date.day)
        day_end = day_start + timedelta(days=1)

        load_data = list(self.load_curve_collection.find(
            {"customer_id": customer_id, "datetime": {"$gt": day_start, "$lte": day_end}},
            {"_id": 0}
        ).sort("datetime", 1))

        settlement_data = list(self.settlement_curve_collection.find(
            {"customer_id": customer_id, "datetime": {"$gt": day_start, "$lte": day_end}},
            {"_id": 0}
        ).sort("datetime", 1))

        # 格式化曲线数据
        load_curve = []
        for doc in load_data:
            time_label = self._format_time_label(doc["datetime"], day_start)
            load_curve.append({
                "time": time_label,
                "load_kwh": doc.get("load_kwh", 0),
            })

        settlement_curve = []
        for doc in settlement_data:
            time_label = self._format_time_label(doc["datetime"], day_start)
            settlement_curve.append({
                "time": time_label,
                "load_kwh": doc.get("load_kwh", 0),
            })

        # 对比数据
        load_map = {doc["datetime"]: doc.get("load_kwh", 0) for doc in load_data}
        settlement_map = {doc["datetime"]: doc.get("load_kwh", 0) for doc in settlement_data}
        all_datetimes = sorted(set(list(load_map.keys()) + list(settlement_map.keys())))

        comparison = []
        for dt in all_datetimes:
            time_label = self._format_time_label(dt, day_start)
            load_val = load_map.get(dt)
            settle_val = settlement_map.get(dt)
            deviation = (load_val - settle_val) if (load_val is not None and settle_val is not None) else None

            comparison.append({
                "time": time_label,
                "load_value": load_val,
                "settlement_value": settle_val,
                "deviation": round(deviation, 4) if deviation is not None else None,
            })

        return {
            "customer_id": customer_id,
            "comparison_date": comparison_date.isoformat(),
            "load_curve": load_curve,
            "settlement_curve": settlement_curve,
            "comparison_data": comparison,
        }

    # ========== 8. 重新生成负荷曲线 ==========

    def regenerate_load_curve(self, customer_id: str, operator: str) -> Dict[str, Any]:
        """
        基于当前分配系数重新计算用户级负荷曲线

        流程：
        1. 获取客户当前的分配系数
        2. 查询load_curve_user中该客户的数据
        3. 根据aggregation_meta中的原始计量点数据和新的分配系数重新计算
        4. 更新load_curve_user
        """
        start_time = time.time()
        logger.info("开始重新生成客户 %s 的负荷曲线", customer_id)

        customer_name = self._get_customer_name(customer_id)
        mp_list = self._get_metering_points_with_allocation(customer_id)

        if not mp_list:
            raise ValueError(f"客户 {customer_id} 无计量点分配系数信息，无法重新生成")

        # 查询现有负荷曲线数据
        existing_data = list(self.load_curve_collection.find(
            {"customer_id": customer_id},
            {"_id": 0}
        ).sort("datetime", 1))

        if not existing_data:
            raise ValueError(f"客户 {customer_id} 无现有负荷曲线数据")

        # 构建分配系数映射
        allocation_map = {}
        for mp in mp_list:
            allocation_map[mp["meter_id"]] = mp["allocation_percentage"]

        updated_count = 0
        now = datetime.now()

        for doc in existing_data:
            meta = doc.get("aggregation_meta", {})
            contributions = meta.get("mp_contributions", [])

            if not contributions:
                continue

            # 使用新的分配系数重新计算
            new_load = 0.0
            new_contributions = []
            for contrib in contributions:
                meter_id = contrib.get("meter_id", "")
                original_load = contrib.get("load_kwh", 0)
                new_allocation = allocation_map.get(meter_id, contrib.get("allocation_percentage", 100.0))
                contribution = original_load * (new_allocation / 100.0)
                new_load += contribution

                new_contributions.append({
                    "mp_id": contrib.get("mp_id", ""),
                    "meter_id": meter_id,
                    "load_kwh": original_load,
                    "allocation_percentage": new_allocation,
                })

            new_meta = {
                "mp_count": len(new_contributions),
                "mp_contributions": new_contributions,
            }

            self.load_curve_collection.update_one(
                {"customer_id": customer_id, "datetime": doc["datetime"]},
                {
                    "$set": {
                        "load_kwh": round(new_load, 4),
                        "aggregation_meta": new_meta,
                        "customer_name": customer_name,
                    }
                }
            )
            updated_count += 1

        elapsed = time.time() - start_time
        logger.info("负荷曲线重新生成完成, 更新%d条, 耗时%.2fs", updated_count, elapsed)

        return {
            "customer_id": customer_id,
            "customer_name": customer_name,
            "updated_count": updated_count,
            "duration_seconds": round(elapsed, 2),
        }
