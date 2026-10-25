import { useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Alert, Button, Card, Col, DatePicker, Row, Select, Space, Table, Tag, App } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import dayjs, { type Dayjs } from 'dayjs';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { CustomerSelect } from '@/components/CustomerSelect';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS, confidenceBand } from '@/components/charts/chartTheme';
import { generateDayAheadStrategy, type DayAheadStrategyResp, type D2RiskAlert } from '@/api/trading';

const TYPE_OPTS = [
  { label: '保守', value: 'conservative' },
  { label: '均衡', value: 'balanced' },
  { label: '激进', value: 'aggressive' },
];

export default function DayAheadStrategyPage() {
  const { message } = App.useApp();
  const [customerId, setCustomerId] = useState('');
  const [date, setDate] = useState<Dayjs>(dayjs().add(1, 'day'));
  const [strategyType, setStrategyType] = useState<'conservative' | 'balanced' | 'aggressive'>('balanced');
  const [result, setResult] = useState<DayAheadStrategyResp | null>(null);

  const dateStr = date.format('YYYY-MM-DD');

  const genMut = useMutation({
    mutationFn: () => generateDayAheadStrategy({ customer_id: customerId, target_date: dateStr, strategy_type: strategyType }),
    onSuccess: (d) => { setResult(d); message.success('日前策略已生成'); },
    onError: (e: any) => message.error(e?.response?.data?.detail || e?.message || '生成失败'),
  });

  const fc = result?.d1_forecast;
  const hp = fc?.hourly_prices ?? [];
  const plan = result?.hourly_trading_plan ?? [];

  const priceOption: EChartsOption = useMemo(() => {
    const band = confidenceBand('区间', hp.map((p) => p.confidence_lower), hp.map((p) => p.confidence_upper), 'rgba(19,194,194,0.18)');
    return {
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: ['预测价格', '区间'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: hp.map((p) => p.time), name: '时刻', boundaryGap: false },
      yAxis: { type: 'value', name: '价格(元/MWh)', scale: true },
      series: [
        ...band,
        { name: '预测价格', type: 'line', smooth: true, showSymbol: false, data: hp.map((p) => p.predicted_price), itemStyle: { color: CHART_COLORS[3] }, z: 2 },
      ],
    };
  }, [hp]);

  const planOption: EChartsOption = useMemo(
    () => ({
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: ['预测负荷', '合约电量', '日前电量'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: plan.map((p) => p.time), name: '时刻', boundaryGap: false },
      yAxis: { type: 'value', name: '电量(MWh)' },
      series: [
        { name: '预测负荷', type: 'line', smooth: true, showSymbol: false, data: plan.map((p) => p.predicted_load), itemStyle: { color: CHART_COLORS[0] } },
        { name: '合约电量', type: 'line', smooth: true, showSymbol: false, data: plan.map((p) => p.contract_amount), itemStyle: { color: CHART_COLORS[1] } },
        { name: '日前电量', type: 'line', smooth: true, showSymbol: false, data: plan.map((p) => p.day_ahead_amount), itemStyle: { color: CHART_COLORS[3] } },
      ],
    }),
    [plan],
  );

  const recColumns: ColumnsType<DayAheadStrategyResp['priority_recommendations'][number]> = [
    { title: '优先级', dataIndex: 'priority', width: 90, render: (v: string) => <Tag color={v === 'high' ? 'error' : v === 'medium' ? 'warning' : 'default'}>{v}</Tag> },
    { title: '时段', dataIndex: 'time_range', width: 140 },
    { title: '动作', dataIndex: 'action', width: 160 },
    { title: '理由', dataIndex: 'reasoning' },
  ];

  const riskColumns: ColumnsType<D2RiskAlert> = [
    { title: '类型', dataIndex: 'type', width: 140 },
    { title: '时段', dataIndex: 'time_range', width: 140 },
    { title: '预测价', dataIndex: 'predicted_price', width: 110, render: (v: number) => (v != null ? `${v} 元/MWh` : '-') },
    { title: '潜在损失', dataIndex: 'potential_loss', width: 120, render: (v: number) => (v != null ? `${v} 元` : '-') },
    { title: '建议', dataIndex: 'recommendation' },
  ];

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle" wrap>
          <Col><CustomerSelect value={customerId} onChange={(v) => { setCustomerId(v); setResult(null); }} /></Col>
          <Col><DatePicker value={date} onChange={(d) => d && setDate(d)} allowClear={false} /></Col>
          <Col><Select value={strategyType} onChange={setStrategyType} options={TYPE_OPTS} style={{ width: 120 }} /></Col>
          <Col><Button type="primary" loading={genMut.isPending} disabled={!customerId} onClick={() => genMut.mutate()}>生成日前策略</Button></Col>
        </Row>
      </Card>

      {!result && <Card><Alert type="info" showIcon message="请选择客户与目标日（默认 D+1）后生成日前交易策略" /></Card>}

      {result && (
        <>
          <KpiCards
            items={[
              { label: '预测均价', value: fc?.avg_price ?? '-', precision: 1, suffix: '元/MWh', color: CHART_COLORS[3] },
              { label: '预测总负荷', value: result.load_forecast?.total_load ?? '-', precision: 0, suffix: 'MWh', color: CHART_COLORS[0] },
              { label: '综合成本', value: result.hourly_trading_plan.reduce((s, p) => s + (p.total_cost || 0), 0) || '-', precision: 0, suffix: '元', color: CHART_COLORS[1] },
              { label: '合约覆盖', value: ((result.plan_config?.contract_coverage_ratio ?? 0) * 100).toFixed(0), suffix: '%', color: CHART_COLORS[2] },
            ]}
          />
          <ChartCard title={`D-1 价格预测与置信区间（${dateStr}）`} option={priceOption} height={360} />
          <ChartCard title={`逐时交易计划（${dateStr}）`} option={planOption} height={360} />
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Card size="small" title="优先建议" style={{ marginBottom: 16 }}>
                {result.priority_recommendations?.length ? (
                  <Table size="small" rowKey={(_, i) => String(i)} columns={recColumns} dataSource={result.priority_recommendations} pagination={false} scroll={{ x: 'max-content' }} />
                ) : (
                  <Alert type="info" showIcon message="暂无优先建议" />
                )}
              </Card>
            </Col>
            <Col xs={24} md={12}>
              <Card size="small" title="风险预警" style={{ marginBottom: 16 }}>
                {result.risk_alerts?.length ? (
                  <Table size="small" rowKey={(_, i) => String(i)} columns={riskColumns} dataSource={result.risk_alerts} pagination={false} scroll={{ x: 'max-content' }} />
                ) : (
                  <Alert type="success" showIcon message="暂无风险预警" />
                )}
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  );
}
