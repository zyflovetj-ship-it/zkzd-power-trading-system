"""
风险引擎 P1 自测：回测统计检验 + 压力测试变换逻辑

用法：
    cd /data/zk-App/zk-energy-new && python -m webapp.scripts.selfcheck_risk_p1

不依赖 MongoDB：用 FakeDB + 构造的 96 点敞口曲线做纯逻辑校验。
"""

from __future__ import annotations

import math
import sys
from datetime import date
from typing import List, Tuple

from webapp.models.risk import PERIODS_PER_DAY, ExposureBucket, PeriodExposure, bucket_of, period_label
from webapp.models.risk_advanced import StressScenario
from webapp.services.risk_backtest_service import (
    RiskBacktestService,
    chi2_sf_df1,
    chi2_sf_df2,
)
from webapp.services.risk_stress_service import RiskStressService

FAILED: List[Tuple[str, str]] = []


def check(name: str, cond: bool, detail: str = "") -> None:
    if cond:
        print(f"  [PASS] {name}")
    else:
        print(f"  [FAIL] {name} {detail}")
        FAILED.append((name, detail))


def approx(a: float, b: float, tol: float = 1e-3) -> bool:
    return abs(a - b) <= tol


class _FakeCol:
    def find(self, *a, **k):
        return []

    def count_documents(self, *a, **k):
        return 0

    def insert_one(self, *a, **k):
        return None


class FakeDB:
    risk_limit = _FakeCol()
    risk_stress_scenario = _FakeCol()
    risk_alert_event = _FakeCol()


def make_exposure(contract=0.2, load=0.1, price=400.0):
    """构造 96 点平坦敞口曲线。"""
    curve = []
    for i in range(PERIODS_PER_DAY):
        net = contract - load
        curve.append(
            PeriodExposure(
                period_index=i,
                period_label=period_label(i),
                timestamp=__import__("datetime").datetime(2026, 1, 1, i // 4, (i % 4) * 15),
                bucket=bucket_of(i),
                contract_mwh=contract,
                load_mwh=load,
                net_position_mwh=round(net, 6),
                fwd_price=price,
                price_exposure=round(net * price, 2),
            )
        )
    return {"summary": None, "curve": curve}


# ---------------------------------------------------------------- 1. 卡方


def test_chi2() -> None:
    print("\n[1] 卡方生存函数")
    # chi2(1) 95% 临界值 3.841 -> p=0.05
    check("chi2_sf_df1(3.841) ≈ 0.05", approx(chi2_sf_df1(3.841), 0.05, 1e-3),
          f"got {chi2_sf_df1(3.841):.5f}")
    # chi2(2) 95% 临界值 5.991 -> p=0.05
    check("chi2_sf_df2(5.991) ≈ 0.05", approx(chi2_sf_df2(5.991), 0.05, 1e-3),
          f"got {chi2_sf_df2(5.991):.5f}")
    check("x=0 时 p=1", approx(chi2_sf_df1(0.0), 1.0))


# ------------------------------------------------------------- 2. Kupiec


def test_kupiec() -> None:
    print("\n[2] Kupiec POF 检验")
    # 250 天、名义 5% -> 期望 12.5 次。实测 12 次应通过
    lr, p = RiskBacktestService.kupiec_pof(250, 12, 0.05)
    check("n=250,x=12 不拒绝 H0 (p>0.05)", p > 0.05, f"lr={lr:.3f} p={p:.4f}")
    check("n=250,x=12 LR 很小", lr < 3.841, f"lr={lr:.3f}")

    # 实测 30 次（远超期望）应拒绝
    lr2, p2 = RiskBacktestService.kupiec_pof(250, 30, 0.05)
    check("n=250,x=30 拒绝 H0 (p<0.05)", p2 < 0.05, f"lr={lr2:.3f} p={p2:.4f}")

    # 实测 0 次（过于保守）也应拒绝
    lr3, p3 = RiskBacktestService.kupiec_pof(250, 0, 0.05)
    check("n=250,x=0 拒绝 H0 (过于保守)", p3 < 0.05, f"lr={lr3:.3f} p={p3:.4f}")

    # 边界：n=0
    lr4, p4 = RiskBacktestService.kupiec_pof(0, 0, 0.05)
    check("n=0 返回 p=1", approx(p4, 1.0))


# ------------------------------------------------- 3. Christoffersen


def test_christoffersen() -> None:
    print("\n[3] Christoffersen 独立性检验")
    # 全无突破：无转移信息，LR 应为 0
    lr, p = RiskBacktestService.christoffersen_ind([0] * 100)
    check("全 0 序列 LR=0", approx(lr, 0.0, 1e-6), f"lr={lr}")
    check("全 0 序列 p=1", approx(p, 1.0, 1e-6))

    # 突破成簇（连续 10 个 1 夹在 0 中）应显著
    hits = [0] * 45 + [1] * 10 + [0] * 45
    lr2, p2 = RiskBacktestService.christoffersen_ind(hits)
    check("成簇突破 p<0.05", p2 < 0.05, f"lr={lr2:.3f} p={p2:.4f}")

    # 随机稀疏突破应不显著
    import random
    random.seed(42)
    hits3 = [1 if random.random() < 0.05 else 0 for _ in range(400)]
    lr3, p3 = RiskBacktestService.christoffersen_ind(hits3)
    check("稀疏随机突破 p>0.05", p3 > 0.05, f"lr={lr3:.3f} p={p3:.4f}")

    # 单元素序列
    lr4, p4 = RiskBacktestService.christoffersen_ind([1])
    check("单元素序列 p=1", approx(p4, 1.0))


# ------------------------------------------------------- 4. 压力测试变换


def test_stress_transform() -> None:
    print("\n[4] 压力测试场景变换")
    svc = RiskStressService(FakeDB())
    exp = make_exposure(contract=0.2, load=0.1, price=400.0)
    # 基准：net=0.1 MWh/点 × 400 元 × 96 = 3840 元
    base_amount = 0.1 * 400.0 * PERIODS_PER_DAY

    # 价格翻倍：净多头，涨价有利 -> 冲击 +3840
    r = svc.run_scenario(
        date(2026, 1, 1),
        StressScenario(scenario_id="t-up", name="价格×2", category="价格", price_mult=2.0),
        base_exposure=exp,
    )
    check("基准敞口 3840 元", approx(r.base_price_exposure, base_amount, 1.0),
          f"got {r.base_price_exposure}")
    check("价格×2 冲击 = +3840 元", approx(r.pnl_impact, base_amount, 1.0),
          f"got {r.pnl_impact}")

    # 价格腰斩：冲击 -1920
    r2 = svc.run_scenario(
        date(2026, 1, 1),
        StressScenario(scenario_id="t-down", name="价格×0.5", category="价格", price_mult=0.5),
        base_exposure=exp,
    )
    check("价格×0.5 冲击 = -1920 元", approx(r2.pnl_impact, -base_amount / 2, 1.0),
          f"got {r2.pnl_impact}")
    check("价格下跌时估算保证金追加 > 0", r2.margin_call_estimate > 0)

    # 合约违约：net 变 -0.1，冲击 = -0.1*400*96 - 3840 = -7680
    r3 = svc.run_scenario(
        date(2026, 1, 1),
        StressScenario(scenario_id="t-default", name="合约违约", category="信用", contract_mult=0.0),
        base_exposure=exp,
    )
    expected = -0.1 * 400.0 * PERIODS_PER_DAY - base_amount
    check("合约违约冲击 = -7680 元", approx(r3.pnl_impact, expected, 1.0),
          f"got {r3.pnl_impact}, want {expected}")
    check("违约场景最不利时段可定位", 0 <= r3.worst_period_index < PERIODS_PER_DAY)

    # 偏差考核：load×1.1 -> 偏差 0.01*96=0.96 MWh, 罚金 0.96*1000*0.1 = 96 元
    r4 = svc.run_scenario(
        date(2026, 1, 1),
        StressScenario(scenario_id="t-pen", name="偏差考核", category="考核",
                       load_mult=1.10, penalty_rate=0.1),
        base_exposure=exp,
    )
    check("偏差考核罚金 ≈ 96 元", approx(r4.penalty_estimate, 96.0, 1.0),
          f"got {r4.penalty_estimate}")
    check("罚金计入 pnl_impact", r4.pnl_impact < r4.stressed_price_exposure - r4.base_price_exposure + 1e-6)

    # 峰段单独放大
    r5 = svc.run_scenario(
        date(2026, 1, 1),
        StressScenario(scenario_id="t-peak", name="峰段×2.5", category="价格", peak_price_mult=2.5),
        base_exposure=exp,
    )
    check("峰段放大只影响峰时段", r5.pnl_impact > 0 and r5.pnl_impact < base_amount,
          f"got {r5.pnl_impact}")


def main() -> int:
    print("=" * 60)
    print("风险引擎 P1 自测（回测 + 压力测试）")
    print("=" * 60)
    test_chi2()
    test_kupiec()
    test_christoffersen()
    test_stress_transform()

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
