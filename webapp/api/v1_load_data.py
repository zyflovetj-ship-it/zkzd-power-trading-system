"""96 点负荷数据导入接口（写入 user_load_data）。

支持两种 Excel 格式：
  A. 宽表：列含 客户(名称或ID) + 日期 + 96 个时段列（00:15/00:30... 或 00:00/00:15...）
  B. 长表：列含 客户 + 时间(YYYY-MM-DD HH:MM) + 功率(kW)

单位约定：功率 kW，15 分钟一点。引擎换算 MWh = kW × 0.25 / 1000。

端点：
  GET  /load-data/template   下载导入模板（宽表）
  POST /load-data/preview    上传校验预览（不落库）
  POST /load-data/import     上传导入落库
  GET  /load-data/records    查询已导入负荷概况
  DELETE /load-data/records  按 客户+年月 删除
"""
import io
import re
import tempfile
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from webapp.tools.mongo import DATABASE
from webapp.tools.security import User, get_current_active_user

router = APIRouter(prefix="/load-data", tags=["Load Data Import"])
COLLECTION = DATABASE["user_load_data"]
CUSTOMERS = DATABASE["customers"]


def _resolve_customer(name_or_id: Optional[str], name_map: Dict[str, str], id_set: set) -> Optional[str]:
    """把客户名/ID 解析为 customer_id。"""
    if not name_or_id:
        return None
    s = str(name_or_id).strip()
    if s in id_set:
        return s
    if s in name_map:
        return name_map[s]
    # 宽松匹配：去空格/全角
    for k, v in name_map.items():
        if k.strip() == s:
            return v
    return None


def _customer_maps():
    name_map, id_set = {}, set()
    for d in CUSTOMERS.find({}, {"_id": 1, "user_name": 1, "short_name": 1}):
        cid = str(d["_id"])
        id_set.add(cid)
        for k in ("user_name", "short_name"):
            if d.get(k):
                name_map[str(d[k]).strip()] = cid
    return name_map, id_set


_TIME_RE = re.compile(r"^(\d{1,2}):(\d{2})$")


def _parse_excel(content: bytes) -> Dict[str, Any]:
    """解析 Excel 为负荷记录列表 + 校验信息。"""
    import openpyxl

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        f.write(content)
        path = f.name
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active

    # 读表头
    header = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]
    # 找客户列、日期列、时间列
    cust_col = date_col = time_col = power_col = None
    time_cols = []  # (col_index, "HH:MM")
    for i, h in enumerate(header):
        if not h:
            continue
        if h in ("客户", "客户名称", "用户名称", "用户", "户名") and cust_col is None:
            cust_col = i
        elif h in ("客户ID", "户号", "customer_id", "用户ID") and cust_col is None:
            cust_col = i
        elif h in ("日期", "date") and date_col is None:
            date_col = i
        elif h in ("时间", "时间戳", "timestamp", "datetime") and time_col is None:
            time_col = i
        elif h in ("功率", "功率(kW)", "负荷", "负荷(kW)", "value", "kW") and power_col is None:
            power_col = i
        else:
            m = _TIME_RE.match(h)
            if m:
                time_cols.append((i, h))

    name_map, id_set = _customer_maps()
    records: List[Dict[str, Any]] = []
    problems: List[str] = []
    unresolved = set()

    if time_cols and date_col is not None and cust_col is not None:
        # ---- 宽表 ----
        for r in range(2, ws.max_row + 1):
            cust_raw = ws.cell(r, cust_col + 1).value
            date_raw = ws.cell(r, date_col + 1).value
            if cust_raw is None and date_raw is None:
                continue
            cid = _resolve_customer(cust_raw, name_map, id_set)
            if not cid:
                unresolved.add(str(cust_raw))
                continue
            # 解析日期
            if isinstance(date_raw, datetime):
                d = date_raw.date()
            else:
                try:
                    d = datetime.strptime(str(date_raw).strip()[:10], "%Y-%m-%d").date()
                except Exception:
                    problems.append("第%d行日期无法解析：%r" % (r, date_raw))
                    continue
            for (ci, tlabel) in time_cols:
                val = ws.cell(r, ci + 1).value
                if val is None:
                    continue
                try:
                    valf = float(val)
                except (TypeError, ValueError):
                    continue
                m = _TIME_RE.match(tlabel)
                hh, mm = int(m.group(1)), int(m.group(2))
                ts = datetime(d.year, d.month, d.day) + timedelta(hours=hh, minutes=mm)
                records.append({
                    "customer_id": cid, "timestamp": ts,
                    "value": valf, "time_str": "%02d:%02d" % (hh, mm),
                })
    elif time_col is not None and power_col is not None and cust_col is not None:
        # ---- 长表 ----
        for r in range(2, ws.max_row + 1):
            cust_raw = ws.cell(r, cust_col + 1).value
            t_raw = ws.cell(r, time_col + 1).value
            p_raw = ws.cell(r, power_col + 1).value
            if cust_raw is None and t_raw is None:
                continue
            cid = _resolve_customer(cust_raw, name_map, id_set)
            if not cid:
                unresolved.add(str(cust_raw))
                continue
            try:
                ts = t_raw if isinstance(t_raw, datetime) else datetime.strptime(str(t_raw).strip()[:16], "%Y-%m-%d %H:%M")
            except Exception:
                problems.append("第%d行时间无法解析：%r" % (r, t_raw))
                continue
            try:
                valf = float(p_raw)
            except (TypeError, ValueError):
                continue
            records.append({"customer_id": cid, "timestamp": ts, "value": valf,
                            "time_str": ts.strftime("%H:%M")})
    else:
        raise ValueError("无法识别表结构：需含 客户 + 日期 + 96时段列（宽表），或 客户 + 时间 + 功率（长表）")

    if unresolved:
        problems.append("以下客户在系统中未找到（请先在客户管理建档）：" + "、".join(sorted(unresolved)[:20]))
    # 统计
    summary = {}
    for rec in records:
        key = (rec["customer_id"], rec["timestamp"].strftime("%Y-%m"))
        summary[key] = summary.get(key, 0) + 1
    months = [{"customer_id": k[0], "month": k[1], "points": v} for k, v in sorted(summary.items())]
    return {"records": records, "problems": problems, "months": months, "path": path}


def _to_docs(records: List[Dict[str, Any]], batch_id: str) -> List[Dict[str, Any]]:
    name_by_id = {}
    for d in CUSTOMERS.find({}, {"_id": 1, "user_name": 1}):
        name_by_id[str(d["_id"])] = d.get("user_name")
    docs = []
    for rec in records:
        ts = rec["timestamp"]
        docs.append({
            "timestamp": ts, "datetime": ts, "value": rec["value"], "load": rec["value"],
            "customer_id": rec["customer_id"], "user_id": rec["customer_id"],
            "user_name": name_by_id.get(rec["customer_id"], ""),
            "meter_id": "imported", "time_str": rec["time_str"],
            "date_str": ts.strftime("%Y-%m-%d"),
            "data_source": "excel_import", "import_batch_id": batch_id,
        })
    return docs


@router.get("/template", summary="下载96点负荷导入模板")
def download_template(current_user: User = Depends(get_current_active_user)):
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "负荷数据"
    bold = Font(bold=True)
    fill = PatternFill("solid", fgColor="DDEBF7")
    ws.cell(1, 1, "客户名称").font = bold
    ws.cell(1, 2, "日期").font = bold
    for i in range(96):
        hh = i // 4
        mm = (i % 4) * 15
        label = "%02d:%02d" % (hh, mm)
        c = ws.cell(1, 3 + i, label)
        c.font = bold
        c.fill = fill
    ws.cell(2, 1, "示例客户甲")
    ws.cell(2, 2, "2027-01-01")
    ws2 = wb.create_sheet("填写说明")
    tips = [
        "【96点负荷数据 填写说明】",
        "",
        "宽表格式：",
        "  A列=客户名称（须与客户管理中的名称一致，或填客户ID）",
        "  B列=日期（YYYY-MM-DD）",
        "  C列起=96个时段（00:00,00:15,...,23:45），填该时段平均功率(kW)",
        "",
        "长表格式（二选一）：",
        "  A列=客户名称, B列=时间(YYYY-MM-DD HH:MM), C列=功率(kW)",
        "",
        "单位：功率 kW（15分钟一点）。系统自动换算 MWh = kW × 0.25 / 1000。",
        "可一次导入多客户、多日期、多月份。",
    ]
    for i, t in enumerate(tips, 1):
        ws2.cell(i, 1, t)
    ws2.column_dimensions["A"].width = 80
    import tempfile
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    wb.save(path)
    data = open(path, "rb").read()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=load_data_template.xlsx"},
    )


@router.post("/preview", summary="上传负荷Excel校验预览（不落库）")
async def preview_excel(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    content = await file.read()
    try:
        info = _parse_excel(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {
        "ok": not info["problems"] and len(info["records"]) > 0,
        "problems": info["problems"],
        "record_count": len(info["records"]),
        "months": info["months"][:60],
    }


@router.post("/import", summary="上传负荷Excel导入落库")
async def import_excel(
    file: UploadFile = File(...),
    replace: bool = Query(True, description="是否覆盖同客户同月的旧数据"),
    current_user: User = Depends(get_current_active_user),
):
    content = await file.read()
    try:
        info = _parse_excel(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    records = info["records"]
    if not records:
        raise HTTPException(status_code=400, detail="未解析到负荷记录（检查表结构/客户名是否匹配）")

    batch_id = "IMP_" + datetime.utcnow().strftime("%Y%m%d%H%M%S")
    # 覆盖：按 (客户, 月) 先删旧
    deleted = 0
    if replace:
        seen = set()
        for rec in records:
            ym = rec["timestamp"].strftime("%Y-%m")
            key = (rec["customer_id"], ym)
            if key in seen:
                continue
            seen.add(key)
            y, mo = int(ym[:4]), int(ym[5:7])
            start = datetime(y, mo, 1)
            end = (start + timedelta(days=32)).replace(day=1)
            deleted += COLLECTION.delete_many({
                "customer_id": rec["customer_id"],
                "timestamp": {"$gte": start, "$lt": end},
            }).deleted_count
    docs = _to_docs(records, batch_id)
    COLLECTION.insert_many(docs)
    try:
        COLLECTION.create_index([("customer_id", 1), ("timestamp", 1)])
    except Exception:
        pass
    return {"inserted": len(docs), "deleted": deleted, "batch_id": batch_id,
            "months": info["months"], "problems": info["problems"]}


@router.get("/records", summary="查询已导入负荷概况")
def list_records(
    customer_id: Optional[str] = Query(None),
    source: Optional[str] = Query(None, description="按来源筛选：excel_import / system_simulation 等"),
    current_user: User = Depends(get_current_active_user),
):
    q: Dict[str, Any] = {}
    if customer_id:
        q["customer_id"] = customer_id
    if source:
        q["data_source"] = source
    pipeline = [
        {"$match": q},
        {"$group": {
            "_id": {"customer_id": "$customer_id",
                    "month": {"$substr": ["$date_str", 0, 7]},
                    "source": {"$ifNull": ["$data_source", "unknown"]}},
            "points": {"$sum": 1},
            "days": {"$addToSet": "$date_str"},
            "user_name": {"$first": "$user_name"},
        }},
        {"$sort": {"_id.month": 1, "_id.source": 1}},
    ]
    groups = []
    for g in COLLECTION.aggregate(pipeline):
        groups.append({
            "customer_id": g["_id"]["customer_id"],
            "user_name": g.get("user_name"),
            "month": g["_id"]["month"],
            "source": g["_id"].get("source"),
            "points": g["points"],
            "days": len(g.get("days") or []),
        })
    # 按来源汇总，便于页面显示各来源占比
    by_source: Dict[str, int] = {}
    for g in groups:
        by_source[g["source"]] = by_source.get(g["source"], 0) + g["points"]
    return {"total_points": COLLECTION.count_documents(q), "groups": groups, "by_source": by_source}


@router.delete("/records", summary="按客户+月份删除负荷")
def delete_records(
    customer_id: str = Query(...),
    month: str = Query(..., description="YYYY-MM"),
    source: Optional[str] = Query(None, description="只删该来源；不传则删全部来源"),
    current_user: User = Depends(get_current_active_user),
):
    y, mo = int(month[:4]), int(month[5:7])
    start = datetime(y, mo, 1)
    end = (start + timedelta(days=32)).replace(day=1)
    q: Dict[str, Any] = {
        "customer_id": customer_id,
        "timestamp": {"$gte": start, "$lt": end},
    }
    if source:
        q["data_source"] = source
    deleted = COLLECTION.delete_many(q).deleted_count
    return {"deleted": deleted, "source": source}
