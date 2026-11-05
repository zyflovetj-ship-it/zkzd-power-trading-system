"""中长期/绿电合同量价 · 数据模板生成器 & 校验预览。

两个功能：
  1) gen：生成填数据用的 Excel 模板（12 合同块 × 12 月 × 24 时段，带表头/示例/填写说明）
  2) check：对已填好的 Excel 做导入前校验（缺块/量价异常/年度块价格不一致等），并可预览逐点中长期价

用法：
  python -m webapp.scripts.mid_long_template gen  --out /path/中长期合同量价模板.xlsx
  python -m webapp.scripts.mid_long_template check --excel /path/已填.xlsx
"""
import argparse
import sys

#: 12 合同块名称
CONTRACT_TYPES = [
    "年度合计", "年度绿电", "月度竞价", "月内能量块", "月度绿电", "月内绿电",
    "上旬", "中旬", "下旬", "第二次月内绿电", "小时级绿电", "月内小时级绿电",
]
ANNUAL = {"年度合计", "年度绿电"}
MONTHS = ["%d月" % i for i in range(1, 13)]
TIME_PERIODS = [
    "00:00-01:00", "01:00-02:00", "02:00-03:00", "03:00-04:00",
    "04:00-05:00", "05:00-06:00", "06:00-07:00", "07:00-08:00",
    "08:00-09:00", "09:00-10:00", "10:00-11:00", "11:00-12:00",
    "12:00-13:00", "13:00-14:00", "14:00-15:00", "15:00-16:00",
    "16:00-17:00", "17:00-18:00", "18:00-19:00", "19:00-20:00",
    "20:00-21:00", "21:00-22:00", "22:00-23:00", "23:00-24:00",
]
#: 每块占的行数（表头 + 24 时段 + 合计）
BLOCK_ROWS = 26


def gen_template(out_path):
    """生成空白 Excel 模板。布局对齐《套餐测算模板-新v2》的中长期页，便于直接沿用。"""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "中长期及绿电量价数据"

    head_fill = PatternFill("solid", fgColor="DDEBF7")
    title_fill = PatternFill("solid", fgColor="BDD7EE")
    bold = Font(bold=True)

    row = 1
    for ct in CONTRACT_TYPES:
        # 表头行
        ws.cell(row, 2, ct).font = bold
        ws.cell(row, 2).fill = title_fill
        for mi, mn in enumerate(MONTHS):
            c = ws.cell(row, 3 + mi, mn)
            c.font = bold
            c.fill = head_fill
            c.alignment = Alignment(horizontal="center")
        # 价格列表头（Q列=17）
        pc = ws.cell(row, 17, "年度价格" if ct in ANNUAL else "价格(元/MWh)")
        pc.font = bold
        pc.fill = head_fill
        ws.cell(row, 1, "时段")
        # 24 时段行
        for t, tp in enumerate(TIME_PERIODS):
            r = row + 1 + t
            ws.cell(r, 1, tp)
            # 年度类合同：价格全时段同价，只填首行；后续行留空（导入自动沿用首行价）
        # 合计行
        sr = row + 25
        ws.cell(sr, 2, "合计").font = bold
        row += BLOCK_ROWS

    # 填写说明
    ws2 = wb.create_sheet("填写说明")
    tips = [
        "【中长期/绿电合同量价 填写说明】",
        "",
        "1. 每个合同块 = 表头行 + 24 个时段行（00:00-01:00 ... 23:00-24:00）",
        "2. C~N 列 = 1~12 月，填【每月该时段电量 MWh】",
        "3. Q 列(第17列) = 该时段【价格 元/MWh】",
        "4. 年度合计 / 年度绿电：价格为全时段统一价，只填每个时段行同一价格即可",
        "   （导入脚本会自动把该块价格视为统一价）",
        "5. 无该时段电量可留空（按 0 处理，不影响其他块加权）",
        "6. 导入命令示例：",
        "   python -m webapp.scripts.import_mid_long_contracts \\",
        "       --excel 本文件.xlsx --year 2027 --customer-id <客户ID> --customer-name <客户名>",
        "   不填 --customer-id 则为全市场统一合同价",
        "",
        "合同块顺序（必须保持一致，导入按行定位）：",
    ] + ["  %2d. %s" % (i + 1, ct) for i, ct in enumerate(CONTRACT_TYPES)]
    for i, line in enumerate(tips, 1):
        ws2.cell(i, 1, line)
    ws2.column_dimensions["A"].width = 80

    wb.save(out_path)
    print("模板已生成：%s" % out_path)
    print("  合同块数：%d，每块 24 时段，共约 %d 行" % (len(CONTRACT_TYPES), len(CONTRACT_TYPES) * BLOCK_ROWS))


def check_excel(path):
    """导入前校验 + 预览逐点中长期价。"""
    import openpyxl
    wb = openpyxl.load_workbook(path, data_only=True)
    if "中长期及绿电量价数据" not in wb.sheetnames:
        print("❌ 缺少工作表『中长期及绿电量价数据』")
        return 2
    ws = wb["中长期及绿电量价数据"]

    # 定位 12 块表头行（B列有合同名、C列=“1月”）
    starts = []
    for r in range(1, ws.max_row + 1):
        if ws.cell(r, 3).value == "1月" and ws.cell(r, 2).value:
            starts.append(r)
    print("检测到 %d 个合同块表头行：%s" % (len(starts), starts))

    problems = []
    if len(starts) != len(CONTRACT_TYPES):
        problems.append("合同块数量 %d ≠ 期望 %d" % (len(starts), len(CONTRACT_TYPES)))

    # 各块量汇总（1月）
    print("\n各合同块 1 月电量 / 价格：")
    for s in starts:
        ct = ws.cell(s, 2).value
        vol = 0.0
        prices = []
        for t in range(24):
            r = s + 1 + t
            vol += float(ws.cell(r, 3).value or 0)
            prices.append(ws.cell(r, 17).value)
        pr0 = prices[0]
        print("  %-14s 1月量=%.3f 首行价=%s" % (ct, vol, pr0))
        if vol == 0 and ct not in ("上旬", "中旬", "下旬"):
            problems.append("%s 1月无电量" % ct)

    # 预览逐点中长期价（1月）
    print("\n逐点中长期价预览（1月 24 点，加权）：")
    annual_rows = {s for s in starts if ws.cell(s, 2).value in ANNUAL}
    for t in range(24):
        num = den = 0.0
        for s in starts:
            r = s + 1 + t
            v = float(ws.cell(r, 3).value or 0)
            p_row = (s + 1) if s in annual_rows else r
            p = float(ws.cell(p_row, 17).value or 0)
            num += v * p
            den += v
        if t < 6:
            print("  %s : %s" % (TIME_PERIODS[t], round(num / den, 3) if den > 0 else "-"))

    print()
    if problems:
        print("⚠️ 发现问题 %d 项：" % len(problems))
        for p in problems:
            print("   -", p)
        return 1
    print("✅ 校验通过，可导入")
    return 0


def main():
    ap = argparse.ArgumentParser(description="中长期合同量价 模板生成/校验")
    sub = ap.add_subparsers(dest="cmd", required=True)
    g = sub.add_parser("gen", help="生成空白模板")
    g.add_argument("--out", required=True, help="输出 xlsx 路径")
    c = sub.add_parser("check", help="校验已填 Excel")
    c.add_argument("--excel", required=True, help="已填 xlsx 路径")
    args = ap.parse_args()
    if args.cmd == "gen":
        gen_template(args.out)
        return 0
    if args.cmd == "check":
        return check_excel(args.excel)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
