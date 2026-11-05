import apiClient from './client';

// 中长期/绿电合同量价管理接口

export interface MidLongBlock {
  contract_type: string;
  jan_volume_mwh: number;
  first_price: number | null;
}

export interface MidLongPreview {
  ok: boolean;
  problems: string[];
  warnings?: string[];
  blocks: MidLongBlock[];
  preview_prices: (number | null)[];
}

export interface MidLongGroup {
  year: number | null;
  customer_id: string | null;
  customer_name: string | null;
  month: number;
  rows: number;
  volume_mwh: number;
}

export interface MidLongRecords {
  total: number;
  groups: MidLongGroup[];
}

/** 下载填写模板（带鉴权） */
export function midLongTemplateUrl() {
  const base = import.meta.env.VITE_API_BASE_URL ?? '';
  return base + '/api/v1/mid-long-contracts/template';
}

export async function downloadMidLongTemplate(filename = 'mid_long_contract_template.xlsx'): Promise<void> {
  const { downloadAuthFile } = await import('./client');
  await downloadAuthFile(midLongTemplateUrl(), filename);
}

/** 上传 Excel 校验预览（不落库） */
export async function previewMidLongExcel(file: File): Promise<MidLongPreview> {
  const fd = new FormData();
  fd.append('file', file);
  const r = await apiClient.post('/api/v1/mid-long-contracts/preview', fd);
  return r.data;
}

/** 导入 Excel */
export async function importMidLongExcel(
  file: File,
  params: { year: number; customer_id?: string; customer_name?: string },
): Promise<{ inserted: number; deleted: number }> {
  const fd = new FormData();
  fd.append('file', file);
  const r = await apiClient.post('/api/v1/mid-long-contracts/import', fd, { params });
  return r.data;
}

/** 查询已导入统计 */
export async function fetchMidLongRecords(params: {
  year?: number;
  customer_id?: string;
}): Promise<MidLongRecords> {
  const r = await apiClient.get('/api/v1/mid-long-contracts/records', { params });
  return r.data;
}

/** 删除 */
export async function deleteMidLongRecords(params: {
  year: number;
  customer_id?: string;
}): Promise<{ deleted: number }> {
  const r = await apiClient.delete('/api/v1/mid-long-contracts/records', { params });
  return r.data;
}
