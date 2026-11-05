"""中长期/绿电合同量价 管理接口（前端界面用）。

端点：
  GET  /mid-long-contracts/template        下载填数据用 Excel 模板
  POST /mid-long-contracts/preview         上传 Excel -> 校验 + 预览逐点中长期价（不落库）
  POST /mid-long-contracts/import          上传 Excel -> 校验通过后导入落库
  GET  /mid-long-contracts/records         查询已导入的合同量价（分页 + 统计）
  DELETE /mid-long-contracts/records       按 年+客户 删除
"""
import io
import tempfile
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse

from webapp.tools.mongo import DATABASE
from webapp.tools.security import User, get_current_active_user

router = APIRouter(prefix="/mid-long-contracts", tags=["Mid-Long Contracts"])
COLLECTION = DATABASE["mid_long_contracts"]


def _parse_upload(content: bytes):
    """把上传的 xlsx 字节写入临时文件并解析为记录列表。"""
    from webapp.scripts.import_mid_long_contracts import _records_from_excel, _detect_block_rows
    import openpyxl

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        f.write(content)
        path = f.name

    wb = openpyxl.load_workbook(path, data_only=True)
    if "中长期及绿电量价数据" not in wb.sheetnames:
        raise ValueError("缺少工作表『中长期及绿电量价数据』")
    ws = wb["中长期及绿电量价数据"]
    block_rows = _detect_block_rows(ws)

    # 预览信息：各块 1 月电量 / 首行价
    blocks = []
    for s in block_rows:
        ct = ws.cell(s, 2).value
        vol = 0.0
        for t in range(24):
            try:
                vol += float(ws.cell(s + 1 + t, 3).value or 0)
            except (TypeError, ValueError):
                pass
        blocks.append({"contract_type": ct, "jan_volume_mwh": round(vol, 3),
                       "first_price": ws.cell(s + 1, 17).value})

    # 逐点中长期价预览（1 月）
    annual_names = {"年度合计", "年度绿电"}
    annual_rows = {s for s in block_rows if ws.cell(s, 2).value in annual_names}
    preview = []
    for t in range(24):
        num = den = 0.0
        for s in block_rows:
            r = s + 1 + t
            try:
                v = float(ws.cell(r, 3).value or 0)
            except (TypeError, ValueError):
                v = 0.0
            p_row = (s + 1) if s in annual_rows else r
            try:
                p = float(ws.cell(p_row, 17).value or 0)
            except (TypeError, ValueError):
                p = 0.0
            num += v * p
            den += v
        preview.append(round(num / den, 3) if den > 0 else None)

    return {"path": path, "block_rows": block_rows, "blocks": blocks, "preview": preview}


@router.get("/template", summary="下载中长期合同量价填写模板")
def download_template(current_user: User = Depends(get_current_active_user)):
    """生成并下载空白填写模板（12 合同块 × 12 月 × 24 时段）。"""
    from webapp.scripts.mid_long_template import gen_template

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        path = f.name
    gen_template(path)
    data = open(path, "rb").read()
    return StreamingResponse(
        io.BytesIO(data),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=mid_long_contract_template.xlsx"},
    )


@router.post("/preview", summary="上传Excel校验并预览（不落库）")
async def preview_excel(
    file: UploadFile = File(..., description="中长期合同量价 Excel"),
    current_user: User = Depends(get_current_active_user),
):
    content = await file.read()
    try:
        info = _parse_upload(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    # 阻断性问题（真正导致无法导入）
    problems = []
    if len(info["block_rows"]) != 12:
        problems.append("合同块数量 %d ≠ 期望 12（请使用标准模板）" % len(info["block_rows"]))
    total_vol = sum((b.get("jan_volume_mwh") or 0) for b in info["blocks"])
    if total_vol <= 0:
        problems.append("1月所有合同块电量合计为 0，无可导入数据")
    # 提示性警告（零电量合同块属正常：部分合同仅特定月份有量，不影响导入）
    warnings = []
    zero_blocks = [b["contract_type"] for b in info["blocks"] if (b.get("jan_volume_mwh") or 0) == 0]
    if zero_blocks:
        warnings.append("以下合同块 1 月无电量（正常，如仅特定月份交易）：" + "、".join(zero_blocks))
    return {
        "ok": not problems,
        "problems": problems,
        "warnings": warnings,
        "blocks": info["blocks"],
        "preview_prices": info["preview"],
    }


@router.post("/import", summary="上传Excel导入中长期合同量价")
async def import_excel(
    file: UploadFile = File(..., description="中长期合同量价 Excel"),
    year: int = Query(..., description="年份，如 2027"),
    customer_id: Optional[str] = Query(None, description="客户ID（空=全市场统一）"),
    customer_name: Optional[str] = Query(None, description="客户名称（可选）"),
    current_user: User = Depends(get_current_active_user),
):
    content = await file.read()
    from webapp.scripts.import_mid_long_contracts import _records_from_excel

    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        records = _records_from_excel(path, year, customer_id, customer_name)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not records:
        raise HTTPException(status_code=400, detail="未解析到任何记录（检查表结构/电量是否为空）")

    # 只清理"同年度+同客户"的旧数据
    deleted = COLLECTION.delete_many({"year": year, "customer_id": customer_id}).deleted_count
    COLLECTION.insert_many(records)
    try:
        COLLECTION.create_index([("year", 1), ("customer_id", 1), ("month", 1), ("contract_type", 1), ("time_index", 1)])
    except Exception:
        pass
    return {"inserted": len(records), "deleted": deleted, "year": year,
            "customer_id": customer_id, "customer_name": customer_name}


@router.get("/records", summary="查询已导入的合同量价（统计）")
def list_records(
    year: Optional[int] = Query(None),
    customer_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
):
    q: Dict[str, Any] = {}
    if year:
        q["year"] = year
    if customer_id:
        q["customer_id"] = customer_id
    total = COLLECTION.count_documents(q)
    # 按 年/客户/月 聚合统计
    pipeline = [
        {"$match": q},
        {"$group": {
            "_id": {"year": "$year", "customer_id": "$customer_id",
                    "customer_name": "$customer_name", "month": "$month"},
            "rows": {"$sum": 1},
            "volume_mwh": {"$sum": "$volume_mwh"},
        }},
        {"$sort": {"_id.year": 1, "_id.month": 1}},
    ]
    groups = []
    for g in COLLECTION.aggregate(pipeline):
        groups.append({
            "year": g["_id"].get("year"),
            "customer_id": g["_id"].get("customer_id"),
            "customer_name": g["_id"].get("customer_name"),
            "month": g["_id"].get("month"),
            "rows": g["rows"],
            "volume_mwh": round(g["volume_mwh"] or 0, 3),
        })
    return {"total": total, "groups": groups}


@router.delete("/records", summary="按年+客户删除合同量价")
def delete_records(
    year: int = Query(...),
    customer_id: Optional[str] = Query(None),
    current_user: User = Depends(get_current_active_user),
):
    q: Dict[str, Any] = {"year": year}
    if customer_id:
        q["customer_id"] = customer_id
    else:
        q["customer_id"] = None
    deleted = COLLECTION.delete_many(q).deleted_count
    return {"deleted": deleted, "year": year, "customer_id": customer_id}
