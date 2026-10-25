import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Collapse, Form, InputNumber, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import { getModelParameters, type ModelType, type EnableStatus, type ModelRecord } from '@/api/modelParams';

// 演示：保存各模型折叠面板内的临时编辑值（仅 UI，不提交）。
const ModelEditor = ({ record }: { record: ModelRecord }) => {
  const [form] = Form.useForm();
  return (
    <Form
      form={form}
      layout="inline"
      initialValues={{ lr: 0.001, window: 96, hidden: 64 }}
      style={{ rowGap: 12 }}
    >
      <Form.Item label="学习率" name="lr">
        <InputNumber step={0.001} min={0} />
      </Form.Item>
      <Form.Item label="窗口长度" name="window">
        <InputNumber min={1} />
      </Form.Item>
      <Form.Item label="隐藏层" name="hidden">
        <InputNumber min={1} />
      </Form.Item>
      <Form.Item>
        <Tag color="default">仅演示，不提交</Tag>
      </Form.Item>
    </Form>
  );
};

export default function ModelParametersPage() {
  const q = useQuery({ queryKey: ['modelParameters'], queryFn: () => getModelParameters() });
  const isLoading = q.isLoading;
  const models = q.data?.models ?? [];

  const [activeKey, setActiveKey] = useState<string[]>([]);

  const maeDistOption: EChartsOption = useMemo(
    () => ({
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: ['MAE'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: models.map((m) => m.name), name: '模型', axisLabel: { interval: 0, rotate: 30 } },
      yAxis: { type: 'value', name: 'MAE' },
      series: [{ name: 'MAE', type: 'bar', data: models.map((m) => m.mae), itemStyle: { color: CHART_COLORS[4] } }],
    }),
    [models],
  );

  const totalModels = models.length;
  const enabledCount = models.filter((m) => m.status === 'enabled').length;
  const latestTrain = models.length ? models.reduce((max, m) => (m.updatedAt > max ? m.updatedAt : max), models[0].updatedAt) : '-';
  const avgMae = models.length ? (models.reduce((s, m) => s + m.mae, 0) / totalModels).toFixed(1) : '0.0';

  const columns: ColumnsType<ModelRecord> = [
    { title: '模型名称', dataIndex: 'name', width: 180 },
    {
      title: '类型',
      dataIndex: 'type',
      width: 120,
      render: (t: ModelType) => <Tag color={t === '价格预测' ? 'orange' : 'blue'}>{t}</Tag>,
    },
    { title: '版本', dataIndex: 'version', width: 90 },
    { title: '关键参数', dataIndex: 'params', width: 300 },
    {
      title: '启用状态',
      dataIndex: 'status',
      width: 100,
      render: (s: EnableStatus) =>
        s === 'enabled' ? <Tag color="success">已启用</Tag> : <Tag color="default">已停用</Tag>,
    },
    { title: '更新时间', dataIndex: 'updatedAt', width: 160 },
  ];

  return (
    <div>
      <KpiCards
        loading={isLoading}
        items={[
          { label: '模型数', value: totalModels, suffix: '个', color: CHART_COLORS[0] },
          { label: '已启用数', value: enabledCount, suffix: '个', color: CHART_COLORS[3] },
          { label: '最近训练', value: latestTrain, color: CHART_COLORS[1] },
          { label: '平均MAE', value: avgMae, precision: 1, color: CHART_COLORS[4] },
        ]}
      />

      <ChartCard title="各模型 MAE 对比" option={maeDistOption} loading={isLoading} height={340} />

      <Card size="small" title="预测模型列表" style={{ marginBottom: 16 }}>
        <Table<ModelRecord>
          rowKey={(r) => r.name}
          columns={columns}
          dataSource={models}
          pagination={false}
          scroll={{ x: 'max-content' }}
          size="small"
        />
      </Card>

      <Card size="small" title="模型参数编辑（演示）" style={{ marginBottom: 16 }}>
        <Collapse
          activeKey={activeKey}
          onChange={(k) => setActiveKey(Array.isArray(k) ? k.map(String) : [String(k)])}
          items={models.map((m) => ({
            key: m.name,
            label: (
              <span>
                <Tag color={m.status === 'enabled' ? 'success' : 'default'}>{m.status === 'enabled' ? '已启用' : '已停用'}</Tag>
                {m.name}（{m.version}）
              </span>
            ),
            children: <ModelEditor record={m} />,
          }))}
        />
      </Card>
    </div>
  );
}
