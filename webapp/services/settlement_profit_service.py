"""经营利润分析服务（真实读库）

收入 ← 零售结算：电量(MWh) × 合同零售电价(元/MWh)
成本 ← 批发购电：电量(MWh) × 日前现货电价(元/MWh)，按时间戳对齐
毛利 = 收入 − 成本；毛利率 = 毛利 / 收入

单位口径：user_load_data.value 为 15 分钟平均功率(kW)，电量 = value × 0.25h / 1000 (MWh)。
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

HOURS_PER_POINT = 0.25


class SettlementProfitService:
    """经营利润：按月份输出收入/成本/毛利。"""

    def __init__(self, db) -> None:
        self.db = db

    def get_profit(self, months: int = 12) -> Dict[str, Any]:
        warnings: List[str] = []
        periods = self._recent_months(months)

        contracts = list(self.db.retail_contracts.find({}))
        price_by_customer: Dict[str, float] = {}
        for c in contracts:
            cfg = ((c.get("package_snapshot") or {}).get("pricing_config") or {})
            val = cfg.get("fixed_price_value") or cfg.get("fixed_price") or cfg.get("energy_price")
            if val is None:
                warnings.append("合同 %s 缺零售电价，其收入未计入" % (c.get("contract_name") or c.get("_id")))
                continue
            price_by_customer[str(c.get("customer_id") or "")] = float(val) * 1000.0  # 元/MWh

        revenue, cost = self._calc_by_month(periods, price_by_customer, warnings)

        rows: List[Dict[str, Any]] = []
        total_rev = 0.0
        for period in periods:
            rev = revenue.get(period, 0.0)
            cst = cost.get(period, 0.0)
            if rev <= 0 and cst <= 0:
                continue
            gross = rev - cst
            rows.append({
                "month": period,
                "revenue": round(rev, 2),
                "cost": round(cst, 2),
                "gross": round(gross, 2),
                "margin": round(gross / rev * 100.0, 2) if rev else 0.0,
            })
            total_rev += rev

        # 收入构成：当前仅有售电收入一项，如实输出，不虚构拆分
        composition = [{"name": "售电收入", "value": round(total_rev, 2)}] if total_rev else []

        if not rows:
            warnings.append("所选月份内无收入/成本数据")
        return {"rows": rows, "revenueComposition": composition, "warnings": warnings}

    # ------------------------------------------------------------ 内部

    @staticmethod
    def _recent_months(months: int) -> List[str]:
        now = datetime.now()
        out = []
        for i in range(months - 1, -1, -1):
            idx = now.year * 12 + (now.month - 1) - i
            y, m0 = divmod(idx, 12)
            out.append("%04d-%02d" % (y, m0 + 1))
        return out

    @staticmethod
    def _month_bounds(period: str):
        start = datetime.strptime(period, "%Y-%m").replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        return start, end

    def _calc_by_month(
        self,
        periods: List[str],
        price_by_customer: Dict[str, float],
        warnings: List[str],
    ) -> Tuple[Dict[str, float], Dict[str, float]]:
        """按月算收入与成本。负荷与电价按**时间戳**对齐，缺点只影响该点。"""
        revenue: Dict[str, float] = defaultdict(float)
        cost: Dict[str, float] = defaultdict(float)
        if not periods:
            return revenue, cost

        start, _ = self._month_bounds(periods[0])
        _, end = self._month_bounds(periods[-1])

        # 电价映射
        price_map: Dict[datetime, float] = {}
        for d in self.db.day_ahead_spot_price.find(
            {"timestamp": {"$gt": start, "$lte": end}}, {"timestamp": 1, "value": 1, "_id": 0}
        ):
            ts, val = d.get("timestamp"), d.get("value")
            if ts is not None and val is not None:
                price_map[ts] = float(val)
        if not price_map:
            warnings.append("day_ahead_spot_price 无数据，成本侧不可信")

        missing_price = 0
        for d in self.db.user_load_data.find(
            {"timestamp": {"$gt": start, "$lte": end}},
            {"timestamp": 1, "value": 1, "customer_id": 1, "_id": 0},
        ):
            ts, val = d.get("timestamp"), d.get("value")
            if ts is None or val is None:
                continue
            biz = ts - timedelta(days=1) if (ts.hour == 0 and ts.minute == 0) else ts
            period = biz.strftime("%Y-%m")
            if period not in periods:
                continue
            mwh = float(val) * HOURS_PER_POINT / 1000.0
            cid = str(d.get("customer_id") or "")
            retail_price = price_by_customer.get(cid)
            if retail_price is not None:
                revenue[period] += mwh * retail_price
            p = price_map.get(ts)
            if p is None:
                missing_price += 1
                continue
            cost[period] += mwh * p

        if missing_price:
            warnings.append("%d 个负荷时点缺少电价，成本未计入该时点" % missing_price)
        return revenue, cost
