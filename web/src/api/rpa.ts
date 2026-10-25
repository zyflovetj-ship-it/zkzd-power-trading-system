import apiClient from './client';

// RPA 数据下载监控
export interface SummaryStats {
  success: number;
  skipped: number;
  failed: number;
  alerts: number;
}

export interface TaskExecutionSummary {
  pipeline_name: string;
  task_key: string;
  daily_status: 'SUCCESS' | 'SKIPPED' | 'FAILED';
  execution_time: string | null;
  execution_count: number;
  last_success_date: string | null;
  records_inserted: number;
  records_updated: number;
  records_skipped: number;
  target_collections: string[];
  error_message: string | null;
  message: string | null;
  duration_seconds: number | null;
}

export interface DailySummaryResponse {
  date: string;
  summary: SummaryStats;
  tasks: TaskExecutionSummary[];
  has_data: boolean;
}

export interface ExecutionHistoryItem {
  pipeline_name: string;
  task_key: string;
  execution_time: string;
  status: string;
  records_inserted: number;
  records_updated: number;
  records_skipped: number;
  error_message: string | null;
  message: string | null;
  duration_seconds: number | null;
}

export interface ExecutionBatch {
  batch_index: number;
  batch_time: string;
  start_time: string;
  end_time: string;
  task_count: number;
  success_count: number;
  failed_count: number;
  records: ExecutionHistoryItem[];
}

export interface ExecutionHistoryResponse {
  date: string;
  total_batches: number;
  batches: ExecutionBatch[];
  has_data: boolean;
}

export interface AlertItem {
  level: 'critical' | 'warning' | 'info';
  rule: string;
  pipeline_name: string;
  task_key: string;
  message: string;
  timestamp: string | null;
  can_retry: boolean;
}

export async function getRpaDaily(date: string): Promise<DailySummaryResponse> {
  const r = await apiClient.get('/api/v1/rpa/execution/daily', { params: { date } });
  return r.data;
}
export async function getRpaHistory(date: string): Promise<ExecutionHistoryResponse> {
  const r = await apiClient.get('/api/v1/rpa/execution/history', { params: { date } });
  return r.data;
}
export async function getRpaAlerts(date: string): Promise<{ date: string; alerts: AlertItem[] }> {
  const r = await apiClient.get('/api/v1/rpa/alerts', { params: { date } });
  return r.data;
}
export async function retryRpaTask(pipelineName: string, taskKey: string): Promise<unknown> {
  const r = await apiClient.post(
    `/api/v1/rpa/tasks/${encodeURIComponent(pipelineName)}/${encodeURIComponent(taskKey)}/retry`,
  );
  return r.data;
}
