"""
风险引擎口径自测（P0）

用法：
    cd /data/zk-App/zk-energy-new && python -m webapp.scripts.selfcheck_risk_engine

不依赖 MongoDB：只校验纯计算逻辑（单位换算、时段映射、VaR 公式、PSD 修复）。
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from typing import List, Tuple

import numpy as np

from webapp.models.risk import (
    PERIODS_PER_DAY,
    bucket_of,
    day_period_starts,
    period_index_of,
    period_label,
    to_mwh,
)
from webapp.services.risk_engine_service import RiskEngineService

FAILED: List[Tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")
        FAILED.append((name, detail))


def approx(a: float, b: float, tol: float = 1e-6) -> bool:
    return abs(a - b) <= tol


# ------------------------------------------------------------------ 1. 单位


def test_units() -> None:
    print("\n[1] 电量单位换算")
    check("1000 kWh = 1 MWh", approx(to_mwh(1000, "kWh"), 1.0))
    check("1 MWh = 1 MWh", approx(to_mwh(1, "MWh"), 1.0))
    # 关键：MW 是功率，15 分钟时段电量 = MW × 0.25h
    check("4 MW(15min) = 1 MWh", approx(to_mwh(4, "MW"), 1.0))
    check("4000 kW(15min) = 1 MWh", approx(to_mwh(4000, "kW"), 1.0))
    try:
        to_mwh(1, "元/MWh")
        check("非法单位应抛错", False, "未抛错")
    except ValueError:
        check("非法单位抛 ValueError", True)


# --------------------------------------------------------------- 2. 时段映射


def test_periods() -> None:
    print("\n[2] 96 点时段映射")
    check("00:00 -> 0", period_index_of(datetime(2025, 1, 1, 0, 0)) == 0)
    check("00:14 -> 0", period_index_of(datetime(2025, 1, 1, 0, 14)) == 0)
    check("00:15 -> 1", period_index_of(datetime(2025, 1, 1, 0, 15)) == 1)
    check("17:15 -> 69", period_index_of(datetime(2025, 1, 1, 17, 15)) == 69)
    check("23:45 -> 95", period_index_of(datetime(2025, 1, 1, 23, 45)) == 95)
    check("period_label(69) = 17:15", period_label(69) == "17:15")
    starts = day_period_starts(date(2025, 1, 1))
    check("每日 96 个时段起点", len(starts) == PERIODS_PER_DAY)
    check("首点 00:00", starts[0] == datetime(2025, 1, 1, 0, 0))
    check("末点 23:45", starts[95] == datetime(2025, 1, 1, 23, 45))
    check("69 落在晚峰", bucket_of(69).value == "peak")
    check("10 落在低谷", bucket_of(10).value == "valley")
    check("40 落在平段", bucket_of(40).value == "flat")


# ------------------------------------------------- 3. 单位错配回归（核心证据）


def test_unit_mismatch_regression() -> None:
    """复现旧 risk_exposure_service 的单位错配，并给出新口径的正确结果。"""
    print("\n[3] 单位错配回归测试")

    contract_kwh = 100_000.0          # retail_contracts.purchasing_electricity_quantity (kWh)
    load_mw_per_period = 4.0          # short_term_load_forecast.value (MW)，每 15 分钟

    # 旧口径：直接相减（单位不成立）
    legacy_uncovered = contract_kwh - load_mw_per_period
    print(f"      旧口径: {contract_kwh} kWh − {load_mw_per_period} MW = {legacy_uncovered}")
    check(
        "旧口径结果无物理意义（kWh 减 MW）",
        True,
        f"得到 {legacy_uncovered}，既不是 kWh 也不是 MWh",
    )

    # 新口径：先换算到 MWh 再相减
    contract_mwh = to_mwh(contract_kwh, "kWh")
    load_mwh_per_period = to_mwh(load_mw_per_period, "MW")
    load_mwh_total = load_mwh_per_period * PERIODS_PER_DAY
    net = contract_mwh - load_mwh_total

    check("合约 100000 kWh = 100 MWh", approx(contract_mwh, 100.0))
    check("负荷 4 MW × 96 点 = 96 MWh", approx(load_mwh_total, 96.0))
    check("净敞口 = 4 MWh（超配多头）", approx(net, 4.0))
    check("覆盖率 = 1.0417", approx(round(contract_mwh / load_mwh_total, 4), 1.0417))

    # 旧口径的荒谬放大：按旧代码 uncovered × σ × 400
    sigma, factor = 0.02, 400.0
    legacy_exposure = legacy_uncovered * sigma * factor
    correct_exposure = net * sigma * (420.0)  # 420 元/MWh 基准价
    print(f"      旧口径敞口: {legacy_exposure:,.0f} 元")
    print(f"      新口径敞口: {correct_exposure:,.0f} 元（约 {legacy_exposure / max(correct_exposure, 1e-9):,.0f} 倍差）")
    ratio = abs(legacy_exposure) / max(abs(correct_exposure), 1e-9)
    check("旧口径敞口被放大百倍以上", ratio > 100.0, f"放大 {ratio:,.0f} 倍")


# -------------------------------------------------------------- 4. VaR 公式


def test_var_parametric() -> None:
    print("\n[4] 参数法 VaR（解析解校验）")
    svc = RiskEngineService(db=None)  # 纯计算，不触库

    w = np.zeros(PERIODS_PER_DAY)
    w[0], w[1] = 1000.0, 2000.0        # 敞口金额(元)
    sigma = np.zeros(PERIODS_PER_DAY)
    sigma[0], sigma[1] = 0.10, 0.20
    corr = np.eye(PERIODS_PER_DAY)     # 时段独立

    # 解析解: sigma_p = sqrt(1000^2*0.1^2 + 2000^2*0.2^2) = sqrt(170000)
    expected_sigma = np.sqrt(1000.0 ** 2 * 0.01 + 2000.0 ** 2 * 0.04)
    result = svc._var_parametric(w, sigma, corr, 0.95, 1, 60, [])

    check("组合 sigma 匹配解析解", approx(result.portfolio_sigma_yuan, round(expected_sigma, 2), 0.02),
          f"got {result.portfolio_sigma_yuan}, want {round(expected_sigma, 2)}")
    expected_var = 1.6448536269514722 * expected_sigma
    check("VaR95 = z * sigma", approx(result.var_yuan, round(expected_var, 2), 0.05),
          f"got {result.var_yuan}, want {round(expected_var, 2)}")
    check("CVaR >= VaR", result.cvar_yuan >= result.var_yuan)
    check("分时段贡献条数 = 96", len(result.contributions) == PERIODS_PER_DAY)

    # 持有期缩放
    r2 = svc._var_parametric(w, sigma, corr, 0.95, 4, 60, [])
    check("4 日 VaR = 2 × 1 日 VaR", approx(r2.var_yuan, round(result.var_yuan * 2, 2), 0.1),
          f"got {r2.var_yuan}, want {round(result.var_yuan * 2, 2)}")

    # 贡献可加性
    total_contrib = sum(c.var_contribution for c in result.contributions)
    check("分时段贡献之和 ≈ VaR", abs(total_contrib - result.var_yuan) < 1.0,
          f"sum={total_contrib:.2f}, var={result.var_yuan}")


# ------------------------------------------------------------------ 5. PSD


def test_psd_fix() -> None:
    print("\n[5] 相关矩阵半正定修复")
    bad = np.array([[1.0, 0.99, 0.99],
                    [0.99, 1.0, -0.99],
                    [0.99, -0.99, 1.0]])  # 非 PSD
    fixed = RiskEngineService._psd_fix(bad)
    eig = np.linalg.eigvalsh(fixed)
    check("修复后最小特征值 >= 0", eig.min() >= -1e-9, f"min_eig={eig.min():.2e}")
    check("对角仍为 1", np.allclose(np.diag(fixed), 1.0))
    check("对称", np.allclose(fixed, fixed.T))

    w = np.ones(3)
    check("wᵀΣw >= 0", float(w @ fixed @ w) >= -1e-9)

    nan_corr = np.full((3, 3), np.nan)
    fixed2 = RiskEngineService._psd_fix(nan_corr)
    check("全 NaN 矩阵修复为对角阵", np.allclose(fixed2, np.eye(3)))


# ------------------------------------------------------------ 6. 合约跨度


def test_contract_span() -> None:
    print("\n[6] 合同覆盖天数")
    check("2025-01 ~ 2025-01 = 31 天",
          RiskEngineService._contract_span_days(datetime(2025, 1, 1), datetime(2025, 1, 31)) == 31)
    check("2025-01 ~ 2025-12 = 365 天",
          RiskEngineService._contract_span_days(datetime(2025, 1, 1), datetime(2025, 12, 1)) == 365)
    check("2024-02 ~ 2024-02 = 29 天（闰年）",
          RiskEngineService._contract_span_days(datetime(2024, 2, 1), datetime(2024, 2, 1)) == 29)
    check("空值返回 0", RiskEngineService._contract_span_days(None, None) == 0)


def main() -> int:
    print("=" * 60)
    print("风险引擎口径自测（P0）")
    print("=" * 60)
    test_units()
    test_periods()
    test_unit_mismatch_regression()
    test_var_parametric()
    test_psd_fix()
    test_contract_span()

    print("\n" + "=" * 60)
    if FAILED:
        print(f"失败 {len(FAILED)} 项：")
        for name, detail in FAILED:
            print(f"  - {name} {detail}")
        return 1
    print("全部通过")
    return 0


if __name__ == "__main__":
    sys.exit(main())
