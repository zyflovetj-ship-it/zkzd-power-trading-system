import apiClient from './client';

// 国网代购电价（price_sgcc 集合）—— 后端仅提供只读接口 + 公开 PDF 下载
export interface SgccPriceData {
  _id: string; // "YYYY-MM"
  attachment_name?: string;
  avg_on_grid_price: number;
  historical_deviation_discount: number;
  network_loss_price: number;
  purchase_price: number;
  purchase_scale_kwh: number;
  system_op_cost_discount: number;
  full_data?: { price_composition: (string | number)[][] };
}

export interface SgccListResult {
  total: number;
  pageData: SgccPriceData[];
  chartData: SgccPriceData[];
}

export async function fetchSgccPrices(params: {
  page?: number;
  pageSize?: number; // 注意：该接口用 camelCase 的 pageSize
}): Promise<SgccListResult> {
  const r = await apiClient.get('/api/v1/prices/sgcc', { params });
  return r.data;
}

/** 公开端点（无需 JWT），返回 PDF 流，直接用浏览器打开即可 */
export function getSgccPdfUrl(month: string): string {
  const base = apiClient.defaults.baseURL ?? '';
  return `${base}/api/v1/prices/sgcc/${encodeURIComponent(month)}/pdf`;
}

export interface MissingMonthsResult {
  year: number;
  total: number;
  present: number;
  missing: string[];
}

/** 查询某年已入库/缺失月份 */
export async function getMissingMonths(year: number): Promise<MissingMonthsResult> {
  const r = await apiClient.get('/api/v1/prices/sgcc/missing-months', { params: { year } });
  return r.data;
}

/** 上传 Excel 导入代购电价（代购电情况模板 / 月份+代购价格两列） */
export async function importSgccExcel(file: File, year: number): Promise<unknown> {
  const fd = new FormData();
  fd.append('file', file);
  const r = await apiClient.post('/api/v1/prices/sgcc/import-excel', fd, { params: { year } });
  return r.data;
}

/** 上传 PDF 公告（存档并尽力解析价格） */
export async function importSgccPdf(file: File, month: string): Promise<unknown> {
  const fd = new FormData();
  fd.append('file', file);
  const r = await apiClient.post('/api/v1/prices/sgcc/import-pdf', fd, { params: { month } });
  return r.data;
}
