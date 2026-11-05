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
// 2026 新规：非分时支持「价格浮动 + 比例分成」；分时仅支持「价格浮动」，禁止比例分成。
export const MODEL_CODE_OPTIONS = [
  { label: '固定联动-不分时', value: 'fixed_linked_fee_non_time' },
  { label: '固定联动-分时', value: 'fixed_linked_fee_time' },
  { label: '价差型-不分时', value: 'price_spread_non_time' },
];

// 分时套餐仅可选「价格浮动」类模型（新规禁止分时比例分成）
export const TIME_MODEL_OPTIONS = [
  { label: '固定联动-分时', value: 'fixed_linked_fee_time' },
];

// 不分时套餐可选「价格浮动 + 比例分成」
export const NON_TIME_MODEL_OPTIONS = [
  { label: '固定联动-不分时', value: 'fixed_linked_fee_non_time' },
  { label: '价差型-不分时', value: 'price_spread_non_time' },
];

// 依据套餐类型返回可选定价模型（供 CrudPage 级联下拉）
export function fetchModelOptions(type?: string): Promise<{ label: string; value: string }[]> {
  const list = type === 'time_based' ? TIME_MODEL_OPTIONS : NON_TIME_MODEL_OPTIONS;
  return Promise.resolve(list as { label: string; value: string }[]);
}

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


// ============ 套餐测算（江苏 2027 新规，对齐《套餐测算模板 新v2》） ============
export interface MarketContext {
  wholesale_price: number;
  flat_base_price?: number;
  reference_price?: number;
  share_cost_compensation?: number;
  share_imbalance?: number;
  share_market_adjust?: number;
  share_price?: number;
}

export interface CalcParams {
  peak_coef?: number;
  valley_coef?: number;
  service_fee?: number;
  f_ratio?: number;
  k1_share?: number;
  k2_share?: number;
  k3_share?: number;
  green_mode?: string;
  env_value?: number;
}

export interface CalcResult {
  pricing_mode: string;
  total_mwh: number;
  volumes: { peak_mwh: number; flat_mwh: number; valley_mwh: number };
  prices: {
    wholesale_price: number;
    flat_base_price: number;
    service_fee: number;
    reference_price: number;
    flat_price: number;
    peak_price: number;
    valley_price: number;
  };
  share: {
    cost_compensation: number;
    imbalance: number;
    market_adjust: number;
    total: number;
    retail: number;
    k1: number;
    k2: number;
    k3: number;
  };
  energy_fee: number;
  energy_avg_price: number;
  cap_price: number;
  capped: boolean;
  settle_price: number;
  green_mode: string;
  green_add: number;
  sell_price: number;
  total_cost: number;
  sgcc?: { purchase_price: number; avg_on_grid_price: number; source?: string } | null;
  vs_sgcc?: {
    sgcc_price: number;
    package_price: number;
    diff: number;
    saving_rate: number;
    verdict: string;
  };
  wholesale_auto?: {
    method: string;
    holding_ratio: number;
    k2_ratio: number;
    mid_long_price: number;
    day_ahead_avg: number;
    real_time_avg: number;
    matched_points: number;
    unmatched_points: number;
  };
  warning?: string;
  sgcc_warning?: string;
  [key: string]: any;
}

/** 路径A：按历史负荷曲线测算（后端 /retail-packages/{id}/calc-from-load） */
export async function calcFromLoad(
  packageId: string,
  payload: {
    customer_id: string;
    period: string;
    market: MarketContext;
    params?: CalcParams;
    auto_market?: boolean;
    holding_ratio?: number;
    k2_ratio?: number;
    mid_long_price?: number;
  },
): Promise<CalcResult> {
  const r = await apiClient.post(`/api/v1/retail-packages/${packageId}/calc-from-load`, payload);
  return r.data;
}

/** 路径B：按核查联测算（后端 /retail-packages/{id}/calc-from-bill） */
export async function calcFromBill(
  packageId: string,
  payload: {
    bill: {
      period: string;
      total_mwh: number;
      peak_mwh?: number;
      flat_mwh?: number;
      valley_mwh?: number;
      current_amount?: number;
      customer_name?: string;
    };
    market: MarketContext;
    params?: CalcParams;
  },
): Promise<CalcResult> {
  const r = await apiClient.post(`/api/v1/retail-packages/${packageId}/calc-from-bill`, payload);
  return r.data;
}

// ============ 年度批量测算（用户 × 12 月） ============
export interface AnnualDetailRow {
  user: string;
  ktype: string;
  customer_id: string;
  month: number;
  data_source?: string;
  volume_mwh: number;
  p_wholesale: number;
  p_share: number;
  p_reference: number;
  p_cap: number;
  peak_price: number;
  flat_price: number;
  valley_price: number;
  retail_avg: number;
  capped: boolean;
  settle_price: number;
  green_add: number;
  sell_price: number;
  cost: number;
  sgcc_price: number;
  sgcc_peak_price?: number;
  sgcc_flat_price?: number;
  sgcc_valley_price?: number;
  sgcc_weighted?: number;
  profit_per_mwh: number;
  profit_wan: number;
}

export interface AnnualMonthlyRow {
  month: number;
  volume_mwh: number;
  sell_price: number | null;
  profit_wan: number;
  peak_mwh: number;
  flat_mwh: number;
  valley_mwh: number;
}

export interface ComplianceItem {
  key: string;
  name: string;
  value: number | null;
  min: number | null;
  max: number | null;
  unit: string;
  rule: string;
  ref: string;
  pass: boolean;
  message: string;
}

export interface ComplianceResult {
  valid: boolean;
  items: ComplianceItem[];
  errors: string[];
  warnings: string[];
  notice?: string;
}

export interface AnnualCalcResult {
  year: number;
  package_id: string;
  package_name?: string;
  kpi: {
    total_volume_mwh: number;
    avg_profit_per_mwh: number | null;
    total_profit_wan: number;
    capped_count: number;
    user_month_count: number;
    f_ratio: number;
    kp: number;
    peak_coef: number;
    valley_coef: number;
  };
  monthly: AnnualMonthlyRow[];
  details: AnnualDetailRow[];
  compliance: ComplianceResult;
  warnings: string[];
}

export async function calcAnnual(
  packageId: string,
  payload: {
    year: number;
    customer_ids?: string[];
    auto_market?: boolean;
    holding_ratio?: number;
    k2_ratio?: number;
    ktype?: string;
    market_source?: 'manual' | 'system';
    market?: MarketContext;
    params?: CalcParams;
  },
): Promise<AnnualCalcResult> {
  const r = await apiClient.post(`/api/v1/retail-packages/${packageId}/calc-annual`, payload);
  return r.data;
}

export async function validateCompliance(config: Record<string, unknown>): Promise<ComplianceResult> {
  const r = await apiClient.post('/api/v1/retail-packages/compliance/validate', config);
  return r.data;
}

// ============ 风险预警 & 法定代表人确认 ============
export interface RiskWarningItem {
  key: string;
  name: string;
  value: number | null;
  rule: string;
  unit: string;
  pass: boolean;
  message?: string;
}

export interface RiskWarningResult {
  package_id: string;
  package_name?: string;
  triggered: boolean;
  items: RiskWarningItem[];
  errors: string[];
  confirmed: boolean;
  confirmed_by?: string;
  confirmed_at?: string;
  note?: string;
  requires_legal_confirm: boolean;
  notice: string;
}

export async function getRiskWarning(packageId: string): Promise<RiskWarningResult> {
  const r = await apiClient.get(`/api/v1/retail-packages/${packageId}/risk-warning`);
  return r.data;
}

export async function legalConfirm(
  packageId: string,
  payload: { confirmed_by: string; note?: string; attachment_name?: string },
): Promise<unknown> {
  const r = await apiClient.post(`/api/v1/retail-packages/${packageId}/legal-confirm`, payload);
  return r.data;
}

export async function getConfirmLogs(packageId: string): Promise<{ items: Record<string, unknown>[] }> {
  const r = await apiClient.get(`/api/v1/retail-packages/${packageId}/confirm-logs`);
  return r.data;
}
