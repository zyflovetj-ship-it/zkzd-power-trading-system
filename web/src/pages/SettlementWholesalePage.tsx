import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Table } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import { getSettlementWholesale, type WholesaleRow } from '@/api/settlement';

export default function SettlementWholesalePage() {
  const q = useQuery({ queryKey: ['settlementWholesale'], queryFn: () => getSettlementWholesale() });
  const isLoading = q.isLoading;
  const rows = q.data?.rows ?? [];

  const kpiItems = useMemo(
    () => [
      { label: '结算电量', value: rows.reduce((s, r) => s + r.volume, 0), precision: 0, suffix: 'MWh', color: CHART_COLORS[0] },
      { label: '结算金额', value: rows.reduce((s, r) => s + r.amount, 0), precision: 0, suffix: '元', color: CHART_COLORS[1] },
      { label: '偏差电费', value: rows.reduce((s, r) => s + r.devFee, 0), precision: 0, suffix: '元', color: CHART_COLORS[2] },
      {
        label: '综合电价',
        value: rows.length ? rows.reduce((s, r) => s + r.amount, 0) / rows.reduce((s, r) => s + r.volume, 0) : 0,
        precision: 1,
        suffix: '元/MWh',
        color: CHART_COLORS[3],
      },
    ],
    [rows],
  );

  const amountOption: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['结算金额'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: rows.map((r) => `${r.unit}\n${r.period}`), axisLabel: { interval: 0, rotate: 25 }, name: '结算单元' },
    yAxis: { type: 'value', name: '结算金额(元)' },
    series: [{ name: '结算金额', type: 'bar', data: rows.map((r) => r.amount), itemStyle: { color: CHART_COLORS[1] } }],
  };

  const columns: ColumnsType<WholesaleRow> = [
    { title: '结算单元', dataIndex: 'unit', width: 130 },
    { title: '结算周期', dataIndex: 'period', width: 110 },
    { title: '电量(MWh)', dataIndex: 'volume', width: 120, render: (v: number) => v.toLocaleString() },
    { title: '单价(元/MWh)', dataIndex: 'price', width: 130, render: (v: number) => v.toFixed(1) },
    { title: '金额(元)', dataIndex: 'amount', width: 140, render: (v: number) => v.toLocaleString() },
    { title: '偏差电量', dataIndex: 'devVolume', width: 110, render: (v: number) => (v > 0 ? `+${v}` : v) },
    { title: '偏差电费(元)', dataIndex: 'devFee', width: 130, render: (v: number) => (v >= 0 ? `+${v.toLocaleString()}` : v.toLocaleString()) },
  ];

  return (
    <div>
      <KpiCards loading={isLoading} items={kpiItems} />
      <ChartCard title="各结算单元结算金额" option={amountOption} loading={isLoading} height={360} />
      <Card size="small" title="批发侧预结算明细" style={{ marginBottom: 16 }}>
        <Table<WholesaleRow>
          rowKey={(r) => `${r.unit}-${r.period}`}
          columns={columns}
          dataSource={rows}
          pagination={false}
          scroll={{ x: 'max-content' }}
          size="small"
        />
      </Card>
    </div>
  );
}
