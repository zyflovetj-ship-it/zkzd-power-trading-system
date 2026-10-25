import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import { getSettlementProfit, type ProfitRow } from '@/api/settlement';

export default function SettlementProfitPage() {
  const q = useQuery({ queryKey: ['settlementProfit'], queryFn: () => getSettlementProfit() });
  const isLoading = q.isLoading;
  const rows = q.data?.rows ?? [];
  const revenueComposition = q.data?.revenueComposition ?? [];

  const kpiItems = useMemo(
    () => [
      { label: '总收入', value: rows.reduce((s, r) => s + r.revenue, 0), precision: 0, suffix: '元', color: CHART_COLORS[0] },
      { label: '总成本', value: rows.reduce((s, r) => s + r.cost, 0), precision: 0, suffix: '元', color: CHART_COLORS[1] },
      { label: '毛利', value: rows.reduce((s, r) => s + r.gross, 0), precision: 0, suffix: '元', color: CHART_COLORS[2] },
      {
        label: '毛利率',
        value: rows.length ? (rows.reduce((s, r) => s + r.gross, 0) / rows.reduce((s, r) => s + r.revenue, 0)) * 100 : 0,
        precision: 1,
        suffix: '%',
        color: CHART_COLORS[3],
      },
    ],
    [rows],
  );

  const trendOption: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['毛利'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: rows.map((r) => r.month), boundaryGap: false, name: '月份' },
    yAxis: { type: 'value', name: '毛利(元)' },
    series: [{ name: '毛利', type: 'line', smooth: true, showSymbol: false, data: rows.map((r) => r.gross), itemStyle: { color: CHART_COLORS[2] }, areaStyle: { opacity: 0.15 } }],
  };

  const pieOption: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { trigger: 'item', formatter: '{b}: {c}元 ({d}%)' },
    legend: { ...baseLegend, data: revenueComposition.map((c) => c.name) },
    series: [
      {
        name: '收入构成',
        type: 'pie',
        radius: ['40%', '68%'],
        center: ['50%', '56%'],
        data: revenueComposition.map((c) => ({ name: c.name, value: c.value })),
      },
    ],
  };

  const columns: ColumnsType<ProfitRow> = [
    { title: '月份', dataIndex: 'month', width: 110 },
    { title: '收入(元)', dataIndex: 'revenue', width: 140, render: (v: number) => v.toLocaleString() },
    { title: '成本(元)', dataIndex: 'cost', width: 140, render: (v: number) => v.toLocaleString() },
    { title: '毛利(元)', dataIndex: 'gross', width: 140, render: (v: number) => v.toLocaleString() },
    { title: '毛利率(%)', dataIndex: 'margin', width: 110, render: (v: number) => <Tag color="blue">{v.toFixed(1)}%</Tag> },
  ];

  return (
    <div>
      <KpiCards loading={isLoading} items={kpiItems} />
      <ChartCard title="近 12 个月毛利趋势" option={trendOption} loading={isLoading} height={360} />
      <ChartCard title="收入构成" option={pieOption} loading={isLoading} height={360} />
      <Card size="small" title="月度利润表" style={{ marginBottom: 16 }}>
        <Table<ProfitRow> rowKey="month" columns={columns} dataSource={rows} pagination={false} size="small" />
      </Card>
    </div>
  );
}
