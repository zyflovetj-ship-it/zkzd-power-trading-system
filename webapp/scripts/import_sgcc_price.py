"""国网代购电价导入脚本（写入 price_sgcc 集合）。

支持两种来源：
  1) Excel《套餐测算模板-新v2.xlsx》的「代购电情况」页（行2=代购电价格 元/kWh，行3=用户代购电均价 元/kWh）
  2) JSON 列表：[{"month":"2027-01","price_kwh":0.3937,"avg_kwh":0.41865}, ...]

用法：
  python -m webapp.scripts.import_sgcc_price --excel /path/套餐测算模板-新v2.xlsx --year 2027
  python -m webapp.scripts.import_sgcc_price --json /path/sgcc_seed.json
"""
import argparse
import json
import sys
from datetime import datetime

from webapp.tools.mongo import DATABASE

COLLECTION = DATABASE["price_sgcc"]


def _records_from_excel(path, year):
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb["代购电情况"]
    price = [ws.cell(2, c).value for c in range(2, 14)]   # 1..12 月
    avg = [ws.cell(3, c).value for c in range(2, 14)]
    out = []
    for i in range(12):
        p = price[i]
        if p in (None, 0):
            continue
        out.append({
            "month": f"{year}-{i + 1:02d}",
            "price_kwh": float(p),
            "avg_kwh": float(avg[i] or 0),
        })
    return out


def _records_from_json(path):
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


def upsert(records, source):
    n = 0
    for rec in records:
        mid = rec["month"]
        price_kwh = float(rec["price_kwh"])
        avg_kwh = float(rec.get("avg_kwh") or 0)
        doc = {
            "_id": mid,
            "month": mid,
            "purchase_price": round(price_kwh * 1000, 2),       # 元/MWh
            "avg_on_grid_price": round(avg_kwh * 1000, 2),      # 元/MWh
            "purchase_scale_kwh": rec.get("purchase_scale_kwh", 0),
            "historical_deviation_discount": rec.get("historical_deviation_discount", 0),
            "network_loss_price": rec.get("network_loss_price", 0),
            "system_op_cost_discount": rec.get("system_op_cost_discount", 0),
            "attachment_name": rec.get("attachment_name") or f"{mid}电网代理购电价格公告.pdf",
            "full_data": {"price_composition": [
                ["项目", "金额（元/千瓦时）"],
                ["一、代理购电价格", f"{price_kwh:.4f}"],
            ]},
            "source": source,
            "imported_at": datetime.utcnow(),
        }
        COLLECTION.replace_one({"_id": mid}, doc, upsert=True)
        n += 1
    return n


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel")
    ap.add_argument("--json")
    ap.add_argument("--year", type=int, default=2027)
    args = ap.parse_args()

    if args.excel:
        records = _records_from_excel(args.excel, args.year)
        source = "套餐测算模板-新v2"
    elif args.json:
        records = _records_from_json(args.json)
        source = "json_import"
    else:
        print("必须指定 --excel 或 --json")
        sys.exit(1)

    n = upsert(records, source)
    print(f"已写入/更新 {n} 条 price_sgcc 记录，当前总数 {COLLECTION.count_documents({})}")


if __name__ == "__main__":
    main()
