"""零售套餐测算服务（江苏 2027 新规口径）。

两条数据源，最终都调用 PricingEngine.calculate_jiangsu_2027：
  A. 历史负荷曲线：user_load_data（96点, value=kW）× tou_rules（峰平谷时段）→ 分时电量
  B. 核查联：供电公司电费核查联单结构化数据 → 分时电量 + 现状电费

说明：user_load_data.value 是 15 分钟平均功率(kW)，电量 = value × 0.25h ÷ 1000 = MWh。
"""
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pymongo.database import Database

from webapp.services.pricing_engine import PricingEngine
from webapp.services.tou_service import get_tou_rule_by_date

logger = logging.getLogger(__name__)

HOURS_PER_POINT = 0.25  # 15 分钟
DEFAULT_RATIO = {"peak": 0.15, "flat": 0.40, "valley": 0.45}

# 代购电峰谷浮动系数（目录电价口径，按用电类型三档）
# 对齐《套餐测算模板-新v2.xlsx》代购电情况!C8：
#   两部制 峰1.8/平1.0/谷0.35；单一制-100kVA及以上 峰1.7；以下 峰1.6
SGCC_TOU_COEFFICIENTS = {
    "两部制": {"峰": 1.8, "平": 1.0, "谷": 0.35},
    "单一制-100千伏安及以上": {"峰": 1.7, "平": 1.0, "谷": 0.35},
    "单一制-100千伏安以下": {"峰": 1.6, "平": 1.0, "谷": 0.35},
}
DEFAULT_KTYPE = "单一制-100千伏安以下"
# 中长期持仓考核线（不足则提示）
HOLDING_ASSESS_LINE = 0.70

# 绿电类合同块：零售参考价 max 口径不纳入（对齐 Excel 峰谷时段表!B116 只取 年度/月度竞价/能量块）
GREEN_CONTRACT_TYPES = {
    "年度绿电", "月度绿电", "月内绿电", "上旬", "中旬", "下旬",
    "第二次月内绿电", "小时级绿电", "月内小时级绿电",
}


class PackageCalcService:
    """零售套餐测算服务。"""

    def __init__(self, db: Database) -> None:
        self.db = db
        self._spot_cache: Dict[tuple, Dict[str, float]] = {}

    # ----------------------------- 参数提取 -----------------------------
    @staticmethod
    def _package_params(package: dict, overrides: Optional[dict] = None) -> Dict[str, Any]:
        """从套餐 pricing_config 提取测算参数，允许请求覆盖。"""
        cfg = (package or {}).get("pricing_config") or {}
        params: Dict[str, Any] = {
            "peak_coef": cfg.get("peak_coef", cfg.get("peakup", 1.6)),
            "valley_coef": cfg.get("valley_coef", cfg.get("valdown", 0.4)),
            "service_fee": cfg.get("service_fee"),
            "kp": cfg.get("kp", cfg.get("float_price", 0.002)),
            "f_ratio": cfg.get("f_ratio", cfg.get("f", 0.05)),
            "k1_share": cfg.get("k1_share", 1.0),
            "k2_share": cfg.get("k2_share", 1.0),
            "k3_share": cfg.get("k3_share", 1.0),
            "include_share_in_base": cfg.get("include_share_in_base", True),
            "green_mode": cfg.get("green_mode", "否"),
            "env_value": cfg.get("env_value", cfg.get("green_price", 30.0)),
        }
        if overrides:
            params.update({k: v for k, v in overrides.items() if v is not None})
        return params

    # ---------------------- 国网代购电价（基础数据菜单） ----------------------
    def _sgcc_for_period(self, period: str) -> Optional[Dict[str, Any]]:
        """从 price_sgcc 集合读取该月国网代购电价（基础数据→国网代购电价格菜单）。

        返回 {purchase_price, avg_on_grid_price}（元/MWh），无数据返回 None。
        """
        try:
            doc = self.db.price_sgcc.find_one(
                {"_id": period},
                {"purchase_price": 1, "avg_on_grid_price": 1, "month": 1, "source": 1},
            )
        except Exception as e:
            logger.warning("读取 price_sgcc 失败: %s", e)
            return None
        if not doc:
            return None
        return {
            "purchase_price": float(doc.get("purchase_price") or 0.0),
            "avg_on_grid_price": float(doc.get("avg_on_grid_price") or 0.0),
            "source": doc.get("source"),
        }

    @staticmethod
    def _sgcc_coef(ktype: Optional[str]) -> Dict[str, float]:
        """按用电类型取代购电峰谷系数，未匹配则用默认档（单一制-100千伏安以下）。"""
        k = str(ktype or "").strip()
        for key, coef in SGCC_TOU_COEFFICIENTS.items():
            if key in k:
                return coef
        return SGCC_TOU_COEFFICIENTS[DEFAULT_KTYPE]

    def _sgcc_tou(self, sgcc: Optional[dict], ktype: Optional[str], volumes: Dict[str, float]) -> Optional[Dict[str, Any]]:
        """按用电类型系数把代购电价格展开为分时价，并按峰平谷电量加权得代购电加权均价。

        Excel 口径（代购电情况!C8）：代购电分时价 = 系数 × 代购电价格(purchase_price)。
        返回 {ktype_coef, purchase_price, peak/flat/valley_price, weighted_price}。
        """
        if not sgcc:
            return None
        pp = float(sgcc.get("purchase_price") or 0.0)  # 元/MWh（与 Excel 0.3937 元/kWh 一致）
        coef = self._sgcc_coef(ktype)
        prices = {"peak": round(pp * coef["峰"], 3),
                  "flat": round(pp * coef["平"], 3),
                  "valley": round(pp * coef["谷"], 3)}
        qp = float(volumes.get("peak_mwh") or 0.0)
        qf = float(volumes.get("flat_mwh") or 0.0)
        qv = float(volumes.get("valley_mwh") or 0.0)
        tot = qp + qf + qv
        weighted = round((qp * prices["peak"] + qf * prices["flat"] + qv * prices["valley"]) / tot, 3) if tot > 0 else None
        return {
            "ktype": self._norm_ktype(ktype),
            "ktype_coef": coef,
            "purchase_price": round(pp, 3),
            "peak_price": prices["peak"],
            "flat_price": prices["flat"],
            "valley_price": prices["valley"],
            "weighted_price": weighted,
        }

    @staticmethod
    def _norm_ktype(ktype: Optional[str]) -> str:
        k = str(ktype or "").strip()
        for key in SGCC_TOU_COEFFICIENTS:
            if key in k:
                return key
        return DEFAULT_KTYPE

    def _ktype_of(self, customer_id: Optional[str]) -> Optional[str]:
        """从客户档案读取用电类型（当前数据可能为空，返回 None 走默认档）。"""
        if not customer_id:
            return None
        try:
            from bson import ObjectId
            doc = self.db["customers"].find_one({"_id": ObjectId(customer_id)},
                                                {"electricity_type": 1, "user_type": 1})
        except Exception:
            return None
        return (doc or {}).get("electricity_type") or (doc or {}).get("user_type")

    def _attach_sgcc(self, result: Dict[str, Any], period: str, ktype: Optional[str] = None) -> Dict[str, Any]:
        """把国网代购电价挂到测算结果，并按用电类型系数做分时价与"套餐 vs 代购"对比。"""
        sgcc = self._sgcc_for_period(period)
        if not sgcc:
            result["sgcc"] = None
            result["sgcc_warning"] = "该月无国网代购电价数据（基础数据→国网代购电价格）"
            return result
        result["sgcc"] = sgcc
        # 代购电分时价（按用电类型三档系数 × 代购电价格，按峰平谷电量加权）
        volumes = result.get("volumes") or {}
        result["sgcc_tou"] = self._sgcc_tou(sgcc, ktype, volumes)
        avg = sgcc["avg_on_grid_price"]
        if avg > 0:
            sell = float(result.get("sell_price") or 0.0)
            diff = round(sell - avg, 3)
            result["vs_sgcc"] = {
                "sgcc_price": round(avg, 3),
                "package_price": round(sell, 3),
                "diff": diff,
                "saving_rate": round(diff / avg, 4),
                "verdict": "套餐更省" if diff < 0 else ("套餐更贵" if diff > 0 else "持平"),
            }
        return result

    # -------------------- 路径A：历史负荷 → 峰平谷电量 --------------------
    def _aggregate_load_by_tou(self, customer_id: str, period: str) -> Dict[str, float]:
        """按 tou_rules 把 96 点负荷聚合成峰/平/谷电量（MWh）。"""
        start = datetime.strptime(period, "%Y-%m").replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        cursor = self.db.user_load_data.find(
            {"customer_id": customer_id, "timestamp": {"$gt": start, "$lte": end}},
            {"timestamp": 1, "value": 1, "_id": 0},
        )
        out = {"peak_mwh": 0.0, "flat_mwh": 0.0, "valley_mwh": 0.0}
        tou_cache: Dict[str, Dict[str, str]] = {}
        for d in cursor:
            ts = d.get("timestamp")
            val = d.get("value")
            if ts is None or val is None:
                continue
            # 24:00 点（存为次日 00:00）归到前一业务日，时段取 23:45
            is_midnight = ts.hour == 0 and ts.minute == 0
            biz = ts - timedelta(days=1) if is_midnight else ts
            day_key = biz.strftime("%Y-%m-%d")
            if day_key not in tou_cache:
                tou_cache[day_key] = get_tou_rule_by_date(biz)
            time_str = "23:45" if is_midnight else ts.strftime("%H:%M")
            seg = tou_cache[day_key].get(time_str, "平段")
            mwh = float(val) * HOURS_PER_POINT / 1000.0
            if "峰" in seg:
                out["peak_mwh"] += mwh
            elif "谷" in seg:
                out["valley_mwh"] += mwh
            else:
                out["flat_mwh"] += mwh
        return out

    # ------------------ 批发分时价合成（模板 分时!B31） ------------------
    @staticmethod
    def _ts_key(ts) -> Optional[str]:
        """把 timestamp（datetime 或字符串）归一化为 'YYYY-MM-DD HH:MM'。"""
        if ts is None:
            return None
        if isinstance(ts, str):
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%dT%H:%M:%S"):
                try:
                    return datetime.strptime(ts, fmt).strftime("%Y-%m-%d %H:%M")
                except ValueError:
                    continue
            return None
        try:
            return ts.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return None

    def _spot_map(self, collection: str, period: str) -> Dict[str, float]:
        """读取某月 96 点现货价：key='YYYY-MM-DD HH:MM' -> 元/MWh（带进程内缓存）。"""
        ck = (collection, period)
        if ck in self._spot_cache:
            return self._spot_cache[ck]
        m: Dict[str, float] = {}
        try:
            cursor = self.db[collection].find(
                {"date_str": {"$regex": "^" + period}},
                {"timestamp": 1, "avg_clearing_price": 1, "value": 1},
            )
        except Exception as e:
            logger.warning("读取 %s 失败: %s", collection, e)
            return m
        for d in cursor:
            k = self._ts_key(d.get("timestamp"))
            pr = d.get("avg_clearing_price")
            if pr is None:
                pr = d.get("value")
            if k and pr is not None:
                m[k] = float(pr)
        self._spot_cache[ck] = m
        return m

    def _aggregate_load_with_prices(
        self,
        customer_id: str,
        period: str,
        holding_ratio: float = 0.9,
        k2_ratio: float = 0.05,
        mid_long_price: Optional[float] = None,
    ) -> Dict[str, Any]:
        """聚合峰平谷电量，并用日前/实时/中长期合成批发分时价。

        合成公式（模板 分时!B31）：
          批发分时价 = (持仓 − K2)×中长期价 + (1 − 持仓)×日前价 + K2×实时价
        中长期价缺省用日前均价兜底。
        """
        start = datetime.strptime(period, "%Y-%m").replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        da = self._spot_map("day_ahead_spot_price", period)
        rt = self._spot_map("real_time_spot_price", period)
        if mid_long_price is None:
            mid_long_price = (sum(da.values()) / len(da)) if da else 0.0
        mid = float(mid_long_price)

        out: Dict[str, Any] = {
            "peak_mwh": 0.0, "flat_mwh": 0.0, "valley_mwh": 0.0,
            "_flat_cost": 0.0, "_total_cost": 0.0, "_matched": 0, "_unmatched": 0,
        }
        tou_cache: Dict[str, Dict[str, str]] = {}
        for d in self.db.user_load_data.find(
            {"customer_id": customer_id, "timestamp": {"$gt": start, "$lte": end}},
            {"timestamp": 1, "value": 1, "_id": 0},
        ):
            ts = d.get("timestamp")
            val = d.get("value")
            if ts is None or val is None:
                continue
            is_midnight = getattr(ts, "hour", None) == 0 and getattr(ts, "minute", None) == 0
            biz = ts - timedelta(days=1) if is_midnight else ts
            day_key = biz.strftime("%Y-%m-%d") if hasattr(biz, "strftime") else str(biz)
            if day_key not in tou_cache:
                tou_cache[day_key] = get_tou_rule_by_date(biz)
            time_str = "23:45" if is_midnight else ts.strftime("%H:%M")
            seg = tou_cache[day_key].get(time_str, "平段")

            key = self._ts_key(ts)
            da_p = da.get(key)
            rt_p = rt.get(key)
            if da_p is None and rt_p is None:
                out["_unmatched"] += 1
                price = mid
            else:
                out["_matched"] += 1
                if da_p is None:
                    da_p = rt_p
                if rt_p is None:
                    rt_p = da_p
                price = (holding_ratio - k2_ratio) * mid + (1 - holding_ratio) * da_p + k2_ratio * rt_p

            mwh = float(val) * HOURS_PER_POINT / 1000.0
            if "峰" in seg:
                out["peak_mwh"] += mwh
            elif "谷" in seg:
                out["valley_mwh"] += mwh
            else:
                out["flat_mwh"] += mwh
                out["_flat_cost"] += mwh * price
            out["_total_cost"] += mwh * price

        total = out["peak_mwh"] + out["flat_mwh"] + out["valley_mwh"]
        out["flat_base_price"] = (out["_flat_cost"] / out["flat_mwh"]) if out["flat_mwh"] > 0 else 0.0
        out["wholesale_price"] = (out["_total_cost"] / total) if total > 0 else 0.0
        out["mid_long_price"] = round(mid, 3)
        out["holding_ratio"] = holding_ratio
        out["k2_ratio"] = k2_ratio
        out["day_ahead_avg"] = round((sum(da.values()) / len(da)), 3) if da else 0.0
        out["real_time_avg"] = round((sum(rt.values()) / len(rt)), 3) if rt else 0.0
        return out

    def _mid_long_price_series(
        self, year: int, month: int, customer_id: Optional[str] = None
    ) -> Optional[List[float]]:
        """按 12 合同块量价，计算该月 24 时段的逐点中长期价（对齐 Excel 分时!B142）。

        公式：点t中长期价 = Σ_合同块(该块t时段电量 × 该块t时段价) / Σ_合同块(该块t时段电量)
        年度类合同价格全部时段取同价（Excel 用 $Q$2/$Q$32 绝对引用，导入时已固化为同一价）。

        客户级优先：先找该 customer_id 的专属合同；无则回退到全市场统一合同（customer_id 为空）。
        两种情况都无数据返回 None（引擎回退到月度均价兜底）。
        """
        def _query(cid):
            q = {"month": month}
            if cid:
                q["customer_id"] = cid
            else:
                q["customer_id"] = None
            try:
                cur = self.db["mid_long_contracts"].find(
                    q, {"contract_type": 1, "time_index": 1, "volume_mwh": 1, "price": 1, "_id": 0}
                )
                return list(cur)
            except Exception:
                return []

        rows = []
        # 1) 客户级专属
        if customer_id:
            rows = [r for r in _query(customer_id) if r.get("year") in (None, year)]
        # 2) 回退全市场统一
        if not rows:
            rows = [r for r in _query(None) if r.get("year") in (None, year)]
        # 3) 兜底：任何该月数据（含 year/客户字段缺省的老数据）
        if not rows:
            try:
                cur = self.db["mid_long_contracts"].find(
                    {"month": month}, {"contract_type": 1, "time_index": 1, "volume_mwh": 1, "price": 1, "year": 1, "_id": 0}
                )
                rows = [r for r in cur if r.get("year") in (None, year)]
            except Exception:
                rows = []
        if not rows:
            return None

        agg = [{"num": 0.0, "den": 0.0} for _ in range(24)]
        for r in rows:
            t = int(r.get("time_index") or 0)
            if t < 0 or t > 23:
                continue
            v = float(r.get("volume_mwh") or 0.0)
            pr = float(r.get("price") or 0.0)
            agg[t]["num"] += v * pr
            agg[t]["den"] += v
        series: List[float] = []
        has_any = False
        for t in range(24):
            if agg[t]["den"] > 0:
                series.append(round(agg[t]["num"] / agg[t]["den"], 3))
                has_any = True
            else:
                series.append(0.0)
        return series if has_any else None

    def _mid_long_volume_series(self, year: int, month: int, customer_id: Optional[str] = None) -> Optional[List[float]]:
        """逐点中长期成交量（MWh）：各合同块在某时段的电量合计。

        对齐 Excel 分时!B87（中长期成交量）：
            B87 = Σ_合同块 该块 t 时段电量（含月度竞价按结算比例的折算）
        简化实现：直接对各合同块该时段电量求和（合同量价表已是月度分摊后口径）。
        返回 24 点列表；无合同数据返回 None。
        """
        def _query(cid):
            q = {"month": month, "customer_id": cid if cid else None}
            try:
                return list(self.db["mid_long_contracts"].find(
                    q, {"time_index": 1, "volume_mwh": 1, "year": 1, "_id": 0}))
            except Exception:
                return []

        rows = []
        if customer_id:
            rows = [r for r in _query(customer_id) if r.get("year") in (None, year)]
        if not rows:
            rows = [r for r in _query(None) if r.get("year") in (None, year)]
        if not rows:
            return None

        vol = [0.0] * 24
        has = False
        for r in rows:
            t = int(r.get("time_index") or 0)
            if t < 0 or t > 23:
                continue
            v = float(r.get("volume_mwh") or 0.0)
            vol[t] += v
            if v > 0:
                has = True
        return vol if has else None

    def _holding_curve_series(
        self,
        year: int,
        month: int,
        total_mwh: Optional[float] = None,
        customer_id: Optional[str] = None,
        shares: Optional[List[float]] = None,
    ) -> Optional[List[float]]:
        """逐点持仓曲线（严格对齐 Excel 分时!B115「市场中长期持仓曲线」）。

        Excel 公式：
            B115 = 中长期成交量[t] / (该月总用电量 × 该时段负荷占比[t])
        已验证：15.2513 / (455.21 × 0.0415) = 0.8073 ✓

        参数：
          total_mwh  该月总用电量（MWh）。优先用调用方传入（核查联账单的 total_mwh，
                     即 Excel 的「零售用户结算电量 + 一类用户结算电量」）；未给则取合同总量。
          shares     24 时段负荷占比（合计=1）。未给则按 TOU 峰/平/谷时段等分还原。
        返回 24 点持仓比例；缺数据返回 None（调用方回退标量）。
        """
        vols = self._mid_long_volume_series(year, month, customer_id)
        if not vols:
            return None
        total_vol = sum(vols)
        if total_vol <= 0:
            return None

        base_mwh = float(total_mwh) if (total_mwh and total_mwh > 0) else total_vol
        if base_mwh <= 0:
            return None

        share = shares if (shares and len(shares) == 24) else self._month_shares(year, month)
        if not share:
            return None

        # ---- 量纲/量级合理性守卫 ----
        # 合同量价表可能与当前账单口径不同（如模板样本 455MWh vs 真实企业 3986MWh）。
        # 若合同总量与结算电量的比值落在合理持仓区间外（<30% 或 >150%），
        # 说明两者不是同一口径，逐点持仓不可信 -> 返回 None 由调用方回退标量。
        implied_total_holding = total_vol / base_mwh
        if implied_total_holding < 0.30 or implied_total_holding > 1.50:
            logger.info(
                "逐点持仓跳过：合同总量 %.1f MWh 与结算电量 %.1f MWh 不同量纲（隐含持仓 %.1f%%）",
                total_vol, base_mwh, implied_total_holding * 100,
            )
            return None

        curve: List[float] = []
        for t in range(24):
            settle_t = base_mwh * share[t]
            if settle_t <= 0:
                curve.append(0.0)
                continue
            # 不做 max(1.0) 截断——持仓 >100% 是真实业务状态（超配），如实反映
            curve.append(round(vols[t] / settle_t, 6))
        if not any(c > 0 for c in curve):
            return None
        return curve

    def _month_shares(self, year: int, month: int) -> Optional[List[float]]:
        """24 时段负荷占比（合计=1）。

        优先用该月真实负荷数据（user_load_data）；无则按 TOU 峰/平/谷时段等分还原。
        """
        try:
            start = datetime(year, month, 1)
            end = (start + timedelta(days=32)).replace(day=1)
            agg = list(self.db["user_load_data"].aggregate([
                {"$match": {"timestamp": {"$gte": start, "$lt": end}}},
                {"$group": {"_id": {"$hour": "$timestamp"}, "v": {"$sum": "$value"}}},
            ]))
        except Exception:
            agg = []
        buckets: Dict[int, float] = {}
        for a in agg:
            h = a.get("_id")
            if h is None:
                continue
            h = int(h)
            if 0 <= h <= 23:
                buckets[h] = buckets.get(h, 0.0) + float(a.get("v") or 0.0)
        total = sum(buckets.values())
        if total > 0:
            return [buckets.get(h, 0.0) / total for h in range(24)]

        # 兜底：按 TOU 时段等分（峰/平/谷各自的时段均摊）
        try:
            tou = get_tou_rule_by_date(start)
        except Exception:
            return None
        labels: List[str] = []
        for h in range(24):
            seg = tou.get("%02d:00" % h) or tou.get("%02d:15" % h) or "平段"
            labels.append("峰" if "峰" in seg else ("谷" if "谷" in seg else "平"))
        # 用 DEFAULT_RATIO 作为峰平谷电量占比，段内等分
        seg_share = {"峰": DEFAULT_RATIO["peak"], "平": DEFAULT_RATIO["flat"], "谷": DEFAULT_RATIO["valley"]}
        cnt = {k: labels.count(k) for k in ("峰", "平", "谷")}
        out = []
        for lab in labels:
            n = cnt.get(lab) or 1
            out.append(seg_share.get(lab, 0.0) / n)
        tot = sum(out)
        if tot <= 0:
            return None
        return [x / tot for x in out]

    def _mid_long_ref_series(
        self, year: int, month: int, customer_id: Optional[str] = None
    ) -> Optional[List[float]]:
        """零售参考价的逐点序列：每个时段取【各非绿电合同块价格的最大值】。

        对齐 Excel《套餐测算模板-新v2》峰谷时段表!B116：
            B116 = MAX(日前, 实时, 年度价, 月度竞价价, 能量块价)  ← 只取非绿电合同块
        返回 24 点列表；无合同数据返回 None。
        """
        def _query(cid):
            q = {"month": month}
            q["customer_id"] = cid if cid else None
            try:
                return list(self.db["mid_long_contracts"].find(
                    q, {"contract_type": 1, "time_index": 1, "price": 1, "year": 1, "_id": 0}))
            except Exception:
                return []

        rows = []
        if customer_id:
            rows = [r for r in _query(customer_id) if r.get("year") in (None, year)]
        if not rows:
            rows = [r for r in _query(None) if r.get("year") in (None, year)]
        if not rows:
            return None

        mx = [0.0] * 24
        has = False
        for r in rows:
            ct = r.get("contract_type") or ""
            if ct in GREEN_CONTRACT_TYPES:
                continue
            t = int(r.get("time_index") or 0)
            if t < 0 or t > 23:
                continue
            pr = float(r.get("price") or 0.0)
            if pr > mx[t]:
                mx[t] = pr
            if pr > 0:
                has = True
        return mx if has else None

    def _load_points_with_prices(
        self,
        customer_id: str,
        period: str,
        holding_ratio: float = 0.9,
        k2_ratio: float = 0.05,
        mid_long_price: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """逐点聚合：保留每个 96 点时刻的时段标签/电量/批发分时价/参考价序列。

        与 _aggregate_load_with_prices 的区别：不把电量压成峰平谷三个总量，而是返回
        逐点序列，供 PricingEngine.calculate_jiangsu_2027_pointwise 做逐点卷积计价
        （对齐模板 峰谷时段表/分时）。

        返回：{peak_mwh, flat_mwh, valley_mwh, total_mwh,
               labels[], curve[], wholesale[], max_pnt[],
               flat_base_price, wholesale_price, mid_long_price, holding_ratio, k2_ratio,
               day_ahead_avg, real_time_avg, matched, unmatched}
        无负荷数据返回 None。
        """
        start = datetime.strptime(period, "%Y-%m").replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        da = self._spot_map("day_ahead_spot_price", period)
        rt = self._spot_map("real_time_spot_price", period)
        if mid_long_price is None:
            mid_long_price = (sum(da.values()) / len(da)) if da else 0.0
        mid = float(mid_long_price)
        # 逐点中长期价（来自合同量价，对齐 Excel 分时!B142）；无数据则为 None -> 回退标量 mid
        try:
            _y, _m = int(period[:4]), int(period[5:7])
        except Exception:
            _y, _m = 0, 0
        mid_series = self._mid_long_price_series(_y, _m, customer_id) if _y and _m else None
        ref_series = self._mid_long_ref_series(_y, _m, customer_id) if _y and _m else None
        # 负荷路径：时段占比直接用该月真实负荷（user_load_data 小时分布）
        hold_series = self._holding_curve_series(
            _y, _m, total_mwh=None, customer_id=customer_id
        ) if _y and _m else None

        labels: List[str] = []
        curve: List[float] = []
        wholesale: List[float] = []
        max_pnt: List[float] = []
        peak_mwh = flat_mwh = valley_mwh = 0.0
        flat_cost = 0.0
        total_cost = 0.0
        matched = unmatched = 0
        tou_cache: Dict[str, Dict[str, str]] = {}

        for d in self.db.user_load_data.find(
            {"customer_id": customer_id, "timestamp": {"$gt": start, "$lte": end}},
            {"timestamp": 1, "value": 1, "_id": 0},
        ):
            ts = d.get("timestamp")
            val = d.get("value")
            if ts is None or val is None:
                continue
            is_midnight = getattr(ts, "hour", None) == 0 and getattr(ts, "minute", None) == 0
            biz = ts - timedelta(days=1) if is_midnight else ts
            day_key = biz.strftime("%Y-%m-%d") if hasattr(biz, "strftime") else str(biz)
            if day_key not in tou_cache:
                tou_cache[day_key] = get_tou_rule_by_date(biz)
            time_str = "23:45" if is_midnight else ts.strftime("%H:%M")
            tou_seg = tou_cache[day_key].get(time_str, "平段")

            key = self._ts_key(ts)
            da_p = da.get(key)
            rt_p = rt.get(key)
            # 该点所属 24 时段序号（00:00 点归属前一日 23:45 时段）
            tp_idx = 23 if is_midnight else getattr(ts, "hour", 0)
            mid_t = mid_series[tp_idx] if (mid_series and 0 <= tp_idx < 24 and mid_series[tp_idx] > 0) else mid
            if da_p is None and rt_p is None:
                unmatched += 1
                price = mid_t
                ref = mid_t
            else:
                matched += 1
                if da_p is None:
                    da_p = rt_p
                if rt_p is None:
                    rt_p = da_p
                hold_t = hold_series[tp_idx] if (hold_series and 0 <= tp_idx < 24 and hold_series[tp_idx] > 0) else holding_ratio
                price = (hold_t - k2_ratio) * mid_t + (1 - hold_t) * da_p + k2_ratio * rt_p
                # 零售参考价 max(日前, 实时, 各非绿电合同块价)（模板 峰谷时段表!B116）
                ref_t = ref_series[tp_idx] if (ref_series and 0 <= tp_idx < 24 and ref_series[tp_idx] > 0) else mid_t
                ref = max(da_p, rt_p, ref_t)

            mwh = float(val) * HOURS_PER_POINT / 1000.0
            # 时段标签归一化为 峰/平/谷
            if "峰" in tou_seg:
                lab = "峰"
                peak_mwh += mwh
            elif "谷" in tou_seg:
                lab = "谷"
                valley_mwh += mwh
            else:
                lab = "平"
                flat_mwh += mwh
                flat_cost += mwh * price
            total_cost += mwh * price

            labels.append(lab)
            curve.append(mwh)
            wholesale.append(price)
            max_pnt.append(ref)

        total = peak_mwh + flat_mwh + valley_mwh
        if total <= 0 or not curve:
            return None

        return {
            "peak_mwh": round(peak_mwh, 4),
            "flat_mwh": round(flat_mwh, 4),
            "valley_mwh": round(valley_mwh, 4),
            "total_mwh": round(total, 4),
            "labels": labels,
            "curve": curve,
            "wholesale": wholesale,
            "max_pnt": max_pnt,
            "flat_base_price": round((flat_cost / flat_mwh) if flat_mwh > 0 else 0.0, 3),
            "wholesale_price": round((total_cost / total) if total > 0 else 0.0, 3),
            "mid_long_price": round(mid, 3),
            "mid_long_source": "contract_pointwise" if mid_series else "monthly_avg",
            "holding_source": "contract_pointwise" if hold_series else "scalar",
            "holding_curve": hold_series,
            "holding_ratio": holding_ratio,
            "k2_ratio": k2_ratio,
            "day_ahead_avg": round((sum(da.values()) / len(da)), 3) if da else 0.0,
            "real_time_avg": round((sum(rt.values()) / len(rt)), 3) if rt else 0.0,
            "matched": matched,
            "unmatched": unmatched,
        }

    @staticmethod
    def _hourly_avg(spot_map: Dict[str, float]) -> List[Optional[float]]:
        """把 96 点现货价按小时聚合成 24 点均值（用于核查联逐点化）。"""
        buckets: Dict[int, List[float]] = {h: [] for h in range(24)}
        for k, v in (spot_map or {}).items():
            if v is None:
                continue
            try:
                h = int(str(k)[11:13])
            except (ValueError, IndexError):
                continue
            if h == 24:
                h = 23
            if 0 <= h <= 23:
                buckets[h].append(float(v))
        return [(sum(buckets[h]) / len(buckets[h]) if buckets[h] else None) for h in range(24)]

    def _bill_points_with_prices(
        self,
        bill: dict,
        period: str,
        holding_ratio: float = 0.9,
        k2_ratio: float = 0.05,
        mid_long_price: Optional[float] = None,
        customer_id: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """核查联逐点化：把月度峰平谷电量按 TOU 规则摊回 24 时段，配现货/中长期价，供逐点引擎。

        核查联没有 96 点曲线，但有准确的峰/平/谷电量。做法：
          1) 用该月 1 号的 TOU 规则确定 24 时段各属 峰/平/谷；
          2) 把峰(平/谷)电量在其所属时段内均摊 -> 得到 24 点电量曲线（段合计与原账单严格一致）；
          3) 现货价按小时聚合成 24 点；中长期价/参考价取合同逐点序列；
          4) 合成逐点批发价 -> 进 calculate_jiangsu_2027_pointwise。

        无现货价数据时返回 None（调用方回退三段聚合）。
        """
        total = float(bill.get("total_mwh") or 0.0)
        if total <= 0:
            return None
        peak = bill.get("peak_mwh")
        flat = bill.get("flat_mwh")
        valley = bill.get("valley_mwh")
        if peak is None or flat is None or valley is None:
            peak = total * DEFAULT_RATIO["peak"]
            flat = total * DEFAULT_RATIO["flat"]
            valley = total * DEFAULT_RATIO["valley"]
        peak = float(peak)
        flat = float(flat)
        valley = float(valley)

        # 24 时段标签（用该月 1 号 TOU）
        try:
            start = datetime.strptime(period, "%Y-%m").replace(day=1)
        except Exception:
            return None
        tou = get_tou_rule_by_date(start)
        labels: List[str] = []
        for h in range(24):
            seg = tou.get("%02d:00" % h) or tou.get("%02d:15" % h) or "平段"
            if "峰" in seg:
                labels.append("峰")
            elif "谷" in seg:
                labels.append("谷")
            else:
                labels.append("平")
        n_peak = labels.count("峰")
        n_flat = labels.count("平")
        n_valley = labels.count("谷")
        if n_peak == 0 or n_flat == 0 or n_valley == 0:
            return None

        # 摊回 24 点电量
        curve: List[float] = []
        for lab in labels:
            if lab == "峰":
                curve.append(peak / n_peak)
            elif lab == "谷":
                curve.append(valley / n_valley)
            else:
                curve.append(flat / n_flat)

        # 现货价（小时均值）
        da_map = self._spot_map("day_ahead_spot_price", period)
        rt_map = self._spot_map("real_time_spot_price", period)
        if not da_map and not rt_map:
            return None
        da_h = self._hourly_avg(da_map)
        rt_h = self._hourly_avg(rt_map)

        # 中长期价 / 参考价逐点
        try:
            _y, _m = int(period[:4]), int(period[5:7])
        except Exception:
            _y, _m = 0, 0
        mid_series = self._mid_long_price_series(_y, _m, customer_id) if _y and _m else None
        ref_series = self._mid_long_ref_series(_y, _m, customer_id) if _y and _m else None
        # 逐点持仓曲线：分母用账单总用电量（= Excel 零售+一类用户结算电量）
        _curve_sum = sum(curve)
        _bill_shares = [c / _curve_sum for c in curve] if _curve_sum > 0 else None
        hold_series = self._holding_curve_series(
            _y, _m, total_mwh=total, customer_id=customer_id, shares=_bill_shares
        ) if _y and _m else None
        da_vals = [v for v in da_h if v is not None]
        mid = float(mid_long_price) if mid_long_price is not None else (sum(da_vals) / len(da_vals) if da_vals else 0.0)

        wholesale: List[float] = []
        max_pnt: List[float] = []
        for h in range(24):
            da_t = da_h[h] if da_h[h] is not None else (rt_h[h] if rt_h[h] is not None else mid)
            rt_t = rt_h[h] if rt_h[h] is not None else da_t
            mid_t = mid_series[h] if (mid_series and mid_series[h] > 0) else mid
            hold_t = hold_series[h] if (hold_series and hold_series[h] > 0) else holding_ratio
            wholesale.append(round((hold_t - k2_ratio) * mid_t + (1 - hold_t) * da_t + k2_ratio * rt_t, 4))
            ref_t = ref_series[h] if (ref_series and ref_series[h] > 0) else mid_t
            max_pnt.append(round(max(da_t, rt_t, ref_t), 4))

        flat_curve = sum(curve[h] for h in range(24) if labels[h] == "平")
        flat_cost = sum(curve[h] * wholesale[h] for h in range(24) if labels[h] == "平")
        total_curve = sum(curve)
        total_cost = sum(curve[h] * wholesale[h] for h in range(24))

        return {
            "peak_mwh": round(peak, 4),
            "flat_mwh": round(flat, 4),
            "valley_mwh": round(valley, 4),
            "total_mwh": round(total_curve, 4),
            "labels": labels,
            "curve": curve,
            "wholesale": wholesale,
            "max_pnt": max_pnt,
            "flat_base_price": round((flat_cost / flat_curve) if flat_curve > 0 else 0.0, 3),
            "wholesale_price": round((total_cost / total_curve) if total_curve > 0 else 0.0, 3),
            "mid_long_price": round(mid, 3),
            "mid_long_source": "contract_pointwise" if mid_series else "monthly_avg",
            "holding_source": "contract_pointwise" if hold_series else "scalar",
            "holding_curve": hold_series,
            "holding_ratio": holding_ratio,
            "k2_ratio": k2_ratio,
            "day_ahead_avg": round((sum(da_vals) / len(da_vals)), 3) if da_vals else 0.0,
            "real_time_avg": round(sum(v for v in rt_h if v is not None) / max(1, sum(1 for v in rt_h if v is not None)), 3) if rt_h else 0.0,
            "matched": 0,
            "unmatched": 0,
        }

    def _bill_points_for_month(
        self,
        customer_id: str,
        period: str,
        holding_ratio: float = 0.9,
        k2_ratio: float = 0.05,
        mid_long_price: Optional[float] = None,
    ) -> Optional[Dict[str, Any]]:
        """无 96 点负荷时，用该月【核查联】的月度峰平谷电量按 TOU 摊回 24 时段。

        供 calc_annual 在「无负荷曲线」时回退使用（方案 C）。
        返回与 _load_points_with_prices 同结构的 points；无核查联返回 None。
        """
        try:
            bill = self.db["bill_verification"].find_one(
                {"customer_id": customer_id, "period": period}
            )
        except Exception:
            return None
        if not bill:
            return None
        return self._bill_points_with_prices(
            bill, period, holding_ratio, k2_ratio, mid_long_price, customer_id
        )

    def calc_from_load(
        self,
        package: dict,
        customer_id: str,
        period: str,
        market: Optional[dict] = None,
        overrides: Optional[dict] = None,
        auto_market: bool = False,
        holding_ratio: float = 0.9,
        k2_ratio: float = 0.05,
        mid_long_price: Optional[float] = None,
        pointwise: bool = True,
    ) -> Dict[str, Any]:
        """路径A：按历史负荷曲线测算套餐电费。

        auto_market=True 时，自动用日前/实时/中长期合成批发分时价（模板 分时!B31）。
        pointwise=True（默认）时走逐点卷积引擎 calculate_jiangsu_2027_pointwise，
        与《套餐测算模板-新v2.xlsx》逐点对齐；False 则回退三段聚合版。
        """
        market = dict(market or {})
        params = self._package_params(package, overrides)
        agg = None
        points = None
        result = None
        if auto_market and pointwise:
            # ---- 逐点模式（对齐 Excel）----
            points = self._load_points_with_prices(
                customer_id, period, holding_ratio, k2_ratio, mid_long_price
            )
            if points is not None:
                market["wholesale_price"] = points["wholesale_price"]
                market["flat_base_price"] = points["flat_base_price"]
                if market.get("reference_price") in (None, 0):
                    market["reference_price"] = points["wholesale_price"]
                result = PricingEngine.calculate_jiangsu_2027_pointwise(
                    params,
                    {"labels": points["labels"], "curve": points["curve"],
                     "wholesale": points["wholesale"], "max_pnt": points["max_pnt"]},
                    market,
                )
                volumes = {k: points[k] for k in ("peak_mwh", "flat_mwh", "valley_mwh")}
        if result is None:
            # ---- 三段聚合 / 手工行情 回退 ----
            if auto_market:
                agg = self._aggregate_load_with_prices(
                    customer_id, period, holding_ratio, k2_ratio, mid_long_price
                )
                volumes = {k: agg[k] for k in ("peak_mwh", "flat_mwh", "valley_mwh")}
                market["wholesale_price"] = agg["wholesale_price"]
                market["flat_base_price"] = agg["flat_base_price"]
                if market.get("reference_price") in (None, 0):
                    market["reference_price"] = agg["wholesale_price"]
            else:
                volumes = self._aggregate_load_by_tou(customer_id, period)
            result = PricingEngine.calculate_jiangsu_2027(params, volumes, market)

        total = sum(volumes.values())
        result.update(
            {
                "source": "load_curve",
                "customer_id": customer_id,
                "period": period,
                "params": params,
            }
        )
        if points is not None:
            result["wholesale_auto"] = {
                "method": "日前/实时/中长期合成（逐点卷积）",
                "holding_ratio": points["holding_ratio"],
                "k2_ratio": points["k2_ratio"],
                "mid_long_price": points["mid_long_price"],
                "day_ahead_avg": points["day_ahead_avg"],
                "real_time_avg": points["real_time_avg"],
                "matched_points": points["matched"],
                "unmatched_points": points["unmatched"],
            }
        elif agg is not None:
            result["wholesale_auto"] = {
                "method": "日前/实时/中长期合成",
                "holding_ratio": agg["holding_ratio"],
                "k2_ratio": agg["k2_ratio"],
                "mid_long_price": agg["mid_long_price"],
                "day_ahead_avg": agg["day_ahead_avg"],
                "real_time_avg": agg["real_time_avg"],
                "matched_points": agg["_matched"],
                "unmatched_points": agg["_unmatched"],
            }
        result = self._attach_sgcc(result, period, self._ktype_of(customer_id))
        if total <= 0:
            result["warning"] = (
                "该客户在所选月份无负荷数据（可能为模拟数据缺失），"
                "请检查 user_load_data 或先接入真实负荷"
            )
        return result

    # ------------------------- 路径B：核查联测算 -------------------------
    def calc_from_bill(
        self,
        package: dict,
        bill: dict,
        market: dict,
        overrides: Optional[dict] = None,
        pointwise: bool = True,
        holding_ratio: float = 0.9,
        k2_ratio: float = 0.05,
        customer_id: Optional[str] = None,
        market_source: str = "manual",
    ) -> Dict[str, Any]:
        """路径B：按核查联测算套餐电费，并与现状实收电费对比。

        pointwise=True（默认）：把月度峰平谷电量按 TOU 摊回 24 时段，走逐点引擎
        （对齐 Excel 精度）；无现货价数据时自动回退三段聚合。

        market_source:
          "manual"（默认）—— 用调用方传入的 market（手工填批发价）
          "system"        —— 从【成本基线】自动取批发价与分摊（P4 打通）
        """
        total = float(bill.get("total_mwh") or 0.0)
        peak = bill.get("peak_mwh")
        flat = bill.get("flat_mwh")
        valley = bill.get("valley_mwh")
        if peak is None or flat is None or valley is None:
            # 核查联未给峰平谷，按默认占比拆分（可在前端按实际填）
            peak = total * DEFAULT_RATIO["peak"]
            flat = total * DEFAULT_RATIO["flat"]
            valley = total * DEFAULT_RATIO["valley"]
        volumes = {
            "peak_mwh": float(peak),
            "flat_mwh": float(flat),
            "valley_mwh": float(valley),
        }
        params = self._package_params(package, overrides)
        market = dict(market or {})

        # P4：行情来源 = 成本基线
        market_meta = None
        if str(market_source).lower() == "system":
            try:
                from webapp.services.cost_basis_service import CostBasisService
                mk = CostBasisService(self.db).as_market(bill.get("period") or "", customer_id)
                market_meta = mk
                for _k in ("wholesale_price", "flat_base_price",
                           "share_cost_compensation", "share_imbalance", "share_market_adjust"):
                    if mk.get(_k) is not None:
                        market[_k] = mk[_k]
            except Exception as _e:
                logger.warning("成本基线取行情失败，回退手工行情: %s", _e)

        result = None
        points = None
        if pointwise:
            points = self._bill_points_with_prices(
                bill, bill.get("period") or "", holding_ratio, k2_ratio,
                market.get("mid_long_price"), customer_id,
            )
            if points is not None:
                mk = dict(market)
                # 封顶基准 T4：优先用调用方给的批发价假设，未给则用逐点合成均价
                if mk.get("wholesale_price") in (None, 0):
                    mk["wholesale_price"] = points["wholesale_price"]
                mk["flat_base_price"] = points["flat_base_price"]
                if mk.get("reference_price") in (None, 0):
                    mk["reference_price"] = points["wholesale_price"]
                result = PricingEngine.calculate_jiangsu_2027_pointwise(
                    params,
                    {"labels": points["labels"], "curve": points["curve"],
                     "wholesale": points["wholesale"], "max_pnt": points["max_pnt"]},
                    mk,
                )
                volumes = {k: points[k] for k in ("peak_mwh", "flat_mwh", "valley_mwh")}

        if result is None:
            result = PricingEngine.calculate_jiangsu_2027(params, volumes, market)

        result.update(
            {
                "source": "bill",
                "pricing_mode": result.get("pricing_mode") or ("jiangsu_2027_pointwise" if points else "jiangsu_2027"),
                "period": bill.get("period"),
                "customer_name": bill.get("customer_name"),
                "account_id": bill.get("account_id"),
                "params": params,
            }
        )
        if market_meta is not None:
            result["market_meta"] = market_meta
        if points is not None:
            result["wholesale_auto"] = {
                "method": "核查联电量按TOU摊回24时段 + 现货/中长期逐点合成",
                "mid_long_source": points["mid_long_source"],
                "holding_ratio": points["holding_ratio"],
                "k2_ratio": points["k2_ratio"],
                "day_ahead_avg": points["day_ahead_avg"],
                "real_time_avg": points["real_time_avg"],
            }

        result = self._attach_sgcc(result, result.get("period") or "", (bill or {}).get("ktype"))
        current = bill.get("current_amount")
        if current is not None:
            current = float(current)
            diff = round(result["total_cost"] - current, 2)
            result["current_amount"] = current
            result["diff"] = diff
            result["saving_rate"] = round(diff / current, 4) if current else None
            result["verdict"] = "套餐更省" if diff < 0 else ("套餐更贵" if diff > 0 else "持平")
        return result

    # ==================================================================
    # 年度批量测算（每用户 × 12 月，2027 新规全链路）
    # ==================================================================
    def calc_annual(
        self,
        package: dict,
        customer_ids: List[str],
        year: int,
        market: Optional[dict] = None,
        overrides: Optional[dict] = None,
        auto_market: bool = True,
        holding_ratio: float = 0.9,
        k2_ratio: float = 0.05,
        mid_long_price: Optional[float] = None,
        ktype: Optional[str] = None,
        pointwise: bool = True,
        market_source: str = "manual",
    ) -> Dict[str, Any]:
        """逐用户 × 逐月测算，输出明细 + 年度汇总 + 合规校验。

        ktype: 用电类型（两部制/单一制-100千伏安及以上/以下）。为空则取客户档案，
               再为空用默认档（单一制-100千伏安以下）。
        market_source: "manual"（手工行情）/ "system"（从成本基线逐月自动取批发价与分摊）
        """
        from webapp.services.compliance_service import ComplianceService

        market = dict(market or {})
        params = self._package_params(package, overrides)
        _use_system_market = str(market_source).lower() == "system"
        merged_cfg = dict((package or {}).get("pricing_config") or {})
        merged_cfg.update(overrides or {})
        compliance = ComplianceService().validate(merged_cfg)

        # 客户名称/用电类型
        cust_meta: Dict[str, Dict[str, Any]] = {}
        for cid in customer_ids:
            doc = None
            try:
                from bson import ObjectId
                doc = self.db["customers"].find_one({"_id": ObjectId(cid)})
            except Exception:
                doc = None
            doc_ktype = (doc or {}).get("electricity_type") or (doc or {}).get("user_type")
            cust_meta[cid] = {
                "name": (doc or {}).get("user_name") or cid,
                # 优先客户档案，其次入参 ktype，最后默认档
                "ktype": doc_ktype or ktype or DEFAULT_KTYPE,
            }

        details: List[Dict[str, Any]] = []
        monthly: List[Dict[str, Any]] = []
        warnings: List[str] = []
        bill_fallback_months: set = set()   # 用核查联回退的月份
        total_volume = 0.0
        total_profit_wan = 0.0
        capped_count = 0
        user_month_count = 0
        month_agg = {m: {"volume_mwh": 0.0, "profit_wan": 0.0, "amount": 0.0,
                         "peak_mwh": 0.0, "flat_mwh": 0.0, "valley_mwh": 0.0} for m in range(1, 13)}

        for cid in customer_ids:
            for m in range(1, 13):
                period = "%d-%02d" % (year, m)
                agg = None
                points = None
                r = None
                mk = dict(market)
                # P4：逐月从成本基线取行情（每个客户/月独立）
                if _use_system_market:
                    try:
                        from webapp.services.cost_basis_service import CostBasisService
                        _mk_sys = CostBasisService(self.db).as_market(period, cid)
                        for _k in ("wholesale_price", "flat_base_price",
                                   "share_cost_compensation", "share_imbalance", "share_market_adjust"):
                            if _mk_sys.get(_k) is not None:
                                mk[_k] = _mk_sys[_k]
                    except Exception as _e:
                        logger.warning("成本基线取行情失败(%s): %s", period, _e)
                _src = None
                if auto_market and pointwise:
                    points = self._load_points_with_prices(
                        cid, period, holding_ratio, k2_ratio, mid_long_price)
                    _src = "load_curve" if points is not None else None
                    if points is None:
                        # 方案C：无 96 点负荷 → 回退该月核查联（按 TOU 摊回 24 时段）
                        points = self._bill_points_for_month(
                            cid, period, holding_ratio, k2_ratio, mid_long_price)
                        if points is not None:
                            _src = "bill_verification"
                            bill_fallback_months.add(period)
                    if points is not None:
                        # system 模式下保留成本基线注入的批发价/平段基准（成本视角优先）
                        if not _use_system_market:
                            mk["wholesale_price"] = points["wholesale_price"]
                            mk["flat_base_price"] = points["flat_base_price"]
                        if mk.get("reference_price") in (None, 0):
                            mk["reference_price"] = mk.get("wholesale_price") or points["wholesale_price"]
                        volumes = {k: points[k] for k in ("peak_mwh", "flat_mwh", "valley_mwh")}
                        r = PricingEngine.calculate_jiangsu_2027_pointwise(
                            params,
                            {"labels": points["labels"], "curve": points["curve"],
                             "wholesale": points["wholesale"], "max_pnt": points["max_pnt"]},
                            mk,
                        )
                if r is None:
                    if auto_market:
                        agg = self._aggregate_load_with_prices(
                            cid, period, holding_ratio, k2_ratio, mid_long_price)
                        volumes = {k: agg[k] for k in ("peak_mwh", "flat_mwh", "valley_mwh")}
                        mk["wholesale_price"] = agg["wholesale_price"]
                        mk["flat_base_price"] = agg["flat_base_price"]
                        if mk.get("reference_price") in (None, 0):
                            mk["reference_price"] = agg["wholesale_price"]
                    else:
                        volumes = self._aggregate_load_by_tou(cid, period)
                    # 方案C：仍无电量时，回退该月核查联（非逐点路径也支持）
                    if sum(volumes.values()) <= 0:
                        _bp = self._bill_points_for_month(
                            cid, period, holding_ratio, k2_ratio, mid_long_price)
                        if _bp is not None:
                            volumes = {k: _bp[k] for k in ("peak_mwh", "flat_mwh", "valley_mwh")}
                            _src = "bill_verification"
                            bill_fallback_months.add(period)
                            if mk.get("wholesale_price") in (None, 0):
                                mk["wholesale_price"] = _bp["wholesale_price"]
                            if mk.get("flat_base_price") in (None, 0):
                                mk["flat_base_price"] = _bp["flat_base_price"]
                    r = PricingEngine.calculate_jiangsu_2027(params, volumes, mk)

                vol = sum(volumes.values())
                if vol <= 0:
                    continue
                sgcc = self._sgcc_for_period(period) or {}
                sgcc_tou = self._sgcc_tou(sgcc or None, cust_meta[cid]["ktype"], volumes)
                # 购电成本 = 批发市场价 + 分摊合计（对齐模板 总表!C13 = 成本测算!B56 + 峰谷时段表!T8）
                cost = float(r["prices"]["wholesale_price"]) + float(r["share"]["total"])
                sell = float(r["sell_price"])
                profit = round(sell - cost, 3)
                profit_wan = round(profit * vol / 10000.0, 4)

                user_month_count += 1
                total_volume += vol
                total_profit_wan += profit_wan
                if r["capped"]:
                    capped_count += 1

                mo = month_agg[m]
                mo["volume_mwh"] += vol
                mo["profit_wan"] += profit_wan
                mo["amount"] += sell * vol
                mo["peak_mwh"] += volumes["peak_mwh"]
                mo["flat_mwh"] += volumes["flat_mwh"]
                mo["valley_mwh"] += volumes["valley_mwh"]

                details.append({
                    "user": cust_meta[cid]["name"],
                    "ktype": cust_meta[cid]["ktype"],
                    "customer_id": cid,
                    "month": m,
                    "data_source": _src or "load_curve",
                    "volume_mwh": round(vol, 4),
                    "p_wholesale": r["prices"]["wholesale_price"],
                    "p_share": r["share"]["total"],
                    "p_reference": r["prices"]["reference_price"],
                    "p_cap": r["cap_price"],
                    "peak_price": r["prices"]["peak_price"],
                    "flat_price": r["prices"]["flat_price"],
                    "valley_price": r["prices"]["valley_price"],
                    "retail_avg": r["energy_avg_price"],
                    "capped": r["capped"],
                    "settle_price": r["settle_price"],
                    "green_add": r["green_add"],
                    "sell_price": sell,
                    "cost": round(cost, 3),
                    "sgcc_price": round(float(sgcc.get("avg_on_grid_price") or 0.0), 3),
                    "sgcc_peak_price": (sgcc_tou or {}).get("peak_price"),
                    "sgcc_flat_price": (sgcc_tou or {}).get("flat_price"),
                    "sgcc_valley_price": (sgcc_tou or {}).get("valley_price"),
                    "sgcc_weighted": (sgcc_tou or {}).get("weighted_price"),
                    "profit_per_mwh": profit,
                    "profit_wan": profit_wan,
                })

        for m in range(1, 13):
            mo = month_agg[m]
            vol = mo["volume_mwh"]
            monthly.append({
                "month": m,
                "volume_mwh": round(vol, 4),
                "sell_price": round(mo["amount"] / vol, 3) if vol else None,
                "profit_wan": round(mo["profit_wan"], 4),
                "peak_mwh": round(mo["peak_mwh"], 4),
                "flat_mwh": round(mo["flat_mwh"], 4),
                "valley_mwh": round(mo["valley_mwh"], 4),
            })

        if user_month_count == 0:
            warnings.append("所选客户在 %d 年没有可用负荷数据，无法测算" % year)
        if not auto_market:
            warnings.append("未开启自动取批发价，使用的是手工填写的市场行情")
        if bill_fallback_months:
            _ms = "、".join(sorted(bill_fallback_months))
            warnings.append(
                "以下月份无 96 点负荷曲线，已用【核查联】月度峰平谷电量按 TOU 摊回 24 时段测算"
                "（精度略低于真实负荷曲线）：%s" % _ms
            )
        if holding_ratio < HOLDING_ASSESS_LINE:
            warnings.append(
                "中长期持仓比例 %.0f%% 低于考核线 %.0f%%，可能不满足持仓考核要求，请按实际用电情况调整"
                % (holding_ratio * 100, HOLDING_ASSESS_LINE * 100)
            )

        kpi = {
            "total_volume_mwh": round(total_volume, 4),
            "avg_profit_per_mwh": round(total_profit_wan * 10000.0 / total_volume, 3) if total_volume else None,
            "total_profit_wan": round(total_profit_wan, 4),
            "capped_count": capped_count,
            "user_month_count": user_month_count,
            "f_ratio": params.get("f_ratio"),
            "kp": params.get("kp"),
            "peak_coef": params.get("peak_coef"),
            "valley_coef": params.get("valley_coef"),
        }

        return {
            "year": year,
            "package_id": str((package or {}).get("id") or (package or {}).get("_id") or ""),
            "package_name": (package or {}).get("package_name"),
            "kpi": kpi,
            "monthly": monthly,
            "details": details,
            "compliance": compliance,
            "warnings": warnings,
        }
