import apiClient from './client';

// ============ 类型定义 ============
export type CustomerStatus = 'prospect' | 'pending' | 'active' | 'suspended' | 'terminated';

export interface Meter {
  meter_id: string;
  multiplier: number;
}

export interface MeteringPoint {
  metering_point_id: string;
  allocation_percentage: number;
  meter: Meter;
}

export interface UtilityAccount {
  account_id: string;
  metering_points: MeteringPoint[];
}

export interface CustomerListItem {
  id: string;
  user_name: string;
  short_name?: string;
  user_type?: string;
  industry?: string;
  region?: string;
  status: CustomerStatus;

  metering_point_count: number;
  contracted_capacity?: number | null;
  created_at: string;
  updated_at: string;
}

export interface CustomerDetail {
  id: string;
  user_name: string;
  short_name?: string;
  user_type?: string;
  industry?: string;
  voltage?: string;
  region?: string;
  district?: string;
  address?: string;
  contact_person?: string;
  contact_phone?: string;
  status: CustomerStatus;
  customer_code?: string;
  package_id?: string;
  utility_accounts?: UtilityAccount[];
  created_at: string;
  updated_at: string;
}

export interface CustomerCreate {
  user_name: string;
  short_name?: string;
  user_type?: string;
  industry?: string;
  voltage?: string;
  region?: string;
  district?: string;
  address?: string;
  contact_person?: string;
  contact_phone?: string;

  utility_accounts?: UtilityAccount[];
}

export interface CustomerListParams {
  keyword?: string;
  user_type?: string;
  industry?: string;
  region?: string;
  status?: CustomerStatus;
  page?: number;
  page_size?: number;
}

export interface CustomerListResult {
  items: CustomerListItem[];
  total: number;
  page: number;
  page_size: number;
}

// ============ 常量选项 ============
export const USER_TYPES = ['标准工商业', '大型工商业', '农业用户', '居民用户'];
export const INDUSTRIES = [
  '制造业', '建筑业', '批发和零售业', '交通运输业', '住宿和餐饮业', '信息传输业',
  '金融业', '房地产业', '租赁和商务服务业', '科学研究和技术服务业', '水利环境和公共设施管理业',
  '居民服务和其他服务业', '教育', '卫生和社会工作', '文化体育和娱乐业', '公共管理和社会组织', '国际组织',
];
export const VOLTAGE_LEVELS = ['220V', '380V', '10kV', '35kV', '110kV', '220kV', '500kV'];
export const REGIONS = [
  '南京市', '无锡市', '徐州市', '常州市', '苏州市', '南通市', '连云港市', '淮安市', '盐城市', '扬州市', '镇江市', '泰州市', '宿迁市',
];
export const CUSTOMER_STATUS_OPTIONS = [
  { label: '意向', value: 'prospect' },
  { label: '待生效', value: 'pending' },
  { label: '执行中', value: 'active' },
  { label: '已暂停', value: 'suspended' },
  { label: '已终止', value: 'terminated' },
];

// ============ API 函数 ============
export async function fetchCustomers(params: CustomerListParams): Promise<CustomerListResult> {
  const r = await apiClient.get('/api/v1/customers', { params });
  return r.data;
}

export async function getCustomer(id: string): Promise<CustomerDetail> {
  const r = await apiClient.get(`/api/v1/customers/${id}`);
  return r.data;
}

export async function createCustomer(data: CustomerCreate): Promise<CustomerDetail> {
  const r = await apiClient.post('/api/v1/customers', data);
  return r.data;
}

export async function updateCustomer(id: string, data: Partial<CustomerCreate>): Promise<CustomerDetail> {
  const r = await apiClient.put(`/api/v1/customers/${id}`, data);
  return r.data;
}

export async function deleteCustomer(id: string): Promise<void> {
  await apiClient.delete(`/api/v1/customers/${id}`);
}

// 状态流转
export async function signContract(id: string, contractId?: string): Promise<CustomerDetail> {
  const r = await apiClient.post(`/api/v1/customers/${id}/sign-contract`, { contract_id: contractId });
  return r.data;
}
export async function cancelContract(id: string, reason?: string): Promise<CustomerDetail> {
  const r = await apiClient.post(`/api/v1/customers/${id}/cancel-contract`, { reason });
  return r.data;
}
export async function activateCustomer(id: string): Promise<CustomerDetail> {
  const r = await apiClient.post(`/api/v1/customers/${id}/activate`, {});
  return r.data;
}
export async function suspendCustomer(id: string, reason?: string): Promise<CustomerDetail> {
  const r = await apiClient.post(`/api/v1/customers/${id}/suspend`, { reason });
  return r.data;
}
export async function resumeCustomer(id: string): Promise<CustomerDetail> {
  const r = await apiClient.post(`/api/v1/customers/${id}/resume`, {});
  return r.data;
}
export async function terminateCustomer(id: string, reason?: string): Promise<CustomerDetail> {
  const r = await apiClient.post(`/api/v1/customers/${id}/terminate`, { reason });
  return r.data;
}
