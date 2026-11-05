"""国网代购电价导入接口（按月更新）。

- Excel 导入：支持《套餐测算模板-新v2》「代购电情况」页布局，或通用两列（月份/代购价）表
- PDF 导入：存档公告 PDF，并尽力抽取「代理购电价格」数值（标记 needs_review）
- 缺失月份提醒：按月核对某年已入库月份

注意：代理购电价格**按月调整**（发改办价格〔2021〕809号），应逐月更新。
"""
import io
import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile

from webapp.tools.mongo import DATABASE
from webapp.tools.security import User, get_current_active_user

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/prices/sgcc", tags=["SGCC Price"])
COLLECTION = DATABASE["price_sgcc"]


def _month_id(year: int, month: int) -> str:
    return f"{year}-{month:02d}"


def _upsert(records: List[Dict[str, Any]], source: str) -> Dict[str, int]:
    inserted = updated = 0
    for rec in records:
        mid = rec["month"]
        price_kwh = float(rec["price_kwh"])
        avg_kwh = float(rec.get("avg_kwh") or 0)
        doc = {
            "_id": mid,
            "month": mid,
            "purchase_price": round(price_kwh * 1000, 2),   # 元/MWh
            "avg_on_grid_price": round(avg_kwh * 1000, 2),  # 元/MWh
            "attachment_name": rec.get("attachment_name") or f"{mid}电网代理购电价格公告.pdf",
            "full_data": {"price_composition": [
                ["项目", "金额（元/千瓦时）"],
                ["一、代理购电价格", f"{price_kwh:.4f}"],
            ]},
            "source": source,
            "imported_at": datetime.utcnow(),
        }
        if rec.get("needs_review"):
            doc["needs_review"] = True
        existed = COLLECTION.find_one({"_id": mid}, {"_id": 1})
        COLLECTION.replace_one({"_id": mid}, doc, upsert=True)
        if existed:
            updated += 1
        else:
            inserted += 1
    return {"inserted": inserted, "updated": updated}


def _parse_excel(content: bytes, year: int) -> Dict[str, Any]:
    import openpyxl

    wb = openpyxl.load_workbook(io.BytesIO(content), data_only=True)
    # 1) 模板「代购电情况」布局
    ws = None
    for name in wb.sheetnames:
        if "代购电" in name:
            ws = wb[name]
            break
    if ws is not None:
        price_row = avg_row = None
        for r in range(1, 10):
            label = str(ws.cell(r, 1).value or "")
            if "代购电价格" in label:
                price_row = r
            if "代购电均价" in label or "用户代购电均价" in label:
                avg_row = r
        if price_row:
            records = []
            for i in range(12):
                c = 2 + i
                p = ws.cell(price_row, c).value
                if p in (None, "", 0):
                    continue
                a = ws.cell(avg_row, c).value if avg_row else 0
                records.append({
                    "month": _month_id(year, i + 1),
                    "price_kwh": float(p),
                    "avg_kwh": float(a or 0),
                })
            if records:
                return {"records": records, "layout": "代购电情况"}

    # 2) 通用两列表
    ws0 = wb[wb.sheetnames[0]]
    header = [str(ws0.cell(1, c).value or "") for c in range(1, ws0.max_column + 1)]
    m_col = next((i for i, h in enumerate(header) if "月" in h), None)
    p_col = next((i for i, h in enumerate(header) if "代购" in h or "价格" in h), None)
    a_col = next((i for i, h in enumerate(header) if "均价" in h), None)
    if m_col is None or p_col is None:
        raise ValueError("无法识别 Excel 结构：请使用「代购电情况」模板，或含『月份』『代购价格』两列的表")
    records = []
    for r in range(2, ws0.max_row + 1):
        mv = ws0.cell(r, m_col + 1).value
        pv = ws0.cell(r, p_col + 1).value
        if pv in (None, ""):
            continue
        # 月份解析：2027-01 / 1 / 1月
        month = None
        s = str(mv or "").strip()
        m1 = re.match(r"^(\d{4})-(\d{1,2})$", s)
        m2 = re.match(r"^(\d{1,2})月?$", s)
        if m1:
            records.append({"month": f"{m1.group(1)}-{int(m1.group(2)):02d}",
                            "price_kwh": float(pv),
                            "avg_kwh": float(ws0.cell(r, a_col + 1).value or 0) if a_col is not None else 0})
            continue
        if m2:
            month = int(m2.group(1))
        if month is None or not (1 <= month <= 12):
            continue
        records.append({
            "month": _month_id(year, month),
            "price_kwh": float(pv),
            "avg_kwh": float(ws0.cell(r, a_col + 1).value or 0) if a_col is not None else 0,
        })
    return {"records": records, "layout": "通用表"}


def _parse_pdf(content: bytes) -> Dict[str, Any]:
    try:
        from pypdf import PdfReader
    except Exception:
        return {"available": False, "price_kwh": None, "text_len": 0}
    reader = PdfReader(io.BytesIO(content))
    text = "\n".join((p.extract_text() or "") for p in reader.pages)
    price = None
    # 找「代理购电价格」附近 0.xxxx 数字
    m = re.search(r"代理购电价格[^0-9]{0,20}(\d\.\d{3,4})", text)
    if m:
        price = float(m.group(1))
    else:
        m2 = re.search(r"(\d\.\d{3,4})\s*元/?千瓦", text)
        if m2:
            price = float(m2.group(1))
    return {"available": True, "price_kwh": price, "text_len": len(text)}


@router.get("/missing-months", summary="国网代购电价缺失月份")
def missing_months(year: int = Query(..., description="年份，如 2027")):
    existing = {d["_id"] for d in COLLECTION.find({"_id": {"$regex": f"^{year}-"}}, {"_id": 1})}
    all_months = [_month_id(year, m) for m in range(1, 13)]
    missing = [m for m in all_months if m not in existing]
    return {"year": year, "total": 12, "present": 12 - len(missing), "missing": missing}


@router.post("/import-excel", summary="上传Excel导入国网代购电价")
async def import_sgcc_excel(
    file: UploadFile = File(..., description="代购电情况模板或含 月份/代购价格 的Excel"),
    year: int = Query(2027, description="年份（用于 1-12 月映射）"),
    current_user: User = Depends(get_current_active_user),
):
    try:
        content = await file.read()
        parsed = _parse_excel(content, year)
        records = parsed["records"]
        if not records:
            raise HTTPException(status_code=400, detail="未解析到有效数据行")
        stat = _upsert(records, source="excel_import")
        return {"layout": parsed["layout"], "rows": len(records), **stat}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("导入代购电价Excel失败: %s", e, exc_info=True)
        raise HTTPException(status_code=400, detail=f"导入失败: {e}")


@router.post("/import-pdf", summary="上传PDF公告（存档并尽力解析价格）")
async def import_sgcc_pdf(
    file: UploadFile = File(..., description="国网代理购电价格公告PDF"),
    month: str = Query(..., description="归属月份 YYYY-MM"),
    current_user: User = Depends(get_current_active_user),
):
    content = await file.read()
    parsed = _parse_pdf(content)
    COLLECTION.update_one(
        {"_id": month},
        {"$set": {
            "attachment_name": file.filename,
            "pdf_binary_data": content,
            "pdf_imported_at": datetime.utcnow(),
        }},
        upsert=True,
    )
    price = parsed.get("price_kwh")
    if price is not None:
        COLLECTION.update_one(
            {"_id": month},
            {"$set": {
                "purchase_price": round(price * 1000, 2),
                "needs_review": True,
                "source": "pdf_import",
            }},
        )
    return {
        "month": month,
        "pdf_saved": True,
        "pypdf_available": parsed.get("available", False),
        "parsed_price_kwh": price,
        "needs_review": price is not None,
        "message": (
            "已存档PDF并解析出代理购电价格，请核对" if price is not None
            else ("PDF已存档；未能自动解析价格，请用Excel导入数值" if parsed.get("available")
                  else "PDF已存档；服务端未安装pypdf，无法解析，请用Excel导入数值")
        ),
    }
