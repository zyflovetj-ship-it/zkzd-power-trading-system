import apiClient from './client';

// ============ 类型定义 ============
export type ContractStatus = 'pending' | 'active' | 'expired';

export interface Contract {
  id: string;
  contract_name: string;
  package_name: string;
  package_id: string;
  customer_name: string;
  customer_id: string;
  purchasing_electricity_quantity: number;
  purchase_start_month: string;
  purchase_end_month: string;
  status: ContractStatus;
  created_at: string;
  updated_at: string;
}

export interface ContractListResult {
  items: Contract[];
  total: number;
  page: number;
  page_size: number;
}

export interface ContractListParams {
  contract_name?: string;
  package_name?: string;
  customer_name?: string;
  status?: ContractStatus | 'all';
  purchase_start_month?: string;
  purchase_end_month?: string;
  page?: number;
  page_size?: number;
}

export interface ContractCreate {
  contract_name?: string;
  package_name: string;
  package_id: string;
  customer_name: string;
  customer_id: string;
  purchasing_electricity_quantity: number;
  purchase_start_month: string;
  purchase_end_month: string;
}

export interface ImportError {
  row: number;
  field: string;
  value: unknown;
  message: string;
  suggestion?: string;
}
export interface ImportResult {
  total: number;
  success: number;
  failed: number;
  errors: ImportError[];
}
export interface ExportParams {
  package_name?: string;
  customer_name?: string;
  status?: ContractStatus | 'all';
  start_month?: string;
  end_month?: string;
}

// ============ API 函数 ============
export async function fetchContracts(params: ContractListParams): Promise<ContractListResult> {
  const r = await apiClient.get('/api/v1/retail-contracts', { params });
  return r.data;
}

export async function getContract(id: string): Promise<Contract> {
  const r = await apiClient.get(`/api/v1/retail-contracts/${id}`);
  return r.data;
}

export async function createContract(data: ContractCreate): Promise<Contract> {
  const r = await apiClient.post('/api/v1/retail-contracts', data);
  return r.data;
}

export async function updateContract(id: string, data: Partial<ContractCreate>): Promise<Contract> {
  const r = await apiClient.put(`/api/v1/retail-contracts/${id}`, data);
  return r.data;
}

export async function deleteContract(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/retail-contracts/${id}`);
}

/** 导入 Excel（form-data） */
export async function importContracts(file: File): Promise<ImportResult> {
  const fd = new FormData();
  fd.append('file', file);
  const r = await apiClient.post('/api/v1/retail-contracts/import', fd, {
    headers: { 'Content-Type': 'multipart/form-data' },
  });
  return r.data;
}

/** 导出 Excel（返回 blob，由调用方下载） */
export async function exportContracts(params?: ExportParams): Promise<Blob> {
  const r = await apiClient.get('/api/v1/retail-contracts/export', {
    params,
    responseType: 'blob',
  });
  return r.data;
}
