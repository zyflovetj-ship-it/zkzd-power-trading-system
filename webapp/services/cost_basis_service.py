"""成本基线服务（事前成本，供报价决策）。

背景：系统原有 4 条链路（竞价空间 / 能量块 / 合约曲线 / 套餐测算）互不打通，
      缺少「综合购电成本」这一转换器，导致套餐测算的批发价只能手工拍。
      本服务补上这一环。

成本构成（事前口径）：
    中长期合约成本 = Σ(合约月电量 × 合约价)              ← retail_contracts
    现货采购成本   = 敞口电量 × 日前现货均价               ← 敞口(负荷−持仓) + day_ahead_spot_price
    三类分摊       = 成本补偿 + 不平衡 + 市场调节          ← 参数传入（默认 0，不臆造）
    综合成本单价   = 总成本 / 总电量                       ← 元/MWh

敞口口径：
    敞口 = MAX(负荷 − 持仓, 0)    正=需现货补购；负=余量可售（不计现货成本）

数据来源优先级：
    负荷：user_load_data（96点功率，kW）→ 无则 bill_verification（核查联月电量）
    持仓：contract_curves（合约分解 96 点）→ 无则视为 0 持仓
    现货价：day_ahead_spot_price.avg_clearing_price 月度均价

⚠️ 默认口径说明（可切换）：
    - 现货成本价默认用【日前现货均价】，非能量块成交价
      （能量块目前全为 draft，无成交数据；待成交环节就绪后可切换）
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pymongo.database import Database

logger = logging.getLogger(__name__)

HOURS_PER_POINT = 0.25
COLLECTION = "cost_basis"


class CostBasisService:
    """综合购电成本基线计算。"""

    def __init__(self, db: Database) -> None:
        self.db = db
        self.collection = db[COLLECTION]

    # ----------------------------- 工具 -----------------------------
    @staticmethod
    def _month_bounds(year: int, month: int):
        start = datetime(year, month, 1)
        end = datetime(year + 1, 1, 1) if month == 12 else datetime(year, month + 1, 1)
        return start, end

    # ----------------------------- 电量 -----------------------------
    def _load_mwh(self, customer_id: Optional[str], year: int, month: int) -> Dict[str, Any]:
        """该月总用电量（MWh）。优先 96 点负荷，其次核查联。"""
        start, end = self._month_bounds(year, month)
        q: Dict[str, Any] = {"timestamp": {"$gte": start, "$lt": end}}
        if customer_id:
            q["customer_id"] = customer_id
        total = 0.0
        points = 0
        for d in self.db["user_load_data"].find(q, {"value": 1, "_id": 0}):
            v = d.get("value")
            if v is None:
                continue
            total += float(v) * HOURS_PER_POINT / 1000.0
            points += 1
        if points > 0:
            return {"mwh": round(total, 4), "source": "user_load_data", "points": points}

        # 回退核查联
        period = "%04d-%02d" % (year, month)
        bq: Dict[str, Any] = {"period": period}
        if customer_id:
            bq["customer_id"] = customer_id
        total = 0.0
        cnt = 0
        for d in self.db["bill_verification"].find(bq, {"total_mwh": 1, "_id": 0}):
            total += float(d.get("total_mwh") or 0.0)
            cnt += 1
        if cnt > 0:
            return {"mwh": round(total, 4), "source": "bill_verification", "points": cnt}
        return {"mwh": 0.0, "source": None, "points": 0}

    def _position_mwh(self, customer_id: Optional[str], year: int, month: int) -> Dict[str, Any]:
        """该月持仓电量（MWh），来自合约分解曲线。"""
        start, end = self._month_bounds(year, month)
        q: Dict[str, Any] = {"status": "active"}
        if customer_id:
            q["customer_id"] = customer_id
        total = 0.0
        hit = 0
        for cv in self.db["contract_curves"].find(q, {"daily_contracts": 1, "_id": 0}):
            for dc in cv.get("daily_contracts") or []:
                date_str = dc.get("date") or ""
                if not date_str.startswith("%04d-%02d" % (year, month)):
                    continue
                pts = dc.get("points") or []
                if len(pts) != 96:
                    continue
                total += sum(float(p or 0.0) for p in pts)
                hit += 1
        return {"mwh": round(total, 4), "source": "contract_curves" if hit else None, "days": hit}

    # ----------------------------- 价格 -----------------------------
    def _spot_avg(self, year: int, month: int) -> Dict[str, Any]:
        """该月日前现货均价（元/MWh）。"""
        prefix = "%04d-%02d" % (year, month)
        vals: List[float] = []
        for d in self.db["day_ahead_spot_price"].find(
            {"date_str": {"$regex": "^" + prefix}, "avg_clearing_price": {"$ne": None}},
            {"avg_clearing_price": 1, "_id": 0},
        ):
            v = d.get("avg_clearing_price")
            if v is not None:
                vals.append(float(v))
        if not vals:
            return {"price": None, "points": 0}
        return {"price": round(sum(vals) / len(vals), 3), "points": len(vals)}

    def _contracts(self, customer_id: Optional[str], year: int, month: int) -> Dict[str, Any]:
        """该月中长期合约成本（MWh / 元）。复用合约分解的月分摊口径。"""
        from webapp.services.contract_decompose_service import ContractDecomposeService

        start, end = self._month_bounds(year, month)
        q: Dict[str, Any] = {
            "purchase_start_month": {"$lte": end},
            "purchase_end_month": {"$gte": start},
        }
        if customer_id:
            q["customer_id"] = customer_id
        svc = ContractDecomposeService(self.db)
        mwh = 0.0
        amount = 0.0
        cnt = 0
        for c in self.db["retail_contracts"].find(q):
            if (c.get("status") or "active") not in ("pending", "active"):
                continue
            v = svc._contract_month_volume(c, year, month)
            if v <= 0:
                continue
            p = svc._contract_price(c)
            mwh += v
            amount += v * p
            cnt += 1
        return {
            "mwh": round(mwh, 4),
            "amount": round(amount, 2),
            "avg_price": round(amount / mwh, 3) if mwh > 0 else None,
            "count": cnt,
        }

    # ----------------------------- 主流程 -----------------------------
    def compute(
        self,
        month: str,
        customer_id: Optional[str] = None,
        share: Optional[Dict[str, float]] = None,
        persist: bool = True,
    ) -> Dict[str, Any]:
        """计算某月综合购电成本基线。

        month: 'YYYY-MM'
        share: {cost_compensation, imbalance, market_adjust} 元/MWh；默认 0（不臆造）
        """
        try:
            year, mon = int(month[:4]), int(month[5:7])
        except Exception:
            raise ValueError("month 格式应为 YYYY-MM")

        warnings: List[str] = []
        share = share or {}
        cc = float(share.get("cost_compensation") or 0.0)
        imb = float(share.get("imbalance") or 0.0)
        ma = float(share.get("market_adjust") or 0.0)
        share_unit = cc + imb + ma

        load = self._load_mwh(customer_id, year, mon)
        position = self._position_mwh(customer_id, year, mon)
        spot = self._spot_avg(year, mon)
        contracts = self._contracts(customer_id, year, mon)

        total_mwh = load["mwh"]
        if total_mwh <= 0:
            warnings.append("该月无负荷/核查联数据，无法计算成本基线")
        if load["source"] is None:
            warnings.append("负荷数据缺失：请先导入 96 点负荷（M8）或核查联（M9）")
        if position["mwh"] <= 0:
            warnings.append("无合约分解曲线：持仓视为 0，敞口=全部负荷（建议先做合约分解 M6）")
        if spot["price"] is None:
            warnings.append("该月无日前现货价：现货采购成本未计入（请导入现货价 M10）")
        if contracts["count"] == 0:
            warnings.append("该月无有效中长期合约：合约成本为 0（请补 retail_contracts）")

        # 敞口
        exposure = max(total_mwh - position["mwh"], 0.0)
        # 现货成本（仅敞口部分）
        spot_cost = round(exposure * spot["price"], 2) if (spot["price"] is not None and exposure > 0) else 0.0
        # 分摊成本（按总电量）
        share_cost = round(total_mwh * share_unit, 2)

        contract_cost = contracts["amount"]
        total_cost = round(contract_cost + spot_cost + share_cost, 2)
        unit_cost = round(total_cost / total_mwh, 3) if total_mwh > 0 else None

        components = [
            {"name": "中长期合约", "mwh": contracts["mwh"], "price": contracts["avg_price"],
             "amount": contract_cost, "source": "retail_contracts"},
            {"name": "现货采购", "mwh": round(exposure, 4), "price": spot["price"],
             "amount": spot_cost, "source": "day_ahead_spot_price"},
            {"name": "三类分摊", "mwh": total_mwh, "price": round(share_unit, 3),
             "amount": share_cost, "source": "params"},
        ]

        coverage_ratio = round(position["mwh"] / total_mwh, 4) if total_mwh > 0 else None
        if coverage_ratio is not None and coverage_ratio < 0.7:
            warnings.append("持仓覆盖率 %.1f%% 低于考核线 70%%" % (coverage_ratio * 100))
        if coverage_ratio is not None and coverage_ratio > 1.0:
            surplus = round(position["mwh"] - total_mwh, 4)
            warnings.append(
                "持仓超配 %.1f%%（余量 %.1f MWh 可售）：当前成本基线未计入售电收益，"
                "成本单价会偏高，实际毛利应另加余量售电收入" % ((coverage_ratio - 1) * 100, surplus)
            )

        result = {
            "month": month,
            "customer_id": customer_id,
            "total_mwh": total_mwh,
            "position_mwh": position["mwh"],
            "exposure_mwh": round(exposure, 4),
            "coverage_ratio": coverage_ratio,
            "contract_cost": contract_cost,
            "spot_cost": spot_cost,
            "share_cost": share_cost,
            "total_cost": total_cost,
            "unit_cost": unit_cost,
            "components": components,
            "spot_price_basis": spot["price"],
            "share_params": {"cost_compensation": cc, "imbalance": imb, "market_adjust": ma},
            "sources": {
                "load": load["source"], "position": position["source"],
                "spot": "day_ahead_spot_price" if spot["price"] is not None else None,
                "contracts": contracts["count"],
            },
            "warnings": warnings,
            "computed_at": datetime.utcnow(),
        }

        if persist:
            key = {"month": month, "customer_id": customer_id}
            self.collection.replace_one(key, dict(result, **key), upsert=True)
            try:
                self.collection.create_index([("month", 1), ("customer_id", 1)], unique=True)
            except Exception:
                pass
        return result

    def get(self, month: str, customer_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """读取已计算的成本基线。"""
        doc = self.collection.find_one({"month": month, "customer_id": customer_id}, {"_id": 0})
        return doc

    def _flat_base_price(self, year: int, month: int) -> Optional[float]:
        """该月【平段】现货均价（元/MWh），用于分时定价的平段基准。"""
        try:
            from webapp.services.tou_service import get_tou_rule_by_date
            tou = get_tou_rule_by_date(datetime(year, month, 1))
        except Exception:
            return None
        flat_times = {t for t, seg in (tou or {}).items() if "平" in str(seg)}
        if not flat_times:
            return None
        prefix = "%04d-%02d" % (year, month)
        vals: List[float] = []
        for d in self.db["day_ahead_spot_price"].find(
            {"date_str": {"$regex": "^" + prefix}, "avg_clearing_price": {"$ne": None}},
            {"time_str": 1, "avg_clearing_price": 1, "_id": 0},
        ):
            if d.get("time_str") in flat_times:
                v = d.get("avg_clearing_price")
                if v is not None:
                    vals.append(float(v))
        if not vals:
            return None
        return round(sum(vals) / len(vals), 3)

    def as_market(
        self, month: str, customer_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """把成本基线转换成可直接喂给套餐测算的 market 参数（P4 打通点）。

        口径要点：
          wholesale_price（模板 T4）= (合约成本 + 现货成本) / 总电量
              —— **不含分摊**，因为引擎封顶价公式里分摊是单独加的：
                 封顶价 = 参考价 + 分摊合计 + (T4 − 分摊合计) × F
                 若 T4 已含分摊会重复计算。
          share_* = 成本基线用的分摊参数，原样传给引擎。
          flat_base_price = 该月平段现货均价（用于三段聚合模式）。

        返回 None 值表示该字段无数据，调用方应保留原值。
        """
        try:
            year, mon = int(month[:4]), int(month[5:7])
        except Exception:
            raise ValueError("month 格式应为 YYYY-MM")

        doc = self.get(month, customer_id)
        if doc is None:
            doc = self.compute(month, customer_id, persist=False)

        total = float(doc.get("total_mwh") or 0.0)
        wholesale = None
        if total > 0:
            wholesale = round(
                (float(doc.get("contract_cost") or 0.0) + float(doc.get("spot_cost") or 0.0)) / total, 3
            )
        share = doc.get("share_params") or {}
        return {
            "wholesale_price": wholesale,
            "flat_base_price": self._flat_base_price(year, mon),
            "reference_price": None,   # 让引擎用逐点 max 计算，不覆盖
            "share_cost_compensation": share.get("cost_compensation"),
            "share_imbalance": share.get("imbalance"),
            "share_market_adjust": share.get("market_adjust"),
            "market_source": "cost_basis",
            "unit_cost": doc.get("unit_cost"),
            "coverage_ratio": doc.get("coverage_ratio"),
            "warnings": doc.get("warnings") or [],
        }

    def list_months(self, limit: int = 24) -> List[Dict[str, Any]]:
        """最近若干月的成本基线概览。"""
        rows = []
        for d in self.collection.find({}, {"_id": 0}).sort("month", -1).limit(limit):
            rows.append({
                "month": d.get("month"),
                "customer_id": d.get("customer_id"),
                "total_mwh": d.get("total_mwh"),
                "unit_cost": d.get("unit_cost"),
                "coverage_ratio": d.get("coverage_ratio"),
                "computed_at": d.get("computed_at"),
            })
        return rows
