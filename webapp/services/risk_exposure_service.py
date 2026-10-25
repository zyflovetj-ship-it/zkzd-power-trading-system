"""风险敞口分析服务（真实读库，复用风险引擎）

设计取舍
--------
旧实现是 59 行硬编码样例。新实现**不另起一套敞口算法**，而是复用
RiskEngineService 的真实分时段计算（它已做 96 点持仓/负荷对齐、kW→MWh 换算、
按分时段相关性的 VaR），再把结果聚合成旧页面所需的 24 小时视图。
这样驾驶舱与旧敞口页口径永远一致，避免两套数字打架。

前端契约（risk.ts RiskExposureResp）：
  totalExposure / priceExposure / volumeExposure / var95（单位：万元 / 万kWh）
  monthly[{month, contract, spot}]、priceExposureHourly[24]、volumeExposureHourly[24]、hours[24]
"""

import logging
from datetime import date, datetime, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

#: 元 -> 万元
YUAN_PER_WAN = 10000.0


class RiskExposureService:
    """旧敞口页的真实数据适配层：复用风险引擎，输出 24 小时/月度视图。"""

    def __init__(self, db) -> None:
        self.db = db

    def get_exposure(self, delivery_date: date = None) -> Dict[str, Any]:
        from webapp.services.risk_engine_service import RiskEngineService

        warnings: List[str] = []
        d = delivery_date or self._latest_data_date()
        engine = RiskEngineService(self.db)

        try:
            exp = engine.build_exposure(d)
        except Exception as exc:
            logger.error("风险引擎敞口计算失败: %s", exc, exc_info=True)
            return self._empty(["风险引擎计算失败：%s" % exc])

        curve = exp["curve"]
        summary = exp["summary"]

        # --- 24 小时聚合（96 点 -> 24 点，每 4 点一小时）
        hours: List[str] = []
        price_hourly: List[float] = []
        volume_hourly: List[float] = []
        for h in range(24):
            idxs = range(h * 4, h * 4 + 4)
            price_hourly.append(round(
                sum(curve[i].price_exposure for i in idxs) / YUAN_PER_WAN, 4))
            # 电量敞口取绝对值之和（万 kWh）
            volume_hourly.append(round(
                sum(abs(curve[i].net_position_mwh) for i in idxs) / 10.0, 4))
            hours.append("%02d:00" % h)

        # --- 汇总
        total_price_wan = round(abs(summary.price_exposure_yuan) / YUAN_PER_WAN, 4)
        total_volume_wan_kwh = round(
            sum(abs(p.net_position_mwh) for p in curve) / 10.0, 4)  # MWh -> 万kWh

        var95_wan = 0.0
        try:
            var = engine.compute_var(d)
            var95_wan = round(var.var_yuan / YUAN_PER_WAN, 4)
            if var.warnings:
                warnings.extend(var.warnings)
        except Exception as exc:
            warnings.append("VaR 计算失败：%s" % exc)

        # --- 月度：合约电量 vs 现货（未覆盖）电量
        monthly = self._monthly_exposure()

        if summary.warnings:
            warnings.extend(summary.warnings)

        return {
            "totalExposure": round(total_price_wan + total_volume_wan_kwh, 4),
            "priceExposure": total_price_wan,
            "volumeExposure": total_volume_wan_kwh,
            "var95": var95_wan,
            "monthly": monthly,
            "priceExposureHourly": price_hourly,
            "volumeExposureHourly": volume_hourly,
            "hours": hours,
            "warnings": warnings,
        }

    # ------------------------------------------------------------ 内部

    def _latest_data_date(self) -> date:
        """取电价数据的最新业务日，避免默认今天而无数据。"""
        doc = self.db.day_ahead_spot_price.find_one({}, sort=[("timestamp", -1)])
        ts = (doc or {}).get("timestamp")
        if isinstance(ts, datetime):
            return ts.date()
        return date.today()

    def _monthly_exposure(self) -> List[Dict[str, Any]]:
        """近 12 个月的 合约电量 与 未覆盖电量（均按万 kWh）。"""
        now = datetime.now()
        out: List[Dict[str, Any]] = []

        # 合约电量按合同起止月份均摊
        contracts = list(self.db.retail_contracts.find({}))
        contract_by_month: Dict[str, float] = {}
        for c in contracts:
            qty_mwh = float(c.get("purchasing_electricity_quantity") or 0) / 1000.0
            s, e = c.get("purchase_start_month"), c.get("purchase_end_month")
            if not isinstance(s, datetime) or not isinstance(e, datetime) or qty_mwh <= 0:
                continue
            cur = s.replace(day=1)
            stop = e.replace(day=1)
            months = []
            while cur <= stop:
                months.append(cur.strftime("%Y-%m"))
                cur = (cur + timedelta(days=32)).replace(day=1)
            if months:
                per = qty_mwh / len(months)
                for m in months:
                    contract_by_month[m] = contract_by_month.get(m, 0.0) + per

        # 实际用电按月
        actual_by_month: Dict[str, float] = {}
        for d in self.db.user_load_data.find({}, {"timestamp": 1, "value": 1, "_id": 0}):
            ts, v = d.get("timestamp"), d.get("value")
            if ts is None or v is None:
                continue
            biz = ts - timedelta(days=1) if (ts.hour == 0 and ts.minute == 0) else ts
            m = biz.strftime("%Y-%m")
            actual_by_month[m] = actual_by_month.get(m, 0.0) + float(v) * 0.25 / 1000.0

        for i in range(11, -1, -1):
            idx = now.year * 12 + (now.month - 1) - i
            y, m0 = divmod(idx, 12)
            m = "%04d-%02d" % (y, m0 + 1)
            contract = contract_by_month.get(m, 0.0)
            actual = actual_by_month.get(m, 0.0)
            # spot 列表示未覆盖（敞口）电量：合约不足部分
            spot = max(0.0, actual - contract) if contract else actual
            out.append({
                "month": "%d月" % (m0 + 1),
                "contract": round(contract / 10.0, 4),
                "spot": round(spot / 10.0, 4),
            })
        return out

    @staticmethod
    def _empty(warnings: List[str]) -> Dict[str, Any]:
        return {
            "totalExposure": 0.0, "priceExposure": 0.0, "volumeExposure": 0.0,
            "var95": 0.0, "monthly": [],
            "priceExposureHourly": [0.0] * 24, "volumeExposureHourly": [0.0] * 24,
            "hours": ["%02d:00" % h for h in range(24)],
            "warnings": warnings,
        }
