"""批发侧预结算服务（真实读库）

数据链路
--------
结算电量 ← settlement_curve_user（RPA 计量口径，48 点/30 分钟，load_kwh 为时段电量）
结算电价 ← day_ahead_spot_price（96 点/15 分钟，元/MWh）
偏差电量 ← user_load_data（实际，96 点，value 为平均功率 kW）
           short_term_load_forecast（预测，96 点，value 为平均功率 kW）

单位口径（重要）
----------------
user_load_data / short_term_load_forecast 的 value 是**该 15 分钟时段的平均功率(kW)**，
时段电量 = value × 0.25h。已用零售合约交叉校验：
  437 kW × 0.25h × 96 点 ≈ 10.5 MWh/日 ≈ 合约 10.87 MWh/日。
若把 value 直接当 kWh 累加，电量与金额都会虚高 4 倍（实测 4.00×）。

结算曲线与电价的粒度对齐
------------------------
曲线是 30 分钟点（结束时刻标记：00:30…24:00），电价是 15 分钟点。
一个 30 分钟槽由两个 15 分钟电价覆盖（T-15min 与 T），取二者均值作为该槽电价。
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

#: 15 分钟时段折算小时数
HOURS_PER_POINT = 0.25
#: 96 点功率源 → 电量换算：kWh = kW × 0.25
KW_TO_KWH = HOURS_PER_POINT


class SettlementWholesaleService:
    """批发侧预结算：按结算单元（客户）× 月份聚合。"""

    CURVE_COLLECTION = "settlement_curve_user"
    PRICE_COLLECTION = "day_ahead_spot_price"
    ACTUAL_COLLECTION = "user_load_data"
    FORECAST_COLLECTION = "short_term_load_forecast"

    def __init__(self, db) -> None:
        self.db = db
        #: customer_id -> 展示用客户名（由结算曲线侧填充）
        self._unit_names: Dict[str, str] = {}

    # ------------------------------------------------------------------ 入口

    def get_rows(self, months: int = 3) -> Dict[str, Any]:
        """返回最近 N 个月的批发预结算行。

        :return: {"rows": [{unit, period, volume, price, amount, devVolume, devFee}],
                  "warnings": [...]}
        """
        warnings: List[str] = []
        periods = self._recent_months(months)

        curve = self._curve_by_month(periods)
        if not curve:
            warnings.append(
                "settlement_curve_user 无可用数据，请先执行 RPA 导入（import-rpa-data）生成结算曲线"
            )

        price_map = self._price_by_timestamp(periods)
        actual = self._power_sum_by_month(periods, self.ACTUAL_COLLECTION)
        forecast = self._power_sum_by_month(periods, self.FORECAST_COLLECTION)

        rows: List[Dict[str, Any]] = []
        # 以曲线中出现的 (unit, period) 为主键
        for (cid, period), points in sorted(curve.items()):
            volume_kwh = sum(p["kwh"] for p in points)
            if volume_kwh <= 0:
                continue
            amount = sum(
                p["kwh"] * price_map.get(p["ts"], 0.0) / 1000.0 for p in points
            )
            price = amount * 1000.0 / volume_kwh if volume_kwh else 0.0

            # 偏差：同一单元同一月，实际 − 预测（均按 kW×0.25 转 MWh）
            act_mwh = actual.get((cid, period), 0.0)
            fc_mwh = forecast.get((cid, period), 0.0)
            dev_mwh = act_mwh - fc_mwh if fc_mwh else 0.0
            # 偏差电费：按该月结算均价计价（正偏差计费、负偏差冲减）
            dev_fee = dev_mwh * price if price else 0.0

            rows.append({
                "unit": self._unit_names.get(cid, cid) or "未知单元",
                "period": period,
                "volume": round(volume_kwh / 1000.0, 4),
                "price": round(price, 2),
                "amount": round(amount, 2),
                "devVolume": round(dev_mwh, 4),
                "devFee": round(dev_fee, 2),
            })

        if not rows:
            warnings.append("所选月份内无结算电量，rows 为空")
        missing_price = sum(1 for p in price_map.values() if not p)
        if price_map and missing_price == len(price_map):
            warnings.append("所选月份内电价全部缺失，amount/price 不可信")

        return {"rows": rows, "warnings": warnings}

    # ------------------------------------------------------------ 数据装配

    @staticmethod
    def _recent_months(months: int) -> List[str]:
        """最近 N 个月（含当月），格式 YYYY-MM。"""
        now = datetime.now()
        out: List[str] = []
        for i in range(months - 1, -1, -1):
            idx = now.year * 12 + (now.month - 1) - i
            y, m0 = divmod(idx, 12)
            out.append("%04d-%02d" % (y, m0 + 1))
        return out

    def _month_bounds(self, period: str) -> Tuple[datetime, datetime]:
        dt = datetime.strptime(period, "%Y-%m")
        start = dt.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = (start + timedelta(days=32)).replace(day=1)
        return start, end

    def _curve_by_month(self, periods: List[str]):
        """结算曲线 → {(unit, period): [{ts, kwh}]}。

        业务日约定：24:00 存为次日 00:00，归属前一日；此处按月聚合，
        跨月边界点（月初 00:00）归属上月，避免月初重复计。
        """
        result = defaultdict(list)
        if not periods:
            return result
        start, _ = self._month_bounds(periods[0])
        _, end = self._month_bounds(periods[-1])
        cursor = self.db[self.CURVE_COLLECTION].find(
            {"datetime": {"$gt": start, "$lte": end}},
            {"datetime": 1, "load_kwh": 1, "customer_id": 1, "customer_name": 1, "_id": 0},
        )
        for d in cursor:
            ts = d.get("datetime")
            kwh = d.get("load_kwh")
            if ts is None or kwh is None:
                continue
            # 次日 00:00 归前一业务日（进而归前一月）
            biz = ts - timedelta(days=1) if (ts.hour == 0 and ts.minute == 0) else ts
            period = biz.strftime("%Y-%m")
            if period not in periods:
                continue
            cid = str(d.get("customer_id") or "")
            cname = d.get("customer_name") or cid or "未知单元"
            # 聚合键统一用 customer_id：user_load_data 无 customer_name，
            # short_term_load_forecast 连 customer_id 都没有，用显示名做键会导致偏差恒为 0。
            self._unit_names[cid] = cname
            result[(cid, period)].append({"ts": ts, "kwh": float(kwh)})
        return result

    def _price_by_timestamp(self, periods: List[str]) -> Dict[datetime, float]:
        """电价映射（15 分钟粒度）。"""
        out: Dict[datetime, float] = {}
        if not periods:
            return out
        start, _ = self._month_bounds(periods[0])
        _, end = self._month_bounds(periods[-1])
        cursor = self.db[self.PRICE_COLLECTION].find(
            {"timestamp": {"$gt": start, "$lte": end}},
            {"timestamp": 1, "value": 1, "_id": 0},
        )
        for d in cursor:
            ts, val = d.get("timestamp"), d.get("value")
            if ts is not None and val is not None:
                out[ts] = float(val)
        return out

    def _power_sum_by_month(self, periods: List[str], collection: str) -> Dict[Tuple[str, str], float]:
        """按 (客户, 月) 汇总电量 MWh —— 从 96 点功率源换算。"""
        out: Dict[Tuple[str, str], float] = defaultdict(float)
        if not periods:
            return out
        start, _ = self._month_bounds(periods[0])
        _, end = self._month_bounds(periods[-1])
        cursor = self.db[collection].find(
            {"timestamp": {"$gt": start, "$lte": end}},
            {"timestamp": 1, "value": 1, "customer_name": 1, "customer_id": 1, "_id": 0},
        )
        for d in cursor:
            ts, val = d.get("timestamp"), d.get("value")
            if ts is None or val is None:
                continue
            biz = ts - timedelta(days=1) if (ts.hour == 0 and ts.minute == 0) else ts
            period = biz.strftime("%Y-%m")
            if period not in periods:
                continue
            cid = str(d.get("customer_id") or "")
            if not cid:
                # short_term_load_forecast 未落 customer_id：系统当前单客户，
                # 归到唯一客户；多客户场景必须先在数据侧补 customer_id，否则偏差不可信。
                cid = self._sole_customer_id()
            if not cid:
                continue
            out[(cid, period)] += float(val) * KW_TO_KWH / 1000.0
        return out

    def _sole_customer_id(self) -> Optional[str]:
        """系统只有一个客户时返回其 id，否则返回 None（避免错误归集）。"""
        ids = self.db["customers"].distinct("_id")
        if len(ids) == 1:
            return str(ids[0])
        return None
