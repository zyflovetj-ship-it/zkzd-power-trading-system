"""竞价空间（Bidding Space）计算与校验服务。

系统内存在两套口径，本服务统一收口：

1) 日文件口径（业务主用，与交易中心/调度发布文件一致）：
   竞价空间 = 短期系统负荷 − 光伏汇总 − 风电汇总 − 受电计划 − 储能发电计划 − 燃机固定出力总值 − 煤电发电计划

2) 兼容口径（沿用 v1.py 既有算法，保留不改）：
   日前 = 负荷预测 − 风电 − 光伏 − 非市场化机组 − 联络线计划
   实时 = 系统负荷 − 风电 − 光伏 − 非市场化机组 − 联络线潮流
   非市场化机组 = 水电 + max(抽蓄, 0) + max(储能, 0)

数据表：
   daily_release         日前（含各成分 + 竞价空间）
   actual_operation      实时（系统负荷/联络线 + 各成分）
   real_time_generation  实时发电（风光水/抽蓄/储能）
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pymongo.database import Database

logger = logging.getLogger(__name__)


class BiddingSpaceService:
    """竞价空间计算与校验。"""

    def __init__(self, db: Database) -> None:
        self.db = db

    # ------------------------- 核心公式 -------------------------
    @staticmethod
    def calc(load: float, pv: float, wind: float, tieline: float,
             storage: float, gas: float, coal: float) -> float:
        """日文件口径竞价空间。

        竞价空间 = 负荷 − 光伏 − 风电 − 受电 − 储能 − 燃机 − 煤电
        """
        return float(load) - float(pv) - float(wind) - float(tieline) \
            - float(storage) - float(gas) - float(coal)

    @staticmethod
    def calc_day_ahead_compat(load_forecast: float, wind: float, pv: float,
                              nonmarket_unit: float, tieline_plan: float) -> float:
        """兼容口径（日前）：负荷预测 − 风电 − 光伏 − 非市场化机组 − 联络线计划。"""
        return float(load_forecast) - float(wind) - float(pv) - float(nonmarket_unit) - float(tieline_plan)

    @staticmethod
    def calc_real_time_compat(system_load: float, wind: float, solar: float,
                              hydro: float, pumped_storage: float, battery_storage: float,
                              tieline_flow: float) -> float:
        """兼容口径（实时）：系统负荷 − 风电 − 光伏 − 非市场化机组 − 联络线潮流。"""
        nonmarket_unit = float(hydro) + max(float(pumped_storage), 0.0) + max(float(battery_storage), 0.0)
        return float(system_load) - float(wind) - float(solar) - nonmarket_unit - float(tieline_flow)

    # ------------------------- 查询/计算 -------------------------
    @staticmethod
    def _date_range(date_str: str):
        start = datetime.strptime(date_str, "%Y-%m-%d")
        return start, start + timedelta(days=1)

    def get_bidding_space(self, date_str: str) -> Dict[str, Any]:
        """读取某日竞价空间（优先用发布值，其次用成分重算）。"""
        start, end = self._date_range(date_str)
        da = {d["time_str"]: d for d in self.db["daily_release"].find(
            {"date_str": date_str}, {"_id": 0}).sort("time_str", 1)}
        rt = {d["time_str"]: d for d in self.db["actual_operation"].find(
            {"date_str": date_str}, {"_id": 0}).sort("time_str", 1)}

        points: List[Dict[str, Any]] = []
        for ts in sorted(set(list(da.keys()) + list(rt.keys()))):
            a = da.get(ts)
            r = rt.get(ts)
            da_space = rt_space = None
            da_comp = rt_comp = None
            if a:
                da_comp = {
                    "load": a.get("system_load_forecast"),
                    "pv": a.get("pv_forecast"),
                    "wind": a.get("wind_forecast"),
                    "tieline": a.get("tieline_plan"),
                    "storage": a.get("storage_plan"),
                    "gas": a.get("gas_unit_plan"),
                    "coal": a.get("coal_unit_plan"),
                }
                da_space = a.get("bidding_space_pub")
                if da_space is None:
                    da_space = self.calc(*(da_comp[k] or 0 for k in
                                           ("load", "pv", "wind", "tieline", "storage", "gas", "coal")))
            if r:
                rt_comp = {
                    "load": r.get("system_load"),
                    "pv": r.get("pv_actual"),
                    "wind": r.get("wind_actual"),
                    "tieline": r.get("tieline_flow"),
                    "storage": r.get("storage_actual"),
                    "gas": r.get("gas_actual"),
                    "coal": r.get("coal_actual"),
                }
                rt_space = r.get("bidding_space_pub")
                if rt_space is None:
                    rt_space = self.calc(*(rt_comp[k] or 0 for k in
                                           ("load", "pv", "wind", "tieline", "storage", "gas", "coal")))
            points.append({
                "time_str": ts,
                "bidding_space_da": None if da_space is None else round(float(da_space), 2),
                "bidding_space_rt": None if rt_space is None else round(float(rt_space), 2),
                "deviation": (None if (da_space is None or rt_space is None)
                              else round(float(rt_space) - float(da_space), 2)),
                "components_da": {k: (None if v is None else round(float(v), 2)) for k, v in da_comp.items()} if da_comp else None,
                "components_rt": {k: (None if v is None else round(float(v), 2)) for k, v in rt_comp.items()} if rt_comp else None,
            })
        return {"date": date_str, "points": points, "count": len(points)}

    def verify(self, date_str: str) -> Dict[str, Any]:
        """校验：用成分重算值与文件发布值逐点比对。"""
        result = {"date": date_str, "day_ahead": {}, "real_time": {}}
        for coll, pub_key, prefix in (
            ("daily_release", "bidding_space_pub", "day_ahead"),
            ("actual_operation", "bidding_space_pub", "real_time"),
        ):
            docs = list(self.db[coll].find({"date_str": date_str}, {"_id": 0}))
            diffs = []
            checked = 0
            for d in docs:
                pub = d.get(pub_key)
                if pub is None:
                    continue
                if coll == "daily_release":
                    calc = self.calc(d.get("system_load_forecast", 0), d.get("pv_forecast", 0),
                                     d.get("wind_forecast", 0), d.get("tieline_plan", 0),
                                     d.get("storage_plan", 0), d.get("gas_unit_plan", 0),
                                     d.get("coal_unit_plan", 0))
                else:
                    calc = self.calc(d.get("system_load", 0), d.get("pv_actual", 0),
                                     d.get("wind_actual", 0), d.get("tieline_flow", 0),
                                     d.get("storage_actual", 0), d.get("gas_actual", 0),
                                     d.get("coal_actual", 0))
                checked += 1
                if abs(calc - float(pub)) > 0.05:
                    diffs.append({"time_str": d.get("time_str"), "calc": round(calc, 2), "pub": float(pub)})
            result[prefix] = {"checked": checked, "mismatch": len(diffs), "samples": diffs[:3]}
        return result
