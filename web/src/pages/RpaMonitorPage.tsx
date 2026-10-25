import { useCallback, useEffect, useState } from 'react';
import { App, Alert as AntAlert, Button, Card, Col, DatePicker, Row, Statistic, Table, Tag, Space, Tabs, Empty } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  MinusOutlined,
  ReloadOutlined,
  WarningOutlined,
} from '@ant-design/icons';
import dayjs, { type Dayjs } from 'dayjs';
import {
  getRpaAlerts,
  getRpaDaily,
  getRpaHistory,
  retryRpaTask,
  type AlertItem,
  type DailySummaryResponse,
  type ExecutionBatch,
  type ExecutionHistoryResponse,
  type TaskExecutionSummary,
} from '@/api/rpa';

function StatusTag({ status }: { status: string }) {
  if (status === 'SUCCESS') return <Tag color="success" icon={<CheckCircleOutlined />}>成功</Tag>;
  if (status === 'FAILED') return <Tag color="error" icon={<CloseCircleOutlined />}>失败</Tag>;
  return <Tag icon={<MinusOutlined />}>跳过</Tag>;
}

const levelColor: Record<AlertItem['level'], string> = {
  critical: 'error',
  warning: 'warning',
  info: 'info',
};
const levelLabel: Record<AlertItem['level'], string> = {
  critical: '严重',
  warning: '警告',
  info: '提示',
};

export default function RpaMonitorPage() {
  const { message } = App.useApp();
  const [date, setDate] = useState<Dayjs>(dayjs());
  const [loading, setLoading] = useState(false);
  const [daily, setDaily] = useState<DailySummaryResponse | null>(null);
  const [history, setHistory] = useState<ExecutionHistoryResponse | null>(null);
  const [alerts, setAlerts] = useState<AlertItem[]>([]);
  const [batchIndex, setBatchIndex] = useState(0);

  const load = useCallback(async () => {
    const ds = date.format('YYYY-MM-DD');
    setLoading(true);
    try {
      const [d, h, a] = await Promise.all([getRpaDaily(ds), getRpaHistory(ds), getRpaAlerts(ds)]);
      setDaily(d);
      setHistory(h);
      setAlerts(a.alerts ?? []);
      setBatchIndex((h.batches?.length ?? 0) - 1 >= 0 ? (h.batches?.length ?? 1) - 1 : 0);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [date, message]);

  useEffect(() => {
    load();
  }, [load]);

  const retryOne = async (a: AlertItem) => {
    try {
      await retryRpaTask(a.pipeline_name, a.task_key);
      message.success(`已发起重试：${a.task_key}`);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '重试失败');
    }
  };

  const retryAll = async () => {
    const retryable = alerts.filter((a) => a.can_retry);
    if (!retryable.length) {
      message.info('没有可重试的任务');
      return;
    }
    try {
      await Promise.all(retryable.map((a) => retryRpaTask(a.pipeline_name, a.task_key).catch(() => null)));
      message.success(`已批量发起 ${retryable.length} 个重试`);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '重试失败');
    }
  };

  const dailyColumns: ColumnsType<TaskExecutionSummary> = [
    { title: '管道', dataIndex: 'pipeline_name', width: 160 },
    { title: '任务', dataIndex: 'task_key', width: 200 },
    { title: '状态', dataIndex: 'daily_status', width: 90, render: (s: string) => <StatusTag status={s} /> },
    {
      title: '记录数',
      key: 'rec',
      width: 110,
      render: (_: unknown, r: TaskExecutionSummary) =>
        r.daily_status === 'SUCCESS' ? (
          <>
            {r.records_inserted > 0 && `+${r.records_inserted}`}
            {r.records_updated > 0 && ` ↻${r.records_updated}`}
          </>
        ) : (
          '-'
        ),
    },
    {
      title: '执行时间',
      dataIndex: 'execution_time',
      width: 120,
      render: (v: string | null) => (v ? dayjs(v).format('HH:mm:ss') : '-'),
    },
    {
      title: '耗时',
      dataIndex: 'duration_seconds',
      width: 90,
      render: (v: number | null) => (v != null ? `${v.toFixed(1)}s` : '-'),
    },
  ];

  const batchColumns: ColumnsType<ExecutionBatch['records'][number]> = [
    { title: '时间', dataIndex: 'execution_time', width: 110, render: (v: string) => dayjs(v).format('HH:mm:ss') },
    { title: '管道', dataIndex: 'pipeline_name', width: 160 },
    { title: '任务', dataIndex: 'task_key', width: 200 },
    { title: '状态', dataIndex: 'status', width: 90, render: (s: string) => <StatusTag status={s} /> },
    { title: '耗时', dataIndex: 'duration_seconds', width: 90, render: (v: number | null) => (v != null ? `${v.toFixed(1)}s` : '-') },
    { title: '消息', dataIndex: 'error_message', width: 260, render: (v: string | null, r) => v || r.message || '-' },
  ];

  const currentBatch: ExecutionBatch | undefined = history?.batches?.[batchIndex];

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Space wrap>
          <DatePicker value={date} onChange={(d) => d && setDate(d)} allowClear={false} />
          <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>
            刷新
          </Button>
          <Button onClick={() => setDate(dayjs().subtract(1, 'day'))}>昨日</Button>
        </Space>
      </Card>

      {!daily?.has_data ? (
        <Card>
          <Empty description={`${date.format('YYYY-MM-DD')} 暂无执行记录（预计执行时间 09:10 / 12:00 / 21:00）`} />
        </Card>
      ) : (
        <>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col xs={12} sm={8} md={5}><Card><Statistic title="任务数" value={daily.tasks.length} /></Card></Col>
            <Col xs={12} sm={8} md={5}><Card><Statistic title="成功" value={daily.summary.success} valueStyle={{ color: '#3f8600' }} /></Card></Col>
            <Col xs={12} sm={8} md={5}><Card><Statistic title="跳过" value={daily.summary.skipped} /></Card></Col>
            <Col xs={12} sm={8} md={5}><Card><Statistic title="失败" value={daily.summary.failed} valueStyle={{ color: '#cf1322' }} /></Card></Col>
            <Col xs={12} sm={8} md={4}><Card><Statistic title="告警" value={alerts.length} valueStyle={{ color: '#d46b08' }} /></Card></Col>
          </Row>

          {alerts.length > 0 && (
            <Card
              title={
                <Space>
                  <WarningOutlined />
                  告警 ({alerts.length})
                </Space>
              }
              style={{ marginBottom: 16 }}
              extra={
                alerts.some((a) => a.can_retry) && (
                  <Button size="small" icon={<ReloadOutlined />} onClick={retryAll}>
                    全部重试
                  </Button>
                )
              }
            >
              {alerts.map((a, i) => (
                <AntAlert
                  key={i}
                  type={levelColor[a.level] as any}
                  showIcon
                  style={{ marginBottom: 8 }}
                  message={
                    <Space>
                      <Tag color={levelColor[a.level]}>{levelLabel[a.level]}</Tag>
                      <b>{a.task_key}</b>
                      <span>{a.message}</span>
                    </Space>
                  }
                  action={
                    a.can_retry && (
                      <Button size="small" onClick={() => retryOne(a)}>
                        重试
                      </Button>
                    )
                  }
                />
              ))}
            </Card>
          )}

          <Card title="当日执行摘要" style={{ marginBottom: 16 }}>
            <Table<TaskExecutionSummary>
              rowKey={(r) => `${r.pipeline_name}-${r.task_key}`}
              columns={dailyColumns}
              dataSource={daily.tasks}
              loading={loading}
              pagination={false}
              scroll={{ x: 'max-content' }}
              size="small"
            />
          </Card>

          {history?.has_data && currentBatch && (
            <Card title="执行历史">
              <Tabs
                activeKey={String(batchIndex)}
                onChange={(k) => setBatchIndex(Number(k))}
                items={history.batches.map((b, i) => ({
                  key: String(i),
                  label: `${b.batch_time} 第${b.batch_index}次`,
                }))}
              />
              <Space style={{ marginBottom: 12 }}>
                <Tag>任务数: {currentBatch.task_count}</Tag>
                <Tag color="success">成功: {currentBatch.success_count}</Tag>
                <Tag color="error">失败: {currentBatch.failed_count}</Tag>
              </Space>
              <Table
                rowKey={(_, i) => String(i)}
                columns={batchColumns}
                dataSource={currentBatch.records}
                pagination={false}
                scroll={{ x: 'max-content' }}
                size="small"
              />
            </Card>
          )}
        </>
      )}
    </div>
  );
}
