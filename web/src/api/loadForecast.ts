import apiClient from '@/api/client';

// ============================================================================
// 负荷预测域 + 客户负荷分析 API
// 短/中长期负荷预测、预测基础数据、客户负荷曲线/电量。
// ============================================================================

// ---------- 短期负荷预测 ----------

export interface ShortTermPoint {
  time: string; // HH:MM 或 24:00
  forecast_value: number;
  actual_value?: number;
  timestamp?: string;
}
export interface ShortTermCurveResp {
  forecast_date: string;
  forecast_target_date: string;
  forecast_type: string;
  data: ShortTermPoint[];
  total_points: number;
  completeness: number;
  has_actual: boolean;
}
export interface ShortTermMultipleResp {
  forecast_date: string;
  curves: ShortTermCurveResp[];
}
export interface ShortTermAccuracyResp {
  forecast_date: string;
  forecast_target_date: string;
  forecast_type: string;
  mae: number;
  mape: number;
  rmse: number;
  max_error: number;
  max_error_time: string;
}
export interface ShortTermListRow {
  forecast_date: string;
  forecast_target_date: string;
  forecast_types: string[];
  has_actual: boolean;
  created_at: string;
}

export async function getShortTermCurve(forecastDate: string, forecastType = 'd+1'): Promise<ShortTermCurveResp> {
  const r = await apiClient.get('/api/v1/short-term-load-forecast/curve', {
    params: { forecast_date: forecastDate, forecast_type: forecastType },
  });
  return r.data;
}
export async function getShortTermMultiple(forecastDate: string, forecastTypes?: string[]): Promise<ShortTermMultipleResp> {
  const r = await apiClient.get('/api/v1/short-term-load-forecast/multiple-curves', {
    params: {
      forecast_date: forecastDate,
      forecast_types: forecastTypes ? forecastTypes.join(',') : undefined,
    },
  });
  return r.data;
}
export async function getShortTermAccuracy(forecastDate: string, forecastType = 'd+1'): Promise<ShortTermAccuracyResp> {
  const r = await apiClient.get('/api/v1/short-term-load-forecast/accuracy', {
    params: { forecast_date: forecastDate, forecast_type: forecastType },
  });
  return r.data;
}
export async function getShortTermList(startDate: string, endDate: string): Promise<ShortTermListRow[]> {
  const r = await apiClient.get('/api/v1/short-term-load-forecast/list', {
    params: { start_date: startDate, end_date: endDate },
  });
  return r.data;
}

// ---------- 中长期负荷预测 ----------

export interface MediumLongPoint {
  month: string; // YYYY-MM
  forecast_value: number;
  upper_bound: number;
  lower_bound: number;
  timestamp?: string;
}
export interface MediumLongResp {
  forecast_date: string;
  forecast_horizon_months: number;
  data: MediumLongPoint[];
  total_months: number;
}
export interface MediumLongListRow {
  forecast_date: string;
  forecast_horizon_months: number;
  created_at: string;
}

export async function getMediumLongLatest(): Promise<MediumLongResp> {
  const r = await apiClient.get('/api/v1/medium-long-term-load-forecast/latest');
  return r.data;
}
export async function getMediumLongByDate(forecastDate: string): Promise<MediumLongResp> {
  const r = await apiClient.get(`/api/v1/medium-long-term-load-forecast/${forecastDate}`);
  return r.data;
}
export async function getMediumLongList(): Promise<MediumLongListRow[]> {
  const r = await apiClient.get('/api/v1/medium-long-term-load-forecast');
  return r.data;
}

// ---------- 预测基础数据 ----------

export interface BaseAvailabilityMatrixCell {
  data_item_id: number;
  data_item_name?: string;
  date: string;
  is_available: boolean;
  sample_timestamp: string | null;
}
export interface ForecastBaseAvailabilityResp {
  base_date: string;
  date_range: string[];
  availability_matrix: BaseAvailabilityMatrixCell[][];
}
export interface BaseCurvePoint {
  time: string;
  value: number;
  timestamp?: string;
}
export interface BaseCurve {
  data_item_id: number;
  data_item_name: string;
  date: string;
  data: BaseCurvePoint[];
  total_points: number;
  completeness: number;
}
export interface ForecastBaseCurvesResp {
  curves: BaseCurve[];
}
export interface BaseCurveRequestItem {
  data_item_id: number;
  date: string;
}

export async function getForecastBaseAvailability(
  baseDate: string,
  dateRange: 'recent_3' | 'recent_7' | 'historical_10' | 'desktop_full_range' = 'recent_7',
): Promise<ForecastBaseAvailabilityResp> {
  const r = await apiClient.get('/api/v1/forecast-base-data/availability', {
    params: { base_date: baseDate, date_range: dateRange },
  });
  return r.data;
}
export async function getForecastBaseCurves(items: BaseCurveRequestItem[]): Promise<ForecastBaseCurvesResp> {
  const r = await apiClient.post('/api/v1/forecast-base-data/curves', items);
  return r.data;
}

export interface MonthlyCurvePoint {
  time_index: number;
  monthly_avg: number | null;
  workday_avg: number | null;
  weekend_avg: number | null;
  holiday_avg: number | null;
  count: number;
}
export interface MonthlyCurveResp {
  month: string;
  data: MonthlyCurvePoint[];
}

export async function getMonthlyLoadCurve(month: string): Promise<MonthlyCurveResp> {
  const r = await apiClient.get('/api/v1/load_analysis/monthly_curve', { params: { month } });
  return r.data;
}

// ---------- 客户负荷分析 ----------

export interface LoadCurveResp {
  [date: string]: Array<{ time: string; value: number }>;
}
export interface DailyEnergyResp {
  [month: string]: Array<{ day: number; energy: number }>;
}
export type AvailableDatesResp = string[];
export type AvailableMonthsResp = string[];
export type UsersResp = Array<{ user_name: string }>;
export type MetersResp = Array<{ meter_id: string; account_id: string }>;

export async function getLoadCurve(meterId: string, dates: string[]): Promise<LoadCurveResp> {
  const r = await apiClient.get('/api/v1/load_curve', { params: { meter_id: meterId, date: dates }, paramsSerializer: { indexes: null } });
  return r.data;
}
export async function getDailyEnergy(meterId: string, months: string[]): Promise<DailyEnergyResp> {
  const r = await apiClient.get('/api/v1/daily_energy', { params: { meter_id: meterId, month: months }, paramsSerializer: { indexes: null } });
  return r.data;
}
export async function getTotalDailyEnergy(months: string[]): Promise<DailyEnergyResp> {
  const r = await apiClient.get('/api/v1/total_daily_energy', { params: { month: months }, paramsSerializer: { indexes: null } });
  return r.data;
}
export async function getAvailableDates(meterId: string): Promise<AvailableDatesResp> {
  const r = await apiClient.get('/api/v1/available-dates', { params: { meter_id: meterId } });
  return r.data;
}
export async function getAvailableMonths(): Promise<AvailableMonthsResp> {
  const r = await apiClient.get('/api/v1/available_months');
  return r.data;
}
export async function getUsers(): Promise<UsersResp> {
  const r = await apiClient.get('/api/v1/users');
  return r.data;
}
export async function getMeters(userName: string): Promise<MetersResp> {
  const r = await apiClient.get('/api/v1/meters', { params: { user_name: userName } });
  return r.data;
}
