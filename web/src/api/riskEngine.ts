import apiClient from './client';

// 风险引擎（P1）：分时段敞口 / VaR / 回测 / 压力测试 / 限额 / 预警
// 后端：webapp/api/v1_risk_engine.py，挂在 /api/v1/risk-engine 下

export type CheckLevel = 'ok' | 'warn' | 'fail';

export interface ValidateCheck {
  name: string;
  level: CheckLevel;
  detail: string;
  actual: unknown;
  expected: unknown;
}

export interface ValidateResp {
  delivery_date: string;
  overall: CheckLevel;
  checks: ValidateCheck[];
  timestamp_semantics: string;
  units: Record<string, string>;
}

export interface PeriodExposure {
  period_index: number;
  period_label: string;
  bucket: 'peak' | 'flat' | 'valley';
  contract_mwh: number;
  load_mwh: number;
  net_position_mwh: number;
  fwd_price: number;
  price_exposure: number;
}

export interface ExposureSummary {
  delivery_date: string;
  total_contract_mwh: number;
  total_load_mwh: number;
  total_net_mwh: number;
  peak_net_mwh: number;
  flat_net_mwh: number;
  valley_net_mwh: number;
  max_long_period_mwh: number;
  max_short_period_mwh: number;
  price_exposure_yuan: number;
  coverage_ratio: number;
  risk_level: 'low' | 'medium' | 'high';
  warnings: string[];
}

export interface ExposureResp {
  summary: ExposureSummary;
  curve: PeriodExposure[];
}

export interface VarResp {
  method: string;
  confidence: number;
  horizon_days: number;
  var_yuan: number;
  cvar_yuan: number;
  portfolio_sigma_yuan: number;
  sample_days: number;
  warnings: string[];
}

export interface LimitBreach {
  limit_id: string;
  scope: string;
  limit_type: string;
  threshold: number;
  actual: number;
  usage_ratio: number;
  severity: 'warning' | 'breach';
}

export interface LimitsResp {
  delivery_date: string;
  var_yuan: number;
  breaches: LimitBreach[];
  max_severity: 'ok' | 'warning' | 'breach';
}

export interface BacktestResp {
  method: string;
  confidence: number;
  window_days: number;
  samples: number;
  exceptions: number;
  expected_exceptions: number;
  kupiec_lr: number;
  kupiec_pvalue: number;
  christoffersen_lr: number;
  christoffersen_pvalue: number;
  cc_lr: number;
  cc_pvalue: number;
  passed: boolean;
  verdict: string;
  warnings: string[];
}

export interface StressScenarioResult {
  scenario_id: string;
  name: string;
  category: string;
  severity: 'low' | 'medium' | 'high';
  base_price_exposure: number;
  stressed_price_exposure: number;
  pnl_impact: number;
  impact_ratio: number;
  worst_period_index: number;
  worst_period_label: string;
  worst_period_impact: number;
  margin_call_estimate: number;
  penalty_estimate: number;
  limit_breaches: Array<Record<string, unknown>>;
  warnings: string[];
}

export interface StressSuiteResp {
  delivery_date: string;
  scenarios: StressScenarioResult[];
  worst_scenario_id: string;
  worst_pnl_impact: number;
  total_margin_call: number;
  warnings: string[];
}

export interface AlertItem {
  alert_id: string;
  alert_type: string;
  severity: 'info' | 'warning' | 'critical';
  title: string;
  message: string;
  source: string;
  delivery_date: string | null;
  status: string;
}

const q = (date?: string) => (date ? '?date=' + date : '');

export const getEngineMeta = () =>
  apiClient.get('/api/v1/risk-engine/meta').then((r) => r.data);

export const getValidate = (date?: string) =>
  apiClient.get<ValidateResp>('/api/v1/risk-engine/validate' + q(date)).then((r) => r.data);

export const getEngineExposure = (date?: string) =>
  apiClient.get<ExposureResp>('/api/v1/risk-engine/exposure' + q(date)).then((r) => r.data);

export const getEngineVar = (date?: string, method = 'parametric') =>
  apiClient
    .get<VarResp>('/api/v1/risk-engine/var' + q(date) + '&method=' + method)
    .then((r) => r.data);

export const getEngineLimits = (date?: string) =>
  apiClient.get<LimitsResp>('/api/v1/risk-engine/limits' + q(date)).then((r) => r.data);

export const getEngineBacktest = (date?: string, method = 'parametric', windowDays = 20) =>
  apiClient
    .get<BacktestResp>(
      '/api/v1/risk-engine/backtest' + q(date) + '&method=' + method + '&window_days=' + windowDays,
    )
    .then((r) => r.data);

export const runStressSuite = (date?: string) =>
  apiClient.post<StressSuiteResp>('/api/v1/risk-engine/stress/run' + q(date)).then((r) => r.data);

export const getAlerts = (status = 'open') =>
  apiClient
    .get<{ total: number; items: AlertItem[] }>('/api/v1/risk-engine/alerts?status=' + status)
    .then((r) => r.data);

export const createSnapshot = (date?: string) =>
  apiClient.post('/api/v1/risk-engine/snapshot' + q(date)).then((r) => r.data);
