"""江苏 2027 新规逐点引擎 · Excel 回归对拍测试。

基准来源：《套餐测算模板-新v2.xlsx》 峰谷时段表 / 分时（1月，24 时段）。
黄金值：T2 零售参考价 / T3 封顶价 / T9 零售分摊 / T10 用户电价 / T11 非分时 / T12 最终(分时) / T13 非分时最终。
判定：与 Excel 单元格值误差 < 0.01 元/MWh 即通过。

用法：
    python3 -m tests.test_pricing_2027_regression      # 在仓库根目录执行
或：
    PYTHONPATH=. python3 tests/test_pricing_2027_regression.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from webapp.services.pricing_engine import PricingEngine  # noqa: E402

GOLDEN_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "jiangsu2027_1m_golden.json")
MIDLONG_BLOCKS_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "jiangsu2027_midlong_blocks_1m.json")
TOL = 0.01


def _cmp(name, calc, gold, results):
    ok = abs(calc - gold) < TOL
    results.append(ok)
    print("  %-16s calc=%10.3f  gold=%10.3f  diff=%+.4f  %s"
          % (name, calc, gold, calc - gold, "OK" if ok else "MISMATCH!"))
    return ok


def _test_mid_long_price(results=None):
    """逐点中长期价回归：12 合同块 1 月量价 -> 24 点加权价，对比 Excel 分时!B142:B165。"""
    if results is None:
        results = []
    if not os.path.exists(MIDLONG_BLOCKS_PATH):
        print("(跳过：缺 midlong fixture)")
        return results
    d = json.load(open(MIDLONG_BLOCKS_PATH, encoding="utf8"))
    blocks, gold = d["blocks"], d["gold"]
    calc = []
    for t in range(24):
        num = den = 0.0
        for b in blocks:
            v = b["volumes"][t]
            num += v * b["prices"][t]
            den += v
        calc.append(round(num / den, 3) if den > 0 else 0.0)
    print("=== 逐点中长期价（12 合同块加权）vs Excel 分时!B142:B165 ===")
    bad = 0
    for t in range(24):
        ok = abs(calc[t] - (gold[t] or 0)) < TOL
        if not ok:
            bad += 1
            print("  t%02d calc=%.3f gold=%r MISMATCH" % (t, calc[t], gold[t]))
    results.append(bad == 0)
    print("  24 点%s" % ("全部命中 ✅" if bad == 0 else ("%d 点偏差 ❌" % bad)))
    return results


def main() -> int:
    d = json.load(open(GOLDEN_PATH, encoding="utf8"))
    g, p, sh = d["golden"], d["params"], d["share"]

    params = {
        "service_fee": p["P3_fee"],
        "peak_coef": p["P4_peak"],
        "valley_coef": p["P5_valley"],
        "f_ratio": p["P6_F"],
        "k1_share": p["P9_K1"],
        "k2_share": p["P10_K2s"],
        "k3_share": p["P11_K3"],
        "green_mode": "否",
    }
    market = {
        "wholesale_price": g["T4"],
        "share_cost_compensation": sh["cc"],
        "share_imbalance": sh["imb"],
        "share_market_adjust": sh["ma"],
    }
    points = {
        "labels": d["labels"],
        "curve": d["curve"],
        "wholesale": d["wholesale"],
        "max_pnt": d["max_pnt"],
    }

    r = PricingEngine.calculate_jiangsu_2027_pointwise(params, points, market)

    print("=== 江苏2027 逐点引擎 vs Excel《套餐测算模板-新v2》1月 ===")
    results = []
    _cmp("T9 零售分摊", r["share"]["retail"], g["T9"], results)
    _cmp("T10 用户电价", r["energy_avg_price"], g["T10"], results)
    _cmp("T2 零售参考价", r["prices"]["reference_price"], g["T2"], results)
    _cmp("T3 封顶价", r["cap_price"], g["T3"], results)
    _cmp("T11 非分时", r["non_tou_price"], g["T11"], results)
    _cmp("T12 最终(分时)", r["settle_price"], g["T12"], results)
    _cmp("T13 非分时最终", r["settle_price_non_tou"], g["T13"], results)

    # 逐点中长期价（合同块加权）
    results = _test_mid_long_price(results)

    ok = all(results)
    print("\n" + ("PASS ✅ 全部命中 Excel 黄金值（误差 < %.2f）" % TOL if ok
                  else "FAIL ❌ 存在偏差"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
