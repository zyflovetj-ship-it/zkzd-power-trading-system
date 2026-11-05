import apiClient from './client';

// ===== 96点负荷导入 =====
export interface LoadMonthGroup {
  customer_id: string;
  user_name?: string;
  month: string;
  source?: string;
  points: number;
  days?: number;
}

export function loadTemplateUrl() {
  const base = import.meta.env.VITE_API_BASE_URL ?? '';
  return base + '/api/v1/load-data/template';
}

/** 下载 96 点负荷导入模板（带鉴权） */
export async function downloadLoadTemplate(filename = 'load_data_template.xlsx'): Promise<void> {
  const { downloadAuthFile } = await import('./client');
  await downloadAuthFile(loadTemplateUrl(), filename);
}

export async function previewLoadExcel(file: File) {
  const fd = new FormData();
  fd.append('file', file);
  const r = await apiClient.post('/api/v1/load-data/preview', fd);
  return r.data as { ok: boolean; problems: string[]; record_count: number; months: LoadMonthGroup[] };
}

export async function importLoadExcel(file: File, replace = true) {
  const fd = new FormData();
  fd.append('file', file);
  const r = await apiClient.post('/api/v1/load-data/import', fd, { params: { replace } });
  return r.data as { inserted: number; deleted: number; months: LoadMonthGroup[]; problems: string[] };
}

export async function fetchLoadRecords(params: { customer_id?: string; source?: string }) {
  const r = await apiClient.get('/api/v1/load-data/records', { params });
  return r.data as { total_points: number; groups: LoadMonthGroup[]; by_source?: Record<string, number> };
}

export async function deleteLoadRecords(params: { customer_id: string; month: string; source?: string }) {
  const r = await apiClient.delete('/api/v1/load-data/records', { params });
  return r.data as { deleted: number; source?: string };
}

// ===== 核查联批量导入 + 测算 =====
export interface BillRow {
  customer_id: string;
  customer_name: string;
  period: string;
  total_mwh: number;
  peak_mwh?: number;
  flat_mwh?: number;
  valley_mwh?: number;
  current_amount?: number;
  ktype?: string;
}

export function billTemplateUrl() {
  const base = import.meta.env.VITE_API_BASE_URL ?? '';
  return base + '/api/v1/bills/template';
}

/** 下载核查联导入模板（带鉴权） */
export async function downloadBillTemplate(filename = 'bill_template.xlsx'): Promise<void> {
  const { downloadAuthFile } = await import('./client');
  await downloadAuthFile(billTemplateUrl(), filename);
}

export async function previewBillExcel(file: File) {
  const fd = new FormData();
  fd.append('file', file);
  const r = await apiClient.post('/api/v1/bills/preview', fd);
  return r.data as { ok: boolean; problems: string[]; record_count: number; sample: BillRow[] };
}

export async function importBillExcel(file: File) {
  const fd = new FormData();
  fd.append('file', file);
  const r = await apiClient.post('/api/v1/bills/import', fd);
  return r.data as { inserted: number; updated: number; problems: string[] };
}

export async function fetchBillRecords(params: { period?: string; customer_id?: string }) {
  const r = await apiClient.get('/api/v1/bills/records', { params });
  return r.data as { total: number; rows: BillRow[] };
}

export async function deleteBillRecords(params: { customer_id?: string; period?: string }) {
  const r = await apiClient.delete('/api/v1/bills/records', { params });
  return r.data as { deleted: number };
}

export async function batchCalcBills(payload: {
  package_id: string;
  period?: string;
  customer_ids?: string[];
  market?: Record<string, number>;
  params?: Record<string, number | string>;
  pointwise?: boolean;
  holding_ratio?: number;
  k2_ratio?: number;
  market_source?: 'manual' | 'system';
}) {
  const r = await apiClient.post('/api/v1/bills/batch-calc', payload);
  return r.data as { count: number; rows: any[]; summary: Record<string, number> };
}

// ===== 账单PDF自动解析 =====
export interface ParsedBillRecord {
  customer_id?: string;
  customer_name?: string;
  account_id?: string;
  period?: string;
  total_mwh?: number;
  peak_mwh?: number;
  flat_mwh?: number;
  valley_mwh?: number;
  current_amount?: number;
  market_fee?: number;
  ktype?: string;
  category?: string;
  [k: string]: unknown;
}

export interface ParsedBillResult {
  file: string;
  ok: boolean;
  problems: string[];
  record: ParsedBillRecord | null;
}

export async function parseBillPdfs(files: File[]): Promise<{
  ok_count: number;
  fail_count: number;
  results: ParsedBillResult[];
}> {
  const fd = new FormData();
  files.forEach((f) => fd.append('files', f));
  const r = await apiClient.post('/api/v1/bills/parse-pdf-batch', fd);
  return r.data;
}

export async function importParsedBills(records: ParsedBillRecord[]): Promise<{
  inserted: number;
  updated: number;
  skipped: number;
}> {
  const r = await apiClient.post('/api/v1/bills/import-parsed', { records });
  return r.data;
}
