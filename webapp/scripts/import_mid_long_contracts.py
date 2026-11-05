"""中长期/绿电合同量价导入脚本（写入 mid_long_contracts 集合）。

数据源：《套餐测算模板-新v2.xlsx》「中长期及绿电量价数据」页。
  12 个合同块 × 12 个月 × 24 时段 -> 电量(C..N列) + 价格(Q列)。
  年度类合同(年度合计/年度绿电)价格取该块首行(对齐 Excel $Q$2/$Q$32 绝对引用)。

用法：
  python -m webapp.scripts.import_mid_long_contracts --excel /path/套餐测算模板-新v2.xlsx --year 2027
  python -m webapp.scripts.import_mid_long_contracts --json /path/midlong.json --year 2027
"""
import argparse
import json
import sys

from webapp.tools.mongo import DATABASE

COLLECTION = DATABASE["mid_long_contracts"]

#: 12 个合同块的表头行（Excel 中长期及绿电量价数据页）
_BLOCK_START_ROWS = [1, 31, 59, 88, 115, 142, 169, 196, 223, 250, 277, 304]
#: 年度类块（价格取首行）
_ANNUAL_BLOCKS = {1, 31}


def _detect_block_rows(ws):
    """动态定位 12 个合同块的表头行（B列有合同名 且 C列=='1月'）。

    兼容两种布局：官方模板（块间距不规则）与自生成模板（每块 26 行）。
    """
    starts = []
    for r in range(1, ws.max_row + 1):
        c = ws.cell(r, 3).value
        b = ws.cell(r, 2).value
        if c == "1月" and b:
            starts.append(r)
    return starts


def _records_from_excel(path, year, customer_id=None, customer_name=None):
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["中长期及绿电量价数据"]
    # 时段标签：优先取峰谷时段表；缺失则用默认 24 时段
    if "峰谷时段表" in wb.sheetnames:
        tou = wb["峰谷时段表"]
        time_labels = [tou.cell(r, 1).value for r in range(3, 27)]
    else:
        from webapp.models.mid_long_contract import TIME_PERIODS as _TP
        time_labels = list(_TP)

    block_rows = _detect_block_rows(ws)
    if not block_rows:
        # 回退到官方模板固定行
        block_rows = list(_BLOCK_START_ROWS)

    out = []
    for s in block_rows:
        ct = ws.cell(s, 2).value
        if not ct:
            continue
        is_annual = ct in ("年度合计", "年度绿电")
        # 年度块价格也按【逐时段】读取：Excel 零售参考价 B116 引用的是 $B83/$B84...
        # （列绝对、行相对），即每个时段各自的年度合同价，不是全时段统一首行价。
        # 若某年度块非首行价为空，则回退首行价（兼容只填首行的手工模板）。
        first_price = ws.cell(s + 1, 17).value
        for m in range(12):
            col = 3 + m  # C=1月
            for t in range(24):
                r = s + 1 + t
                vol = ws.cell(r, col).value
                price = ws.cell(r, 17).value
                if is_annual and t > 0 and (price is None or price == ""):
                    price = first_price
                if isinstance(price, str):
                    price = None if price.startswith("=") else price
                # 无电量即跳过（价格为时段维度、全年共享，避免空月份产生冗余0量记录）
                if vol is None or vol == "":
                    continue
                try:
                    vol_f = float(vol or 0)
                except (TypeError, ValueError):
                    vol_f = 0.0
                try:
                    pr_f = float(price or 0)
                except (TypeError, ValueError):
                    pr_f = 0.0
                out.append({
                    "year": year,
                    "customer_id": customer_id,
                    "customer_name": customer_name,
                    "month": m + 1,
                    "contract_type": ct,
                    "time_index": t,
                    "time_period": time_labels[t] if t < len(time_labels) else "",
                    "volume_mwh": round(vol_f, 4),
                    "price": round(pr_f, 3),
                })
    return out


def _records_from_json(path, year, customer_id=None, customer_name=None):
    data = json.load(open(path, encoding="utf8"))
    items = data.get("records") if isinstance(data, dict) else data
    out = []
    for it in items:
        out.append({
            "year": year,
            "customer_id": it.get("customer_id", customer_id),
            "customer_name": it.get("customer_name", customer_name),
            "month": int(it["m"] if "m" in it else it["month"]),
            "contract_type": it.get("ct") or it.get("contract_type"),
            "time_index": int(it["t"] if "t" in it else it["time_index"]),
            "time_period": it.get("time") or it.get("time_period"),
            "volume_mwh": round(float(it.get("vol") or it.get("volume_mwh") or 0), 4),
            "price": round(float(it.get("price") or 0), 3),
        })
    return out


def main():
    ap = argparse.ArgumentParser(description="导入中长期/绿电合同量价")
    ap.add_argument("--excel", help="套餐测算模板-新v2.xlsx 路径")
    ap.add_argument("--json", help="JSON 数据路径")
    ap.add_argument("--year", type=int, required=True, help="年份，如 2027")
    ap.add_argument("--customer-id", default=None, help="客户ID（不填=全市场统一合同价）")
    ap.add_argument("--customer-name", default=None, help="客户名称（可选，便于展示）")
    ap.add_argument("--replace", action="store_true", default=True, help="覆盖同年度旧数据（默认是）")
    args = ap.parse_args()

    if args.excel:
        records = _records_from_excel(args.excel, args.year, args.customer_id, args.customer_name)
    elif args.json:
        records = _records_from_json(args.json, args.year, args.customer_id, args.customer_name)
    else:
        print("必须指定 --excel 或 --json", file=sys.stderr)
        return 2

    if not records:
        print("未解析到任何记录", file=sys.stderr)
        return 2

    if args.replace:
        # 只清理"同年度 + 同客户"的旧数据，避免误删其他客户的合同
        del_q = {"year": args.year, "customer_id": args.customer_id}
        deleted = COLLECTION.delete_many(del_q).deleted_count
        who = args.customer_name or args.customer_id or "全市场统一"
        print("清理[%s]同年度旧数据 %d 条" % (who, deleted))
    COLLECTION.insert_many(records)
    # 索引（含 customer_id 便于客户级查询）
    try:
        COLLECTION.create_index([("year", 1), ("customer_id", 1), ("month", 1), ("contract_type", 1), ("time_index", 1)])
    except Exception:
        pass
    print("导入完成：%d 条（year=%d）" % (len(records), args.year))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
