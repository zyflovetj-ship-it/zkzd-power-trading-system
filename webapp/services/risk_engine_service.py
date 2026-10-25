"""
分时段风险敞口计算引擎（P0）

与旧 risk_exposure_service 的关系
---------------------------------
旧模块不删除、不改动，前端 /api/v1/risk-exposure 继续可用；
本引擎是**新口径的唯一实现**，输出结构不同，前端需走 /api/v1/risk/*。

修复的四个口径缺陷
------------------
1. 单位错配：合约量是 kWh、负荷是 MW，旧代码直接相减。本模块在边界用 to_mwh() 显式换算。
2. 跨期错配：旧代码"合同月总量 − 历史累计用电量"，量纲与时间维都不可比。
   本模块先把合约量按日分摊、再按负荷形状分摊到 96 点，与逐时段负荷相减。
3. 波动率频度错配：旧代码用相邻 15 分钟价格收益当"日波动率"。
   本模块按 period_index 分组取**同点隔日**对数收益，天然是日频，无需 sqrt(96) 缩放。
4. 静默兜底：旧代码 try/except 后返回 0.0，导致"有数据但金额恒为 0"。
   本模块所有降级路径都写入 warnings，缺数据就是缺数据。
"""

from __future__ import annotations

import hashlib
import logging
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pymongo.database import Database

from webapp.models.risk import (
    MODEL_VERSION,
    PERIODS_PER_DAY,
    ExposureBucket,
    ExposureSummary,
    LimitBreach,
    PeriodExposure,
    PeriodRiskContribution,
    RiskSnapshotMeta,
    VarResult,
    bucket_of,
    day_period_starts,
    period_label,
    to_mwh,
)

logger = logging.getLogger(__name__)

#: 正态分位数表，避免引入 scipy
_Z_TABLE = {0.90: 1.2815515655446004, 0.95: 1.6448536269514722, 0.99: 2.3263478740408408}


@dataclass
class RiskEngineConfig:
    """引擎参数。全部可在构造时覆盖，便于回测不同参数下的指标稳定性。"""

    load_unit: str = "kW"                  # short_term_load_forecast / user_load_data 入库单位（数值为 kW 量级，见 init_*_load_data 脚本）
    contract_unit: str = "kWh"             # retail_contracts 的入库单位
    lookback_days: int = 60                # 波动率/相关性样本窗口
    min_sigma_samples: int = 10            # 少于此样本数不出 VaR
    shape_lookback_days: int = 7           # 推导合约曲线形状用的历史负荷窗口
    price_fallback_days: int = 7           # 未来日期无价格时，向前找最近可用日的最大回溯天数
    #: timestamp 语义：
    #:   "start" —— timestamp 是时段起点（00:00, 00:15, ... 23:45）
    #:   "end"   —— timestamp 是时段结束时刻（00:15, 00:30, ... 次日 00:00）
    #: 当前库内模拟数据由 init_*_mock_data.py 生成，全部是 "end" 语义，
    #: 若按 "start" 解析会整体错位一个 15 分钟时段。
    timestamp_semantics: str = "end"
    risk_level_high: float = 1_000_000.0   # 敞口金额分级阈值(元)
    risk_level_medium: float = 200_000.0


class RiskEngineService:
    """分时段风险敞口 / VaR / 限额 计算引擎。"""

    def __init__(self, db: Database, config: Optional[RiskEngineConfig] = None) -> None:
        self.db = db
        self.cfg = config or RiskEngineConfig()
        self._sem: Optional[str] = None

    # ------------------------------------------------------------------ 入口

    def build_exposure(self, delivery_date: date) -> Dict[str, Any]:
        """构建某交割日的 96 点敞口曲线 + 汇总。

        :param delivery_date: 交割日（电价与负荷所属的自然日）
        :return: {"summary": ExposureSummary, "curve": List[PeriodExposure]}
        """
        warnings: List[str] = []

        contract_curve = self._contract_curve(delivery_date, warnings)
        load_curve = self._load_curve(delivery_date, warnings)
        price_curve = self._delivery_price_curve(delivery_date, warnings)

        net = contract_curve - load_curve
        price_exposure = net * price_curve

        starts = day_period_starts(delivery_date)
        curve: List[PeriodExposure] = []
        for i in range(PERIODS_PER_DAY):
            curve.append(
                PeriodExposure(
                    period_index=i,
                    period_label=period_label(i),
                    timestamp=starts[i],
                    bucket=bucket_of(i),
                    contract_mwh=round(float(contract_curve[i]), 6),
                    load_mwh=round(float(load_curve[i]), 6),
                    net_position_mwh=round(float(net[i]), 6),
                    fwd_price=round(float(price_curve[i]), 4),
                    price_exposure=round(float(price_exposure[i]), 2),
                )
            )

        total_contract = float(contract_curve.sum())
        total_load = float(load_curve.sum())
        total_net = float(net.sum())
        total_amount = float(price_exposure.sum())

        peak_mask = np.array([bucket_of(i) is ExposureBucket.PEAK for i in range(PERIODS_PER_DAY)])
        flat_mask = np.array([bucket_of(i) is ExposureBucket.FLAT for i in range(PERIODS_PER_DAY)])
        valley_mask = np.array([bucket_of(i) is ExposureBucket.VALLEY for i in range(PERIODS_PER_DAY)])

        coverage = (total_contract / total_load) if total_load > 0 else 0.0
        if total_load <= 0:
            warnings.append("负荷曲线全为 0，覆盖率与敞口不可信：请检查 short_term_load_forecast 是否覆盖该日")
        if total_contract <= 0:
            warnings.append("合约曲线全为 0：请检查 retail_contracts 中是否有覆盖该交割日的生效合约")

        risk_level = "low"
        if abs(total_amount) >= self.cfg.risk_level_high:
            risk_level = "high"
        elif abs(total_amount) >= self.cfg.risk_level_medium:
            risk_level = "medium"

        summary = ExposureSummary(
            delivery_date=delivery_date,
            total_contract_mwh=round(total_contract, 4),
            total_load_mwh=round(total_load, 4),
            total_net_mwh=round(total_net, 4),
            peak_net_mwh=round(float(net[peak_mask].sum()), 4),
            flat_net_mwh=round(float(net[flat_mask].sum()), 4),
            valley_net_mwh=round(float(net[valley_mask].sum()), 4),
            max_long_period_mwh=round(float(net.max()), 4),
            max_short_period_mwh=round(float(net.min()), 4),
            price_exposure_yuan=round(total_amount, 2),
            coverage_ratio=round(coverage, 4),
            risk_level=risk_level,
            warnings=warnings,
        )
        return {"summary": summary, "curve": curve}

    def compute_var(
        self,
        delivery_date: date,
        confidence: float = 0.95,
        horizon_days: int = 1,
        method: str = "parametric",
    ) -> VarResult:
        """按分时段相关性计算组合 VaR / CVaR。

        模型：PnL = Σ_i w_i · r_i，w_i 为该时段敞口金额，r_i 为该时段同点隔日对数收益。
        参数法 σ_P = sqrt(wᵀ Σ w)，Σ_ij = σ_i σ_j ρ_ij。
        """
        if confidence not in _Z_TABLE:
            raise ValueError(f"confidence 仅支持 {sorted(_Z_TABLE)}")
        if horizon_days < 1:
            raise ValueError("horizon_days 必须 >= 1")

        warnings: List[str] = []
        exposure = self.build_exposure(delivery_date)
        warnings.extend(exposure["summary"].warnings)
        curve = exposure["curve"]
        w = np.array([p.price_exposure for p in curve], dtype=float)

        panel = self._price_panel(
            delivery_date - timedelta(days=self.cfg.lookback_days + 1), delivery_date
        )
        sigma, corr, sample_days = self._sigma_and_corr(panel, warnings)

        if sigma is None:
            warnings.append(
                f"价格样本不足（需要 > {self.cfg.min_sigma_samples} 天），不出 VaR 数值。"
                "请补齐 day_ahead_spot_price 历史数据。"
            )
            return VarResult(
                method=method,
                confidence=confidence,
                horizon_days=horizon_days,
                sample_days=sample_days,
                warnings=warnings,
            )

        if method == "historical":
            return self._var_historical(panel, w, confidence, horizon_days, sample_days, warnings)
        return self._var_parametric(w, sigma, corr, confidence, horizon_days, sample_days, warnings)

    def check_limits(
        self, summary: ExposureSummary, var_yuan: Optional[float] = None
    ) -> List[LimitBreach]:
        """对敞口汇总与 VaR 做限额检查。限额定义读 risk_limit 集合，无定义时用内置默认。"""
        limits = list(self.db.risk_limit.find({"enabled": True}))
        if not limits:
            limits = self._default_limits()

        metrics = {
            "total_price_exposure": abs(summary.price_exposure_yuan),
            "net_position_mwh": abs(summary.total_net_mwh),
            "max_period_mwh": max(abs(summary.max_long_period_mwh), abs(summary.max_short_period_mwh)),
            "var_yuan": abs(var_yuan) if var_yuan is not None else 0.0,
            "coverage_gap": max(0.0, 1.0 - summary.coverage_ratio),
        }

        breaches: List[LimitBreach] = []
        for lim in limits:
            ltype = lim.get("limit_type")
            if ltype not in metrics:
                continue
            if ltype == "var_yuan" and var_yuan is None:
                continue
            actual = metrics[ltype]
            threshold = float(lim.get("threshold", 0) or 0)
            if threshold <= 0:
                continue
            ratio = actual / threshold
            if ratio >= 1.0:
                severity = "breach"
            elif ratio >= float(lim.get("warn_ratio", 0.8)):
                severity = "warning"
            else:
                continue
            breaches.append(
                LimitBreach(
                    limit_id=str(lim.get("limit_id") or lim.get("_id")),
                    scope=str(lim.get("scope", "portfolio")),
                    limit_type=ltype,
                    threshold=threshold,
                    actual=round(actual, 2),
                    usage_ratio=round(ratio, 4),
                    severity=severity,
                )
            )
        return breaches

    def validate_inputs(self, delivery_date: date) -> Dict[str, Any]:
        """入库数据自洽性校验。

        风控系统的第一职责是**不让脏数据算出可信数字**。本方法把"算得出但不可信"
        的情况显式暴露出来，而不是像旧实现那样 try/except 后返回 0。

        检查项：
          1. 合约覆盖      —— 该交割日是否有生效零售合约
          2. 负荷覆盖      —— 96 点负荷预测是否齐全
          3. 电价覆盖      —— 96 点电价是否齐全
          4. 量级自洽      —— 合约日均电量与负荷日均电量的比值是否在合理区间
          5. 电价合理性    —— 是否落在 [-500, 5000] 元/MWh（含负电价）
          6. 负荷合理性    —— 是否出现负值或全零
          7. 波动率样本    —— 价格历史天数是否够算 VaR
        """
        checks: List[Dict[str, Any]] = []

        def add(name: str, level: str, detail: str, actual: Any = None, expected: Any = None) -> None:
            checks.append(
                {"name": name, "level": level, "detail": detail, "actual": actual, "expected": expected}
            )

        exposure = self.build_exposure(delivery_date)
        summary = exposure["summary"]
        curve = exposure["curve"]

        # 1. 合约
        n_contract = self.db.retail_contracts.count_documents(
            {
                "purchase_start_month": {"$lte": datetime.combine(delivery_date, time(23, 59, 59))},
                "purchase_end_month": {"$gte": datetime.combine(delivery_date, time(0, 0))},
            }
        )
        add("合约覆盖", "ok" if n_contract > 0 else "fail",
            f"覆盖该交割日的零售合约 {n_contract} 份", n_contract, ">= 1")

        # 2/3/6. 曲线覆盖与合理性
        load_points = sum(1 for c in curve if c.load_mwh > 0)
        add("负荷覆盖", "ok" if load_points == PERIODS_PER_DAY else ("fail" if load_points == 0 else "warn"),
            f"负荷非零时段 {load_points}/96", load_points, 96)

        price_points = sum(1 for c in curve if c.fwd_price != 0)
        add("电价覆盖", "ok" if price_points == PERIODS_PER_DAY else ("fail" if price_points == 0 else "warn"),
            f"电价非零时段 {price_points}/96", price_points, 96)

        neg_load = sum(1 for c in curve if c.load_mwh < 0)
        add("负荷合理性", "fail" if neg_load else "ok", f"负荷负值时段 {neg_load} 个", neg_load, 0)

        prices = [c.fwd_price for c in curve if c.fwd_price != 0]
        if prices:
            lo, hi = min(prices), max(prices)
            level = "ok" if (lo >= -500 and hi <= 5000) else "warn"
            add("电价合理性", level, f"电价区间 {lo:.2f} ~ {hi:.2f} 元/MWh", [round(lo, 2), round(hi, 2)], [-500, 5000])

        # 4. 量级自洽（本次实测的真实问题就出在这里）
        contract_daily = summary.total_contract_mwh
        load_daily = summary.total_load_mwh
        if contract_daily > 0 and load_daily > 0:
            ratio = contract_daily / load_daily
            if ratio > 20 or ratio < 0.05:
                add(
                    "量级自洽",
                    "fail",
                    (
                        f"合约日均 {contract_daily:.2f} MWh 与负荷日均 {load_daily:.2f} MWh 相差 "
                        f"{max(ratio, 1 / ratio):.0f} 倍，单位或量级疑似错配，敞口结果不可用。"
                        "请核对 retail_contracts.purchasing_electricity_quantity(kWh) 与 "
                        "short_term_load_forecast.value 的实际单位。"
                    ),
                    round(ratio, 4),
                    [0.05, 20],
                )
            else:
                add("量级自洽", "ok", f"合约/负荷 = {ratio:.3f}", round(ratio, 4), [0.05, 20])

        # 7. 波动率样本
        panel = self._price_panel(
            delivery_date - timedelta(days=self.cfg.lookback_days + 1), delivery_date
        )
        days = 0 if panel.empty else int(panel.dropna(how="all").shape[0])
        need = self.cfg.min_sigma_samples + 1
        add("波动率样本", "ok" if days >= need else "fail",
            f"可用价格历史 {days} 天（算 VaR 至少需要 {need} 天）", days, f">= {need}")

        levels = [c["level"] for c in checks]
        overall = "fail" if "fail" in levels else ("warn" if "warn" in levels else "ok")
        return {
            "delivery_date": delivery_date.isoformat(),
            "overall": overall,
            "checks": checks,
            "timestamp_semantics": self.semantics(),
            "units": {"contract": self.cfg.contract_unit, "load": self.cfg.load_unit, "price": "元/MWh"},
        }

    def save_snapshot(self, delivery_date: date) -> Dict[str, Any]:
        """落快照。指标一经写入不再覆盖，保证可回溯复现。"""
        exposure = self.build_exposure(delivery_date)
        var = self.compute_var(delivery_date)
        counts = self._input_counts(delivery_date)

        meta = RiskSnapshotMeta(
            as_of=datetime.now(),
            delivery_date=delivery_date,
            data_fingerprint=self._fingerprint(delivery_date, counts),
            input_counts=counts,
            params={
                "lookback_days": float(self.cfg.lookback_days),
                "confidence": var.confidence,
                "horizon_days": float(var.horizon_days),
            },
        )
        doc = {
            "as_of": meta.as_of,
            "delivery_date": delivery_date.isoformat(),
            "model_version": meta.model_version,
            "data_fingerprint": meta.data_fingerprint,
            "input_counts": meta.input_counts,
            "params": meta.params,
            "summary": exposure["summary"].model_dump(mode="json"),
            "curve": [p.model_dump(mode="json") for p in exposure["curve"]],
            "var": var.model_dump(mode="json"),
            "limits": [b.model_dump() for b in self.check_limits(exposure["summary"], var.var_yuan)],
            "created_at": datetime.now(),
        }
        result = self.db.risk_metric_snapshot.insert_one(doc)
        return {"snapshot_id": str(result.inserted_id), **meta.model_dump(mode="json")}

    # ------------------------------------------------------- 曲线构造（核心）

    def _contract_curve(self, delivery_date: date, warnings: List[str]) -> np.ndarray:
        """零售合约 → 批发侧锁定电量曲线（MWh，逐 96 点）。

        P0 分摊逻辑（无显式合同曲线时的可解释近似）：
          月内日均电量 = 合同总电量 / 合同覆盖自然日数
          当日 96 点 = 日均电量 × 该客户历史负荷形状（Σ形状 = 1）
        接入 contract_curves 后应改为直读曲线，届时保留本方法作 fallback。
        """
        curve = np.zeros(PERIODS_PER_DAY, dtype=float)
        contracts = list(
            self.db.retail_contracts.find(
                {
                    "purchase_start_month": {"$lte": datetime.combine(delivery_date, time(23, 59, 59))},
                    "purchase_end_month": {"$gte": datetime.combine(delivery_date, time(0, 0))},
                }
            )
        )
        if not contracts:
            return curve

        for c in contracts:
            qty = float(c.get("purchasing_electricity_quantity") or 0)
            if qty <= 0:
                continue
            total_mwh = to_mwh(qty, self.cfg.contract_unit)

            start = c.get("purchase_start_month")
            end = c.get("purchase_end_month")
            total_days = self._contract_span_days(start, end)
            daily_mwh = total_mwh / total_days if total_days > 0 else total_mwh

            shape = self._load_shape(str(c.get("customer_id") or ""), delivery_date, warnings)
            curve += daily_mwh * shape

        return curve

    def _load_curve(self, delivery_date: date, warnings: List[str]) -> np.ndarray:
        """负荷曲线（MWh，逐 96 点）。优先短期预测，缺失时退化为历史同型日。"""
        docs = list(
            self.db.short_term_load_forecast.find(
                {"timestamp": self._day_query(delivery_date)},
                {"timestamp": 1, "value": 1, "forecast_type": 1, "_id": 0},
            )
        )
        curve = np.zeros(PERIODS_PER_DAY, dtype=float)
        if docs:
            # 同一日可能有多套 d+1/d+2/d+3，优先最近一期（d+1）
            by_type: Dict[str, List[dict]] = {}
            for d in docs:
                by_type.setdefault(str(d.get("forecast_type") or "unknown"), []).append(d)
            preferred = None
            for key in ("d+1", "d+2", "d+3"):
                if key in by_type:
                    preferred = by_type[key]
                    break
            if preferred is None:
                preferred = next(iter(by_type.values()))
            else:
                if len(by_type) > 1:
                    warnings.append(
                        f"该日存在多套负荷预测 {sorted(by_type)}，已取 d+1"
                    )
            for d in preferred:
                ts = self._as_datetime(d.get("timestamp"))
                val = d.get("value")
                if ts is None or val is None:
                    continue
                curve[self._period_of(ts)] = to_mwh(float(val), self.cfg.load_unit)
            return curve

        # 退化：历史同型日（同 weekday）96 点均值
        fallback = self._historical_load_shape(delivery_date)
        if fallback is None:
            warnings.append(
                "该日无短期负荷预测，且历史负荷不足，负荷曲线置 0（敞口=全额超配，勿用于决策）"
            )
            return curve
        warnings.append("该日无短期负荷预测，已退化为历史同 weekday 96 点均值曲线")
        return fallback

    def _delivery_price_curve(self, delivery_date: date, warnings: List[str]) -> np.ndarray:
        """交割日电价曲线（元/MWh）。P0 用日前现货价作远期代理。"""
        panel = self._price_panel(delivery_date, delivery_date + timedelta(days=1))
        if not panel.empty and not panel.iloc[0].isna().all():
            row = panel.iloc[0].astype(float)
            if row.isna().any():
                warnings.append("交割日电价存在缺失时段，已用当日均值填充")
                row = row.fillna(row.mean())
            return row.to_numpy(dtype=float)

        # 未来日期尚未出清：向前找最近可用日
        for back in range(1, self.cfg.price_fallback_days + 1):
            d = delivery_date - timedelta(days=back)
            prev = self._price_panel(d, d + timedelta(days=1))
            if not prev.empty and not prev.iloc[0].isna().all():
                row = prev.iloc[0].astype(float)
                row = row.fillna(row.mean())
                warnings.append(
                    f"交割日 {delivery_date} 尚无出清价格，已用 {d} 同日曲线作代理"
                )
                return row.to_numpy(dtype=float)

        warnings.append("交割日及回溯窗口内均无电价，价格敞口按 0 计，勿用于决策")
        return np.zeros(PERIODS_PER_DAY, dtype=float)

    def _load_shape(
        self, customer_id: str, delivery_date: date, warnings: List[str]
    ) -> np.ndarray:
        """某客户的历史负荷形状（Σ=1），用于把日电量分摊到 96 点。"""
        shape = self._historical_load_shape(delivery_date, customer_id=customer_id)
        if shape is None or shape.sum() <= 0:
            warnings.append(
                f"客户 {customer_id or '(空)'} 无历史负荷，合约曲线按均匀形状分摊（1/96）"
            )
            return np.full(PERIODS_PER_DAY, 1.0 / PERIODS_PER_DAY)
        return shape / shape.sum()

    def _historical_load_shape(
        self, delivery_date: date, customer_id: Optional[str] = None
    ) -> Optional[np.ndarray]:
        """近 N 天 96 点均值曲线（MWh）。customer_id 为空时取全部客户合计。"""
        query: Dict[str, Any] = {
            "timestamp": self._panel_query(
                delivery_date - timedelta(days=self.cfg.shape_lookback_days), delivery_date
            )
        }
        if customer_id:
            query["customer_id"] = customer_id
        docs = list(self.db.user_load_data.find(query, {"timestamp": 1, "value": 1, "_id": 0}))
        if not docs:
            return None
        acc = np.zeros(PERIODS_PER_DAY, dtype=float)
        cnt = np.zeros(PERIODS_PER_DAY, dtype=float)
        for d in docs:
            ts = self._as_datetime(d.get("timestamp"))
            val = d.get("value")
            if ts is None or val is None:
                continue
            idx = self._period_of(ts)
            acc[idx] += to_mwh(float(val), self.cfg.load_unit)
            cnt[idx] += 1
        with np.errstate(invalid="ignore", divide="ignore"):
            avg = np.where(cnt > 0, acc / np.maximum(cnt, 1), 0.0)
        if avg.sum() <= 0:
            return None
        return avg

    # ------------------------------------------------------------ 统计与 VaR

    # -------------------------------------------------- 时间戳语义与区间

    def semantics(self) -> str:
        """返回 timestamp 语义，config 显式指定优先，否则自动探测一次并缓存。"""
        if self._sem is not None:
            return self._sem
        if self.cfg.timestamp_semantics in ("start", "end"):
            self._sem = self.cfg.timestamp_semantics
            return self._sem
        self._sem = self._detect_semantics()
        return self._sem

    def _detect_semantics(self) -> str:
        """按数据首点分钟数探测语义：:00 起为 start，:15 起且末点为次日 00:00 为 end。"""
        try:
            doc = self.db.day_ahead_spot_price.find_one({}, {"timestamp": 1}, sort=[("timestamp", 1)])
            ts = self._as_datetime((doc or {}).get("timestamp"))
            if ts is None:
                return "end"
            return "start" if ts.minute == 0 else "end"
        except Exception as exc:
            logger.warning("探测 timestamp 语义失败，回退 end: %s", exc)
            return "end"

    def _period_of(self, ts: datetime) -> int:
        """timestamp → period_index，按当前语义解析。"""
        idx = ts.hour * 4 + ts.minute // 15
        if self.semantics() == "end":
            # 结束时刻标记：00:15 是 period 0，次日 00:00 是 period 95
            idx -= 1
            if idx < 0:
                idx += PERIODS_PER_DAY
        return idx % PERIODS_PER_DAY

    def _day_query(self, day: date) -> Dict[str, Any]:
        """取某一交割日 96 点的时间区间查询条件。

        start 语义用半开区间 [00:00, 次日00:00)；end 语义用左开右闭 (00:00, 次日00:00]，
        否则 period 0 与 period 95 会各丢一个点。
        """
        a = datetime.combine(day, time(0, 0))
        b = a + timedelta(days=1)
        if self.semantics() == "end":
            return {"$gt": a, "$lte": b}
        return {"$gte": a, "$lt": b}

    def _panel_query(self, start: date, end_exclusive: date) -> Dict[str, Any]:
        """价格面板区间：取 [start, end_exclusive) 覆盖的所有 96 点。"""
        a = datetime.combine(start, time(0, 0))
        b = datetime.combine(end_exclusive, time(0, 0))
        if self.semantics() == "end":
            return {"$gt": a, "$lte": b}
        return {"$gte": a, "$lt": b}

    # ------------------------------------------------------------ 统计与 VaR

    def _price_panel(self, start: date, end: date) -> pd.DataFrame:
        """价格面板：index=日期，columns=period_index(0..95)。同点重复取均值。"""
        docs = list(
            self.db.day_ahead_spot_price.find(
                {"timestamp": self._panel_query(start, end)},
                {"timestamp": 1, "value": 1, "_id": 0},
            )
        )
        rows = []
        for d in docs:
            ts = self._as_datetime(d.get("timestamp"))
            val = d.get("value")
            if ts is None or val is None:
                continue
            # end 语义下，次日 00:00 属于前一自然日，日期归属要回退一天
            day = ts.date()
            if self.semantics() == "end" and ts.hour == 0 and ts.minute == 0:
                day = day - timedelta(days=1)
            rows.append({"day": day, "period": self._period_of(ts), "price": float(val)})
        if not rows:
            return pd.DataFrame()
        df = pd.DataFrame(rows)
        panel = df.groupby(["day", "period"])["price"].mean().unstack("period")
        return panel.reindex(columns=range(PERIODS_PER_DAY))

    def _sigma_and_corr(
        self, panel: pd.DataFrame, warnings: List[str]
    ) -> Tuple[Optional[np.ndarray], Optional[np.ndarray], int]:
        """分时段 σ 与相关矩阵。

        关键：按 period_index 分组，取**同点隔日**对数收益 → 天然日频，
        不需要 sqrt(96) 缩放。旧代码用相邻 15 分钟收益，是 15min 频，两者相差约 10 倍。
        """
        if panel.empty or len(panel) < self.cfg.min_sigma_samples + 1:
            return None, None, 0

        logp = np.log(panel.where(panel > 0))
        rets = logp.diff().iloc[1:].dropna(how="all")
        if len(rets) < self.cfg.min_sigma_samples:
            return None, None, len(rets)

        sigma = rets.std(ddof=1, skipna=True).to_numpy(dtype=float)
        n_ok = int(np.isfinite(sigma).sum())
        if n_ok < PERIODS_PER_DAY * 0.5:
            warnings.append(
                f"仅 {n_ok}/96 个时段有足够价格样本，VaR 可靠性不足"
            )
        # 缺样本时段用中位数替代，避免 0 波动率虚降 VaR
        med = float(np.nanmedian(sigma)) if n_ok > 0 else 0.0
        sigma = np.where(np.isfinite(sigma), sigma, med)
        if not np.isfinite(sigma).all() or float(np.nansum(sigma)) <= 0:
            return None, None, len(rets)

        corr = rets.corr().to_numpy(dtype=float)
        return sigma, self._psd_fix(corr), len(rets)

    @staticmethod
    def _psd_fix(corr: np.ndarray) -> np.ndarray:
        """相关矩阵修复为半正定，保证 wᵀΣw >= 0。"""
        c = np.nan_to_num(corr, nan=0.0, posinf=0.0, neginf=0.0)
        np.fill_diagonal(c, 1.0)
        c = (c + c.T) / 2.0
        vals, vecs = np.linalg.eigh(c)
        vals = np.clip(vals, 1e-8, None)
        c = vecs @ np.diag(vals) @ vecs.T
        d = np.sqrt(np.clip(np.diag(c), 1e-12, None))
        c = c / np.outer(d, d)
        np.fill_diagonal(c, 1.0)
        return c

    def _var_parametric(
        self,
        w: np.ndarray,
        sigma: np.ndarray,
        corr: np.ndarray,
        confidence: float,
        horizon_days: int,
        sample_days: int,
        warnings: List[str],
    ) -> VarResult:
        z = _Z_TABLE[confidence]
        cov = np.outer(sigma, sigma) * corr
        var_pnl = float(w @ cov @ w)
        sigma_p = float(np.sqrt(max(var_pnl, 0.0)))
        scale = float(np.sqrt(horizon_days))
        var_yuan = z * sigma_p * scale
        # 正态 CVaR：σ·φ(z)/(1-α)
        cvar_yuan = sigma_p * scale * self._normal_pdf(z) / (1.0 - confidence)

        contributions: List[PeriodRiskContribution] = []
        if sigma_p > 0:
            marginal = cov @ w
            comp = w * marginal / sigma_p * z * scale
            for i in range(PERIODS_PER_DAY):
                contributions.append(
                    PeriodRiskContribution(
                        period_index=i,
                        period_label=period_label(i),
                        exposure_yuan=round(float(w[i]), 2),
                        sigma_yuan=round(float(abs(w[i]) * sigma[i] * scale), 2),
                        var_contribution=round(float(comp[i]), 2),
                    )
                )
        return VarResult(
            method="parametric",
            confidence=confidence,
            horizon_days=horizon_days,
            var_yuan=round(var_yuan, 2),
            cvar_yuan=round(cvar_yuan, 2),
            portfolio_sigma_yuan=round(sigma_p * scale, 2),
            sample_days=sample_days,
            contributions=contributions,
            warnings=warnings,
        )

    def _var_historical(
        self,
        panel: pd.DataFrame,
        w: np.ndarray,
        confidence: float,
        horizon_days: int,
        sample_days: int,
        warnings: List[str],
    ) -> VarResult:
        """历史模拟法：天然处理电力价格厚尾与负电价，优先推荐。"""
        logp = np.log(panel.where(panel > 0))
        rets = logp.diff().iloc[1:]
        rets = rets.dropna(how="all")
        if rets.empty:
            warnings.append("历史收益样本为空，无法做历史模拟")
            return VarResult(method="historical", confidence=confidence, warnings=warnings)

        r = rets.to_numpy(dtype=float)
        # 缺失时段收益按 0 处理（该时段无持仓价格变动信息）
        r = np.nan_to_num(r, nan=0.0)
        pnl = r @ w
        if horizon_days > 1:
            pnl = pnl * float(np.sqrt(horizon_days))

        alpha = 1.0 - confidence
        q = float(np.quantile(pnl, alpha))
        tail = pnl[pnl <= q]
        var_yuan = max(0.0, -q)
        cvar_yuan = max(0.0, -float(tail.mean())) if tail.size else var_yuan

        sigma_p = float(np.std(pnl, ddof=1)) if pnl.size > 1 else 0.0
        return VarResult(
            method="historical",
            confidence=confidence,
            horizon_days=horizon_days,
            var_yuan=round(var_yuan, 2),
            cvar_yuan=round(cvar_yuan, 2),
            portfolio_sigma_yuan=round(sigma_p, 2),
            sample_days=sample_days,
            warnings=warnings,
        )

    # ------------------------------------------------------------------ 工具

    @staticmethod
    def _normal_pdf(x: float) -> float:
        return float(np.exp(-0.5 * x * x) / np.sqrt(2.0 * np.pi))

    @staticmethod
    def _as_datetime(value: Any) -> Optional[datetime]:
        if isinstance(value, datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.fromisoformat(value)
            except ValueError:
                return None
        return None

    @staticmethod
    def _contract_span_days(start: Any, end: Any) -> int:
        """合同覆盖自然日数（按整月口径）。"""
        s = RiskEngineService._as_datetime(start)
        e = RiskEngineService._as_datetime(end)
        if s is None or e is None:
            return 0
        first = date(s.year, s.month, 1)
        if e.month == 12:
            last_exclusive = date(e.year + 1, 1, 1)
        else:
            last_exclusive = date(e.year, e.month + 1, 1)
        return (last_exclusive - first).days

    def _default_limits(self) -> List[Dict[str, Any]]:
        """内置默认限额（软限 80% 预警）。生产环境应写入 risk_limit 集合后覆盖。"""
        return [
            {"limit_id": "default-total-exposure", "scope": "portfolio",
             "limit_type": "total_price_exposure", "threshold": 5_000_000.0,
             "warn_ratio": 0.8, "enabled": True},
            {"limit_id": "default-net-position", "scope": "portfolio",
             "limit_type": "net_position_mwh", "threshold": 5_000.0,
             "warn_ratio": 0.8, "enabled": True},
            {"limit_id": "default-max-period", "scope": "period",
             "limit_type": "max_period_mwh", "threshold": 300.0,
             "warn_ratio": 0.8, "enabled": True},
            {"limit_id": "default-var", "scope": "portfolio",
             "limit_type": "var_yuan", "threshold": 1_000_000.0,
             "warn_ratio": 0.8, "enabled": True},
            {"limit_id": "default-coverage-gap", "scope": "portfolio",
             "limit_type": "coverage_gap", "threshold": 0.3,
             "warn_ratio": 0.8, "enabled": True},
        ]

    def _input_counts(self, delivery_date: date) -> Dict[str, int]:
        window = self._day_query(delivery_date)
        return {
            "contracts": self.db.retail_contracts.count_documents({}),
            "load_points": self.db.short_term_load_forecast.count_documents({"timestamp": window}),
            "price_points": self.db.day_ahead_spot_price.count_documents({"timestamp": window}),
        }

    @staticmethod
    def _fingerprint(delivery_date: date, counts: Dict[str, int]) -> str:
        raw = "|".join(
            [delivery_date.isoformat(), MODEL_VERSION]
            + [f"{k}={v}" for k, v in sorted(counts.items())]
        )
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
