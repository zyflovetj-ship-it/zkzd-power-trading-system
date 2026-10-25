import { useState } from 'react';
import { useQuery, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Modal, Space, Switch, Table, Tag, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { KpiCards } from '@/components/charts/KpiCards';
import { CHART_COLORS } from '@/components/charts/chartTheme';
import {
  getSchedulerStats,
  getTaskLogs,
  getTasks,
  toggleTask,
  triggerTask,
  type ExecutionLog,
  type TaskItem,
} from '@/api/scheduler';

const STATUS_TAG: Record<string, string> = {
  success: 'success',
  failed: 'error',
  running: 'processing',
  skipped: 'default',
};

const fmtTime = (v?: string | null) => (v ? v.replace('T', ' ').slice(0, 19) : '-');

const describeSchedule = (t: TaskItem) => {
  const c = t.schedule_config;
  if (!c) return '-';
  if (c.trigger_type === 'cron') return 'cron: ' + (c.cron_expression ?? '-');
  if (c.trigger_type === 'interval') return '每 ' + (c.interval_seconds ?? 0) + ' 秒';
  if (c.trigger_type === 'date') return '定时: ' + (c.run_at ?? '-');
  return c.trigger_type;
};

/** 定时任务监控：任务列表 + 启停 + 手动触发 + 执行日志 */
export default function SchedulerPage() {
  const qc = useQueryClient();
  const tasksQ = useQuery({ queryKey: ['schedulerTasks'], queryFn: getTasks });
  const statsQ = useQuery({ queryKey: ['schedulerStats'], queryFn: getSchedulerStats });

  const [logTask, setLogTask] = useState<string | null>(null);
  const logsQ = useQuery({
    queryKey: ['schedulerLogs', logTask],
    queryFn: () => getTaskLogs(logTask as string),
    enabled: !!logTask,
  });

  const refresh = () => {
    tasksQ.refetch();
    statsQ.refetch();
  };

  const onToggle = async (t: TaskItem, enabled: boolean) => {
    try {
      await toggleTask(t.name, enabled);
      message.success('任务已' + (enabled ? '启用' : '禁用'));
      refresh();
    } catch {
      message.error('操作失败');
    }
  };

  const onTrigger = async (t: TaskItem) => {
    try {
      const r = await triggerTask(t.name);
      message.success('已触发：' + String((r as { message?: string })?.message ?? t.name));
      setTimeout(refresh, 800);
    } catch {
      message.error('触发失败（任务可能未启用）');
    }
  };

  const stats = statsQ.data;

  const columns: ColumnsType<TaskItem> = [
    { title: '任务', dataIndex: 'display_name', width: 160, render: (v, r) => v || r.name },
    { title: '标识', dataIndex: 'name', width: 200 },
    { title: '类型', dataIndex: 'task_type', width: 120, render: (v: string) => <Tag>{v}</Tag> },
    { title: '调度', key: 'schedule', width: 200, render: (_, r) => describeSchedule(r) },
    {
      title: '状态', dataIndex: 'is_enabled', width: 90,
      render: (v: boolean) => <Tag color={v ? 'success' : 'default'}>{v ? '启用' : '禁用'}</Tag>,
    },
    { title: '上次执行', dataIndex: 'last_run_at', width: 170, render: (v: string | null) => fmtTime(v) },
    {
      title: '启停', key: 'toggle', width: 80,
      render: (_, r) => (
        <Switch size="small" checked={r.is_enabled} onChange={(c) => onToggle(r, c)} />
      ),
    },
    {
      title: '操作', key: 'ops', width: 160,
      render: (_, r) => (
        <Space>
          <Button size="small" type="link" onClick={() => onTrigger(r)}>立即执行</Button>
          <Button size="small" type="link" onClick={() => setLogTask(r.name)}>日志</Button>
        </Space>
      ),
    },
  ];

  const logColumns: ColumnsType<ExecutionLog> = [
    {
      title: '状态', dataIndex: 'status', width: 100,
      render: (v: string) => <Tag color={STATUS_TAG[v] ?? 'default'}>{v}</Tag>,
    },
    { title: '开始', dataIndex: 'started_at', width: 180, render: (v?: string) => fmtTime(v) },
    { title: '结束', dataIndex: 'finished_at', width: 180, render: (v?: string) => fmtTime(v) },
    {
      title: '耗时(ms)', dataIndex: 'duration_ms', width: 110, align: 'right',
      render: (v?: number) => (v == null ? '-' : v.toLocaleString()),
    },
    { title: '信息', dataIndex: 'message', render: (v?: string, r?: ExecutionLog) => v ?? r?.error_message ?? '-' },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card
        size="small"
        title="定时任务监控"
        extra={<Button onClick={refresh} loading={tasksQ.isLoading || statsQ.isLoading}>刷新</Button>}
      >
        <KpiCards
          columns={6}
          loading={statsQ.isLoading}
          items={[
            { label: '任务总数', value: stats?.total_tasks ?? 0, color: CHART_COLORS[0] },
            { label: '已启用', value: stats?.enabled_tasks ?? 0, color: CHART_COLORS[3] },
            { label: '已禁用', value: stats?.disabled_tasks ?? 0, color: CHART_COLORS[6] },
            { label: '近期成功', value: stats?.recent_success_count ?? 0, color: CHART_COLORS[3] },
            { label: '近期失败', value: stats?.recent_failed_count ?? 0, color: CHART_COLORS[7] },
            { label: '运行中', value: stats?.recent_running_count ?? 0, color: CHART_COLORS[1] },
          ]}
        />
      </Card>

      <Card size="small" title="任务列表" loading={tasksQ.isLoading}>
        <Table
          size="small"
          rowKey="name"
          columns={columns}
          dataSource={tasksQ.data?.items ?? []}
          pagination={false}
          scroll={{ x: 1100 }}
        />
      </Card>

      <Modal
        open={!!logTask}
        title={'执行日志 · ' + (logTask ?? '')}
        onCancel={() => setLogTask(null)}
        footer={null}
        width={900}
      >
        <Table
          size="small"
          rowKey={(r, i) => String(r.id ?? i)}
          columns={logColumns}
          dataSource={logsQ.data?.items ?? []}
          loading={logsQ.isLoading}
          pagination={{ pageSize: 10, hideOnSinglePage: true }}
        />
      </Modal>
    </Space>
  );
}
