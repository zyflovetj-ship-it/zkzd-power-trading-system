import apiClient from './client';

// ============ 类型定义 ============
export type PackageType = 'time_based' | 'non_time_based';
export type PackageStatus = 'draft' | 'active' | 'archived';

export interface RetailPackageListItem {
  id: string;
  package_name: string;
  package_type: PackageType;
  model_code: string;
  is_green_power: boolean;
  status: PackageStatus;
  contract_count?: number;
  created_at: string;
  updated_at: string;
}

export interface RetailPackage extends RetailPackageListItem {
  package_description?: string;
  pricing_config?: Record<string, any>;
}

export interface PackageListResult {
  items: RetailPackageListItem[];
  total: number;
  page: number;
  page_size: number;
}

export interface PackageListParams {
  keyword?: string;
  package_type?: PackageType;
  is_green_power?: string;
  model_code?: string;
  status?: PackageStatus;
  page?: number;
  page_size?: number;
}

export interface PackageCreate {
  package_name: string;
  package_description?: string;
  package_type: PackageType;
  model_code: string;
  is_green_power: boolean;
  pricing_config?: Record<string, any>;
  save_as_draft?: boolean;
}

export const PACKAGE_TYPE_OPTIONS = [
  { label: '分时段', value: 'time_based' },
  { label: '不分时段', value: 'non_time_based' },
];
export const PACKAGE_STATUS_OPTIONS = [
  { label: '草稿', value: 'draft' },
  { label: '生效', value: 'active' },
  { label: '归档', value: 'archived' },
];
// 定价模型代码（与后端 pricing_model 对齐；展示名可按需扩展）
export const MODEL_CODE_OPTIONS = [
  { label: '固定联动-不分时', value: 'fixed_linked_fee_non_time' },
  { label: '固定联动-分时', value: 'fixed_linked_fee_time' },
  { label: '价差型-不分时', value: 'price_spread_non_time' },
  { label: '价差型-分时', value: 'price_spread_time' },
];

// ============ API 函数 ============
export async function fetchPackages(params: PackageListParams): Promise<PackageListResult> {
  const r = await apiClient.get('/api/v1/retail-packages', { params });
  return r.data;
}

export async function getPackage(id: string): Promise<RetailPackage> {
  const r = await apiClient.get(`/api/v1/retail-packages/${id}`);
  return r.data;
}

export async function createPackage(
  data: Omit<PackageCreate, 'save_as_draft'>,
  saveAsDraft = true,
): Promise<RetailPackage> {
  const r = await apiClient.post('/api/v1/retail-packages', data, {
    params: { save_as_draft: saveAsDraft },
  });
  return r.data;
}

export async function updatePackage(id: string, data: Partial<PackageCreate>): Promise<RetailPackage> {
  const r = await apiClient.put(`/api/v1/retail-packages/${id}`, data);
  return r.data;
}

export async function deletePackage(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/retail-packages/${id}`);
}

export async function copyPackage(id: string): Promise<RetailPackage> {
  const r = await apiClient.post(`/api/v1/retail-packages/${id}/copy`);
  return r.data;
}

export async function activatePackage(id: string): Promise<RetailPackage> {
  const r = await apiClient.post(`/api/v1/retail-packages/${id}/activate`);
  return r.data;
}

export async function archivePackage(id: string): Promise<RetailPackage> {
  const r = await apiClient.post(`/api/v1/retail-packages/${id}/archive`);
  return r.data;
}

/**
 * 价格试算（后端 /api/v1/retail-packages/calculate-price）。
 * 后端 PricingEngine 已实现（fixed_linked / price_spread 两种定价模式），
 * 可正常返回各时段价格与总费用，前端 PricePage 价格试算按钮已启用。
 */
export async function calculatePrice(payload: {
  package_id: string;
  date: string;
  time_period: string;
  volume_mwh: number;
}): Promise<unknown> {
  const r = await apiClient.post('/api/v1/retail-packages/calculate-price', payload);
  return r.data;
}
