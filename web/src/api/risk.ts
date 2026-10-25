import apiClient from './client';

// 风险管理模块（持仓合约管理 / 风险敞口分析）

export interface PositionContract {
  customer: string;
  contractNo: string;
  volume: number;
  avgPrice: number;
  startDate: string;
  endDate: string;
  coverage: number;
}

export interface RiskPositionResp {
  contracts: PositionContract[];
}

export interface MonthlyExposure {
  month: string;
  contract: number;
  spot: number;
}

export interface RiskExposureResp {
  totalExposure: number;
  priceExposure: number;
  volumeExposure: number;
  var95: number;
  monthly: MonthlyExposure[];
  priceExposureHourly: number[];
  volumeExposureHourly: number[];
  hours: string[];
}

export const getRiskPositionContracts = () =>
  apiClient.get<RiskPositionResp>('/api/v1/risk/position-contracts/').then((r) => r.data);

export const getRiskExposure = () =>
  apiClient.get<RiskExposureResp>('/api/v1/risk/exposure/').then((r) => r.data);
