"""持仓合约管理服务（真实读库）

数据链路
--------
合同主数据 ← retail_contracts（合同电量 kWh、起止月份）
合约均价 ← retail_contracts.package_snapshot.pricing_config.fixed_price_value（元/kWh）
已执行电量 ← user_load_data（96 点，value = 15 分钟平均功率 kW，电量 = value × 0.25h）
覆盖率 = 已执行电量 / 合同电量
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

HOURS_PER_POINT = 0.25


class RiskPositionService:
    """持仓合约：真实读库，输出前端 camelCase 契约。"""

    def __init__(self, db) -> None:
        self.db = db

    def get_contracts(self) -> Dict[str, Any]:
        warnings: List[str] = []
        contracts = list(self.db.retail_contracts.find({}))
        if not contracts:
            warnings.append("retail_contracts 为空")

        out: List[Dict[str, Any]] = []
        for c in contracts:
            cid = str(c.get("customer_id") or "")
            cname = c.get("customer_name") or cid
            cno = c.get("contract_name") or str(c.get("_id") or "")

            qty_kwh = float(c.get("purchasing_electricity_quantity") or 0)
            start = c.get("purchase_start_month")
            end = c.get("purchase_end_month")

            avg_price = None
            cfg = ((c.get("package_snapshot") or {}).get("pricing_config") or {})
            val = cfg.get("fixed_price_value") or cfg.get("fixed_price") or cfg.get("energy_price")
            if val is not None:
                avg_price = float(val) * 1000.0  # 元/kWh -> 元/MWh
            else:
                warnings.append("合同 %s 缺零售电价，avgPrice 记 0" % cno)

            executed_kwh = self._executed_energy_kwh(cid, start, end)

            out.append({
                "customer": cname,
                "contractNo": cno,
                "volume": round(qty_kwh / 1000.0, 4),          # MWh
                "avgPrice": round(avg_price, 2) if avg_price is not None else 0.0,
                "startDate": start.strftime("%Y-%m-%d") if isinstance(start, datetime) else str(start or ""),
                "endDate": end.strftime("%Y-%m-%d") if isinstance(end, datetime) else str(end or ""),
                "coverage": round(executed_kwh / qty_kwh * 100.0, 2) if qty_kwh else 0.0,
            })

        return {"contracts": out, "warnings": warnings}

    def _executed_energy_kwh(self, customer_id: str, start, end) -> float:
        """合同期内已执行电量(kWh)。value 为功率 kW，×0.25h 得电量。"""
        if not isinstance(start, datetime) or not isinstance(end, datetime):
            return 0.0
        month_end = (end.replace(day=1) + timedelta(days=32)).replace(day=1)
        q: Dict[str, Any] = {"timestamp": {"$gte": start, "$lt": month_end}}
        if customer_id:
            q["customer_id"] = customer_id
        total = 0.0
        for d in self.db.user_load_data.find(q, {"value": 1, "_id": 0}):
            v = d.get("value")
            if v is not None:
                total += float(v) * HOURS_PER_POINT
        return total
