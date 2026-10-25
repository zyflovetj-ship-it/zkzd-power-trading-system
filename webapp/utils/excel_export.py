"""
通用 Excel 导出助手

设计说明
--------
导出端点只做一件事：把 service 返回的行数据落成 xlsx 流。
表头是给人看的中文名，不参与前端 TypeScript 类型契约，
因此可以安全地基于现有 service 实现，无需改动 GET 接口。

列定义用 (源字段, 表头名) 显式声明，避免 dict 顺序漂移导致错列。
"""

import io
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Sequence, Tuple
from urllib.parse import quote

import pandas as pd
from fastapi.responses import StreamingResponse

logger = logging.getLogger(__name__)

XLSX_MIME = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

#: 列定义：(数据源字段名, Excel 表头名)
Columns = Sequence[Tuple[str, str]]

#: 样例桩数据的统一警示语。
#: 结算/持仓等模块当前仍返回确定性样例（2026-10-25 决策：先样例，后转真实库）。
#: 导出物会脱离系统以 Excel 形式流转，必须自带数据来源声明，
#: 避免样例数字被当作真实财务数据用于对账或报送。
SAMPLE_DATA_NOTICE = (
    "本表为系统样例（演示）数据，尚未接入真实业务集合；"
    "不可用于财务对账、结算确认或对外报送。"
)
REAL_DATA_NOTICE = "本表数据来源为系统真实业务集合。"


def rows_to_frame(rows: List[Dict[str, Any]], columns: Columns) -> pd.DataFrame:
    """按列定义抽取字段并改名为中文表头；缺失字段填空。"""
    df = pd.DataFrame(rows or [])
    out = pd.DataFrame()
    for key, label in columns:
        out[label] = df[key] if key in df.columns else [""] * len(df)
    return out


#: 一个 Sheet：(Sheet 名, 行数据, 列定义)
Sheet = Tuple[str, List[Dict[str, Any]], Columns]


def _wrap(buf: io.BytesIO, filename_prefix: str, total_rows: int) -> StreamingResponse:
    buf.seek(0)
    filename = "{0}_{1}.xlsx".format(
        filename_prefix, datetime.now().strftime("%Y%m%d_%H%M%S")
    )
    logger.info("导出 %s：%d 行", filename, total_rows)
    return StreamingResponse(
        buf,
        media_type=XLSX_MIME,
        headers={
            "Content-Disposition": "attachment; filename*=UTF-8''{0}".format(quote(filename))
        },
    )


def build_excel_response(
    rows: List[Dict[str, Any]],
    columns: Columns,
    filename_prefix: str,
    sheet_name: str = "Sheet1",
    data_notice: Optional[Dict[str, str]] = None,
) -> StreamingResponse:
    """生成单 Sheet 的 xlsx 下载响应。"""
    return build_multi_excel_response(
        [(sheet_name, rows, columns)], filename_prefix, data_notice=data_notice
    )


def build_multi_excel_response(
    sheets: Sequence[Sheet],
    filename_prefix: str,
    data_notice: Optional[Dict[str, str]] = None,
) -> StreamingResponse:
    """生成多 Sheet 的 xlsx 下载响应，文件名带时间戳并做 UTF-8 编码以兼容中文。

    :param data_notice: 追加"数据来源说明"Sheet 的键值对，用于声明数据性质。
    """
    buf = io.BytesIO()
    total = 0
    with pd.ExcelWriter(buf, engine="openpyxl") as writer:
        for name, rows, columns in sheets:
            frame = rows_to_frame(rows, columns)
            total += len(frame)
            frame.to_excel(writer, index=False, sheet_name=name[:31])
        if data_notice:
            notice_df = pd.DataFrame(
                list(data_notice.items()), columns=["项目", "内容"]
            )
            notice_df.to_excel(writer, index=False, sheet_name="数据来源说明")
    return _wrap(buf, filename_prefix, total)
