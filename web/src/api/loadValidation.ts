import apiClient from './client';

// 负荷数据校验模块

export type CheckStatus = 'pass' | 'error' | 'missing';

export interface ValidationRecord {
  date: string;
  customer: string;
  metric: string;
  status: CheckStatus;
  problem: string;
  detectValue: string;
}

export interface LoadValidationResp {
  records: ValidationRecord[];
}

export const getLoadValidation = () =>
  apiClient.get<LoadValidationResp>('/api/v1/basic-data/load-validation/').then((r) => r.data);
