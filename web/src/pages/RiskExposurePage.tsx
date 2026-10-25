import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Segmented, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import { getRiskExposure, type MonthlyExposure } from '@/api/risk';

export default function RiskExposurePage() {
  const q = useQuery({ queryKey: ['riskExposure'], queryFn: () => getRiskExposure() });
  const isLoading = q.isLoading;
  const data = q.data;

  const [view, setView] = useState<'price' | 'volume'>('price');

  const hours = data?.hours ?? [];
  const priceExposure = data?.priceExposureHourly ?? [];
  const volumeExposure = data?.volumeExposureHourly ?? [];
  const monthly = data?.monthly ?? [];
  const totalExposure = data?.totalExposure ?? 0;
  const totalPrice = data?.priceExposure ?? 0;
  const totalVolume = data?.volumeExposure ?? 0;
  const var95 = data?.var95 ?? 0;

  const hourlyOption: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: [view === 'price' ? '价格敞口' : '电量敞口'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: hours, boundaryGap: false, name: '时刻' },
    yAxis: { type: 'value', name: view === 'price' ? '价格敞口(万元)' : '电量敞口(万kWh)' },
    series: [
      {
        name: view === 'price' ? '价格敞口' : '电量敞口',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: view === 'price' ? priceExposure : volumeExposure,
        itemStyle: { color: CHART_COLORS[view === 'price' ? 2 : 0] },
        areaStyle: { opacity: 0.15 },
      },
    ],
  };

  const stackOption: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['合约敞口', '现货敞口'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: monthly.map((m) => m.month), boundaryGap: false },
    yAxis: { type: 'value', name: '敞口(万元)' },
    series: [
      { name: '合约敞口', type: 'line', stack: 'exp', smooth: true, showSymbol: false, data: monthly.map((m) => m.contract), areaStyle: { opacity: 0.4 }, itemStyle: { color: CHART_COLORS[0] } },
      { name: '现货敞口', type: 'line', stack: 'exp', smooth: true, showSymbol: false, data: monthly.map((m) => m.spot), areaStyle: { opacity: 0.4 }, itemStyle: { color: CHART_COLORS[2] } },
    ],
  };

  const monthlyBarOption: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['合约敞口', '现货敞口'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: monthly.map((m) => m.month) },
    yAxis: { type: 'value', name: '敞口(万元)' },
    series: [
      { name: '合约敞口', type: 'bar', data: monthly.map((m) => m.contract), itemStyle: { color: CHART_COLORS[0] } },
      { name: '现货敞口', type: 'bar', data: monthly.map((m) => m.spot), itemStyle: { color: CHART_COLORS[2] } },
    ],
  };

  const monthlyColumns: ColumnsType<MonthlyExposure> = [
    { title: '月份', dataIndex: 'month', width: 100 },
    { title: '合约敞口(万元)', dataIndex: 'contract', width: 160, render: (v: number) => v.toLocaleString() },
    { title: '现货敞口(万元)', dataIndex: 'spot', width: 160, render: (v: number) => v.toLocaleString() },
    {
      title: '合计(万元)',
      key: 'total',
      width: 140,
      render: (_, r) => <Tag color="blue">{(r.contract + r.spot).toLocaleString()}</Tag>,
    },
  ];

  const kpiItems = useMemo(
    () => [
      { label: '总敞口', value: totalExposure, precision: 0, suffix: '万元', color: CHART_COLORS[1] },
      { label: '价格风险敞口', value: totalPrice, precision: 0, suffix: '万元', color: CHART_COLORS[2] },
      { label: '电量风险敞口', value: totalVolume, precision: 0, suffix: '万元', color: CHART_COLORS[0] },
      { label: 'VaR(95%)', value: var95, precision: 0, suffix: '万元', color: CHART_COLORS[3] },
    ],
    [totalExposure, totalPrice, totalVolume, var95],
  );

  return (
    <div>
      <KpiCards loading={isLoading} items={kpiItems} />
      <Card size="small" style={{ marginBottom: 16 }}>
        <Segmented
          value={view}
          onChange={(v) => setView(v as 'price' | 'volume')}
          options={[
            { label: '价格敞口', value: 'price' },
            { label: '电量敞口', value: 'volume' },
          ]}
        />
      </Card>
      <ChartCard title="24小时逐时敞口" option={hourlyOption} loading={isLoading} height={360} />
      <ChartCard title="合约 vs 现货敞口（堆叠）" option={stackOption} loading={isLoading} height={360} />
      <ChartCard title="月度敞口对比" option={monthlyBarOption} loading={isLoading} height={320} />
      <Card size="small" title="月度敞口明细" style={{ marginBottom: 16 }}>
        <Table<MonthlyExposure> rowKey="month" columns={monthlyColumns} dataSource={monthly} pagination={false} size="small" />
      </Card>
    </div>
  );
}
