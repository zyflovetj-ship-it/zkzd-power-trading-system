import apiClient from './client';

export interface BiddingComponents {
  load: number | null;
  pv: number | null;
  wind: number | null;
  tieline: number | null;
  storage: number | null;
  gas: number | null;
  coal: number | null;
}

export interface BiddingPoint {
  time_str: string;
  bidding_space_da: number | null;
  bidding_space_rt: number | null;
  deviation: number | null;
  components_da: BiddingComponents | null;
  components_rt: BiddingComponents | null;
}

export interface BiddingSpaceResult {
  date: string;
  count: number;
  points: BiddingPoint[];
}

export interface BiddingVerifySide {
  checked: number;
  mismatch: number;
  samples: Array<{ time_str: string; calc: number; pub: number }>;
}

export interface BiddingVerifyResult {
  date: string;
  day_ahead: BiddingVerifySide;
  real_time: BiddingVerifySide;
}

export interface BiddingDatesResult {
  dates: string[];
  dates_with_realtime: string[];
  total: number;
  total_with_realtime: number;
}

export async function fetchBiddingDates(limit = 120): Promise<BiddingDatesResult> {
  const r = await apiClient.get('/api/v1/market/bidding-space/dates', { params: { limit } });
  return r.data;
}

export async function fetchBiddingSpace(date: string): Promise<BiddingSpaceResult> {
  const r = await apiClient.get('/api/v1/market/bidding-space', { params: { date } });
  return r.data;
}

export async function verifyBiddingSpace(date: string): Promise<BiddingVerifyResult> {
  const r = await apiClient.get('/api/v1/market/bidding-space/verify', { params: { date } });
  return r.data;
}
