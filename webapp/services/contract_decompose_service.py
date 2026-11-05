"""合约分解服务：把中长期合约电量分解到日 → 96 点，输出可直接用于持仓/敞口/结算的曲线。

分解口径：
  1. 月度电量 = 合约总电量 × (该月与合约执行期重叠天数 / 合约总天数)
  2. 月 → 日：优先用该客户该月「实际日电量占比」；无数据时回退到日类型权重（工作日1.0/周六日0.85）；
             再无数据则按自然日均分
  3. 日 → 96 点：用该客户历史「平均日负荷形状」（96 点归一化权重）；无数据用默认双峰形状
  4. 合约均价：取 package_snapshot.pricing_config.fixed_price_value（元/kWh → 元/MWh），缺失回退 400
"""
import logging
import statistics
import uuid
from calendar import monthrange
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pymongo.database import Database

logger = logging.getLogger(__name__)

HOURS_PER_POINT = 0.25
TIME_LIST = ["%02d:%02d" % (i // 4, (i % 4) * 15) for i in range(96)]


class ContractDecomposeService:
    def __init__(self, db: Database) -> None:
        self.db = db

    # ---------------- 数据获取 ----------------
    @staticmethod
    def _month_bounds(year: int, month: int):
        start = datetime(year, month, 1)
        end = datetime(year, month, monthrange(year, month)[1], 23, 59, 59)
        return start, end

    def _contract_month_volume(self, contract: dict, year: int, month: int) -> float:
        """按执行期重叠天数比例，把合约总电量分摊到指定月份（MWh）。"""
        m_start, m_end = self._month_bounds(year, month)
        c_start = contract.get("purchase_start_month")
        c_end = contract.get("purchase_end_month")
        if isinstance(c_start, str):
            c_start = datetime.fromisoformat(c_start)
        if isinstance(c_end, str):
            c_end = datetime.fromisoformat(c_end)
        if not c_start or not c_end:
            return 0.0
        overlap_start = max(c_start, m_start)
        overlap_end = min(c_end, m_end)
        if overlap_start > overlap_end:
            return 0.0
        total_days = (c_end.date() - c_start.date()).days + 1
        overlap_days = (overlap_end.date() - overlap_start.date()).days + 1
        total_mwh = float(contract.get("purchasing_electricity_quantity") or 0) / 1000.0
        return total_mwh * overlap_days / max(total_days, 1)

    @staticmethod
    def _contract_price(contract: dict) -> float:
        snap = contract.get("package_snapshot") or {}
        cfg = snap.get("pricing_config") or {}
        v = cfg.get("fixed_price_value")
        if v is None:
            v = cfg.get("fixed_price") or cfg.get("price")
        try:
            v = float(v)
        except (TypeError, ValueError):
            return 400.0
        # 源口径为 元/kWh → 转 元/MWh
        return v * 1000.0 if v < 10 else v

    def _daily_load_mwh(self, customer_id: str, year: int, month: int) -> Dict[str, float]:
        """该客户该月每日电量（MWh）。"""
        start, end = self._month_bounds(year, month)
        out: Dict[str, float] = {}
        for d in self.db["user_load_data"].find(
            {"customer_id": customer_id, "timestamp": {"$gte": start, "$lte": end}},
            {"timestamp": 1, "value": 1, "_id": 0},
        ):
            ts = d.get("timestamp")
            if not hasattr(ts, "strftime"):
                continue
            key = ts.strftime("%Y-%m-%d")
            out[key] = out.get(key, 0.0) + float(d.get("value") or 0) * HOURS_PER_POINT / 1000.0
        return out

    def _daily_point_counts(self, customer_id: str, year: int, month: int) -> Dict[str, int]:
        """该客户该月每日实际负荷点数（用于判断数据是否完整）。"""
        start, end = self._month_bounds(year, month)
        out: Dict[str, int] = {}
        for d in self.db["user_load_data"].find(
            {"customer_id": customer_id, "timestamp": {"$gte": start, "$lte": end}},
            {"timestamp": 1, "_id": 0},
        ):
            ts = d.get("timestamp")
            if hasattr(ts, "strftime"):
                k = ts.strftime("%Y-%m-%d")
                out[k] = out.get(k, 0) + 1
        return out

    def _daily_load_points(self, customer_id: str, year: int, month: int) -> Dict[str, List[float]]:
        """该客户该月每日 96 点实际负荷（MWh/点）。"""
        start, end = self._month_bounds(year, month)
        out: Dict[str, List[float]] = {}
        for d in self.db["user_load_data"].find(
            {"customer_id": customer_id, "timestamp": {"$gte": start, "$lte": end}},
            {"timestamp": 1, "value": 1, "_id": 0},
        ):
            ts = d.get("timestamp")
            if not hasattr(ts, "strftime"):
                continue
            minutes = ts.hour * 60 + ts.minute
            idx = 95 if minutes == 0 else (minutes // 15) - 1
            idx = max(0, min(95, idx))
            arr = out.setdefault(ts.strftime("%Y-%m-%d"), [0.0] * 96)
            arr[idx] += float(d.get("value") or 0) * HOURS_PER_POINT / 1000.0
        return out

    def _load_shape(self, customer_id: str, year: int, month: int) -> Optional[List[float]]:
        """该客户该月平均日负荷形状（96 点，和为 1）。"""
        start, end = self._month_bounds(year, month)
        acc = {t: 0.0 for t in TIME_LIST}
        days = set()
        for d in self.db["user_load_data"].find(
            {"customer_id": customer_id, "timestamp": {"$gte": start, "$lte": end}},
            {"timestamp": 1, "value": 1, "_id": 0},
        ):
            ts = d.get("timestamp")
            if not hasattr(ts, "strftime"):
                continue
            days.add(ts.strftime("%Y-%m-%d"))
            minutes = ts.hour * 60 + ts.minute
            if minutes == 0:
                idx = 95
            else:
                idx = (minutes // 15) - 1
            acc[TIME_LIST[max(0, min(95, idx))]] += float(d.get("value") or 0)
        total = sum(acc.values())
        if total <= 0:
            return None
        return [acc[t] / total for t in TIME_LIST]

    @staticmethod
    def _default_shape() -> List[float]:
        """默认双峰形状（无负荷数据时兜底）。"""
        w = []
        for i in range(96):
            h = i / 4.0
            if 8 <= h < 12:
                v = 1.25
            elif 17 <= h < 21:
                v = 1.35
            elif 0 <= h < 6:
                v = 0.72
            else:
                v = 1.0
            w.append(v)
        s = sum(w)
        return [x / s for x in w]

    def _spot_month_stats(self, year: int, month: int):
        """该月日前现货日均价序列与统计（元/MWh）。"""
        start, end = self._month_bounds(year, month)
        daily: Dict[str, List[float]] = {}
        for d in self.db["day_ahead_spot_price"].find(
            {"date_str": {"$regex": "^%04d-%02d" % (year, month)},
             "avg_clearing_price": {"$ne": None}},
            {"date_str": 1, "avg_clearing_price": 1, "_id": 0},
        ):
            v = d.get("avg_clearing_price")
            if v is None:
                continue
            daily.setdefault(d["date_str"], []).append(float(v))
        series = [sum(v) / len(v) for v in daily.values() if v]
        avg = round(sum(series) / len(series), 3) if series else 0.0
        std = round(statistics.pstdev(series), 3) if len(series) > 1 else 0.0
        return avg, std, len(series)

    # ---------------- 主流程 ----------------
    def decompose(self, customer_id: str, year: int, month: int,
                  params: Optional[dict] = None) -> Dict[str, Any]:
        params = params or {}
        m_start, m_end = self._month_bounds(year, month)
        days_in_month = monthrange(year, month)[1]

        # 1. 合约
        q = {
            "customer_id": customer_id,
            "purchase_start_month": {"$lte": m_end},
            "purchase_end_month": {"$gte": m_start},
        }
        contracts = [c for c in self.db["retail_contracts"].find(q)
                     if (c.get("status") or "active") in ("pending", "active")]

        month_volume = 0.0
        amount = 0.0
        for c in contracts:
            v = self._contract_month_volume(c, year, month)
            month_volume += v
            amount += v * self._contract_price(c)
        blended_cost = round(amount / month_volume, 3) if month_volume else 0.0

        customer = self.db["customers"].find_one({"_id": _oid(customer_id)}, {"user_name": 1})
        customer_name = (customer or {}).get("user_name", customer_id)

        # 2. 月 → 日
        demand_points = self._daily_load_points(customer_id, year, month)
        daily_load = {k: sum(v) for k, v in demand_points.items()}
        dates = [f"{year}-{month:02d}-{d:02d}" for d in range(1, days_in_month + 1)]

        point_counts = self._daily_point_counts(customer_id, year, month)
        complete_days = {d for d in dates if point_counts.get(d, 0) >= 90}

        if complete_days:
            weight_mode = "实际日电量占比（仅用数据完整的 %d 天，其余按日类型权重）" % len(complete_days)
            daily_avg = (sum(daily_load.get(d, 0.0) for d in complete_days) / len(complete_days))
            weights = {}
            for d in dates:
                if d in complete_days:
                    weights[d] = daily_load.get(d, 0.0)
                else:
                    wd = datetime(year, month, int(d[-2:])).weekday()
                    weights[d] = daily_avg * (1.0 if wd < 5 else 0.85)
            total_w = sum(weights.values())
            weights = {d: (w / total_w if total_w else 1.0 / days_in_month) for d, w in weights.items()}
        else:
            weight_mode = "日类型权重(工作日1.0/周六日0.85)"
            weights = {}
            for d in range(1, days_in_month + 1):
                wd = datetime(year, month, d).weekday()
                weights[f"{year}-{month:02d}-{d:02d}"] = 1.0 if wd < 5 else 0.85
            total_w = sum(weights.values())
            weights = {d: w / total_w for d, w in weights.items()}

        # 3. 日 → 96 点
        shape = self._load_shape(customer_id, year, month)
        shape_mode = "实际负荷形状"
        if shape is None:
            shape = self._default_shape()
            shape_mode = "默认双峰形状"

        daily_contracts = []
        total_demand = 0.0
        for d in dates:
            vol = round(month_volume * weights.get(d, 0.0), 4)
            points = [round(vol * shape[i], 6) for i in range(96)]
            demand = round(daily_load.get(d, 0.0), 4)
            total_demand += demand
            dps = demand_points.get(d, [0.0] * 96)
            daily_contracts.append({
                "date": d,
                "volume_mwh": vol,
                "points": points,
                "demand_mwh": demand,
                "demand_points": [round(x, 6) for x in dps],
                "gap_mwh": round(demand - vol, 4),
                # 兼容旧前端字段名
                "predicted_load": demand,
                "contract_amount": vol,
                "spot_amount": round(max(0.0, demand - vol), 4),
            })

        # 4. 汇总
        by_period = {"peak": 0.0, "flat": 0.0, "valley": 0.0}
        tou_map = self._tou_map(year, month)
        for dc in daily_contracts:
            for i, v in enumerate(dc["points"]):
                seg = tou_map.get(TIME_LIST[i], "平")
                if "峰" in seg:
                    by_period["peak"] += v
                elif "谷" in seg:
                    by_period["valley"] += v
                else:
                    by_period["flat"] += v

        spot_avg, spot_std, spot_days = self._spot_month_stats(year, month)
        gap_energy = round(total_demand - month_volume, 4)      # 敞口（正=需现货补，负=余量可卖）
        contract_cost = round(month_volume * blended_cost, 2)
        spot_cost_actual = round(gap_energy * spot_avg, 2)
        portfolio_cost = round(contract_cost + spot_cost_actual, 2)
        pure_spot_cost = round(total_demand * spot_avg, 2)
        var95 = round(1.645 * spot_std * abs(gap_energy), 2) if spot_std else 0.0
        sharpe = round((blended_cost - spot_avg) / spot_std, 3) if spot_std else None

        summary = {
            "total_volume_mwh": round(month_volume, 4),
            "total_demand": round(total_demand, 4),
            "coverage_ratio": round(month_volume / total_demand, 4) if total_demand else None,
            "contract_coverage": round(month_volume / total_demand, 4) if total_demand else None,
            "blended_cost": blended_cost,
            "total_cost": portfolio_cost,
            "portfolio_cost": portfolio_cost,
            "contract_cost": contract_cost,
            "spot_cost": spot_cost_actual,
            "pure_spot_cost": pure_spot_cost,
            "vs_pure_spot": {
                "cost_percentage": (round((portfolio_cost - pure_spot_cost) / pure_spot_cost, 4)
                                    if pure_spot_cost else None),
                "cost_diff": round(portfolio_cost - pure_spot_cost, 2),
            },
            "spot_avg_price": spot_avg,
            "spot_price_std": spot_std,
            "spot_days": spot_days,
            "gap_energy_mwh": gap_energy,
            "value_at_risk_95": var95,
            "sharpe_ratio": sharpe,
            "contract_count": len(contracts),
            "by_period": {k: round(v, 3) for k, v in by_period.items()},
            "ratio_by_period": {
                k: round(v / month_volume, 4) if month_volume else 0.0
                for k, v in by_period.items()
            },
        }

        curve = {
            "curve_id": "CV" + uuid.uuid4().hex[:12].upper(),
            "customer_id": customer_id,
            "customer_name": customer_name,
            "contract_month": {"year": year, "month": month},
            "optimization_params": {
                "objective": params.get("objective", "balanced"),
                "contract_coverage": params.get("contract_coverage"),
                "day_weight_mode": weight_mode,
                "shape_mode": shape_mode,
            },
            "daily_contracts": daily_contracts,
            "summary": summary,
            "created_at": datetime.utcnow(),
            "status": "active",
        }
        self.db["contract_curves"].insert_one(dict(curve))
        return curve

    def _tou_map(self, year: int, month: int) -> Dict[str, str]:
        from webapp.services.tou_service import get_tou_rule_by_date
        try:
            return get_tou_rule_by_date(datetime(year, month, 15))
        except Exception:
            return {}


def _oid(v):
    from bson import ObjectId
    try:
        return ObjectId(v)
    except Exception:
        return v
