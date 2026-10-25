import apiClient from '@/api/client';

// ============================================================================
// 价格预测域 API（D-2 价格预测、日前价格预测）
// 月度价格预测见 market.ts（与中长期价格分析共用 /api/v1/monthly-forecast）。
// ============================================================================

// ---------- D-2 价格预测 ----------

export interface D2Point {
  datetime: string;
  target_date: string;
  predicted_price: number;
  confidence_80_lower: number;
  confidence_80_upper: number;
  confidence_90_lower: number;
  confidence_90_upper: number;
}
export interface D2ByDateResp {
  forecast_id: string;
  forecast_date: string;
  forecast_type: string;
  target_dates: string[];
  data: D2Point[];
}
export interface D2CompPoint {
  time: string;
  predicted: number;
  actual: number;
  difference: number;
}
export interface D2ComparisonResp {
  target_date: string;
  data: D2CompPoint[];
  metrics: { mae: number; rmse: number; mape: number; accuracy: number };
}
export interface D2AccRecord {
  target_date: string;
  wmape_accuracy: number;
  mae: number;
  rmse: number;
  mape: number;
  direction_accuracy: number;
}
export interface D2AccuracyStatsResp {
  start_date: string;
  end_date: string;
  monthly_avg: number;
  best_day: { date: string; accuracy: number };
  worst_day: { date: string; accuracy: number };
  pass_90_count: number;
  total_days: number;
  records: D2AccRecord[];
}

export async function getD2ByDate(forecastDate: string): Promise<D2ByDateResp> {
  const r = await apiClient.get('/api/v1/price-forecast/d2/by-date', { params: { forecast_date: forecastDate } });
  return r.data;
}
export async function getD2Comparison(targetDate: string): Promise<D2ComparisonResp> {
  const r = await apiClient.get('/api/v1/price-forecast/d2/comparison', { params: { target_date: targetDate } });
  return r.data;
}
export async function getD2AccuracyStats(startDate: string, endDate: string): Promise<D2AccuracyStatsResp> {
  const r = await apiClient.get('/api/v1/price-forecast/d2/accuracy-stats', {
    params: { start_date: startDate, end_date: endDate },
  });
  return r.data;
}

// ---------- 日前价格预测 ----------

export interface DayAheadVersion {
  forecast_id: string;
  forecast_type: string;
  model_type: string;
  model_version: string;
  created_at: string;
  target_date: string;
}
export interface DayAheadPoint {
  datetime: string;
  time: string;
  predicted: number;
  actual: number | null;
  confidence_80_lower: number;
  confidence_80_upper: number;
  confidence_90_lower: number;
  confidence_90_upper: number;
  error?: number;
}
export interface DayAheadDataResp {
  forecast_id: string;
  target_date: string;
  data: DayAheadPoint[];
  has_actual: boolean;
}
export interface DayAheadAccuracyResp {
  forecast_id: string;
  target_date: string;
  forecast_type: string;
  customer_id: string | null;
  forecast_date: string | null;
  model_type: string;
  model_version: string;
  wmape_accuracy: number;
  mae: number;
  rmse: number;
  mape: number;
  direction_accuracy: number;
  period_accuracy: Record<string, unknown>;
  stats: Record<string, unknown>;
  rate_90_pass: number;
  rate_85_pass: number;
  r2_score: number;
  calculated_at: string;
}

export async function getDayAheadVersions(targetDate: string, forecastType = 'd1_price'): Promise<DayAheadVersion[]> {
  const r = await apiClient.get('/api/v1/day-ahead-forecast/versions', {
    params: { target_date: targetDate, forecast_type: forecastType },
  });
  return r.data;
}
export async function getDayAheadData(forecastId: string, targetDate: string): Promise<DayAheadDataResp> {
  const r = await apiClient.get('/api/v1/day-ahead-forecast/data', {
    params: { forecast_id: forecastId, target_date: targetDate },
  });
  return r.data;
}
export async function getDayAheadAccuracy(forecastId: string): Promise<DayAheadAccuracyResp> {
  const r = await apiClient.get('/api/v1/day-ahead-forecast/accuracy', { params: { forecast_id: forecastId } });
  return r.data;
}
