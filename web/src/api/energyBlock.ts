import apiClient from './client';

export type MarketType = 'mid_long' | 'day_ahead' | 'real_time';
export type PeriodType = 'peak' | 'flat' | 'valley' | 'time';

export interface EnergyBlockItem {
  period_type: PeriodType;
  time_str?: string | null;
  segment: number;
  volume_mwh: number;
  price: number;
}

export interface EnergyBlockSetCreate {
  market_type: MarketType;
  subject_type?: 'customer' | 'unit' | 'trading_unit';
  subject_id: string;
  subject_name?: string;
  trade_period?: string;
  start_date: string;
  end_date?: string;
  total_volume_mwh?: number;
  expected_ratio?: Record<string, number>;
  direction?: 'buy' | 'sell';
  price_cap?: number;
  status?: 'draft' | 'submitted' | 'cleared' | 'cancelled';
  blocks: EnergyBlockItem[];
}

export interface ValidateResult {
  valid: boolean;
  errors: string[];
  warnings: string[];
  summary: {
    block_count: number;
    total_volume_mwh: number;
    total_amount: number;
    avg_price: number;
    ratio_by_period: Record<string, number>;
    by_period: Record<string, { volume_mwh: number; amount: number; avg_price: number }>;
  };
}

export interface BlockSetListItem {
  block_set_id: string;
  market_type: MarketType;
  subject_id: string;
  subject_name?: string;
  start_date: string;
  end_date: string;
  status: string;
  block_count: number;
  total_volume_mwh: number;
  created_at: string;
  created_by: string;
}

/** 96 点时刻选项 */
export const TIME_OPTIONS = Array.from({ length: 96 }, (_, i) => {
  const h = Math.floor(i / 4);
  const m = (i % 4) * 15;
  const v = String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
  return { label: v, value: v };
});

export async function validateBlocks(payload: EnergyBlockSetCreate): Promise<ValidateResult> {
  const r = await apiClient.post('/api/v1/energy-blocks/validate', payload);
  return r.data;
}

export async function createBlocks(payload: EnergyBlockSetCreate): Promise<unknown> {
  const r = await apiClient.post('/api/v1/energy-blocks', payload);
  return r.data;
}

export async function fetchBlockSets(params: { market_type?: string; subject_id?: string } = {}) {
  const r = await apiClient.get('/api/v1/energy-blocks', { params });
  return r.data as { items: BlockSetListItem[] };
}

export async function deleteBlockSet(setId: string): Promise<void> {
  await apiClient.delete('/api/v1/energy-blocks/' + setId);
}
