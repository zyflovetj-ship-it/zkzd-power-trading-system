import { useMemo, useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Alert, Button, Card, Col, DatePicker, Row, Space, Table, Tag, App } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import dayjs, { type Dayjs } from 'dayjs';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { CustomerSelect } from '@/components/CustomerSelect';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS, confidenceBand } from '@/components/charts/chartTheme';
import { generateD2Strategy, type D2StrategyResp, type D2RiskAlert } from '@/api/trading';

const severityColor: Record<string, string> = { high: 'error', medium: 'warning', low: 'info' };
const severityLabel: Record<string, string> = { high: '高', medium: '中', low: '低' };

export default function D2StrategyPage() {
  const { message } = App.useApp();
  const [customerId, setCustomerId] = useState('');
  const [date, setDate] = useState<Dayjs>(dayjs().add(2, 'day'));
  const [result, setResult] = useState<D2StrategyResp | null>(null);

  const dateStr = date.format('YYYY-MM-DD');

  const genMut = useMutation({
    mutationFn: () => generateD2Strategy({ customer_id: customerId, target_date: dateStr }),
    onSuccess: (d) => { setResult(d); message.success('D-2 策略已生成'); },
    onError: (e: any) => message.error(e?.response?.data?.detail || e?.message || '生成失败'),
  });

  const fc = result?.d2_forecast;
  const hp = fc?.hourly_prices ?? [];
  const loads = result?.load_forecast?.hourly_loads ?? [];
  const contract = result?.current_contract?.hourly_amounts ?? [];

  const priceOption: EChartsOption = useMemo(() => {
    const band = confidenceBand('区间', hp.map((p) => p.confidence_lower), hp.map((p) => p.confidence_upper), 'rgba(250,140,22,0.18)');
    return {
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: ['预测价格', '区间'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: hp.map((p) => p.time), name: '时刻', boundaryGap: false },
      yAxis: { type: 'value', name: '价格(元/MWh)', scale: true },
      series: [
        ...band,
        { name: '预测价格', type: 'line', smooth: true, showSymbol: false, data: hp.map((p) => p.predicted_price), itemStyle: { color: CHART_COLORS[2] }, z: 2 },
      ],
    };
  }, [hp]);

  const loadOption: EChartsOption = useMemo(
    () => ({
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: ['预测负荷', '当前合约电量'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: loads.map((p) => p.time), name: '时刻', boundaryGap: false },
      yAxis: { type: 'value', name: '电量(MWh)' },
      series: [
        { name: '预测负荷', type: 'line', smooth: true, showSymbol: false, data: loads.map((p) => p.predicted_load), itemStyle: { color: CHART_COLORS[0] } },
        { name: '当前合约电量', type: 'line', smooth: true, showSymbol: false, data: contract.map((p) => p.contract_amount), itemStyle: { color: CHART_COLORS[1] } },
      ],
    }),
    [loads, contract],
  );

  const riskColumns: ColumnsType<D2RiskAlert> = [
    { title: '类型', dataIndex: 'type', width: 140 },
    { title: '严重度', dataIndex: 'severity', width: 90, render: (s: string) => <Tag color={severityColor[s]}>{severityLabel[s] ?? s}</Tag> },
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
          <Col><Button type="primary" loading={genMut.isPending} disabled={!customerId} onClick={() => genMut.mutate()}>生成 D-2 策略</Button></Col>
        </Row>
      </Card>

      {!result && <Card><Alert type="info" showIcon message="请选择客户与目标日（默认 D-2）后生成策略" /></Card>}

      {result && (
        <>
          <KpiCards
            items={[
              { label: '预测均价', value: fc?.avg_price ?? '-', precision: 1, suffix: '元/MWh', color: CHART_COLORS[2] },
              { label: '价格区间', value: fc ? `${fc.price_range[0]}~${fc.price_range[1]}` : '-', color: CHART_COLORS[0] },
              { label: '预测总负荷', value: result.load_forecast?.total_load ?? '-', precision: 0, suffix: 'MWh', color: CHART_COLORS[1] },
              { label: '风险预警', value: result.risk_alerts?.length ?? 0, suffix: '条', color: (result.risk_alerts?.length ?? 0) > 0 ? CHART_COLORS[3] : CHART_COLORS[4] },
            ]}
          />
          <ChartCard title={`D-2 价格预测与置信区间（${dateStr}）`} option={priceOption} height={360} />
          <ChartCard title={`负荷预测 vs 当前合约（${dateStr}）`} option={loadOption} height={360} />
          <Card size="small" title="风险预警">
            {result.risk_alerts?.length ? (
              <Table size="small" rowKey={(_, i) => String(i)} columns={riskColumns} dataSource={result.risk_alerts} pagination={false} scroll={{ x: 'max-content' }} />
            ) : (
              <Alert type="success" showIcon message="暂无风险预警" />
            )}
          </Card>
        </>
      )}
    </div>
  );
}
