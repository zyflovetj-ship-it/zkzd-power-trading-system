"""导入日文件中的竞价空间成分数据（日前/实时）。

日文件 sheet「日前」「实时」列（表头驱动识别）：
  时段 | 短期系统负荷 | 光伏汇总 | 风电汇总 | 受电计划 | 储能发电计划 | 燃机固定出力总值 | 煤电发电计划 | 竞价空间

落库：
  daily_release          <- 日前页
  actual_operation       <- 实时页
  real_time_generation   <- 实时页（风光/储能的发电口径映射）

用法：
  python -m webapp.scripts.import_bidding_space --dir /tmp/daily --year 2026
"""
import argparse
import os
import re
from datetime import datetime, timedelta

import openpyxl

from webapp.services.bidding_space_service import BiddingSpaceService
from webapp.tools.mongo import DATABASE

DR = DATABASE["daily_release"]
AO = DATABASE["actual_operation"]
RG = DATABASE["real_time_generation"]
SRC = "market_published"

COLS = {
    "load": ("短期系统负荷",),
    "pv": ("光伏汇总", "光伏"),
    "wind": ("风电汇总", "风电"),
    "tieline": ("受电计划", "受电"),
    "storage": ("储能发电计划", "储能"),
    "gas": ("燃机固定出力",),
    "coal": ("煤电发电计划",),
    "space": ("竞价空间",),
}


def _norm(v):
    return "".join(str(v or "").split())


def _to_f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _parse_date(name, year):
    b = os.path.splitext(os.path.basename(name))[0].strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", b)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^(\d{1,2})月(\d{1,2})日$", b)
    if m:
        return datetime(year, int(m.group(1)), int(m.group(2)))
    return None


def _time_str(v):
    """把时段单元格（time/字符串/时间戳）转成 00:15..24:00。"""
    if v is None:
        return None
    if hasattr(v, "hour") and hasattr(v, "minute"):
        h, mi = v.hour, v.minute
        if h == 0 and mi == 0:
            return "24:00"
        return "%02d:%02d" % (h, mi)
    s = str(v).strip()
    m = re.match(r"^(\d{1,2}):(\d{2})", s)
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if h == 0 and mi == 0:
            return "24:00"
        return "%02d:%02d" % (h, mi)
    return None


def _col_map(ws):
    m = {}
    for c in range(1, ws.max_column + 1):
        h = _norm(ws.cell(1, c).value)
        if not h:
            continue
        for key, kws in COLS.items():
            if key in m:
                continue
            if any(k in h for k in kws):
                m[key] = c
    return m


def read_sheet(ws):
    cols = _col_map(ws)
    if "load" not in cols or "space" not in cols:
        return []
    rows = []
    for r in range(2, 98):
        ts = _time_str(ws.cell(r, 1).value)
        if not ts:
            continue
        item = {"time_str": ts}
        for key, c in cols.items():
            item[key] = _to_f(ws.cell(r, c).value)
        if item.get("load") is None:
            continue
        rows.append(item)
    return rows


def _dt(biz_date, ts):
    if ts == "24:00":
        return datetime(biz_date.year, biz_date.month, biz_date.day) + timedelta(days=1)
    h, m = ts.split(":")
    return datetime(biz_date.year, biz_date.month, biz_date.day, int(h), int(m))


def import_one(path, year):
    from webapp.services.bidding_space_service import BiddingSpaceService as BSS
    biz = _parse_date(os.path.basename(path), year)
    if biz is None:
        return None, "无法解析日期"
    wb = openpyxl.load_workbook(path, data_only=True)
    ds = biz.strftime("%Y-%m-%d")
    n_da = n_rt = 0

    if "日前" in wb.sheetnames:
        for it in read_sheet(wb["日前"]):
            calc = BSS.calc(it.get("load", 0) or 0, it.get("pv", 0) or 0, it.get("wind", 0) or 0,
                            it.get("tieline", 0) or 0, it.get("storage", 0) or 0,
                            it.get("gas", 0) or 0, it.get("coal", 0) or 0)
            DR.replace_one(
                {"date_str": ds, "time_str": it["time_str"]},
                {
                    "date_str": ds, "time_str": it["time_str"], "datetime": _dt(biz, it["time_str"]),
                    "system_load_forecast": it.get("load"),
                    "pv_forecast": it.get("pv"),
                    "wind_forecast": it.get("wind"),
                    "tieline_plan": it.get("tieline"),
                    "storage_plan": it.get("storage"),
                    "gas_unit_plan": it.get("gas"),
                    "coal_unit_plan": it.get("coal"),
                    "nonmarket_unit_forecast": round((it.get("storage") or 0) + (it.get("gas") or 0) + (it.get("coal") or 0), 3),
                    "bidding_space_pub": it.get("space"),
                    "bidding_space_calc": round(calc, 3),
                    "data_source": SRC, "source_file": os.path.basename(path),
                }, upsert=True)
            n_da += 1

    if "实时" in wb.sheetnames:
        rt_rows = read_sheet(wb["实时"])
        if rt_rows and all((it.get("load") or 0) == 0 for it in rt_rows):
            print("    实时页负荷全为 0（当日实时数据未发布），已跳过实时")
            rt_rows = []
        for it in rt_rows:
            calc = BSS.calc(it.get("load", 0) or 0, it.get("pv", 0) or 0, it.get("wind", 0) or 0,
                            it.get("tieline", 0) or 0, it.get("storage", 0) or 0,
                            it.get("gas", 0) or 0, it.get("coal", 0) or 0)
            AO.replace_one(
                {"date_str": ds, "time_str": it["time_str"]},
                {
                    "date_str": ds, "time_str": it["time_str"], "datetime": _dt(biz, it["time_str"]),
                    "system_load": it.get("load"),
                    "pv_actual": it.get("pv"),
                    "wind_actual": it.get("wind"),
                    "tieline_flow": it.get("tieline"),
                    "storage_actual": it.get("storage"),
                    "gas_actual": it.get("gas"),
                    "coal_actual": it.get("coal"),
                    "nonmarket_unit": round((it.get("storage") or 0) + (it.get("gas") or 0) + (it.get("coal") or 0), 3),
                    "bidding_space_pub": it.get("space"),
                    "bidding_space_calc": round(calc, 3),
                    "data_source": SRC, "source_file": os.path.basename(path),
                }, upsert=True)
            RG.replace_one(
                {"date_str": ds, "time_str": it["time_str"]},
                {
                    "date_str": ds, "time_str": it["time_str"], "datetime": _dt(biz, it["time_str"]),
                    "wind_generation": it.get("wind"),
                    "solar_generation": it.get("pv"),
                    "hydro_generation": 0.0,
                    "pumped_storage_generation": it.get("storage"),
                    "battery_storage_generation": 0.0,
                    "coal_generation": it.get("coal"),
                    "gas_generation": it.get("gas"),
                    "data_source": SRC, "source_file": os.path.basename(path),
                }, upsert=True)
            n_rt += 1

    wb.close()
    return biz, "日前%d点 实时%d点" % (n_da, n_rt)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--year", type=int, default=2026)
    args = ap.parse_args()
    files = [os.path.join(args.dir, f) for f in sorted(os.listdir(args.dir))
             if f.lower().endswith(".xlsx") and not f.startswith("~$")]
    ok = fail = 0
    for f in files:
        try:
            d, msg = import_one(f, args.year)
            if d is None:
                print("  SKIP", os.path.basename(f), msg); fail += 1
            else:
                print("  OK  ", os.path.basename(f), "->", d.strftime("%Y-%m-%d"), msg); ok += 1
        except Exception as e:
            print("  FAIL", os.path.basename(f), e); fail += 1
    print("")
    print("完成: 成功", ok, "失败", fail)
    print("daily_release", DR.count_documents({}), "| actual_operation", AO.count_documents({}),
          "| real_time_generation", RG.count_documents({}))


if __name__ == "__main__":
    main()
