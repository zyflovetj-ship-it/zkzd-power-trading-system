"""零售用户结算服务（真实读库）

数据链路
--------
用电量 ← user_load_data（96 点，value = 15 分钟平均功率 kW，电量 = value × 0.25h）
结算电价 ← retail_contracts.package_snapshot.pricing_config.fixed_price_value（元/kWh）
结算金额 = 电量(MWh) × 电价(元/MWh)

单位口径
--------
user_load_data.value 是功率(kW)不是电量。若当 kWh 累加，电量与金额虚高 4 倍
（已用零售合约交叉校验：437kW×0.25h×96 ≈ 10.5 MWh/日 ≈ 合约 10.87 MWh/日）。

回款状态
--------
库内无回款/账单数据源（bills 集合为空），payStatus 统一标记 UNPAID 并在 warnings 中声明，
待接入财务回款表后改为按实回款状态输出。
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

HOURS_PER_POINT = 0.25


class SettlementRetailService:
    """零售用户结算：按合同 × 月份输出。"""

    def __init__(self, db) -> None:
        self.db = db

    def get_rows(self, months: int = 3) -> Dict[str, Any]:
        warnings: List[str] = []
        periods = self._recent_months(months)
        rows: List[Dict[str, Any]] = []

        contracts = list(self.db.retail_contracts.find({}))
        if not contracts:
            warnings.append("retail_contracts 为空，无法结算")

        # 电量按 (customer_id, 月) 汇总
        energy = self._energy_by_month(periods)

        for c in contracts:
            cid = str(c.get("customer_id") or "")
            cname = c.get("customer_name") or cid
            cno = c.get("contract_name") or str(c.get("_id") or "")
            price_kwh = self._retail_price(c, warnings, cno)
            if price_kwh is None:
                continue
            price_mwh = price_kwh * 1000.0

            for period in periods:
                mwh = energy.get((cid, period), 0.0)
                if mwh <= 0:
                    continue
                rows.append({
                    "customer": cname,
                    "contract": cno,
                    "usage": round(mwh, 4),
                    "price": round(price_mwh, 2),
                    "amount": round(mwh * price_mwh, 2),
                    "payStatus": "UNPAID",
                })

        if rows:
            warnings.append("回款状态无数据源（bills 集合为空），payStatus 统一为 UNPAID")
        return {"rows": rows, "warnings": warnings}

    # ------------------------------------------------------------ 内部

    def _retail_price(self, contract: Dict[str, Any], warnings: List[str], cno: str):
        """从合同快照取零售电价(元/kWh)；取不到返回 None 并告警（不静默兜底）。"""
        snap = contract.get("package_snapshot") or {}
        cfg = snap.get("pricing_config") or {}
        val = cfg.get("fixed_price_value")
        if val is None:
            val = cfg.get("fixed_price") or cfg.get("energy_price")
        if val is None:
            warnings.append("合同 %s 缺少 package_snapshot.pricing_config.fixed_price_value，已跳过" % cno)
            return None
        return float(val)

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

    def _energy_by_month(self, periods: List[str]) -> Dict[Any, float]:
        """(customer_id, 月) -> 电量 MWh。"""
        out: Dict[Any, float] = {}
        if not periods:
            return out
        start, _ = self._month_bounds(periods[0])
        _, end = self._month_bounds(periods[-1])
        cursor = self.db.user_load_data.find(
            {"timestamp": {"$gt": start, "$lte": end}},
            {"timestamp": 1, "value": 1, "customer_id": 1, "_id": 0},
        )
        for d in cursor:
            ts, val = d.get("timestamp"), d.get("value")
            if ts is None or val is None:
                continue
            biz = ts - timedelta(days=1) if (ts.hour == 0 and ts.minute == 0) else ts
            period = biz.strftime("%Y-%m")
            if period not in periods:
                continue
            key = (str(d.get("customer_id") or ""), period)
            out[key] = out.get(key, 0.0) + float(val) * HOURS_PER_POINT / 1000.0
        return out
