"""导入《江苏2025-2026年国网代理购电价格.xlsx》。

三张表分别入库：
  电价表        -> price_sgcc（代理购电价格/线损/政府性基金/系统运行费用）  + sgcc_tariff（输配电价/容需量）
  系统运行费用  -> price_sgcc.system_op_breakdown（10 项明细）
  峰谷时段表    -> tou_rules（12 个月各自的 96 点峰/平/谷）

单位：源文件为 元/kWh，库内统一 元/MWh（×1000）。

用法：
  python -m webapp.scripts.import_grid_price --excel /path/江苏2025-2026年国网代理购电价格.xlsx
"""
import argparse
import re
from datetime import datetime

import openpyxl
from bson import ObjectId

from webapp.tools.mongo import DATABASE

K = 1000.0
PRICE = DATABASE["price_sgcc"]
TOU = DATABASE["tou_rules"]
TARIFF = DATABASE["sgcc_tariff"]

SYSTEM_OP_KEYS = [
    "辅助服务费用", "抽水蓄能容量电费", "天然气发电容量电费", "电价交叉补贴新增损益",
    "电力保供购电费用", "上网环节线损代理采购损整", "峰谷分时电价损益", "力调电费损益",
    "煤电容量电费", "新能源可持续发展价格结算机制差价结算费用",
]


def _month_num(label):
    s = str(label or "").strip().replace("月", "")
    try:
        m = int(float(s))
        return m if 1 <= m <= 12 else None
    except (TypeError, ValueError):
        return None


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _sections(ws, keyword):
    """返回 [(year, 标题行号), ...]，标题行下一行为表头，数据从 +2 开始。"""
    out = []
    for r in range(1, ws.max_row + 1):
        v = ws.cell(r, 1).value
        if isinstance(v, str) and keyword in v:
            m = re.search(r"(\d{4})", v)
            if m:
                out.append((int(m.group(1)), r))
    return out


def parse_price_table(ws):
    out = {}
    for year, base_row in _sections(ws, "国网代购电价格表"):
        data = {}
        for r in range(base_row + 2, base_row + 14):
            mon = _month_num(ws.cell(r, 1).value)
            if mon is None:
                continue
            data[mon] = {
                "purchase": _num(ws.cell(r, 2).value),
                "loss": _num(ws.cell(r, 3).value),
                "fund": _num(ws.cell(r, 4).value),
                "sysop": _num(ws.cell(r, 5).value),
            }
        out[year] = data
    return out


def parse_system_op(ws):
    out = {}
    for year, base_row in _sections(ws, "系统运行费"):
        headers = [ws.cell(base_row + 1, c).value for c in range(2, 12)]
        data = {}
        for r in range(base_row + 2, base_row + 14):
            mon = _month_num(ws.cell(r, 1).value)
            if mon is None:
                continue
            breakdown = {}
            for i, name in enumerate(SYSTEM_OP_KEYS):
                val = _num(ws.cell(r, 2 + i).value)
                if val is not None:
                    breakdown[name] = round(val * K, 3)
            data[mon] = breakdown
        out[year] = data
    return out


def parse_tou(ws):
    """峰谷时段表：月份 m 的属性列 = 2*m+1，数据行 4..99（96 点）。"""
    timelines = {m: [] for m in range(1, 13)}
    for m in range(1, 13):
        col = 2 * m + 1
        for r in range(4, 100):
            v = ws.cell(r, col).value
            timelines[m].append(str(v).strip() if v is not None else "平")
    return timelines


def parse_tariff(ws):
    """输配电价按(分类/电压)逐档；容需量按分类(两部制/单一制)取一档。"""
    entries = []
    capacity = {}
    category = None
    sub = None
    for r in range(3, 17):
        g = ws.cell(r, 7).value
        h = ws.cell(r, 8).value
        i = ws.cell(r, 9).value
        if g:
            category = str(g).strip()
        if h:
            sub = str(h).strip()
        dem = _num(ws.cell(r, 12).value)
        cap = _num(ws.cell(r, 13).value)
        # 容需量：每个分类只取第一条有效值（分类级，不是电压级）
        if category and category not in capacity and (dem is not None or cap is not None):
            capacity[category] = {"demand_price": dem, "capacity_price": cap}
        if not i:
            continue
        entries.append({
            "category": category,
            "sub": sub,
            "voltage": str(i).strip(),
            "transmission_price_old": _num(ws.cell(r, 10).value),
            "transmission_price": _num(ws.cell(r, 11).value),
        })
    return entries, capacity


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--excel", required=True)
    args = ap.parse_args()

    wb = openpyxl.load_workbook(args.excel, data_only=True)
    prices = parse_price_table(wb["电价表"])
    sysops = parse_system_op(wb["系统运行费用"])
    timelines = parse_tou(wb["峰谷时段表"])
    tariff, capacity = parse_tariff(wb["电价表"])

    # 清理之前误标为 2027 的示例数据
    removed = PRICE.delete_many({"_id": {"$regex": "^2027-"}}).deleted_count

    written = 0
    for year, months in prices.items():
        for mon, p in months.items():
            mid = "%d-%02d" % (year, mon)
            purchase = p.get("purchase") or 0
            loss = p.get("loss") or 0
            fund = p.get("fund") or 0
            sysop = p.get("sysop") or 0
            doc = {
                "_id": mid,
                "month": mid,
                "purchase_price": round(purchase * K, 2),
                "network_loss_price": round(loss * K, 2),
                "gov_fund": round(fund * K, 2),
                "system_op_cost": round(sysop * K, 2),
                "avg_on_grid_price": round((purchase + loss + fund + sysop) * K, 2),
                "system_op_breakdown": sysops.get(year, {}).get(mon, {}),
                "attachment_name": "江苏%d年国网代理购电价格.xlsx" % year,
                "source": "excel_2025_2026",
                "note": "avg_on_grid_price 不含输配电价与容需量，明细见 sgcc_tariff",
                "imported_at": datetime.utcnow(),
            }
            PRICE.replace_one({"_id": mid}, doc, upsert=True)
            written += 1

    # 峰谷时段：清空旧 base 规则，按 2026 年逐月写入
    removed_tou = TOU.delete_many({"type": "base"}).deleted_count
    tou_cnt = 0
    for m in range(1, 13):
        tl = timelines[m]
        if len(tl) != 96:
            continue
        TOU.insert_one({
            "_id": ObjectId(),
            "type": "base",
            "name": "2026年峰谷时段表（国网公告）",
            "months": [m],
            "activation_date": datetime(2026, 1, 1),
            "timelines": tl,
            # 峰谷浮动系数（代购目录电价口径，两部制）：峰1.8/平1.0/谷0.35
            "coefficients": {"峰": 1.8, "平": 1.0, "谷": 0.35},
            "coefficient_source": "代理购电目录电价口径(两部制)；单一制 峰1.7/1.6、谷0.35",
            "source": "国网2026年峰谷时段表",
            "created_at": datetime.utcnow(),
        })
        tou_cnt += 1

    # 输配电价/容需量
    TARIFF.replace_one(
        {"_id": "2025-2026"},
        {"_id": "2025-2026", "entries": tariff, "capacity_charge": capacity,
         "note": "输配电价单位元/kWh；容需量：需量 元/千瓦·月、容量 元/千伏安·月（按分类）",
         "imported_at": datetime.utcnow()},
        upsert=True,
    )

    print("price_sgcc 写入:", written, "条；删除旧2027:", removed, "条；当前总数:", PRICE.count_documents({}))
    print("tou_rules 写入:", tou_cnt, "条（删除旧base", removed_tou, "）；当前base数:", TOU.count_documents({"type": "base"}))
    print("sgcc_tariff 电压档位数:", len(tariff), "容需量分类:", list(capacity.keys()))
    for m in (1, 7, 12):
        tl = timelines[m]
        print("  %d月 峰/平/谷 点数:" % m,
              sum(1 for x in tl if x == "峰"), sum(1 for x in tl if x == "平"), sum(1 for x in tl if x == "谷"))


if __name__ == "__main__":
    main()
