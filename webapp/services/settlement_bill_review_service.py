"""平台账单复核服务

真实数据源待替换：当前直接返回确定性样例数据，保证接口可用。
"""
from typing import Any, Dict, List
from datetime import datetime


class SettlementBillReviewService:
    def __init__(self, db):
        self.db = db

    def get_bills(self, status: str = "ALL") -> Dict[str, Any]:
        """返回平台账单复核列表（样例数据），可按 status 过滤。

        status 取值：ALL / PENDING / REVIEWED / DIFFERENCE
        """
        bills: List[Dict[str, Any]] = [
            {"billNo": "BILL-2026-0601", "customer": "华能电力", "period": "2026-06", "platformAmount": 10049900, "systemAmount": 10049900, "diff": 0, "status": "REVIEWED"},
            {"billNo": "BILL-2026-0602", "customer": "大唐新能源", "period": "2026-06", "platformAmount": 8286300, "systemAmount": 8292578, "diff": 6278, "status": "DIFFERENCE"},
            {"billNo": "BILL-2026-0603", "customer": "国电投", "period": "2026-06", "platformAmount": 12417600, "systemAmount": 12439092, "diff": 21492, "status": "DIFFERENCE"},
            {"billNo": "BILL-2026-0604", "customer": "华电", "period": "2026-06", "platformAmount": 3362200, "systemAmount": 3362200, "diff": 0, "status": "REVIEWED"},
            {"billNo": "BILL-2026-0605", "customer": "三峡能源", "period": "2026-06", "platformAmount": 4592800, "systemAmount": 4592800, "diff": 0, "status": "PENDING"},
            {"billNo": "BILL-2026-0606", "customer": "中广核", "period": "2026-06", "platformAmount": 3116400, "systemAmount": 3118920, "diff": 2520, "status": "DIFFERENCE"},
            {"billNo": "BILL-2026-0607", "customer": "国华", "period": "2026-06", "platformAmount": 2627200, "systemAmount": 2627200, "diff": 0, "status": "REVIEWED"},
            {"billNo": "BILL-2026-0608", "customer": "大唐", "period": "2026-06", "platformAmount": 3731820, "systemAmount": 3731820, "diff": 0, "status": "PENDING"},
            {"billNo": "BILL-2026-0609", "customer": "华润", "period": "2026-06", "platformAmount": 2983600, "systemAmount": 2983600, "diff": 0, "status": "REVIEWED"},
            {"billNo": "BILL-2026-0610", "customer": "国投", "period": "2026-06", "platformAmount": 2451400, "systemAmount": 2456020, "diff": 4620, "status": "DIFFERENCE"},
        ]
        if status and status != "ALL":
            bills = [b for b in bills if b["status"] == status]
        return {"bills": bills}

    def review_bill(self, bill_no: str, action: str, operator: str, reason: str = None) -> Dict[str, Any]:
        """复核账单：approve -> REVIEWED，reject -> REJECTED。

        账单主数据当前仍为确定性样例（真实 bills 集合待接入），因此复核动作
        以审计留痕为准写入 bills_review_log，返回值携带复核后的账单视图。
        真实数据源接入后，把下面的内存改写替换为 bills.update_one 即可。
        """
        if action not in ("approve", "reject"):
            raise ValueError("action 必须为 approve 或 reject")
        bills = self.get_bills(status="ALL").get("bills", [])
        target = next((b for b in bills if b.get("billNo") == bill_no), None)
        if target is None:
            raise ValueError("账单不存在")

        new_status = "REVIEWED" if action == "approve" else "REJECTED"
        record = {
            "bill_no": bill_no,
            "action": action,
            "operator": operator,
            "reason": reason,
            "before_status": target.get("status"),
            "after_status": new_status,
            "reviewed_at": datetime.now(),
        }
        res = self.db.bills_review_log.insert_one(record)

        target["status"] = new_status
        target["reviewedBy"] = operator
        return {"bill": target, "log_id": str(res.inserted_id)}
