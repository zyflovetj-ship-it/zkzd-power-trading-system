"""核查联（电费核查联单）批量导入 + 批量测算接口。

核查联用于「路径B」测算：只有月度峰平谷电量 + 现状电费，无需 96 点负荷曲线。

集合 bill_verification：
  {customer_id, customer_name, period(YYYY-MM), total_mwh,
   peak_mwh, flat_mwh, valley_mwh, current_amount, ktype, imported_at}

端点：
  GET  /bills/template        下载核查联导入模板
  POST /bills/preview         上传校验预览（不落库）
  POST /bills/import          上传导入落库
  GET  /bills/records         查询已导入核查联
  DELETE /bills/records       按 客户+月份 删除
  POST /bills/batch-calc      批量测算（选定套餐，对多条核查联逐条测算）
"""
import io
import re
import tempfile
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from webapp.tools.mongo import DATABASE
from webapp.tools.security import User, get_current_active_user

router = APIRouter(prefix="/bills", tags=["Bill Verification"])
COLLECTION = DATABASE["bill_verification"]
CUSTOMERS = DATABASE["customers"]

_HEADERS = {
    "customer": ("客户名称", "用户名称", "客户", "户名"),
    "period": ("月份", "计费月份", "period"),
    "total": ("月总电量", "总电量", "total_mwh"),
    "peak": ("峰电量", "peak_mwh"),
    "flat": ("平电量", "flat_mwh"),
    "valley": ("谷电量", "valley_mwh"),
    "amount": ("现状电费", "现状实收电费", "current_amount", "电费"),
    "ktype": ("用电类型", "ktype"),
}


def _customer_maps():
    name_map, id_set = {}, set()
    for d in CUSTOMERS.find({}, {"_id": 1, "user_name": 1, "short_name": 1}):
        cid = str(d["_id"])
        id_set.add(cid)
        for k in ("user_name", "short_name"):
            if d.get(k):
                name_map[str(d[k]).strip()] = cid
    return name_map, id_set


def _parse_period(v) -> Optional[str]:
    if v is None:
        return None
    if isinstance(v, datetime):
        return v.strftime("%Y-%m")
    s = str(v).strip()
    # 支持 2027-01 / 2027年1月 / 2027/1
    import re
    m = re.match(r"(\d{4})[-/年](\d{1,2})", s)
    if m:
        return "%04d-%02d" % (int(m.group(1)), int(m.group(2)))
    return None


def _parse_excel(content: bytes) -> Dict[str, Any]:
    import openpyxl

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        f.write(content)
        path = f.name
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb.active
    header = [str(c.value).strip() if c.value is not None else "" for c in ws[1]]

    def _norm(h):
        # 去掉单位括号与空白，便于容错匹配（如 "月总电量(MWh)" -> "月总电量"）
        import re as _re
        return _re.sub(r"[（(].*?[)）]", "", str(h)).strip()

    norm_header = [_norm(h) for h in header]

    col = {}
    for key, names in _HEADERS.items():
        for i, h in enumerate(norm_header):
            # 精确匹配优先，其次子串匹配
            if h in names or any(n == h for n in names):
                col[key] = i
                break
        if key not in col:
            for i, h in enumerate(norm_header):
                if not h:
                    continue
                if any(n in h for n in names) or any(h in n for n in names if n):
                    col[key] = i
                    break

    if "customer" not in col or "period" not in col or "total" not in col:
        raise ValueError("表头缺失：至少需要 客户名称 / 月份 / 月总电量 三列")

    name_map, id_set = _customer_maps()
    records, problems, unresolved = [], [], set()
    for r in range(2, ws.max_row + 1):
        cust_raw = ws.cell(r, col["customer"] + 1).value
        if cust_raw is None:
            continue
        s = str(cust_raw).strip()
        cid = s if s in id_set else name_map.get(s)
        if not cid:
            unresolved.add(s)
            continue
        period = _parse_period(ws.cell(r, col["period"] + 1).value)
        if not period:
            problems.append("第%d行月份无法解析" % r)
            continue
        def _num(key):
            if key not in col:
                return None
            v = ws.cell(r, col[key] + 1).value
            try:
                return float(v) if v is not None else None
            except (TypeError, ValueError):
                return None
        total = _num("total")
        if total is None:
            problems.append("第%d行月总电量缺失" % r)
            continue
        records.append({
            "customer_id": cid,
            "customer_name": s,
            "period": period,
            "total_mwh": total,
            "peak_mwh": _num("peak"),
            "flat_mwh": _num("flat"),
            "valley_mwh": _num("valley"),
            "current_amount": _num("amount"),
            "ktype": (str(ws.cell(r, col["ktype"] + 1).value).strip() if ("ktype" in col and ws.cell(r, col["ktype"] + 1).value) else None),
        })
    if unresolved:
        problems.append("以下客户未建档：" + "、".join(sorted(unresolved)[:20]))
    return {"records": records, "problems": problems, "path": path}


def _parse_pdf(content: bytes) -> Dict[str, Any]:
    """解析「国网江苏」电费账单 PDF（文本型，无需 OCR）。

    适配 A2+B 决策：
      - total_mwh 取主计量点「计费电量」合计（剔除 0.2% 定比分表、0 电量计量点2）；
      - 尖峰并入峰（本账单尖峰/峰同价，不改动 PricingEngine）；
      - current_amount 取「本期电费」实收；
      - ktype 从「执行电价名」推断：含「两部制」即 两部制，否则默认 单一制-100千伏安以下。
    每个时段取各计量点中的最大「计费电量」，天然落在主计量点（分表/0电量点远小于主表）。
    """
    import pypdf

    reader = pypdf.PdfReader(io.BytesIO(content))
    txt = " ".join((p.extract_text() or "") for p in reader.pages)
    if not txt.strip():
        raise ValueError("PDF 未提取到文本（可能是扫描件，需 OCR）")

    problems: List[str] = []

    # 户名
    m = re.search(r"户名\s+(\S+)", txt)
    if not m:
        raise ValueError("未找到「户名」")
    customer_name = m.group(1).strip()

    # 账单周期（取第一个 YYYY-MM-DD；国网格式：起 ~ 止）
    m = re.search(r"(\d{4}-\d{2}-\d{2})", txt)
    if not m:
        raise ValueError("未找到账单周期")
    period = m.group(1)[:7]

    # 本期电费（实收）
    m = re.search(r"本期电费\s*([\d.]+)", txt)
    if not m:
        raise ValueError("未找到「本期电费」")
    try:
        current_amount = float(m.group(1))
    except ValueError:
        raise ValueError("「本期电费」数值无法解析")

    # 用电类型：执行电价名中若出现「两部制」则判为两部制
    ktype = "两部制" if "两部制" in txt else None

    # 主计量点各时段「计费电量」（取各计量点最大值）
    labels = {"总": "total", "尖峰": "sharp", "峰": "peak", "平": "flat", "谷": "valley"}
    best = {v: 0.0 for v in labels.values()}
    tokens = txt.split()
    for lbl, key in labels.items():
        needle = "正向有功（" + lbl + "）"
        for i, t in enumerate(tokens):
            if t == needle:
                nums: List[float] = []
                j = i + 1
                while j < len(tokens) and len(nums) < 8:
                    if re.fullmatch(r"[-+]?\d+\.?\d*", tokens[j]):
                        nums.append(float(tokens[j]))
                        j += 1
                    else:
                        break
                if len(nums) == 8:
                    # 结构：抄见电量 换表 加减 抄见 算费 损耗 加减 计费（第8=计费电量）
                    best[key] = max(best[key], nums[7])
                break
    total_kwh = best["total"]
    if total_kwh <= 0:
        raise ValueError("未解析到主表计费电量")
    # A2：尖峰并入峰
    peak_kwh = best["peak"] + best["sharp"]
    flat_kwh = best["flat"]
    valley_kwh = best["valley"]

    name_map, id_set = _customer_maps()
    cid = customer_name if customer_name in id_set else name_map.get(customer_name)
    if not cid:
        problems.append("客户「%s」未建档，请先在客户管理建档" % customer_name)

    record = {
        "customer_id": cid,
        "customer_name": customer_name,
        "period": period,
        "total_mwh": round(total_kwh / 1000.0, 6),
        "peak_mwh": round(peak_kwh / 1000.0, 6),
        "flat_mwh": round(flat_kwh / 1000.0, 6),
        "valley_mwh": round(valley_kwh / 1000.0, 6),
        "current_amount": current_amount,
        "ktype": ktype,
    }
    if cid is None:
        # 客户未建档时不入 records，避免 upsert 失败；由 problems 提示
        records: List[Dict[str, Any]] = []
    else:
        records = [record]
    return {"records": records, "problems": problems}


def _parse_bill(content: bytes, filename: str = "") -> Dict[str, Any]:
    """按文件内容自动选择解析器（PDF / Excel）。"""
    if content[:4] == b"%PDF" or (filename or "").lower().endswith(".pdf"):
        return _parse_pdf(content)
    return _parse_excel(content)



def _parse_bill_pdf(content: bytes) -> Dict[str, Any]:
    """解析国网电费账单 PDF（5页版式）为核查联记录。

    提取：户号/户名/账单月份/本期电量/本期电费/市场化购电费/分时抄见电量(尖峰峰平谷深谷)/用电类别/两部制。
    口径：峰=尖峰+峰，谷=谷+深谷；kWh→MWh。
    """
    import io as _io
    import re as _re
    import tempfile as _tf

    import pypdf

    with _tf.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
        f.write(content)
        path = f.name
    reader = pypdf.PdfReader(path)
    full = "\n".join((pg.extract_text() or "") for pg in reader.pages)

    def _g(pattern, cast=str):
        m = _re.search(pattern, full)
        return m.group(1) if m else None

    account = _g(r"户号\s+(\d+)")
    name = _g(r"户名\s+(\S+)")
    dates = _re.findall(r"(\d{4})-(\d{2})-(\d{2})", full)
    period = "%s-%s" % (dates[0][0], dates[0][1]) if dates else None
    total_kwh = _g(r"本期电量\s*([\d,]+)\s*千瓦时")
    total_kwh = int(total_kwh.replace(",", "")) if total_kwh else None
    fee = _g(r"本期电费\s*([\d,.]+)\s*元")
    fee = float(fee.replace(",", "")) if fee else None
    mfee = _g(r"市场化购电费\s+([\d,.]+)")
    market_fee = float(mfee.replace(",", "")) if mfee else None
    category = _g(r"用电类别\s+(\S+)")
    two_part = "两部制" in full

    # 主表分时抄见电量（正向有功）
    seg = {"尖峰": 0, "峰": 0, "平": 0, "谷": 0, "深谷": 0}
    for line in full.split("\n"):
        m2 = _re.match(r"正向有功（(总|尖峰|峰|平|谷|深谷)）\s+(.*)", line.strip())
        if m2 and m2.group(1) != "总":
            nums = _re.findall(r"-?[\d.]+", m2.group(2))
            if len(nums) >= 4:
                try:
                    seg[m2.group(1)] += int(float(nums[3]))
                except (ValueError, IndexError):
                    pass

    peak_kwh = seg["尖峰"] + seg["峰"]
    flat_kwh = seg["平"]
    valley_kwh = seg["谷"] + seg["深谷"]
    segsum = peak_kwh + flat_kwh + valley_kwh

    problems = []
    if not period:
        problems.append("未解析到账单月份")
    if total_kwh is None:
        problems.append("未解析到本期电量")
    if abs(segsum - (total_kwh or 0)) > 10:
        problems.append("分时电量合计 %d 与总电量 %s 不一致" % (segsum, total_kwh))
    if not (name and account):
        problems.append("未解析到户名/户号")

    record = {
        "customer_name": name,
        "account_id": account,
        "period": period,
        "total_mwh": round((total_kwh or 0) / 1000.0, 3),
        "peak_mwh": round(peak_kwh / 1000.0, 3) if peak_kwh else None,
        "flat_mwh": round(flat_kwh / 1000.0, 3) if flat_kwh else None,
        "valley_mwh": round(valley_kwh / 1000.0, 3) if valley_kwh else None,
        "current_amount": fee,
        "market_fee": market_fee,
        "ktype": "两部制" if two_part else None,
        "category": category,
    }
    return {"record": record, "problems": problems, "seg_detail": seg}


@router.post("/parse-pdf", summary="上传电费账单PDF自动解析为核查联（不落库）")
async def parse_pdf(
    file: UploadFile = File(..., description="国网电费账单 PDF"),
    current_user: User = Depends(get_current_active_user),
):
    content = await file.read()
    try:
        info = _parse_bill_pdf(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail="PDF 解析失败：%s" % e)
    rec = info["record"]
    problems = list(info["problems"])
    # 客户匹配
    name_map, id_set = _customer_maps()
    cid = None
    if rec.get("customer_name"):
        s = str(rec["customer_name"]).strip()
        cid = s if s in id_set else name_map.get(s)
        if not cid:
            problems.append("客户『%s』未建档，请先在客户管理建档" % s)
    rec["customer_id"] = cid
    return {"ok": not problems or len(problems) <= 0, "problems": problems,
            "record": rec}


@router.post("/parse-pdf-batch", summary="批量上传多份账单PDF解析（不落库）")
async def parse_pdf_batch(
    files: List[UploadFile] = File(..., description="多份账单 PDF"),
    current_user: User = Depends(get_current_active_user),
):
    results = []
    name_map, id_set = _customer_maps()
    for f in files:
        content = await f.read()
        try:
            info = _parse_bill_pdf(content)
        except Exception as e:
            results.append({"file": f.filename, "ok": False,
                             "problems": ["PDF 解析失败：%s" % e], "record": None})
            continue
        rec = info["record"]
        problems = list(info["problems"])
        cid = None
        if rec.get("customer_name"):
            s = str(rec["customer_name"]).strip()
            cid = s if s in id_set else name_map.get(s)
            if not cid:
                problems.append("客户『%s』未建档" % s)
        rec["customer_id"] = cid
        results.append({"file": f.filename, "ok": not problems,
                        "problems": problems, "record": rec})
    ok_count = sum(1 for r in results if r["ok"])
    return {"ok_count": ok_count, "fail_count": len(results) - ok_count, "results": results}


@router.post("/import-parsed", summary="把PDF解析出的核查联记录落库")
async def import_parsed(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user),
):
    """payload: {records: [{customer_id, customer_name, period, total_mwh,
    peak_mwh, flat_mwh, valley_mwh, current_amount, market_fee, ktype, account_id, category}]}
    """
    records = payload.get("records") or []
    if not records:
        raise HTTPException(status_code=400, detail="records 为空")
    inserted = updated = skipped = 0
    for rec in records:
        if not rec.get("customer_id") or not rec.get("period"):
            skipped += 1
            continue
        doc = {
            "customer_id": rec["customer_id"],
            "customer_name": rec.get("customer_name"),
            "period": rec["period"],
            "total_mwh": float(rec.get("total_mwh") or 0),
            "peak_mwh": rec.get("peak_mwh"),
            "flat_mwh": rec.get("flat_mwh"),
            "valley_mwh": rec.get("valley_mwh"),
            "current_amount": rec.get("current_amount"),
            "market_fee": rec.get("market_fee"),
            "ktype": rec.get("ktype"),
            "account_id": rec.get("account_id"),
            "category": rec.get("category"),
            "imported_at": datetime.utcnow(),
        }
        existed = COLLECTION.find_one({"customer_id": doc["customer_id"], "period": doc["period"]}, {"_id": 1})
        COLLECTION.replace_one({"customer_id": doc["customer_id"], "period": doc["period"]}, doc, upsert=True)
        if existed:
            updated += 1
        else:
            inserted += 1
    try:
        COLLECTION.create_index([("customer_id", 1), ("period", 1)], unique=True)
    except Exception:
        pass
    return {"inserted": inserted, "updated": updated, "skipped": skipped}


@router.get("/template", summary="下载核查联导入模板")
def download_template(current_user: User = Depends(get_current_active_user)):
    import openpyxl
    from openpyxl.styles import Font, PatternFill

    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "核查联"
    bold = Font(bold=True)
    fill = PatternFill("solid", fgColor="DDEBF7")
    cols = ["客户名称", "月份", "月总电量(MWh)", "峰电量(MWh)", "平电量(MWh)", "谷电量(MWh)", "现状实收电费(元)", "用电类型"]
    for i, h in enumerate(cols, 1):
        c = ws.cell(1, i, h)
        c.font = bold
        c.fill = fill
    ws.cell(2, 1, "示例客户甲")
    ws.cell(2, 2, "2027-01")
    ws.cell(2, 3, 1000)
    ws.cell(2, 8, "单一制-100千伏安以下")
    ws2 = wb.create_sheet("填写说明")
    for i, t in enumerate([
        "【核查联填写说明】",
        "1. 客户名称须与客户管理一致（或填客户ID）",
        "2. 月份格式 YYYY-MM，如 2027-01",
        "3. 月总电量必填；峰/平/谷电量可选（不填则按默认占比拆分）",
        "4. 现状实收电费可选（填了可对比套餐省多少）",
        "5. 用电类型：两部制 / 单一制-100千伏安及以上 / 单一制-100千伏安以下",
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
        headers={"Content-Disposition": "attachment; filename=bill_template.xlsx"},
    )


@router.post("/preview", summary="上传核查联校验预览（不落库）")
async def preview_excel(file: UploadFile = File(...), current_user: User = Depends(get_current_active_user)):
    content = await file.read()
    try:
        info = _parse_bill(content, getattr(file, "filename", "") or "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    return {"ok": not info["problems"] and len(info["records"]) > 0,
            "problems": info["problems"], "record_count": len(info["records"]),
            "sample": info["records"][:10]}


@router.post("/import", summary="上传核查联导入落库")
async def import_excel(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
):
    content = await file.read()
    try:
        info = _parse_bill(content, getattr(file, "filename", "") or "")
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    records = info["records"]
    if not records:
        raise HTTPException(status_code=400, detail="未解析到核查联记录")
    # upsert by (customer_id, period)
    inserted = updated = 0
    for rec in records:
        rec["imported_at"] = datetime.utcnow()
        existed = COLLECTION.find_one({"customer_id": rec["customer_id"], "period": rec["period"]}, {"_id": 1})
        COLLECTION.replace_one({"customer_id": rec["customer_id"], "period": rec["period"]}, rec, upsert=True)
        if existed:
            updated += 1
        else:
            inserted += 1
    try:
        COLLECTION.create_index([("customer_id", 1), ("period", 1)], unique=True)
    except Exception:
        pass
    return {"inserted": inserted, "updated": updated, "problems": info["problems"]}


@router.get("/records", summary="查询已导入核查联")
def list_records(
    period: Optional[str] = Query(None),
    customer_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
):
    q: Dict[str, Any] = {}
    if period:
        q["period"] = period
    if customer_id:
        q["customer_id"] = customer_id
    rows = []
    for d in COLLECTION.find(q).sort("period", 1).limit(2000):
        rows.append({
            "customer_id": d.get("customer_id"),
            "customer_name": d.get("customer_name"),
            "period": d.get("period"),
            "total_mwh": d.get("total_mwh"),
            "peak_mwh": d.get("peak_mwh"),
            "flat_mwh": d.get("flat_mwh"),
            "valley_mwh": d.get("valley_mwh"),
            "current_amount": d.get("current_amount"),
            "ktype": d.get("ktype"),
        })
    return {"total": COLLECTION.count_documents(q), "rows": rows}


@router.delete("/records", summary="删除核查联")
def delete_records(
    customer_id: Optional[str] = Query(None),
    period: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
):
    q: Dict[str, Any] = {}
    if customer_id:
        q["customer_id"] = customer_id
    if period:
        q["period"] = period
    if not q:
        raise HTTPException(status_code=400, detail="至少指定客户或月份")
    return {"deleted": COLLECTION.delete_many(q).deleted_count}


@router.post("/batch-calc", summary="核查联批量测算")
async def batch_calc(
    payload: Dict[str, Any] = Body(...),
    current_user: User = Depends(get_current_active_user),
):
    """对选定的核查联逐条按「路径B」测算。

    payload:
      package_id: 套餐ID（必填）
      period: 可选，只测算某月（YYYY-MM）
      customer_ids: 可选，只测算某些客户
      market: {wholesale_price, share_cost_compensation, share_imbalance, share_market_adjust}
      params: 套餐参数覆盖（可选）
    """
    from webapp.services.package_service import PackageService
    from webapp.services.package_calc_service import PackageCalcService

    package_id = payload.get("package_id")
    if not package_id:
        raise HTTPException(status_code=400, detail="缺少 package_id")
    try:
        package = PackageService(DATABASE).get_by_id(package_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

    q: Dict[str, Any] = {}
    if payload.get("period"):
        q["period"] = payload["period"]
    if payload.get("customer_ids"):
        q["customer_id"] = {"$in": payload["customer_ids"]}
    bills = list(COLLECTION.find(q))
    if not bills:
        return {"count": 0, "rows": [], "summary": {}}

    market = payload.get("market") or {}
    params_override = payload.get("params")
    svc = PackageCalcService(DATABASE)
    rows = []
    for b in bills:
        bill = {
            "period": b.get("period"),
            "total_mwh": b.get("total_mwh"),
            "peak_mwh": b.get("peak_mwh"),
            "flat_mwh": b.get("flat_mwh"),
            "valley_mwh": b.get("valley_mwh"),
            "current_amount": b.get("current_amount"),
            "customer_name": b.get("customer_name"),
            "ktype": b.get("ktype") or "单一制-100千伏安以下",
        }
        try:
            r = svc.calc_from_bill(
                package=package, bill=bill, market=dict(market), overrides=params_override,
                pointwise=bool(payload.get("pointwise", True)),
                holding_ratio=float(payload.get("holding_ratio", 0.9)),
                k2_ratio=float(payload.get("k2_ratio", 0.05)),
                customer_id=b.get("customer_id"),
                market_source=str(payload.get("market_source", "manual")),
            )
        except Exception as e:
            rows.append({"customer": b.get("customer_name"), "period": b.get("period"),
                         "error": str(e)})
            continue
        rows.append({
            "customer_id": b.get("customer_id"),
            "customer": b.get("customer_name"),
            "period": b.get("period"),
            "volume_mwh": r.get("total_mwh"),
            "peak_price": (r.get("prices") or {}).get("peak_price"),
            "flat_price": (r.get("prices") or {}).get("flat_price"),
            "valley_price": (r.get("prices") or {}).get("valley_price"),
            "retail_avg": r.get("energy_avg_price"),
            "cap_price": r.get("cap_price"),
            "capped": r.get("capped"),
            "settle_price": r.get("settle_price"),
            "sell_price": r.get("sell_price"),
            "current_amount": r.get("current_amount"),
            "package_amount": r.get("total_cost"),
            "diff": r.get("diff"),
            "saving_rate": r.get("saving_rate"),
            "verdict": r.get("verdict"),
            "sgcc_price": ((r.get("sgcc") or {}) or {}).get("avg_on_grid_price"),
            "pricing_mode": r.get("pricing_mode"),
            "market_source": (r.get("market_meta") or {}).get("market_source") or "manual",
        })

    ok_rows = [x for x in rows if "error" not in x]
    summary = {
        "count": len(rows),
        "success": len(ok_rows),
        "failed": len(rows) - len(ok_rows),
        "total_volume_mwh": round(sum((x.get("volume_mwh") or 0) for x in ok_rows), 3),
        "total_package_amount": round(sum((x.get("package_amount") or 0) for x in ok_rows), 2),
        "total_current_amount": round(sum((x.get("current_amount") or 0) for x in ok_rows), 2),
    }
    return {"count": len(rows), "rows": rows, "summary": summary}
