import { useMemo, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Alert, Button, Card, Col, DatePicker, InputNumber, Row, Select, Space, Table, App } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import dayjs, { type Dayjs } from 'dayjs';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { CustomerSelect } from '@/components/CustomerSelect';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS, confidenceBand } from '@/components/charts/chartTheme';
import {
  generateMonthlyStrategy,
  getMonthlyPriceTrend,
  type MonthlyStrategyResp,
  type MonthlyPriceTrendResp,
} from '@/api/trading';

const OBJECTIVE_OPTS = [
  { label: '成本优先', value: 'cost' },
  { label: '风险优先', value: 'risk' },
  { label: '均衡', value: 'balanced' },
];

export default function MonthlyStrategyPage() {
  const { message } = App.useApp();
  const [customerId, setCustomerId] = useState('');
  const [month, setMonth] = useState<Dayjs>(dayjs().date(1));
  const [annualRatio, setAnnualRatio] = useState<number>(0.5);
  const [monthlyRatio, setMonthlyRatio] = useState<number>(0.3);
  const [spotRatio, setSpotRatio] = useState<number>(0.2);
  const [objective, setObjective] = useState<'cost' | 'risk' | 'balanced'>('balanced');
  const [result, setResult] = useState<MonthlyStrategyResp | null>(null);

  const ym = month.format('YYYY-MM');
  const year = month.year();
  const m = month.month() + 1;

  const trendQ = useQuery({
    queryKey: ['monthlyPriceTrend', ym],
    queryFn: () => getMonthlyPriceTrend(year, m),
    enabled: !!result,
  });

  const genMut = useMutation({
    mutationFn: () =>
      generateMonthlyStrategy({
        customer_id: customerId,
        target_year: year,
        target_month: m,
        annual_contract_ratio: annualRatio,
        monthly_bid_ratio: monthlyRatio,
        spot_ratio: spotRatio,
        optimization_objective: objective,
      }),
    onSuccess: (d) => { setResult(d); message.success('月度策略已生成'); },
    onError: (e: any) => message.error(e?.response?.data?.detail || e?.message || '生成失败'),
  });

  const r = result?.optimization_results;
  const rm = result?.optimization_results?.risk_metrics;
  const trend = trendQ.data as MonthlyPriceTrendResp | undefined;
  const daily = trend?.daily_prices ?? [];

  const mixOption: EChartsOption = useMemo(() => {
    const mix = r?.trading_mix;
    return {
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: ['年度合约', '月内竞价', '现货'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: ['电量(MWh)', '占比', '均价(元/MWh)', '成本(元)'] },
      yAxis: { type: 'value' },
      series: [
        { name: '年度合约', type: 'bar', data: [mix?.annual_contract.amount, mix?.annual_contract.ratio, mix?.annual_contract.avg_price, mix?.annual_contract.total_cost], itemStyle: { color: CHART_COLORS[0] } },
        { name: '月内竞价', type: 'bar', data: [mix?.monthly_bid.amount, mix?.monthly_bid.ratio, mix?.monthly_bid.avg_price, mix?.monthly_bid.total_cost], itemStyle: { color: CHART_COLORS[1] } },
        { name: '现货', type: 'bar', data: [mix?.spot.amount, mix?.spot.ratio, mix?.spot.avg_price, mix?.spot.total_cost], itemStyle: { color: CHART_COLORS[2] } },
      ],
    };
  }, [r]);

  const trendOption: EChartsOption = useMemo(() => {
    const band = confidenceBand('区间', daily.map((d) => d.confidence_lower), daily.map((d) => d.confidence_upper), 'rgba(9,88,217,0.15)');
    return {
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: ['预测价格', '区间'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: daily.map((d) => d.date.slice(5)), name: '日', boundaryGap: false },
      yAxis: { type: 'value', name: '价格(元/MWh)', scale: true },
      series: [
        ...band,
        { name: '预测价格', type: 'line', smooth: true, showSymbol: false, data: daily.map((d) => d.predicted_price), itemStyle: { color: CHART_COLORS[0] }, z: 2 },
      ],
    };
  }, [daily]);

  const timingColumns: ColumnsType<MonthlyStrategyResp['timing_recommendations'][number]> = [
    { title: '日期', dataIndex: 'date', width: 120 },
    { title: '类型', dataIndex: 'type', width: 120 },
    { title: '建议电量', dataIndex: 'recommended_amount', width: 120, render: (v: number) => `${v} MWh` },
    { title: '建议价格区间', width: 200, render: (_, r) => `${r.recommended_price_range[0]} ~ ${r.recommended_price_range[1]} 元/MWh` },
    { title: '理由', dataIndex: 'reasoning' },
  ];

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle" wrap>
          <Col><CustomerSelect value={customerId} onChange={(v) => { setCustomerId(v); setResult(null); }} /></Col>
          <Col><DatePicker picker="month" value={month} onChange={(d) => d && setMonth(d)} allowClear={false} /></Col>
          <Col><Select value={objective} onChange={setObjective} options={OBJECTIVE_OPTS} style={{ width: 140 }} /></Col>
          <Col><Space size={4}><span>年合约</span><InputNumber min={0} max={1} step={0.05} value={annualRatio} onChange={(v) => setAnnualRatio(v ?? 0.5)} style={{ width: 80 }} /></Space></Col>
          <Col><Space size={4}><span>月竞价</span><InputNumber min={0} max={1} step={0.05} value={monthlyRatio} onChange={(v) => setMonthlyRatio(v ?? 0.3)} style={{ width: 80 }} /></Space></Col>
          <Col><Space size={4}><span>现货</span><InputNumber min={0} max={1} step={0.05} value={spotRatio} onChange={(v) => setSpotRatio(v ?? 0.2)} style={{ width: 80 }} /></Space></Col>
          <Col><Button type="primary" loading={genMut.isPending} disabled={!customerId} onClick={() => genMut.mutate()}>生成月度策略</Button></Col>
        </Row>
      </Card>

      {!result && <Card><Alert type="info" showIcon message="请选择客户与月份后生成月度交易策略" /></Card>}

      {result && (
        <>
          <KpiCards
            items={[
              { label: '综合成本', value: r?.total_cost ?? '-', precision: 0, suffix: '元', color: CHART_COLORS[0] },
              { label: '度电成本', value: r?.blended_cost ?? '-', precision: 2, suffix: '元/MWh', color: CHART_COLORS[1] },
              { label: '总电量', value: r?.total_demand ?? '-', precision: 0, suffix: 'MWh', color: CHART_COLORS[2] },
              { label: '较纯现货节省', value: ((result.optimization_results.vs_pure_spot?.savings_percentage ?? 0) * 100).toFixed(1), suffix: '%', color: CHART_COLORS[3] },
              { label: 'VaR(95%)', value: rm?.value_at_risk_95 ?? '-', precision: 0, color: CHART_COLORS[4] },
              { label: '灵活度', value: rm?.flexibility_score ?? '-', precision: 2, color: CHART_COLORS[5] },
            ]}
          />
          <ChartCard title={`交易组合结构（${result.customer_name} · ${ym}）`} option={mixOption} height={340} />
          <ChartCard title={`月度价格趋势与置信区间（${ym}）`} option={trendOption} loading={trendQ.isLoading} height={340} />
          <Card size="small" title="择时建议" style={{ marginBottom: 16 }}>
            <Table size="small" rowKey={(_, i) => String(i)} columns={timingColumns} dataSource={result.timing_recommendations} pagination={false} scroll={{ x: 'max-content' }} />
          </Card>
        </>
      )}
    </div>
  );
}
