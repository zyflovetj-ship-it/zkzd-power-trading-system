"""现货价格（日前/实时 96 点）导入接口。

复用 webapp.scripts.import_spot_daily 已验证的解析逻辑：
  - 日文件：《汇总》页，表头含「日前价格」「实时价格」列，96 行数据，日期取自文件名
  - 统计表：《现货价格统计.xlsx》日期×96点矩阵

端点：
  GET  /spot-prices/template      下载日文件模板
  POST /spot-prices/preview       上传校验预览（不落库）
  POST /spot-prices/import        上传导入落库
  GET  /spot-prices/records       查询已导入概况（按日统计）
  GET  /spot-prices/monthly       某月日前/实时均价统计
  DELETE /spot-prices/records     按日期删除
"""
import io
import os
import re
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from webapp.tools.mongo import DATABASE
from webapp.tools.security import User, get_current_active_user

router = APIRouter(prefix="/spot-prices", tags=["Spot Prices Import"])
DA = DATABASE["day_ahead_spot_price"]
RT = DATABASE["real_time_spot_price"]


def _ts_label(i: int) -> str:
    minutes = (i + 1) * 15
    hh, mm = minutes // 60, minutes % 60
    return "24:00" if hh == 24 else "%02d:%02d" % (hh, mm)


def _parse_date_from_name(name: str, year: int) -> Optional[datetime]:
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


def _read_one(path: str):
    """复用脚本解析：返回 (biz_date, da[96], rt[96], err)"""
    import openpyxl

    wb = openpyxl.load_workbook(path, data_only=True)
    if "汇总" not in wb.sheetnames:
        wb.close()
        return None, None, None, "缺少「汇总」页"
    ws = wb["汇总"]

    def _norm(v):
        return "".join(str(v or "").split())

    def _find_col(*keywords, exclude=()):
        for c in range(1, ws.max_column + 1):
            h = _norm(ws.cell(1, c).value)
            if not h:
                continue
            if any(k in h for k in keywords) and not any(x in h for x in exclude):
                return c
        return None

    c_da = _find_col("日前价格", exclude=("日前-实时",))
    c_rt = _find_col("实时价格", exclude=("日前-实时",))
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
        return None, None, None, "汇总页不足 96 点"
    return da, rt, None, None


def _to_float(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _build_docs(biz_date: datetime, prices: List[Any], price_type: str, source: str) -> List[Dict]:
    docs = []
    base = datetime(biz_date.year, biz_date.month, biz_date.day)
    for i, v in enumerate(prices):
        minutes = (i + 1) * 15
        ts = base + timedelta(minutes=minutes)
        price = _to_float(v)
        docs.append({
            "timestamp": ts, "datetime": ts,
            "value": price, "avg_clearing_price": price,
            "date_str": biz_date.strftime("%Y-%m-%d"),
            "time_str": _ts_label(i),
            "data_source": "market_published",
            "source_file": source,
            "price_type": price_type,
        })
    return docs


@router.get("/template", summary="下载现货价格日文件模板")
def download_template(current_user: User = Depends(get_current_active_user)):
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "汇总"
    bold = Font(bold=True)
    fill = PatternFill("solid", fgColor="DDEBF7")
    for c, h in [(1, "时段"), (2, "出清电量"), (3, "日前-实时价差"), (4, "日前价格"), (5, "实时价格")]:
        cell = ws.cell(1, c, h)
        cell.font = bold
        cell.fill = fill
    for i in range(96):
        ws.cell(2 + i, 1, _ts_label(i))
    ws2 = wb.create_sheet("说明")
    for i, t in enumerate([
        "【现货价格日文件 填写说明】",
        "",
        "1. 文件名即业务日期：2027-01-06.xlsx / 1月6日.xlsx / 1-6.xlsx（配合年份参数）",
        "2. 「汇总」页：日前价格=第4列、实时价格=第5列（表头自动识别，位置可不同）",
        "3. 共 96 行（00:15 ~ 24:00，每15分钟一点），单位 元/MWh",
        "4. 某列整列为空 = 当日该价格未发布，导入时跳过且不动原数据",
        "5. 可一次上传多个日文件批量导入",
    ], 1):
        ws2.cell(i, 1, t)
    ws2.column_dimensions["A"].width = 80
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    wb.save(path)
    data = open(path, "rb").read()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=spot_price_day_template.xlsx"},
    )


@router.post("/preview", summary="上传现货日文件校验预览（不落库）")
async def preview_files(
    files: List[UploadFile] = File(..., description="日文件（可多个）"),
    year: int = Query(..., description="年份（文件名不含年份时用）"),
    current_user: User = Depends(get_current_active_user),
):
    results = []
    for f in files:
        content = await f.read()
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
            tf.write(content)
            path = tf.name
        biz_date = _parse_date_from_name(f.filename, year)
        if biz_date is None:
            results.append({"file": f.filename, "ok": False, "problems": ["无法从文件名解析日期（需 2027-01-06 / 1月6日 / 1-6 格式）"]})
            continue
        try:
            da, rt, _, err = _read_one(path)
        except Exception as e:
            results.append({"file": f.filename, "ok": False, "problems": [str(e)]})
            continue
        if err:
            results.append({"file": f.filename, "ok": False, "problems": [err]})
            continue
        eff_da = [_to_float(v) for v in da]
        eff_rt = [_to_float(v) for v in rt]
        da_n = sum(1 for v in eff_da if v is not None)
        rt_n = sum(1 for v in eff_rt if v is not None)
        probs = []
        if da_n == 0 and rt_n == 0:
            probs.append("价格列全空（当日可能未发布）")
        da_avg = sum(v for v in eff_da if v is not None) / da_n if da_n else None
        rt_avg = sum(v for v in eff_rt if v is not None) / rt_n if rt_n else None
        results.append({
            "file": f.filename,
            "ok": not probs,
            "problems": probs,
            "date": biz_date.strftime("%Y-%m-%d"),
            "day_ahead_points": da_n,
            "real_time_points": rt_n,
            "day_ahead_avg": round(da_avg, 2) if da_avg else None,
            "real_time_avg": round(rt_avg, 2) if rt_avg else None,
        })
    ok = sum(1 for r in results if r["ok"])
    return {"ok_count": ok, "fail_count": len(results) - ok, "results": results}


@router.post("/import", summary="上传现货日文件导入落库")
async def import_files(
    files: List[UploadFile] = File(...),
    year: int = Query(...),
    current_user: User = Depends(get_current_active_user),
):
    inserted_da = inserted_rt = deleted = skipped = 0
    problems = []
    imported_dates = []
    for f in files:
        content = await f.read()
        with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tf:
            tf.write(content)
            path = tf.name
        biz_date = _parse_date_from_name(f.filename, year)
        if biz_date is None:
            problems.append("%s: 无法解析文件名日期" % f.filename)
            skipped += 1
            continue
        try:
            da, rt, _, err = _read_one(path)
        except Exception as e:
            problems.append("%s: %s" % (f.filename, e))
            skipped += 1
            continue
        if err:
            problems.append("%s: %s" % (f.filename, err))
            skipped += 1
            continue
        eff_da = [_to_float(v) for v in da]
        eff_rt = [_to_float(v) for v in rt]
        if not any(v is not None for v in eff_da) and not any(v is not None for v in eff_rt):
            problems.append("%s: 价格列全空，跳过" % f.filename)
            skipped += 1
            continue
        ds = biz_date.strftime("%Y-%m-%d")
        if any(v is not None for v in eff_da):
            deleted += DA.delete_many({"date_str": ds}).deleted_count
            docs = _build_docs(biz_date, eff_da, "day_ahead", f.filename)
            DA.insert_many(docs)
            inserted_da += len(docs)
        if any(v is not None for v in eff_rt):
            deleted += RT.delete_many({"date_str": ds}).deleted_count
            docs = _build_docs(biz_date, eff_rt, "real_time", f.filename)
            RT.insert_many(docs)
            inserted_rt += len(docs)
        imported_dates.append(ds)
    return {"inserted_day_ahead": inserted_da, "inserted_real_time": inserted_rt,
            "deleted_old": deleted, "skipped": skipped, "problems": problems,
            "imported_dates": imported_dates}


@router.get("/records", summary="已导入现货价格概况（按日）")
def list_records(
    date_from: Optional[str] = Query(None, description="YYYY-MM-DD"),
    date_to: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
):
    q: Dict[str, Any] = {}
    if date_from or date_to:
        q["date_str"] = {}
        if date_from:
            q["date_str"]["$gte"] = date_from
        if date_to:
            q["date_str"]["$lte"] = date_to

    def _daily(coll, name):
        pipeline = [
            {"$match": q},
            {"$group": {
                "_id": "$date_str",
                "points": {"$sum": 1},
                "avg": {"$avg": "$value"},
                "mn": {"$min": "$value"},
                "mx": {"$max": "$value"},
            }},
            {"$sort": {"_id": -1}},
            {"$limit": 400},
        ]
        return {g["_id"]: {"points": g["points"], "avg": round(g["avg"], 2) if g["avg"] else None,
                           "min": round(g["mn"], 2) if g["mn"] is not None else None,
                           "max": round(g["mx"], 2) if g["mx"] is not None else None} for g in coll.aggregate(pipeline)}

    da_map = _daily(DA, "day_ahead")
    rt_map = _daily(RT, "real_time")
    dates = sorted(set(da_map) | set(rt_map), reverse=True)
    rows = [{"date": d, "day_ahead": da_map.get(d), "real_time": rt_map.get(d)} for d in dates]
    return {"total_days": len(rows), "rows": rows}


@router.get("/monthly", summary="某月现货均价统计")
def monthly_stats(
    month: str = Query(..., description="YYYY-MM"),
    current_user: User = Depends(get_current_active_user),
):
    prefix = month + "-"

    def _stat(coll):
        pipeline = [
            {"$match": {"date_str": {"$regex": "^" + prefix}}},
            {"$group": {"_id": None, "avg": {"$avg": "$value"}, "mn": {"$min": "$value"}, "mx": {"$max": "$value"}, "n": {"$sum": 1}}},
        ]
        out = list(coll.aggregate(pipeline))
        if not out:
            return None
        g = out[0]
        return {"avg": round(g["avg"], 2) if g["avg"] else None, "min": g["mn"], "max": g["mx"], "points": g["n"]}

    return {"month": month, "day_ahead": _stat(DA), "real_time": _stat(RT)}


@router.delete("/records", summary="按日期删除现货价格")
def delete_records(
    date: str = Query(..., description="YYYY-MM-DD"),
    current_user: User = Depends(get_current_active_user),
):
    d_da = DA.delete_many({"date_str": date}).deleted_count
    d_rt = RT.delete_many({"date_str": date}).deleted_count
    return {"date": date, "deleted_day_ahead": d_da, "deleted_real_time": d_rt}
