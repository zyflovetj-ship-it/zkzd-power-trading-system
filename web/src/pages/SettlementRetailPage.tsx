import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import { getSettlementRetail, type RetailRow, type PayStatus } from '@/api/settlement';

const PAY_LABEL: Record<PayStatus, string> = { PAID: '已缴', UNPAID: '未缴', PARTIAL: '部分缴' };
const PAY_COLOR: Record<PayStatus, string> = { PAID: 'success', UNPAID: 'error', PARTIAL: 'warning' };

export default function SettlementRetailPage() {
  const q = useQuery({ queryKey: ['settlementRetail'], queryFn: () => getSettlementRetail() });
  const isLoading = q.isLoading;
  const rows = q.data?.rows ?? [];

  const kpiItems = useMemo(
    () => [
      { label: '零售结算总额', value: rows.reduce((s, r) => s + r.amount, 0), precision: 0, suffix: '元', color: CHART_COLORS[0] },
      { label: '结算用户数', value: rows.length, precision: 0, suffix: '户', color: CHART_COLORS[1] },
      {
        label: '平均零售电价',
        value: rows.length ? rows.reduce((s, r) => s + r.amount, 0) / rows.reduce((s, r) => s + r.usage, 0) : 0,
        precision: 1,
        suffix: '元/MWh',
        color: CHART_COLORS[2],
      },
      { label: '应收未收', value: rows.filter((r) => r.payStatus !== 'PAID').reduce((s, r) => s + r.amount, 0), precision: 0, suffix: '元', color: CHART_COLORS[3] },
    ],
    [rows],
  );

  const topOption: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['结算金额'] },
    grid: baseGrid,
    xAxis: { type: 'value', name: '结算金额(元)' },
    yAxis: { type: 'category', data: [...rows].sort((a, b) => a.amount - b.amount).map((r) => r.customer), name: '客户' },
    series: [{ name: '结算金额', type: 'bar', data: [...rows].sort((a, b) => a.amount - b.amount).map((r) => r.amount), itemStyle: { color: CHART_COLORS[0] } }],
  };

  const columns: ColumnsType<RetailRow> = [
    { title: '客户', dataIndex: 'customer', width: 130 },
    { title: '合约', dataIndex: 'contract', width: 140 },
    { title: '用电量(MWh)', dataIndex: 'usage', width: 120, render: (v: number) => v.toLocaleString() },
    { title: '零售电价(元/MWh)', dataIndex: 'price', width: 150, render: (v: number) => v.toFixed(1) },
    { title: '结算金额(元)', dataIndex: 'amount', width: 140, render: (v: number) => v.toLocaleString() },
    { title: '缴费状态', dataIndex: 'payStatus', width: 110, render: (s: PayStatus) => <Tag color={PAY_COLOR[s]}>{PAY_LABEL[s]}</Tag> },
  ];

  return (
    <div>
      <KpiCards loading={isLoading} items={kpiItems} />
      <ChartCard title="各客户结算金额 Top" option={topOption} loading={isLoading} height={360} />
      <Card size="small" title="零售用户结算明细" style={{ marginBottom: 16 }}>
        <Table<RetailRow> rowKey="contract" columns={columns} dataSource={rows} pagination={false} scroll={{ x: 'max-content' }} size="small" />
      </Card>
    </div>
  );
}
