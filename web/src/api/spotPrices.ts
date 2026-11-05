import apiClient from './client';

// ===== 现货价格（日前/实时 96点）导入 =====
export interface SpotPreviewResult {
  file: string;
  ok: boolean;
  problems: string[];
  date?: string;
  day_ahead_points?: number;
  real_time_points?: number;
  day_ahead_avg?: number | null;
  real_time_avg?: number | null;
}

export interface SpotDayRow {
  date: string;
  day_ahead?: { points: number; avg: number | null; min: number | null; max: number | null } | null;
  real_time?: { points: number; avg: number | null; min: number | null; max: number | null } | null;
}

export function downloadSpotTemplate() {
  const base = import.meta.env.VITE_API_BASE_URL ?? '';
  return `${base}/api/v1/spot-prices/template`;
}

export async function previewSpotFiles(files: File[], year: number) {
  const fd = new FormData();
  files.forEach((f) => fd.append('files', f));
  const r = await apiClient.post('/api/v1/spot-prices/preview', fd, { params: { year } });
  return r.data as { ok_count: number; fail_count: number; results: SpotPreviewResult[] };
}

export async function importSpotFiles(files: File[], year: number) {
  const fd = new FormData();
  files.forEach((f) => fd.append('files', f));
  const r = await apiClient.post('/api/v1/spot-prices/import', fd, { params: { year } });
  return r.data as { inserted_day_ahead: number; inserted_real_time: number; deleted_old: number; skipped: number; problems: string[]; imported_dates: string[] };
}

export async function fetchSpotRecords(params: { date_from?: string; date_to?: string }) {
  const r = await apiClient.get('/api/v1/spot-prices/records', { params });
  return r.data as { total_days: number; rows: SpotDayRow[] };
}

export async function fetchSpotMonthly(month: string) {
  const r = await apiClient.get('/api/v1/spot-prices/monthly', { params: { month } });
  return r.data as { month: string; day_ahead: { avg: number; min: number; max: number; points: number } | null; real_time: { avg: number; min: number; max: number; points: number } | null };
}

export async function deleteSpotDate(date: string) {
  const r = await apiClient.delete('/api/v1/spot-prices/records', { params: { date } });
  return r.data as { date: string; deleted_day_ahead: number; deleted_real_time: number };
}
