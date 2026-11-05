"""江苏 2027 新规逐点引擎 · 全年 12 月 Excel 回归对拍。

基准来源：《套餐测算模板-新v2.xlsx》峰谷时段表 / 分时（1-12月）。
每月比对：T9 零售分摊 / T10 用户电价 / T2 零售参考价 / T3 封顶价 / T11 非分时 / T12 最终 / T13 非分时最终。
Excel 未填数的月份（如 11/12 月）自动跳过。
判定：误差 < 0.01 元/MWh。

用法：PYTHONPATH=. python3 tests/test_pricing_2027_12m.py
"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from webapp.services.pricing_engine import PricingEngine  # noqa: E402

GOLDEN = os.path.join(os.path.dirname(__file__), "fixtures", "jiangsu2027_12m_golden.json")
TOL = 0.01


def main() -> int:
    data = json.load(open(GOLDEN, encoding="utf8"))
    total_ok = total_bad = 0
    print("=== 江苏2027 逐点引擎 vs Excel《套餐测算模板-新v2》全年12月 ===")
    for m in range(1, 13):
        d = data.get(str(m)) or data.get(m)
        if not d:
            continue
        g = d["golden"]
        if g.get("T10") is None or g.get("T3") is None:
            print("  %2d月  跳过（Excel 未填数）" % m)
            continue
        params = {
            "service_fee": 2.0,
            "peak_coef": float(g.get("P4") or 1.6),
            "valley_coef": 0.4,
            "f_ratio": float(g.get("T14") and 0.05 or 0.05),
            "k1_share": 1.0, "k2_share": 1.0, "k3_share": 0.0,
            "green_mode": "否",
        }
        market = {
            "wholesale_price": g["T4"],
            "share_cost_compensation": g.get("T5") or 0.0,
            "share_imbalance": g.get("T6") or 0.0,
            "share_market_adjust": g.get("T7") or 0.0,
        }
        points = {"labels": d["labels"], "curve": d["curve"],
                  "wholesale": d["wholesale"], "max_pnt": d["max_pnt"]}
        r = PricingEngine.calculate_jiangsu_2027_pointwise(params, points, market)
        checks = [
            ("T9", r["share"]["retail"], g.get("T9")),
            ("T10", r["energy_avg_price"], g.get("T10")),
            ("T2", r["prices"]["reference_price"], g.get("T2")),
            ("T3", r["cap_price"], g.get("T3")),
            ("T11", r["non_tou_price"], g.get("T11")),
            ("T12", r["settle_price"], g.get("T12")),
            ("T13", r["settle_price_non_tou"], g.get("T13")),
        ]
        bad = []
        for name, calc, gold in checks:
            if gold is None:
                continue
            if abs(calc - gold) >= TOL:
                bad.append("%s(%.3f vs %.3f)" % (name, calc, gold))
        if bad:
            total_bad += len(bad)
            print("  %2d月  ❌ %s" % (m, " ".join(bad)))
        else:
            total_ok += 1
            print("  %2d月  ✅ 全部命中（T10=%.3f T3=%.3f T12=%.3f）"
                  % (m, r["energy_avg_price"], r["cap_price"], r["settle_price"]))
    print()
    ok = total_bad == 0
    print(("PASS ✅ %d 个月全部命中 Excel（误差 < %.2f）" % (total_ok, TOL)) if ok
          else ("FAIL ❌ 共 %d 处偏差" % total_bad))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
