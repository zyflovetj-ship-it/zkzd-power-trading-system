import apiClient from './client';

// 定时任务监控（后端 webapp/api/v1_scheduler.py，挂在 /api/v1/scheduler）

export interface ScheduleConfig {
  trigger_type: string;
  cron_expression?: string | null;
  interval_seconds?: number | null;
  run_at?: string | null;
}

export interface TaskItem {
  id: string;
  name: string;
  display_name: string;
  description?: string;
  task_type: string;
  is_enabled: boolean;
  schedule_config: ScheduleConfig;
  last_run_at?: string | null;
  last_status?: string | null;
  next_run_at?: string | null;
}

export interface TaskListResp {
  total: number;
  page: number;
  page_size: number;
  items: TaskItem[];
}

export interface SchedulerStats {
  total_tasks: number;
  enabled_tasks: number;
  disabled_tasks: number;
  recent_success_count: number;
  recent_failed_count: number;
  recent_running_count: number;
}

export const getTasks = () =>
  apiClient.get<TaskListResp>('/api/v1/scheduler/tasks').then((r) => r.data);

export const getSchedulerStats = () =>
  apiClient.get<SchedulerStats>('/api/v1/scheduler/stats').then((r) => r.data);

export interface ExecutionLog {
  id?: string;
  status: string;
  started_at?: string;
  finished_at?: string;
  duration_ms?: number;
  message?: string;
  error_message?: string;
}

export const getTaskLogs = (taskName: string, page = 1, pageSize = 20) =>
  apiClient
    .get<{ items: ExecutionLog[]; total?: number; page?: number; page_size?: number }>(
      '/api/v1/scheduler/tasks/' + taskName + '/logs?page=' + page + '&page_size=' + pageSize,
    )
    .then((r) => r.data);

export const triggerTask = (taskName: string) =>
  apiClient.post('/api/v1/scheduler/tasks/' + taskName + '/trigger').then((r) => r.data);

export const toggleTask = (taskName: string, enabled: boolean) =>
  apiClient
    .post('/api/v1/scheduler/tasks/' + taskName + '/toggle', { is_enabled: enabled })
    .then((r) => r.data);
