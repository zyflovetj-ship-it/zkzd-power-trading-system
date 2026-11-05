"""导入市场发布日文件（日前/实时 96 点出清价）到现货价格集合。

日文件格式：sheet「汇总」，A 列=时段(00:15..24:00)，D 列=日前价格，E 列=实时价格（元/MWh）。
日期来源：文件名（1月6日.xlsx / 2026-01-06.xlsx / 1-6.xlsx），可用 --year 指定年份。

用法：
  python -m webapp.scripts.import_spot_daily --dir /tmp/daily --year 2026
  python -m webapp.scripts.import_spot_daily --file 1月6日.xlsx --month 1 --day 6 --year 2026
"""
import argparse
import os
import re
from datetime import datetime, timedelta

import openpyxl

from webapp.tools.mongo import DATABASE

DA = DATABASE["day_ahead_spot_price"]
RT = DATABASE["real_time_spot_price"]
SRC = "market_published"


def parse_date_from_name(name, year):
    base = os.path.splitext(os.path.basename(name))[0].strip()
    m = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})$", base)
    if m:
        return datetime(int(m.group(1)), int(m.group(2)), int(m.group(3)))
    m = re.match(r"^(\d{1,2})月(\d{1,2})日$", base)
    if m:
        return datetime(year, int(m.group(1)), int(m.group(2)))
    m = re.match(r"^(\d{1,2})-(\d{1,2})$", base)
    if m:
        return datetime(year, int(m.group(1)), int(m.group(2)))
    return None


def _norm(v):
    return "".join(str(v or "").split())


def _find_col(ws, *keywords, exclude=()):
    """在表头行按关键词定位列（忽略空白/换行）；返回列号或 None。"""
    for c in range(1, ws.max_column + 1):
        h = _norm(ws.cell(1, c).value)
        if not h:
            continue
        if any(k in h for k in keywords) and not any(x in h for x in exclude):
            return c
    return None


def read_day_file(path):
    """按表头定位「日前价格」「实时价格」列（各月文件列位置不同）。"""
    wb = openpyxl.load_workbook(path, data_only=True)
    if "汇总" not in wb.sheetnames:
        wb.close()
        raise ValueError("缺少「汇总」页")
    ws = wb["汇总"]
    c_da = _find_col(ws, "日前价格", exclude=("日前-实时",))
    c_rt = _find_col(ws, "实时价格", exclude=("日前-实时",))
    if c_da is None:
        c_da = 4
    if c_rt is None:
        c_rt = 5
    da, rt = [], []
    for r in range(2, 98):
        da.append(ws.cell(r, c_da).value)
        rt.append(ws.cell(r, c_rt).value)
    wb.close()
    if len(da) != 96:
        raise ValueError("汇总页不足 96 点")
    return da, rt, c_da, c_rt


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def build_docs(biz_date, prices, price_type, source_file):
    docs = []
    base = datetime(biz_date.year, biz_date.month, biz_date.day)
    for i, v in enumerate(prices):
        minutes = (i + 1) * 15
        ts = base + timedelta(minutes=minutes)
        hh, mm = minutes // 60, minutes % 60
        time_str = "24:00" if hh == 24 else "%02d:%02d" % (hh, mm)
        price = _to_float(v)
        docs.append({
            "timestamp": ts,
            "datetime": ts,
            "value": price,
            "avg_clearing_price": price,
            "date_str": biz_date.strftime("%Y-%m-%d"),
            "time_str": time_str,
            "data_source": SRC,
            "source_file": source_file,
            "price_type": price_type,
        })
    return docs


def import_one(path, year, month=None, day=None):
    name = os.path.basename(path)
    biz_date = datetime(year, month, day) if (month and day) else parse_date_from_name(name, year)
    if biz_date is None:
        return None, "无法从文件名解析日期: " + name
    da, rt, c_da, c_rt = read_day_file(path)
    eff_da = [_to_float(v) for v in da]
    eff_rt = [_to_float(v) for v in rt]
    has_da = any(v is not None for v in eff_da)
    has_rt = any(v is not None for v in eff_rt)
    # 价格列为空（当日价格未发布）时不要删除已有数据
    if not has_da and not has_rt:
        return None, "价格列为空（当日价格可能未发布），已跳过且未改动原数据"
    ds = biz_date.strftime("%Y-%m-%d")
    if has_da:
        DA.delete_many({"date_str": ds})
        DA.insert_many(build_docs(biz_date, eff_da, "day_ahead", name))
    if has_rt:
        RT.delete_many({"date_str": ds})
        RT.insert_many(build_docs(biz_date, eff_rt, "real_time", name))
    return biz_date, None


def import_stat(path):
    """从《现货价格统计.xlsx》批量导入：日前/实时 96 点矩阵（列头为 Excel 日期序列号）。"""
    import datetime as _dt

    wb = openpyxl.load_workbook(path, data_only=True)
    result = {}
    for sheet, coll, ptype in (
        ("日前日分时-96点", DA, "day_ahead"),
        ("实时日分时-96点", RT, "real_time"),
    ):
        if sheet not in wb.sheetnames:
            continue
        ws = wb[sheet]
        n = 0
        for c in range(2, ws.max_column + 1):
            serial = ws.cell(1, c).value
            if not isinstance(serial, (int, float)):
                continue
            biz = _dt.date(1899, 12, 30) + _dt.timedelta(days=int(serial))
            prices = [ws.cell(r, c).value for r in range(2, 98)]
            if not any(isinstance(v, (int, float)) for v in prices):
                continue
            ds = biz.strftime("%Y-%m-%d")
            coll.delete_many({"date_str": ds})
            coll.insert_many(build_docs(datetime(biz.year, biz.month, biz.day),
                                        prices, ptype, os.path.basename(path)))
            n += 1
        result[ptype] = n
    wb.close()
    print("从统计表导入: 日前", result.get("day_ahead", 0), "天; 实时", result.get("real_time", 0), "天")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dir")
    ap.add_argument("--file")
    ap.add_argument("--stat")
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--month", type=int)
    ap.add_argument("--day", type=int)
    args = ap.parse_args()

    if args.stat:
        import_stat(args.stat)
        print("现货价格库: 日前", DA.count_documents({}), "条 | 实时", RT.count_documents({}), "条")
        print("已导入天数(市场发布): 日前", len(DA.distinct("date_str", {"data_source": SRC})),
              "| 实时", len(RT.distinct("date_str", {"data_source": SRC})))
        return

    if args.file:
        files = [args.file]
    elif args.dir:
        files = [os.path.join(args.dir, f) for f in sorted(os.listdir(args.dir))
                 if f.lower().endswith((".xlsx", ".xls")) and not f.startswith("~$")]
    else:
        print("必须指定 --dir 或 --file")
        return

    ok, fail = 0, 0
    for f in files:
        try:
            d, err = import_one(f, args.year, args.month, args.day)
            if err:
                print("  SKIP", os.path.basename(f), err)
                fail += 1
            else:
                ok += 1
                print("  OK  ", os.path.basename(f), "->", d.strftime("%Y-%m-%d"))
        except Exception as e:
            fail += 1
            print("  FAIL", os.path.basename(f), e)

    print("")
    print("完成: 成功", ok, "失败", fail)
    print("现货价格库: 日前", DA.count_documents({}), "条 | 实时", RT.count_documents({}), "条")
    da_days = len(DA.distinct("date_str", {"data_source": SRC}))
    rt_days = len(RT.distinct("date_str", {"data_source": SRC}))
    print("已导入天数: 日前", da_days, "天 | 实时", rt_days, "天")


if __name__ == "__main__":
    main()
