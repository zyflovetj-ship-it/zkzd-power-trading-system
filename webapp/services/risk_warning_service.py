"""套餐风险预警与「法定代表人二次确认」服务。

依据《江苏电力交易工作指引》第五条：套餐参数越界（如峰系数<1.6、谷系数>0.4、
kP/F/K分摊越界等）触发风险预警，须经法定代表人确认后方可执行。

设计：
  - 套餐文档上挂 risk_warning: {triggered, items, confirmed, confirmed_by, confirmed_at, note}
  - 每次「激活」前复核：若触发预警且未确认 → 拒绝激活
  - 确认动作写入 risk_confirm_logs 审计留痕（不可篡改的独立集合）
"""
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from bson import ObjectId
from pymongo.database import Database

from webapp.services.compliance_service import ComplianceService

logger = logging.getLogger(__name__)


class RiskWarningService:
    """套餐风险预警评估 + 法定代表人确认。"""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.packages = db["retail_packages"]
        self.confirm_logs = db["risk_confirm_logs"]

    # ---------------------------- 评估 ----------------------------
    def evaluate(self, package: dict) -> Dict[str, Any]:
        """评估套餐是否触发风险预警（含是否已获法人确认）。"""
        cfg = (package or {}).get("pricing_config") or {}
        comp = ComplianceService().validate(cfg)
        items: List[Dict[str, Any]] = [it for it in comp["items"] if not it.get("pass")]

        rw = (package or {}).get("risk_warning") or {}
        confirmed = bool(rw.get("confirmed"))
        triggered = bool(items)

        return {
            "package_id": str((package or {}).get("id") or (package or {}).get("_id") or ""),
            "package_name": (package or {}).get("package_name"),
            "triggered": triggered,
            "items": items,
            "errors": comp["errors"],
            "confirmed": confirmed,
            "confirmed_by": rw.get("confirmed_by"),
            "confirmed_at": rw.get("confirmed_at").strftime("%Y-%m-%d %H:%M:%S")
            if isinstance(rw.get("confirmed_at"), datetime) else rw.get("confirmed_at"),
            "note": rw.get("note"),
            "requires_legal_confirm": triggered and not confirmed,
            "notice": "参数越界触发风险预警，须经法定代表人确认后方可执行（交易工作指引第五条）"
            if triggered else "未触发风险预警",
        }

    def evaluate_by_id(self, package_id: str) -> Dict[str, Any]:
        doc = self._get(package_id)
        return self.evaluate(doc)

    def _get(self, package_id: str) -> dict:
        try:
            doc = self.packages.find_one({"_id": ObjectId(package_id)})
        except Exception:
            raise ValueError("无效的套餐ID: %s" % package_id)
        if not doc:
            raise ValueError("套餐不存在: %s" % package_id)
        doc["id"] = str(doc.pop("_id"))
        return doc

    # ------------------------ 法定代表人确认 ------------------------
    def confirm(self, package_id: str, operator: str, confirmed_by: str,
                note: Optional[str] = None, attachment_name: Optional[str] = None) -> Dict[str, Any]:
        """记录法定代表人确认（需存在预警项）。"""
        if not confirmed_by or not str(confirmed_by).strip():
            raise ValueError("必须填写法定代表人姓名")

        doc = self._get(package_id)
        ev = self.evaluate(doc)
        if not ev["triggered"]:
            return {"ok": True, "message": "该套餐未触发风险预警，无需确认", "evaluation": ev}

        now = datetime.utcnow()
        rw = {
            "triggered": True,
            "items": ev["items"],
            "confirmed": True,
            "confirmed_by": str(confirmed_by).strip(),
            "confirmed_at": now,
            "note": note,
            "attachment_name": attachment_name,
            "operator": operator,
        }
        self.packages.update_one({"_id": ObjectId(package_id)},
                                 {"$set": {"risk_warning": rw, "updated_at": now,
                                           "updated_by": operator}})
        # 审计留痕
        self.confirm_logs.insert_one({
            "package_id": package_id,
            "package_name": doc.get("package_name"),
            "action": "legal_confirm",
            "triggered_items": ev["items"],
            "confirmed_by": str(confirmed_by).strip(),
            "operator": operator,
            "note": note,
            "attachment_name": attachment_name,
            "created_at": now,
        })
        logger.info("套餐 %s 法定代表人确认完成，确认人=%s，操作人=%s", package_id, confirmed_by, operator)
        return {"ok": True, "message": "法定代表人确认已记录", "confirmed_by": rw["confirmed_by"],
                "confirmed_at": now.strftime("%Y-%m-%d %H:%M:%S"), "items": len(ev["items"])}

    def revoke(self, package_id: str, operator: str, reason: Optional[str] = None) -> Dict[str, Any]:
        """撤销确认（参数修改后应重新确认）。"""
        now = datetime.utcnow()
        self.packages.update_one(
            {"_id": ObjectId(package_id)},
            {"$set": {"risk_warning.confirmed": False,
                      "risk_warning.revoked_at": now,
                      "risk_warning.revoked_by": operator,
                      "updated_at": now}},
        )
        self.confirm_logs.insert_one({
            "package_id": package_id, "action": "legal_confirm_revoke",
            "operator": operator, "note": reason, "created_at": now,
        })
        return {"ok": True, "message": "已撤销确认，需重新确认后方可激活"}

    def logs(self, package_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        out = []
        for d in self.confirm_logs.find({"package_id": package_id}, {"_id": 0}).sort("created_at", -1).limit(limit):
            if isinstance(d.get("created_at"), datetime):
                d["created_at"] = d["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            out.append(d)
        return out
