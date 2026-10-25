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
