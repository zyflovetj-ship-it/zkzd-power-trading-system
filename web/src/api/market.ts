import apiClient from '@/api/client';

// ============================================================================
// 市场/价格分析域 API（现货价格、现货趋势、中长期价格、合同价格）
// 所有接口均为 GET + query 参数（日期/日期范围），响应形态不统一，按接口分别适配。
// ============================================================================

// ---------- 现货价格分析 ----------

export interface SpotTimePoint {
  period: number;
  time: string;
  time_str: string;
  price_rt: number | null;
  price_da: number | null;
  volume_rt: number | null;
  volume_da: number | null;
  spread: number | null;
  period_type: string;
}

export interface SpotDashboard {
  date: string;
  financial_kpis: {
    vwap_rt: number;
    vwap_da: number;
    vwap_spread: number;
    twap_rt: number;
    twap_da: number;
  };
  risk_kpis: {
    max_positive_spread: { value: number; time_str: string; period: number };
    max_negative_spread: { value: number; time_str: string; period: number };
    max_rt_price: { value: number; time_str: string; period: number };
    min_rt_price: { value: number; time_str: string; period: number };
  };
  time_series: SpotTimePoint[];
  period_summary: Array<{
    period_name: string;
    vwap_da: number;
    vwap_rt: number;
    vwap_spread: number;
    avg_volume_rt: number;
    renewable_ratio: number;
  }>;
}

export interface SpotDayAheadPoint {
  time_str: string;
  datetime: string;
  date_str: string;
  avg_clearing_price: number;
  total_clearing_power: number;
  thermal_clearing_power?: number;
  hydro_clearing_power?: number;
  wind_clearing_power?: number;
  solar_clearing_power?: number;
  pumped_storage_clearing_power?: number;
  battery_storage_generation?: number;
  market_bidding_space?: number;
}

export interface SpotDayAheadResp {
  data: SpotDayAheadPoint[];
  metadata: { correlation: number | null };
}

export interface SpreadTimePoint {
  time_str: string;
  price_spread: number;
  total_volume_deviation: number;
  system_load_deviation: number;
  renewable_deviation: number;
  nonmarket_unit_deviation: number;
  tieline_deviation: number;
  system_load_da: number;
  system_load_rt: number;
  renewable_da: number;
  renewable_rt: number;
  nonmarket_unit_da: number;
  nonmarket_unit_rt: number;
  tieline_da: number;
  tieline_rt: number;
}

export interface SpreadAttributionResp {
  time_series: SpreadTimePoint[];
  systematic_bias: Array<Record<string, unknown> & { period_name: string }>;
  price_distribution: Array<{
    range_min: number;
    range_max: number;
    range_label: string;
    count: number;
  }>;
}

/** 现货总览（KPI + 96 点时序） */
export async function getSpotDashboard(date: string): Promise<SpotDashboard> {
  const r = await apiClient.get('/api/v1/market-analysis/dashboard', { params: { date_str: date } });
  return r.data;
}

/** 日前现货价格 */
export async function getDayAhead(date: string): Promise<SpotDayAheadResp> {
  const r = await apiClient.get('/api/v1/market-analysis/day-ahead', { params: { date } });
  return r.data;
}

/** 实时现货价格 */
export async function getRealTime(date: string): Promise<SpotDayAheadResp> {
  const r = await apiClient.get('/api/v1/market-analysis/real-time', { params: { date } });
  return r.data;
}

/** 价差归因 */
export async function getSpreadAttribution(date: string): Promise<SpreadAttributionResp> {
  const r = await apiClient.get('/api/v1/market-analysis/spread-attribution', { params: { date } });
  return r.data;
}

// ---------- 现货趋势分析 （trend-analysis）----------

export interface PriceTrendResp {
  daily_trends: Array<{
    date: string;
    vwap_da: number;
    vwap_rt: number;
    vwap_spread: number;
    twap_da: number;
    twap_rt: number;
    twap_spread: number;
    positive_spread_count: number;
    negative_spread_count: number;
  }>;
  period_trends: Record<string, Array<{ date: string; period_type: string; vwap: number }>>;
  spread_stats: {
    avgSpread: number;
    positiveSpreadRatio: number;
    negativeSpreadRatio: number;
    maxSpread: number;
    minSpread: number;
  };
  spread_distribution: Array<{ range: string; count: number }>;
}

export interface WeekdayPatternResp {
  distribution: Array<{
    weekday: number;
    weekday_name: string;
    stats: { min: number; q1: number; median: number; q3: number; max: number };
    outliers: number[];
  }>;
  heatmap_data: unknown[];
}

export interface VolatilityResp {
  daily_volatility: Array<{ date: string; cv_rt: number; max_ramp: number; spread_std: number }>;
}

export interface ArbitrageResp {
  daily_arbitrage: Array<{
    date: string;
    max_spread: number;
    best_strategy: string;
    buy_price: number;
    buy_time: string;
    sell_price: number;
    sell_time: string;
    period_type: string;
  }>;
  summary: { avg_max_spread: number; days_count: number };
}

export interface AnomalyResp {
  events: {
    negative_price: { event_type: string; count: number; days: number };
    zero_price: { event_type: string; count: number; days: number };
    high_price: { event_type: string; count: number; days: number };
  };
  daily_extremums: Array<{
    date: string;
    max_price: number;
    max_time: string;
    min_price: number;
    min_time: string;
    range_value: number;
  }>;
  risk_timeslots: unknown[];
}

export interface TimeslotStatsResp {
  kpis: Record<string, unknown>;
  timeslot_stats: Array<Record<string, unknown> & { timeslot: string; time_label: string }>;
  box_plot_data: Array<{ timeslot: string; time_label: string; min: number; q1: number; median: number; q3: number; max: number; outliers: number[] }>;
}

const trendParams = (start: string, end: string) => ({ params: { start_date: start, end_date: end } });

export async function getPriceTrend(start: string, end: string): Promise<PriceTrendResp> {
  const r = await apiClient.get('/api/v1/trend-analysis/price-trend', trendParams(start, end));
  return r.data;
}
export async function getWeekdayPattern(start: string, end: string): Promise<WeekdayPatternResp> {
  const r = await apiClient.get('/api/v1/trend-analysis/weekday-pattern', trendParams(start, end));
  return r.data;
}
export async function getVolatility(start: string, end: string): Promise<VolatilityResp> {
  const r = await apiClient.get('/api/v1/trend-analysis/volatility', trendParams(start, end));
  return r.data;
}
export async function getArbitrage(start: string, end: string): Promise<ArbitrageResp> {
  const r = await apiClient.get('/api/v1/trend-analysis/arbitrage', trendParams(start, end));
  return r.data;
}
export async function getAnomaly(start: string, end: string): Promise<AnomalyResp> {
  const r = await apiClient.get('/api/v1/trend-analysis/anomaly', trendParams(start, end));
  return r.data;
}
export async function getTimeslotStats(start: string, end: string): Promise<TimeslotStatsResp> {
  const r = await apiClient.get('/api/v1/trend-analysis/timeslot-stats', trendParams(start, end));
  return r.data;
}

// ---------- 中长期价格 / 合同价格 ----------

export interface MonthlyForecastVersion {
  forecast_id: string;
  forecast_type: string;
  model_type: string;
  model_version: string;
  created_at: string;
  status: string;
}
export interface MonthlyForecastDataPoint {
  date: string;
  day: number;
  price_max: number;
  price_min: number;
  price_mean: number;
  price_peak: number;
  price_valley: number;
  confidence_80_lower: number;
  confidence_80_upper: number;
  confidence_90_lower: number;
  confidence_90_upper: number;
  actual_mean?: number;
  actual_max?: number;
  actual_min?: number;
  price_spread?: number;
  actual_spread?: number;
}
export interface MonthlyForecastResp {
  forecast_id: string;
  target_month: { year: number; month: number };
  chart_type: string;
  data: MonthlyForecastDataPoint[];
  has_actual: boolean;
  last_month_avg: number | null;
}
export interface ForecastAccuracyResp {
  forecast_id: string;
  target_month: { year: number; month: number };
  forecast_type: string;
  customer_id: string | null;
  mape: number;
  wmape_accuracy: number;
  mae: number;
  rmse: number;
  direction_accuracy: number;
  period_accuracy: Record<string, unknown>;
  stats: Record<string, unknown>;
  rate_90_pass: number;
  rate_85_pass: number;
  r2_score: number;
  daily_errors: unknown[];
  calculated_at: string;
}

export async function getMonthlyForecastVersions(
  targetYear: number,
  targetMonth: number,
  forecastType = 'monthly_price',
): Promise<MonthlyForecastVersion[]> {
  const r = await apiClient.get('/api/v1/monthly-forecast/versions', {
    params: { target_year: targetYear, target_month: targetMonth, forecast_type: forecastType },
  });
  return r.data;
}
export async function getMonthlyForecastData(
  forecastId: string,
  chartType = 'mean_trend',
): Promise<MonthlyForecastResp> {
  const r = await apiClient.get('/api/v1/monthly-forecast/data', {
    params: { forecast_id: forecastId, chart_type: chartType },
  });
  return r.data;
}
export async function getMonthlyForecastAccuracy(forecastId: string): Promise<ForecastAccuracyResp> {
  const r = await apiClient.get('/api/v1/monthly-forecast/accuracy', { params: { forecast_id: forecastId } });
  return r.data;
}

export interface ContractPriceDailySummary {
  date: string;
  kpis: {
    total_quantity: number;
    overall_avg_price: number;
    price_range_min: number;
    price_range_max: number;
    yearly_ratio: number;
    monthly_ratio: number;
    within_month_ratio: number;
    yearly_avg_price: number;
    monthly_avg_price: number;
    within_month_avg_price: number;
  };
  contract_curves: Array<{ period: number; time_str: string; price: number; quantity: number }>;
  spot_curves: Array<{ period: number; time_str: string; price: number; quantity: number }>;
  type_summary: Array<{
    contract_type: string;
    contract_period: string;
    daily_total_quantity: number;
    daily_avg_price: number;
    max_price: number;
    min_price: number;
    peak_valley_spread: number;
  }>;
  curves_by_type: Record<string, Array<{ period: number; time_str: string; price: number; quantity: number }>>;
  curves_by_period: Record<string, Array<{ period: number; time_str: string; price: number; quantity: number }>>;
}
export interface ContractPriceTrendResp {
  daily_trends: Array<{
    date: string;
    contract_vwap: number;
    spot_vwap: number;
    vwap_spread: number;
    positive_spread_count: number;
    negative_spread_count: number;
  }>;
  spread_stats: {
    avgSpread: number;
    positiveSpreadRatio: number;
    negativeSpreadRatio: number;
    maxSpread: number;
    minSpread: number;
  };
  spread_distribution: Array<{ range: string; count: number }>;
}
export interface ContractCurveAnalysisResp {
  curves: Array<{ key: string; contract_type: string; contract_period: string; label: string; color: string; points: Array<{ date: string; vwap: number }> }>;
  spot_curve: { key: string; contract_type: string; contract_period: string; label: string; color: string; points: Array<{ date: string; vwap: number }> };
  date_range: string[];
}
export interface ContractQuantityResp {
  daily_quantities: Array<{
    date: string;
    yearly_qty: number;
    monthly_qty: number;
    within_month_qty: number;
    market_qty: number;
    green_qty: number;
    agency_qty: number;
    total_qty: number;
  }>;
  total_quantity: number;
  period_totals: Record<string, unknown>;
  type_totals: Record<string, unknown>;
  date_range: string[];
}

export async function getContractPriceDailySummary(
  date: string,
  entity = '全市场',
  spotType: 'day_ahead' | 'real_time' = 'day_ahead',
): Promise<ContractPriceDailySummary> {
  const r = await apiClient.get('/api/v1/contract-price/daily-summary', {
    params: { date, entity, spot_type: spotType },
  });
  return r.data;
}
export async function getContractPriceTrend(
  start: string,
  end: string,
  spotType: 'day_ahead' | 'real_time' = 'day_ahead',
): Promise<ContractPriceTrendResp> {
  const r = await apiClient.get('/api/v1/contract-price-trend/price-trend', {
    params: { start_date: start, end_date: end, spot_type: spotType },
  });
  return r.data;
}
export async function getContractCurveAnalysis(
  start: string,
  end: string,
  spotType = '',
): Promise<ContractCurveAnalysisResp> {
  const r = await apiClient.get('/api/v1/contract-price-trend/curve-analysis', {
    params: { start_date: start, end_date: end, spot_type: spotType },
  });
  return r.data;
}
export async function getContractQuantityStructure(start: string, end: string): Promise<ContractQuantityResp> {
  const r = await apiClient.get('/api/v1/contract-price-trend/quantity-structure', {
    params: { start_date: start, end_date: end },
  });
  return r.data;
}
