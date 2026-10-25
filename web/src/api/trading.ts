import apiClient from '@/api/client';

// ============================================================================
// 交易决策域 + 复盘 + 定价模型 API
// 注意：三个 trading 域的 POST /generate 把参数当作 query string（非 JSON body）；
//       复盘域 POST 才是 JSON body；定价模型 /validate 是 JSON body。
// ============================================================================

// ---------- 合同曲线 ----------

export interface ContractCurveDaily {
  date: string;
  predicted_load: number;
  contract_amount: number;
  spot_amount: number;
  contract_price: number;
  predicted_spot_price: number;
  contract_cost: number;
  predicted_spot_cost: number;
  total_cost: number;
}
export interface ContractCurveResp {
  curve_id: string;
  customer_id: string;
  customer_name: string;
  contract_month: { year: number; month: number };
  optimization_params: { objective: string; contract_coverage: number; risk_aversion: number };
  daily_contracts: ContractCurveDaily[];
  summary: {
    total_contract_amount: number;
    total_spot_amount: number;
    total_demand: number;
    contract_coverage: number;
    avg_contract_price: number;
    total_cost: number;
    contract_cost: number;
    spot_cost: number;
    blended_cost: number;
    price_variance: number;
    value_at_risk_95: number;
    sharpe_ratio: number;
    vs_pure_spot: { cost_difference: number; cost_percentage: number };
    vs_equal_contract: { cost_difference: number; cost_percentage: number };
  };
  created_at: string;
  status: string;
}
export interface ContractCurveListRow {
  curve_id: string;
  customer_id: string;
  customer_name: string;
  contract_month: { year: number; month: number };
  optimization_params: Record<string, unknown>;
  summary: Record<string, unknown>;
  created_at: string;
}
export interface ContractCurveScenarioResp {
  scenario_type: string;
  data: Array<Record<string, unknown>>;
}

export async function generateContractCurve(params: {
  customer_id: string;
  target_year: number;
  target_month: number;
  objective?: 'cost_min' | 'risk_min' | 'balanced';
  contract_coverage?: number;
}): Promise<ContractCurveResp> {
  const r = await apiClient.post('/api/v1/trading/contract-curve/generate', null, { params });
  return r.data;
}
export async function getContractCurve(curveId: string): Promise<ContractCurveResp> {
  const r = await apiClient.get('/api/v1/trading/contract-curve/get', { params: { curve_id: curveId } });
  return r.data;
}
export async function getContractCurveScenarios(
  curveId: string,
  scenarioType: 'price_sensitivity' | 'load_sensitivity',
): Promise<ContractCurveScenarioResp> {
  const r = await apiClient.get('/api/v1/trading/contract-curve/scenarios', {
    params: { curve_id: curveId, scenario_type: scenarioType },
  });
  return r.data;
}
export async function listContractCurves(
  customerId: string,
  targetYear: number,
  targetMonth: number,
): Promise<ContractCurveListRow[]> {
  const r = await apiClient.get('/api/v1/trading/contract-curve/list', {
    params: { customer_id: customerId, target_year: targetYear, target_month: targetMonth },
  });
  return r.data;
}

// ---------- 月度交易策略 ----------

export interface MonthlyStrategyResp {
  strategy_id: string;
  customer_id: string;
  customer_name: string;
  target_month: { year: number; month: number };
  strategy_config: {
    annual_contract_ratio: number;
    monthly_bid_ratio: number;
    spot_ratio: number;
    optimization_objective: string;
    risk_aversion: number;
  };
  optimization_results: {
    trading_mix: {
      annual_contract: { amount: number; ratio: number; avg_price: number; total_cost: number };
      monthly_bid: { amount: number; ratio: number; avg_price: number; total_cost: number };
      spot: { amount: number; ratio: number; avg_price: number; total_cost: number };
    };
    total_demand: number;
    blended_cost: number;
    total_cost: number;
    vs_pure_spot: { cost_savings: number; savings_percentage: number };
    vs_full_contract: { cost_increase: number; risk_reduction: number };
    risk_metrics: { cost_variance: number; value_at_risk_95: number; sharpe_ratio: number; flexibility_score: number };
  };
  timing_recommendations: Array<{
    date: string;
    type: string;
    recommended_amount: number;
    recommended_price_range: [number, number];
    reasoning: string;
  }>;
  scenario_analysis: Record<string, unknown>;
  created_at: string;
  status: string;
}
export interface MonthlyPriceTrendResp {
  target_month: { year: number; month: number };
  daily_prices: Array<{ date: string; predicted_price: number; confidence_lower: number; confidence_upper: number }>;
  price_distribution: {
    min: number;
    max: number;
    mean: number;
    std: number;
    percentiles: { p10: number; p25: number; p50: number; p75: number; p90: number };
  };
}
export interface MonthlyStrategyListRow {
  strategy_id: string;
  customer_id: string;
  customer_name: string;
  target_month: { year: number; month: number };
  strategy_config: Record<string, unknown>;
  optimization_results: Record<string, unknown>;
  created_at: string;
}

export async function generateMonthlyStrategy(params: {
  customer_id: string;
  target_year: number;
  target_month: number;
  annual_contract_ratio?: number;
  monthly_bid_ratio?: number;
  spot_ratio?: number;
  optimization_objective?: 'cost' | 'risk' | 'balanced';
}): Promise<MonthlyStrategyResp> {
  const r = await apiClient.post('/api/v1/trading/monthly-strategy/generate', null, { params });
  return r.data;
}
export async function getMonthlyStrategy(strategyId: string): Promise<MonthlyStrategyResp> {
  const r = await apiClient.get('/api/v1/trading/monthly-strategy/get', { params: { strategy_id: strategyId } });
  return r.data;
}
export async function getMonthlyStrategyScenarios(strategyId: string): Promise<{ scenario_analysis: Record<string, unknown> }> {
  const r = await apiClient.get('/api/v1/trading/monthly-strategy/scenarios', { params: { strategy_id: strategyId } });
  return r.data;
}
export async function getMonthlyPriceTrend(
  targetYear: number,
  targetMonth: number,
  forecastType = 'monthly_price',
): Promise<MonthlyPriceTrendResp> {
  const r = await apiClient.get('/api/v1/trading/monthly-strategy/price-trend', {
    params: { target_year: targetYear, target_month: targetMonth, forecast_type: forecastType },
  });
  return r.data;
}
export async function listMonthlyStrategies(
  customerId: string,
  targetYear: number,
  targetMonth: number,
): Promise<MonthlyStrategyListRow[]> {
  const r = await apiClient.get('/api/v1/trading/monthly-strategy/list', {
    params: { customer_id: customerId, target_year: targetYear, target_month: targetMonth },
  });
  return r.data;
}

// ---------- D-2 交易策略 ----------

export interface D2StrategyResp {
  strategy_id: string;
  customer_id: string;
  customer_name: string;
  target_date: string;
  d2_forecast: {
    forecast_id: string;
    avg_price: number;
    price_range: [number, number];
    hourly_prices: Array<{ time: string; predicted_price: number; confidence_lower: number; confidence_upper: number }>;
    price_distribution: { min: number; max: number; mean: number; std: number };
  };
  current_contract: {
    total_amount: number;
    avg_price: number;
    hourly_amounts: Array<{ time: string; contract_amount: number; contract_price: number }>;
  };
  load_forecast: { total_load: number; hourly_loads: Array<{ time: string; predicted_load: number }> };
  strategy_recommendations: Record<string, unknown>;
  risk_alerts: D2RiskAlert[];
  backtesting: Record<string, unknown>;
}
export interface D2RiskAlert {
  type: string;
  severity: string;
  time_range?: string;
  predicted_price?: number;
  std?: number;
  recommendation?: string;
  potential_loss?: number;
}
export interface D2BacktestingResp {
  period: string;
  d2_strategy: { total_cost: number; daily_volatility: number; max_loss: number; sharpe_ratio: number };
  fixed_contract: Record<string, unknown>;
  pure_spot: Record<string, unknown>;
}

export async function generateD2Strategy(params: {
  customer_id: string;
  target_date: string;
  compare_with?: string;
}): Promise<D2StrategyResp> {
  const r = await apiClient.post('/api/v1/trading/d2-strategy/generate', null, { params });
  return r.data;
}
export async function getD2Strategy(strategyId: string): Promise<D2StrategyResp> {
  const r = await apiClient.get('/api/v1/trading/d2-strategy/get', { params: { strategy_id: strategyId } });
  return r.data;
}
export async function getD2Risks(targetDate: string, customerId: string): Promise<{ risk_alerts: D2RiskAlert[] }> {
  const r = await apiClient.get('/api/v1/trading/d2-strategy/risks', {
    params: { target_date: targetDate, customer_id: customerId },
  });
  return r.data;
}
export async function getD2Backtesting(customerId: string, periodDays = 30): Promise<D2BacktestingResp> {
  const r = await apiClient.get('/api/v1/trading/d2-strategy/backtesting', {
    params: { customer_id: customerId, period_days: periodDays },
  });
  return r.data;
}

// ---------- 日前交易策略 ----------

export interface DayAheadStrategyResp {
  plan_id: string;
  customer_id: string;
  customer_name: string;
  target_date: string;
  plan_config: {
    strategy_type: string;
    contract_coverage_ratio: number;
    day_ahead_coverage_ratio: number;
    spot_ratio: number;
  };
  d1_forecast: {
    forecast_id: string;
    avg_price: number;
    price_range: [number, number];
    hourly_prices: Array<{ time: string; predicted_price: number; confidence_lower: number; confidence_upper: number }>;
    price_distribution: { min: number; max: number; mean: number; std: number };
  };
  load_forecast: { total_load: number; hourly_loads: Array<{ time: string; predicted_load: number }> };
  hourly_trading_plan: Array<{
    time: string;
    predicted_load: number;
    contract_amount: number;
    contract_price: number;
    day_ahead_amount: number;
    day_ahead_predicted_price: number;
    coverage: number;
    strategy: string;
    contract_cost: number;
    day_ahead_cost: number;
    total_cost: number;
    vs_contract_only_savings: number;
    vs_spot_only_savings: number;
  }>;
  strategy_recommendations: Record<string, unknown>;
  priority_recommendations: Array<Record<string, unknown>>;
  risk_alerts: D2RiskAlert[];
  created_at: string;
  status: string;
}

export async function generateDayAheadStrategy(params: {
  customer_id: string;
  target_date: string;
  strategy_type?: 'conservative' | 'balanced' | 'aggressive';
}): Promise<DayAheadStrategyResp> {
  const r = await apiClient.post('/api/v1/trading/day-ahead-strategy/generate', null, { params });
  return r.data;
}
export async function getDayAheadStrategy(planId: string): Promise<DayAheadStrategyResp> {
  const r = await apiClient.get('/api/v1/trading/day-ahead-strategy/get', { params: { plan_id: planId } });
  return r.data;
}
export async function getDayAheadRecommendations(targetDate: string, customerId: string): Promise<{ recommendations: Array<Record<string, unknown>> }> {
  const r = await apiClient.get('/api/v1/trading/day-ahead-strategy/recommendations', {
    params: { target_date: targetDate, customer_id: customerId },
  });
  return r.data;
}

// ---------- 中长期复盘（POST JSON body）----------

export interface ReviewResp {
  review_id: string;
  customer_id: string;
  customer_name: string;
  review_period: { start_date: string; end_date: string; type: string };
  execution_metrics: {
    planned_contract_coverage: number;
    actual_contract_coverage: number;
    execution_rate: number;
    avg_deviation: number;
    max_deviation_date: string;
    max_deviation_amount: number;
  };
  cost_metrics: {
    contract_cost: number;
    spot_cost: number;
    total_cost: number;
    blended_price: number;
    market_cost: number;
    cost_savings: number;
    savings_percentage: number;
  };
  timing_analysis: { avg_days_before_effective: number; avg_price_advantage_at_signing: number; timing_accuracy: number };
  strategy_comparison: Array<{ strategy: string; contract_coverage: number; total_cost: number; risk_score: number }>;
  anomalies: Array<{ date: string; type: string; description: string; deviation: number; impact_cost: number; recommendation: string }>;
  summary: {
    highlights: string[];
    issues: string[];
    recommendations: Array<{ priority: string; action: string; reason: string; suggestion: string; expected_benefit: string }>;
  };
  generated_at: string;
  status: string;
}
export interface ReviewCostBenefitResp {
  customer_id: string;
  period: { start_date: string; end_date: string };
  cost_metrics: ReviewResp['cost_metrics'];
  strategy_comparison: ReviewResp['strategy_comparison'];
  cumulative_savings: {
    vs_pure_spot: Array<{ date: string; cumulative_savings: number }>;
    vs_fixed_price: Array<{ date: string; cumulative_savings: number }>;
    total_savings: number;
  };
}
export interface ReviewListResp {
  total: number;
  reviews: Array<{
    review_id: string;
    customer_id: string;
    customer_name: string;
    review_period: { start_date: string; end_date: string; type: string };
    cost_metrics: ReviewResp['cost_metrics'];
    generated_at: string;
  }>;
}

export async function generateReview(body: {
  customer_id: string;
  start_date: string;
  end_date: string;
  compare_baselines?: string[];
}): Promise<ReviewResp> {
  const r = await apiClient.post('/api/v1/review/medium-long-term/generate', body);
  return r.data;
}
export async function getReviewExecution(body: {
  customer_id: string;
  start_date: string;
  end_date: string;
  granularity?: 'day' | 'week' | 'month';
}): Promise<ReviewResp> {
  const r = await apiClient.post('/api/v1/review/medium-long-term/execution', body);
  return r.data;
}
export async function getReviewCostBenefit(body: {
  customer_id: string;
  start_date: string;
  end_date: string;
}): Promise<ReviewCostBenefitResp> {
  const r = await apiClient.post('/api/v1/review/medium-long-term/cost-benefit', body);
  return r.data;
}
export async function getReviewTiming(body: { customer_id: string; start_date: string; end_date: string }): Promise<ReviewResp> {
  const r = await apiClient.post('/api/v1/review/medium-long-term/timing', body);
  return r.data;
}
export async function getReviewStrategyComparison(body: {
  customer_id: string;
  start_date: string;
  end_date: string;
}): Promise<{ strategy_comparison: ReviewResp['strategy_comparison']; recommendations: ReviewResp['summary']['recommendations'] }> {
  const r = await apiClient.post('/api/v1/review/medium-long-term/strategy-comparison', body);
  return r.data;
}
export async function listReviews(customerId?: string, limit = 10): Promise<ReviewListResp> {
  const r = await apiClient.get('/api/v1/review/medium-long-term/list', { params: { customer_id: customerId, limit } });
  return r.data;
}

// ---------- 定价模型（只读 + 校验）----------

export interface PricingModelListItem {
  _id: string;
  model_code: string;
  display_name: string;
  package_type: 'time_based' | 'non_time_based';
  pricing_mode: string;
  floating_type: string | null;
  formula: string;
  description: string;
  enabled: boolean;
  sort_order: number;
}
export interface PricingModelDetail extends PricingModelListItem {
  formula: string; // HTML
  description: string; // HTML
  created_at: string;
  updated_at: string;
}
export interface PricingModelValidateResp {
  valid: boolean;
  errors: string[];
  warnings: string[];
}

export async function listPricingModels(
  packageType?: 'time_based' | 'non_time_based',
  enabled?: boolean,
): Promise<PricingModelListItem[]> {
  const r = await apiClient.get('/api/v1/pricing-models', { params: { package_type: packageType, enabled } });
  return r.data;
}
export async function getPricingModel(modelCode: string): Promise<PricingModelDetail> {
  const r = await apiClient.get(`/api/v1/pricing-models/${modelCode}`);
  return r.data;
}
export async function validatePricingModel(modelCode: string, pricingConfig: Record<string, unknown>): Promise<PricingModelValidateResp> {
  const r = await apiClient.post(`/api/v1/pricing-models/${modelCode}/validate`, { pricing_config: pricingConfig });
  return r.data;
}
