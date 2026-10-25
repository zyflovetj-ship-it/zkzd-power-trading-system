import apiClient from './client';

// 结算管理模块（批发预结算 / 平台账单复核 / 零售用户结算 / 经营利润分析）

export interface WholesaleRow {
  unit: string;
  period: string;
  volume: number;
  price: number;
  amount: number;
  devVolume: number;
  devFee: number;
}

export interface SettlementWholesaleResp {
  rows: WholesaleRow[];
}

export type BillStatus = 'PENDING' | 'REVIEWED' | 'DIFFERENCE';

export interface BillRow {
  billNo: string;
  customer: string;
  period: string;
  platformAmount: number;
  systemAmount: number;
  diff: number;
  status: BillStatus;
}

export interface SettlementBillResp {
  bills: BillRow[];
}

export type PayStatus = 'PAID' | 'UNPAID' | 'PARTIAL';

export interface RetailRow {
  customer: string;
  contract: string;
  usage: number;
  price: number;
  amount: number;
  payStatus: PayStatus;
}

export interface SettlementRetailResp {
  rows: RetailRow[];
}

export interface ProfitRow {
  month: string;
  revenue: number;
  cost: number;
  gross: number;
  margin: number;
}

export interface SettlementProfitResp {
  rows: ProfitRow[];
  revenueComposition: { name: string; value: number }[];
}

export const getSettlementWholesale = () =>
  apiClient.get<SettlementWholesaleResp>('/api/v1/settlement/wholesale/').then((r) => r.data);

export const getSettlementBillReview = (status: 'ALL' | BillStatus = 'ALL') =>
  apiClient
    .get<SettlementBillResp>('/api/v1/settlement/bill-review/', { params: { status } })
    .then((r) => r.data);

export const getSettlementRetail = () =>
  apiClient.get<SettlementRetailResp>('/api/v1/settlement/retail/').then((r) => r.data);

export const getSettlementProfit = () =>
  apiClient.get<SettlementProfitResp>('/api/v1/settlement/profit/').then((r) => r.data);
