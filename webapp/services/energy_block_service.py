"""能量块申报服务：校验 + 落库 + 汇总。

校验规则：
  1. 非空：至少 1 个能量块
  2. 时段合法性：period_type=time 时必须带 time_str，且为 00:00~23:45（96 点）
  3. 价格区间：0 <= price <= price_cap
  4. 段数限制：现货（day_ahead/real_time）同一时段段数 <= 10
  5. 报价单调性（现货）：同一时段内按段序，买入价非递减、卖出价非递增
  6. 总量守恒：给了 total_volume_mwh 时，Σ电量 与总电量偏差 <= max(0.5, 0.1%)
  7. 分时段结构：给了 expected_ratio 时，峰/平/谷电量占比偏差 > 10% 告警
"""
import logging
import re
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from pymongo.database import Database

from webapp.models.energy_block import EnergyBlockSetCreate

logger = logging.getLogger(__name__)

TIME_RE = re.compile(r"^([01]\d|2[0-3]):([0-5]\d)$")
VALID_TIMES = {("%02d:%02d" % (i // 4, (i % 4) * 15)) for i in range(96)}
SPOT_MARKETS = {"day_ahead", "real_time"}
MAX_SEGMENT = 10


class EnergyBlockService:
    def __init__(self, db: Database) -> None:
        self.db = db
        self.collection = db["energy_blocks"]

    # ----------------------------- 校验 -----------------------------
    def validate(self, payload: EnergyBlockSetCreate) -> Dict[str, Any]:
        errors: List[str] = []
        warnings: List[str] = []
        blocks = payload.blocks or []

        if not blocks:
            errors.append("能量块不能为空")

        # 2. 时段合法性
        for i, b in enumerate(blocks, 1):
            if b.period_type == "time":
                if not b.time_str:
                    errors.append(f"第{i}块：period_type=time 时必须填写 time_str")
                elif not TIME_RE.match(b.time_str) or b.time_str not in VALID_TIMES:
                    errors.append(f"第{i}块：time_str={b.time_str} 不是有效的 96 点时刻")

        # 3. 价格区间
        for i, b in enumerate(blocks, 1):
            if b.price > payload.price_cap:
                errors.append(f"第{i}块：价格 {b.price} 超过上限 {payload.price_cap}")

        # 4/5. 现货段数与单调性
        if payload.market_type in SPOT_MARKETS:
            grouped: Dict[str, List] = {}
            for b in blocks:
                key = b.time_str or b.period_type
                grouped.setdefault(key, []).append(b)
            for key, items in grouped.items():
                if len(items) > MAX_SEGMENT:
                    errors.append(f"时段 {key}：段数 {len(items)} 超过现货上限 {MAX_SEGMENT}")
                ordered = sorted(items, key=lambda x: x.segment)
                for a, c in zip(ordered, ordered[1:]):
                    if payload.direction == "buy" and c.price < a.price:
                        warnings.append(f"时段 {key}：买入报价未单调递增（段{a.segment}→{c.segment}）")
                    if payload.direction == "sell" and c.price > a.price:
                        warnings.append(f"时段 {key}：卖出报价未单调递减（段{a.segment}→{c.segment}）")

        # 6. 总量守恒
        total = round(sum(b.volume_mwh for b in blocks), 4)
        if payload.total_volume_mwh is not None:
            tol = max(0.5, payload.total_volume_mwh * 0.001)
            if abs(total - payload.total_volume_mwh) > tol:
                errors.append(
                    f"总量不守恒：申报合计 {total} MWh，申报总量 {payload.total_volume_mwh} MWh，"
                    f"允许偏差 ±{tol:.3f}"
                )

        # 7. 分时段结构
        ratio_actual = self._ratio_by_period(blocks)
        if payload.expected_ratio:
            for k, expect in payload.expected_ratio.items():
                actual = ratio_actual.get(k, 0.0)
                if abs(actual - expect) > 0.10:
                    warnings.append(
                        f"分时段结构偏差：{k} 实际占比 {actual:.1%}，期望 {expect:.1%}（差 {abs(actual-expect):.1%}）"
                    )

        # 汇总
        by_period: Dict[str, Dict[str, float]] = {}
        for b in blocks:
            k = b.period_type if b.period_type != "time" else "time"
            agg = by_period.setdefault(k, {"volume_mwh": 0.0, "amount": 0.0})
            agg["volume_mwh"] += b.volume_mwh
            agg["amount"] += b.volume_mwh * b.price
        for k, v in by_period.items():
            v["avg_price"] = round(v["amount"] / v["volume_mwh"], 3) if v["volume_mwh"] else 0.0
            v["volume_mwh"] = round(v["volume_mwh"], 4)
            v["amount"] = round(v["amount"], 2)

        return {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "summary": {
                "block_count": len(blocks),
                "total_volume_mwh": total,
                "total_amount": round(sum(b.volume_mwh * b.price for b in blocks), 2),
                "avg_price": round(
                    sum(b.volume_mwh * b.price for b in blocks) / total, 3) if total else 0.0,
                "ratio_by_period": ratio_actual,
                "by_period": by_period,
            },
        }

    @staticmethod
    def _ratio_by_period(blocks) -> Dict[str, float]:
        total = sum(b.volume_mwh for b in blocks) or 0.0
        if not total:
            return {}
        out: Dict[str, float] = {}
        for b in blocks:
            k = b.period_type if b.period_type != "time" else "time"
            out[k] = out.get(k, 0.0) + b.volume_mwh
        return {k: round(v / total, 4) for k, v in out.items()}

    # ----------------------------- 落库 -----------------------------
    def create(self, payload: EnergyBlockSetCreate, operator: str) -> Dict[str, Any]:
        result = self.validate(payload)
        if not result["valid"]:
            raise ValueError("；".join(result["errors"]))

        set_id = "EB" + uuid.uuid4().hex[:12].upper()
        now = datetime.utcnow()
        docs = []
        for b in payload.blocks:
            docs.append({
                "block_set_id": set_id,
                "market_type": payload.market_type,
                "subject_type": payload.subject_type,
                "subject_id": payload.subject_id,
                "subject_name": payload.subject_name,
                "trade_period": payload.trade_period,
                "start_date": payload.start_date,
                "end_date": payload.end_date or payload.start_date,
                "period_type": b.period_type,
                "time_str": b.time_str,
                "segment": b.segment,
                "volume_mwh": b.volume_mwh,
                "price": b.price,
                "direction": payload.direction,
                "status": payload.status,
                "created_by": operator,
                "created_at": now,
            })
        self.collection.insert_many(docs)
        return {
            "block_set_id": set_id,
            "block_count": len(docs),
            "total_volume_mwh": result["summary"]["total_volume_mwh"],
            "avg_price": result["summary"]["avg_price"],
            "warnings": result["warnings"],
        }

    def list_sets(self, market_type: Optional[str] = None, subject_id: Optional[str] = None,
                  limit: int = 50) -> List[Dict[str, Any]]:
        pipeline = [{"$sort": {"created_at": -1}}]
        match: Dict[str, Any] = {}
        if market_type:
            match["market_type"] = market_type
        if subject_id:
            match["subject_id"] = subject_id
        if match:
            pipeline.insert(0, {"$match": match})
        pipeline += [
            {"$group": {
                "_id": "$block_set_id",
                "market_type": {"$first": "$market_type"},
                "subject_id": {"$first": "$subject_id"},
                "subject_name": {"$first": "$subject_name"},
                "start_date": {"$first": "$start_date"},
                "end_date": {"$first": "$end_date"},
                "status": {"$first": "$status"},
                "block_count": {"$sum": 1},
                "total_volume_mwh": {"$sum": "$volume_mwh"},
                "created_at": {"$first": "$created_at"},
                "created_by": {"$first": "$created_by"},
            }},
            {"$sort": {"created_at": -1}},
            {"$limit": limit},
        ]
        out = []
        for d in self.collection.aggregate(pipeline):
            d["block_set_id"] = d.pop("_id")
            if isinstance(d.get("created_at"), datetime):
                d["created_at"] = d["created_at"].strftime("%Y-%m-%d %H:%M:%S")
            out.append(d)
        return out

    def get_set(self, set_id: str) -> Dict[str, Any]:
        docs = list(self.collection.find({"block_set_id": set_id}, {"_id": 0}).sort(
            [("period_type", 1), ("time_str", 1), ("segment", 1)]))
        if not docs:
            raise ValueError(f"能量块集合不存在: {set_id}")
        total = sum(d["volume_mwh"] for d in docs)
        amount = sum(d["volume_mwh"] * d["price"] for d in docs)
        return {
            "block_set_id": set_id,
            "market_type": docs[0]["market_type"],
            "subject_id": docs[0]["subject_id"],
            "subject_name": docs[0].get("subject_name"),
            "start_date": docs[0]["start_date"],
            "end_date": docs[0]["end_date"],
            "status": docs[0]["status"],
            "block_count": len(docs),
            "total_volume_mwh": round(total, 4),
            "avg_price": round(amount / total, 3) if total else 0.0,
            "blocks": [{
                "period_type": d["period_type"],
                "time_str": d.get("time_str"),
                "segment": d["segment"],
                "volume_mwh": d["volume_mwh"],
                "price": d["price"],
            } for d in docs],
        }

    def delete_set(self, set_id: str) -> int:
        return self.collection.delete_many({"block_set_id": set_id}).deleted_count
