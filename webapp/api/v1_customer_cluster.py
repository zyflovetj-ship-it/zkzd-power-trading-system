from fastapi import APIRouter, Depends, Query, Body, HTTPException, status, UploadFile, File
from fastapi.responses import StreamingResponse
from typing import List, Optional
from datetime import datetime
import io
import logging
from urllib.parse import quote
import pandas as pd
from webapp.services.customer_cluster_service import CustomerClusterService
from webapp.tools.mongo import DATABASE
from webapp.tools.security import get_current_active_user, User

logger = logging.getLogger(__name__)

router = APIRouter(tags=["客户聚类分析"])


@router.post("", response_model=dict, summary="执行客户聚类")
async def cluster_customers(
    n_clusters: int = Body(3, embed=True, description="聚类数"),
    features: List[str] = Body(["peak_valley_ratio", "load_rate", "volatility"], embed=True, description="特征列表"),
    current_user: User = Depends(get_current_active_user)
):
    service = CustomerClusterService(DATABASE)
    return service.cluster_customers(n_clusters=n_clusters, features=features)


@router.get("/export", summary="导出聚类结果")
async def export_cluster_result(
    n_clusters: int = Query(3, ge=2, le=10, description="聚类数"),
    current_user: User = Depends(get_current_active_user)
):
    service = CustomerClusterService(DATABASE)
    data = service.cluster_customers(n_clusters=n_clusters)
    rows = []
    for item in data.get("results", []):
        rows.append({
            "客户ID": item.get("customer_id", ""),
            "客户名称": item.get("customer_name", ""),
            "簇编号": item.get("cluster", 0),
            "峰谷比": item.get("features", {}).get("peak_valley_ratio", ""),
            "负荷率": item.get("features", {}).get("load_rate", ""),
            "波动性": item.get("features", {}).get("volatility", ""),
        })
    df = pd.DataFrame(rows)
    buf = io.BytesIO()
    df.to_excel(buf, index=False, engine="openpyxl")
    buf.seek(0)
    filename = f"customer_cluster_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f"attachment; filename*=UTF-8''{quote(filename)}"}
    )
