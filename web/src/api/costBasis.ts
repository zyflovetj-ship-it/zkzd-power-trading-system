import apiClient from './client';

// ===== 成本基线（事前综合购电成本） =====
export interface CostComponent {
  name: string;
  mwh: number;
  price: number | null;
  amount: number;
  source: string;
}

export interface CostBasis {
  month: string;
  customer_id?: string | null;
  total_mwh: number;
  position_mwh: number;
  exposure_mwh: number;
  coverage_ratio: number | null;
  contract_cost: number;
  spot_cost: number;
  share_cost: number;
  total_cost: number;
  unit_cost: number | null;
  components: CostComponent[];
  spot_price_basis: number | null;
  share_params?: Record<string, number>;
  sources?: Record<string, unknown>;
  warnings: string[];
}

export interface CostBasisMonthRow {
  month: string;
  customer_id?: string | null;
  total_mwh: number;
  unit_cost: number | null;
  coverage_ratio: number | null;
  computed_at?: string;
}

export async function fetchCostBasis(params: { month: string; customer_id?: string }): Promise<CostBasis> {
  const r = await apiClient.get('/api/v1/cost-basis', { params });
  return r.data;
}

export async function recomputeCostBasis(payload: {
  month: string;
  customer_id?: string;
  share?: { cost_compensation?: number; imbalance?: number; market_adjust?: number };
}): Promise<CostBasis> {
  const r = await apiClient.post('/api/v1/cost-basis/recompute', payload);
  return r.data;
}

export async function fetchCostBasisList(limit = 24): Promise<{ rows: CostBasisMonthRow[] }> {
  const r = await apiClient.get('/api/v1/cost-basis/list', { params: { limit } });
  return r.data;
}
