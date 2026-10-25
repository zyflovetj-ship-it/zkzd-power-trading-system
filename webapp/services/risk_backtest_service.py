"""
VaR 回测服务（P1）

为什么必须有回测
----------------
VaR 是一个"承诺"：95% 置信度意味着约 5% 的交易日允许突破。
如果实测突破率显著偏离 5%，模型就是错的——无论公式写得多漂亮。
监管与内部风控都要求出 VaR 必须附回测结论。

两个检验
--------
1. Kupiec POF（比例失败检验）：突破**频率**是否等于名义水平。
   H0: 突破率 = 1 - confidence
2. Christoffersen 独立性检验：突破是否**成簇**。
   成簇说明模型在波动率切换时反应迟钝（典型是固定窗口的历史模拟）。
3. 条件覆盖 = POF + 独立性，联合检验，df=2。

卡方 p 值用 erfc / exp 解析式，不引入 scipy。
"""

from __future__ import annotations

import logging
import math
from datetime import date, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from pymongo.database import Database

from webapp.models.risk import PERIODS_PER_DAY
from webapp.models.risk_advanced import BacktestResult, BacktestSample, MODEL_VERSION_P1
from webapp.services.risk_engine_service import RiskEngineService

logger = logging.getLogger(__name__)

_Z_TABLE = {0.90: 1.2815515655446004, 0.95: 1.6448536269514722, 0.99: 2.3263478740408408}
_EPS = 1e-12


def chi2_sf_df1(x: float) -> float:
    """卡方分布(df=1) 生存函数：P(X > x) = erfc(sqrt(x/2))。"""
    if x <= 0:
        return 1.0
    return math.erfc(math.sqrt(x / 2.0))


def chi2_sf_df2(x: float) -> float:
    """卡方分布(df=2) 生存函数：P(X > x) = exp(-x/2)。"""
    if x <= 0:
        return 1.0
    return math.exp(-x / 2.0)


class RiskBacktestService:
    """滚动窗口 VaR 回测。"""

    def __init__(self, db: Database, engine: Optional[RiskEngineService] = None) -> None:
        self.db = db
        self.engine = engine or RiskEngineService(db)

    # ------------------------------------------------------------------ 入口

    def run(
        self,
        delivery_date: date,
        confidence: float = 0.95,
        window_days: int = 20,
        method: str = "parametric",
        max_lookback_days: int = 180,
    ) -> BacktestResult:
        """对给定持仓做滚动回测。

        :param delivery_date: 用该日的 96 点敞口作为**固定组合**，回测历史上的 VaR 表现
        :param window_days: 滚动估计窗口
        :param method: parametric / historical
        """
        if confidence not in _Z_TABLE:
            raise ValueError(f"confidence 仅支持 {sorted(_Z_TABLE)}")
        if method not in ("parametric", "historical"):
            raise ValueError("method 仅支持 parametric / historical")
        if window_days < self.engine.cfg.min_sigma_samples + 2:
            raise ValueError(
                f"window_days 至少 {self.engine.cfg.min_sigma_samples + 2}，否则 σ 估不出来"
            )

        warnings: List[str] = []
        exposure = self.engine.build_exposure(delivery_date)
        w = np.array([p.price_exposure for p in exposure["curve"]], dtype=float)
        if not np.any(w):
            warnings.append("当前组合敞口全为 0，回测无意义（先修数据再回测）")
            return BacktestResult(
                method=method, confidence=confidence, window_days=window_days, warnings=warnings
            )

        panel = self.engine._price_panel(
            delivery_date - timedelta(days=max_lookback_days), delivery_date
        )
        if panel.empty:
            warnings.append("无价格历史，无法回测")
            return BacktestResult(
                method=method, confidence=confidence, window_days=window_days, warnings=warnings
            )

        panel = panel.dropna(how="all").sort_index()
        if len(panel) < window_days + 2:
            warnings.append(
                f"可用价格历史仅 {len(panel)} 天，不足回测（需要 > {window_days + 1} 天）"
            )
            return BacktestResult(
                method=method, confidence=confidence, window_days=window_days, warnings=warnings
            )

        logp = np.log(panel.where(panel > 0))
        rets = logp.diff()

        z = _Z_TABLE[confidence]
        samples: List[BacktestSample] = []

        for i in range(window_days, len(panel)):
            hist = panel.iloc[i - window_days:i]
            r_today = rets.iloc[i].to_numpy(dtype=float)

            if method == "parametric":
                sigma, corr, n_used = self.engine._sigma_and_corr(hist, [])
                if sigma is None:
                    continue
                cov = np.outer(sigma, sigma) * corr
                var = float(z * np.sqrt(max(float(w @ cov @ w), 0.0)))
            else:
                hist_rets = logp.iloc[i - window_days:i].diff().iloc[1:]
                if hist_rets.empty:
                    continue
                r_mat = np.nan_to_num(hist_rets.to_numpy(dtype=float), nan=0.0)
                pnl_hist = r_mat @ w
                var = float(max(0.0, -np.quantile(pnl_hist, 1.0 - confidence)))

            pnl = float(np.nansum(np.nan_to_num(r_today, nan=0.0) * w))
            samples.append(
                BacktestSample(
                    day=panel.index[i],
                    var_predicted=round(var, 2),
                    pnl_actual=round(pnl, 2),
                    breached=bool(pnl < -var),
                )
            )

        if not samples:
            warnings.append("没有可用的回测样本（滚动窗口内 σ 始终估不出来）")
            return BacktestResult(
                method=method, confidence=confidence, window_days=window_days, warnings=warnings
            )

        hits = [1 if s.breached else 0 for s in samples]
        n = len(hits)
        x = sum(hits)
        p = 1.0 - confidence

        kupiec_lr, kupiec_p = self.kupiec_pof(n, x, p)
        ind_lr, ind_p = self.christoffersen_ind(hits)
        cc_lr = kupiec_lr + ind_lr
        cc_p = chi2_sf_df2(cc_lr)

        passed = (kupiec_p > 0.05) and (ind_p > 0.05)
        if passed:
            verdict = (
                f"通过：{n} 个检验日中突破 {x} 次（期望 {n * p:.1f} 次），"
                "突破频率与独立性均未被拒绝"
            )
        elif kupiec_p <= 0.05 and x > n * p:
            verdict = f"不通过：突破 {x} 次显著高于期望 {n * p:.1f} 次，VaR 低估风险"
        elif kupiec_p <= 0.05:
            verdict = f"不通过：突破 {x} 次显著低于期望 {n * p:.1f} 次，VaR 过于保守（占用限额）"
        else:
            verdict = "不通过：突破成簇，模型对波动率切换反应迟钝"

        return BacktestResult(
            method=method,
            confidence=confidence,
            window_days=window_days,
            samples=n,
            exceptions=x,
            expected_exceptions=round(n * p, 2),
            kupiec_lr=round(kupiec_lr, 4),
            kupiec_pvalue=round(kupiec_p, 6),
            christoffersen_lr=round(ind_lr, 4),
            christoffersen_pvalue=round(ind_p, 6),
            cc_lr=round(cc_lr, 4),
            cc_pvalue=round(cc_p, 6),
            passed=passed,
            verdict=verdict,
            warnings=warnings,
            detail=samples,
        )

    # -------------------------------------------------------------- 统计检验

    @staticmethod
    def kupiec_pof(n: int, x: int, p: float) -> Tuple[float, float]:
        """Kupiec 比例失败检验。

        LR = -2 ln[ L(p) / L(x/n) ]，H0 下服从 chi2(1)。
        """
        if n <= 0:
            return 0.0, 1.0
        x_hat = x / n
        ll_null = (n - x) * math.log(max(1.0 - p, _EPS)) + x * math.log(max(p, _EPS))
        ll_alt = (n - x) * math.log(max(1.0 - x_hat, _EPS)) + x * math.log(max(x_hat, _EPS))
        lr = max(-2.0 * (ll_null - ll_alt), 0.0)
        return lr, chi2_sf_df1(lr)

    @staticmethod
    def christoffersen_ind(hits: List[int]) -> Tuple[float, float]:
        """Christoffersen 独立性检验：突破是否成簇。H0 下服从 chi2(1)。"""
        if len(hits) < 2:
            return 0.0, 1.0
        n00 = n01 = n10 = n11 = 0
        for i in range(1, len(hits)):
            prev, cur = hits[i - 1], hits[i]
            if prev == 0 and cur == 0:
                n00 += 1
            elif prev == 0 and cur == 1:
                n01 += 1
            elif prev == 1 and cur == 0:
                n10 += 1
            else:
                n11 += 1

        pi01 = n01 / max(n00 + n01, 1)
        pi11 = n11 / max(n10 + n11, 1)
        pi = (n01 + n11) / max(n00 + n01 + n10 + n11, 1)

        ll_null = (n00 + n10) * math.log(max(1.0 - pi, _EPS)) + (n01 + n11) * math.log(max(pi, _EPS))
        ll_alt = (
            n00 * math.log(max(1.0 - pi01, _EPS))
            + n01 * math.log(max(pi01, _EPS))
            + n10 * math.log(max(1.0 - pi11, _EPS))
            + n11 * math.log(max(pi11, _EPS))
        )
        lr = max(-2.0 * (ll_null - ll_alt), 0.0)
        return lr, chi2_sf_df1(lr)
