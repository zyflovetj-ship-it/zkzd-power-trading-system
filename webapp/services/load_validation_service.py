"""负荷数据校验服务（真实读库）

数据源
------
load_curve_user        手工导入负荷曲线（48 点/30 分钟，load_kwh 为时段电量）
settlement_curve_user  RPA 计量结算曲线（48 点/30 分钟，load_kwh 为时段电量）

校验项
------
1. 完整度：每业务日应有 48 点，不足记为 missing
2. 双源一致性：同日两条曲线的电量偏差率超过阈值记为 error
3. 数值异常：单点电量 <= 0 记为 error（负值/零值多为采集故障）

业务日约定：24:00 存为次日 00:00，归属前一日。
"""

import logging
from collections import defaultdict
from datetime import datetime, timedelta
from typing import Any, Dict, List

logger = logging.getLogger(__name__)

#: 每个业务日应有的点数（30 分钟粒度）
POINTS_PER_DAY = 48
#: 双源电量偏差率告警阈值
DEVIATION_THRESHOLD = 0.05


class LoadValidationService:
    """负荷数据校验：基于真实曲线计算，不再返回样例数据。"""

    LOAD_COLLECTION = "load_curve_user"
    SETTLEMENT_COLLECTION = "settlement_curve_user"

    def __init__(self, db) -> None:
        self.db = db

    def get_records(self, days: int = 7) -> Dict[str, Any]:
        """返回最近 N 个业务日的校验记录。

        :return: {"records": [{date, customer, metric, status, problem, detectValue}],
                  "warnings": [...]}
        """
        warnings: List[str] = []
        load_map = self._curve_by_day(self.LOAD_COLLECTION)
        settle_map = self._curve_by_day(self.SETTLEMENT_COLLECTION)

        if not load_map and not settle_map:
            warnings.append(
                "两条曲线均为空：请先执行 transform-manual-data 与 import-rpa-data 生成 48 点曲线"
            )
            return {"records": [], "warnings": warnings}

        all_days = sorted(set(load_map) | set(settle_map))[-days:]
        records: List[Dict[str, Any]] = []

        for day in all_days:
            for cid in sorted(set(load_map.get(day, {})) | set(settle_map.get(day, {}))):
                lc = load_map.get(day, {}).get(cid)
                sc = settle_map.get(day, {}).get(cid)
                name = (lc or sc or {}).get("name") or cid

                # --- 1) 完整度
                for label, side in (("负荷曲线", lc), ("结算曲线", sc)):
                    if side is None:
                        records.append(self._rec(
                            day, name, label, "missing", "缺失：当日无该曲线数据", "-"))
                        continue
                    if side["points"] < POINTS_PER_DAY:
                        records.append(self._rec(
                            day, name, label, "missing",
                            "缺失：仅 %d/%d 点" % (side["points"], POINTS_PER_DAY),
                            "%d 点" % side["points"]))
                        continue
                    # --- 3) 数值异常
                    if side["min_kwh"] <= 0:
                        records.append(self._rec(
                            day, name, label, "error", "异常：存在非正电量点",
                            "min=%.2f kWh" % side["min_kwh"]))
                        continue
                    records.append(self._rec(
                        day, name, label, "pass", "-",
                        "%.2f MWh" % (side["total_kwh"] / 1000.0)))

                # --- 2) 双源一致性
                if lc and sc and lc["points"] == POINTS_PER_DAY and sc["points"] == POINTS_PER_DAY:
                    base = sc["total_kwh"] or 1.0
                    dev = (lc["total_kwh"] - sc["total_kwh"]) / base
                    if abs(dev) > DEVIATION_THRESHOLD:
                        records.append(self._rec(
                            day, name, "双源一致性", "error",
                            "偏差：负荷与结算曲线差异 %.2f%%（阈值 %.0f%%）" % (
                                dev * 100, DEVIATION_THRESHOLD * 100),
                            "%.2f%%" % (dev * 100)))
                    else:
                        records.append(self._rec(
                            day, name, "双源一致性", "pass", "-", "%.2f%%" % (dev * 100)))

        if not records:
            warnings.append("所选区间内无可用校验数据")
        return {"records": records, "warnings": warnings}

    # ------------------------------------------------------------ 内部

    @staticmethod
    def _rec(date: str, customer: str, metric: str, status: str, problem: str, detect: str) -> Dict[str, Any]:
        """构造前端契约记录（camelCase 与 loadValidation.ts 对齐）。"""
        return {
            "date": date,
            "customer": customer,
            "metric": metric,
            "status": status,
            "problem": problem,
            "detectValue": detect,
        }

    def _curve_by_day(self, collection: str):
        """曲线 → {业务日: {customer_id: {name, points, total_kwh, min_kwh}}}。"""
        out: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(dict)
        cursor = self.db[collection].find(
            {}, {"datetime": 1, "load_kwh": 1, "customer_id": 1, "customer_name": 1, "_id": 0}
        )
        for d in cursor:
            ts = d.get("datetime")
            if ts is None:
                continue
            biz = ts - timedelta(days=1) if (ts.hour == 0 and ts.minute == 0) else ts
            day = biz.date().isoformat()
            cid = str(d.get("customer_id") or "unknown")
            kwh = float(d.get("load_kwh") or 0.0)
            slot = out[day].get(cid)
            if slot is None:
                slot = {"name": d.get("customer_name") or cid,
                        "points": 0, "total_kwh": 0.0, "min_kwh": kwh}
                out[day][cid] = slot
            slot["points"] += 1
            slot["total_kwh"] += kwh
            slot["min_kwh"] = min(slot["min_kwh"], kwh)
        return out
