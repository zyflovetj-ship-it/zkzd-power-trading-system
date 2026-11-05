"""导入中长期成交价 → contracts_aggregated_daily（供「中长期价格分析」使用）。

Excel 列（表头驱动识别，顺序不限）：
  日期     必填  YYYY-MM-DD（也接受 2026/10/15）
  品种     可选  年度/月度/月内/年度双边/月度集中竞价…（缺省"整体"）
  时段     可选  峰/平/谷/整体 或 具体时刻 00:00（缺省"整体"）
  电量     必填  MWh
  价格     必填  元/MWh
  实体     可选  缺省"全市场"

落库规则（每个 日期+实体 生成三类文档，贴合 ContractPriceService 约定）：
  1) contract_type=整体,  contract_period=整体   → 日汇总（daily_total_quantity/daily_avg_price）
  2) contract_type=品种,  contract_period=整体   → 各品种汇总
  3) contract_type=品种,  contract_period=时段   → 时段明细（periods 数组）

用法：
  python -m webapp.scripts.import_contract_price --excel /path/中长期成交价.xlsx
"""
import argparse
import os
import re
from collections import defaultdict
from datetime import datetime

import openpyxl

from webapp.tools.mongo import DATABASE

COL = DATABASE["contracts_aggregated_daily"]

ALIASES = {
    "date": ("日期", "交易日期", "date"),
    "type": ("品种", "交易品种", "合同类型", "contract_type"),
    "period": ("时段", "时段类型", "合同周期", "contract_period"),
    "quantity": ("电量", "成交电量", "quantity"),
    "price": ("价格", "成交价", "成交均价", "price"),
    "entity": ("实体", "市场主体", "entity"),
}


def _norm(v):
    return "".join(str(v or "").split())


def _to_f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_date(v):
    if hasattr(v, "strftime"):
        return v.strftime("%Y-%m-%d")
    s = str(v or "").strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%Y.%m.%d", "%Y-%m-%d %H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", s)
    if m:
        return "%s-%02d-%02d" % (m.group(1), int(m.group(2)), int(m.group(3)))
    return None


def _col_map(ws):
    m = {}
    for c in range(1, ws.max_column + 1):
        h = _norm(ws.cell(1, c).value)
        if not h:
            continue
        for key, kws in ALIASES.items():
            if key in m:
                continue
            if any(k in h for k in kws):
                m[key] = c
    return m


def load_rows(path):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[wb.sheetnames[0]]
    cols = _col_map(ws)
    missing = [k for k in ("date", "quantity", "price") if k not in cols]
    if missing:
        wb.close()
        raise ValueError("缺少必需列: %s（已识别列: %s）" % (missing, list(cols)))

    rows = []
    for r in range(2, ws.max_row + 1):
        d = _parse_date(ws.cell(r, cols["date"]).value)
        q = _to_f(ws.cell(r, cols["quantity"]).value)
        p = _to_f(ws.cell(r, cols["price"]).value)
        if not d or q is None or p is None:
            continue
        ctype = _norm(ws.cell(r, cols["type"]).value) if "type" in cols else "整体"
        period = _norm(ws.cell(r, cols["period"]).value) if "period" in cols else "整体"
        entity = _norm(ws.cell(r, cols["entity"]).value) if "entity" in cols else "全市场"
        rows.append({
            "date": d, "entity": entity or "全市场",
            "contract_type": ctype or "整体",
            "contract_period": period or "整体",
            "quantity": q, "price": p,
        })
    wb.close()
    return rows


def _agg(items):
    q = sum(x["quantity"] for x in items)
    amt = sum(x["quantity"] * x["price"] for x in items)
    return round(q, 4), (round(amt / q, 4) if q else 0.0), round(amt, 2)


def upsert(rows):
    grouped = defaultdict(list)
    for r in rows:
        grouped[(r["date"], r["entity"])].append(r)

    written = 0
    for (date, entity), items in grouped.items():
        # 1) 整体/整体
        q, p, amt = _agg(items)
        periods = [{
            "period": x["contract_period"],
            "quantity_mwh": x["quantity"],
            "price_yuan_per_mwh": x["price"],
        } for x in items]
        COL.replace_one(
            {"date": date, "entity": entity, "contract_type": "整体", "contract_period": "整体"},
            {"date": date, "entity": entity, "contract_type": "整体", "contract_period": "整体",
             "date_str": date,
             "daily_total_quantity": q, "daily_avg_price": p, "daily_amount": amt,
             "periods": periods, "source": "excel_import"},
            upsert=True,
        )
        written += 1

        # 2) 按品种汇总
        by_type = defaultdict(list)
        for x in items:
            by_type[x["contract_type"]].append(x)
        for ctype, its in by_type.items():
            q2, p2, amt2 = _agg(its)
            COL.replace_one(
                {"date": date, "entity": entity, "contract_type": ctype, "contract_period": "整体"},
                {"date": date, "entity": entity, "contract_type": ctype, "contract_period": "整体",
                 "date_str": date,
                 "daily_total_quantity": q2, "daily_avg_price": p2, "daily_amount": amt2,
                 "periods": [{"period": x["contract_period"],
                              "quantity_mwh": x["quantity"],
                              "price_yuan_per_mwh": x["price"]} for x in its],
                 "source": "excel_import"},
                upsert=True,
            )
            written += 1

        # 3) 按 (品种, 时段) 明细
        by_tp = defaultdict(list)
        for x in items:
            by_tp[(x["contract_type"], x["contract_period"])].append(x)
        for (ctype, period), its in by_tp.items():
            q3, p3, amt3 = _agg(its)
            COL.replace_one(
                {"date": date, "entity": entity, "contract_type": ctype, "contract_period": period},
                {"date": date, "entity": entity, "contract_type": ctype, "contract_period": period,
                 "date_str": date,
                 "daily_total_quantity": q3, "daily_avg_price": p3, "daily_amount": amt3,
                 "periods": [{"period": period,
                              "quantity_mwh": x["quantity"],
                              "price_yuan_per_mwh": x["price"]} for x in its],
                 "source": "excel_import"},
                upsert=True,
            )
            written += 1
    return written


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", required=True)
    args = ap.parse_args()
    rows = load_rows(args.excel)
    if not rows:
        print("未解析到有效数据行")
        return
    n = upsert(rows)
    print("解析 %d 行，写入/更新 %d 条文档，当前总数 %d" % (len(rows), n, COL.count_documents({})))
    dates = sorted({r["date"] for r in rows})
    print("覆盖日期: %s ~ %s（%d 天）" % (dates[0], dates[-1], len(dates)))


if __name__ == "__main__":
    main()
