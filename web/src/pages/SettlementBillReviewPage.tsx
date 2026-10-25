import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Select, Space, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import { getSettlementBillReview, type BillStatus, type BillRow } from '@/api/settlement';

const STATUS_LABEL: Record<BillStatus, string> = { PENDING: '待复核', REVIEWED: '已复核', DIFFERENCE: '有差异' };
const STATUS_COLOR: Record<BillStatus, string> = { PENDING: 'default', REVIEWED: 'success', DIFFERENCE: 'error' };

export default function SettlementBillReviewPage() {
  const [statusFilter, setStatusFilter] = useState<BillStatus | 'ALL'>('ALL');

  const q = useQuery({
    queryKey: ['billReview', statusFilter],
    queryFn: () => getSettlementBillReview(statusFilter),
  });
  const isLoading = q.isLoading;
  const bills = q.data?.bills ?? [];

  const kpiItems = useMemo(
    () => [
      { label: '账单总数', value: bills.length, precision: 0, suffix: '笔', color: CHART_COLORS[0] },
      { label: '待复核', value: bills.filter((b) => b.status === 'PENDING').length, precision: 0, suffix: '笔', color: CHART_COLORS[3] },
      { label: '已复核', value: bills.filter((b) => b.status === 'REVIEWED').length, precision: 0, suffix: '笔', color: CHART_COLORS[1] },
      { label: '差异总额', value: bills.reduce((s, b) => s + b.diff, 0), precision: 0, suffix: '元', color: CHART_COLORS[2] },
    ],
    [bills],
  );

  const diffOption: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['平台金额', '系统金额'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: bills.map((b) => b.customer), axisLabel: { interval: 0, rotate: 25 }, name: '客户' },
    yAxis: { type: 'value', name: '金额(元)' },
    series: [
      { name: '平台金额', type: 'bar', data: bills.map((b) => b.platformAmount), itemStyle: { color: CHART_COLORS[0] } },
      { name: '系统金额', type: 'bar', data: bills.map((b) => b.systemAmount), itemStyle: { color: CHART_COLORS[1] } },
    ],
  };

  const columns: ColumnsType<BillRow> = [
    { title: '账单号', dataIndex: 'billNo', width: 160 },
    { title: '客户', dataIndex: 'customer', width: 130 },
    { title: '账期', dataIndex: 'period', width: 100 },
    { title: '平台金额(元)', dataIndex: 'platformAmount', width: 140, render: (v: number) => v.toLocaleString() },
    { title: '系统金额(元)', dataIndex: 'systemAmount', width: 140, render: (v: number) => (v === 0 ? '-' : v.toLocaleString()) },
    { title: '差异(元)', dataIndex: 'diff', width: 120, render: (v: number) => (v === 0 ? '-' : v.toLocaleString()) },
    { title: '状态', dataIndex: 'status', width: 110, render: (s: BillStatus) => <Tag color={STATUS_COLOR[s]}>{STATUS_LABEL[s]}</Tag> },
  ];

  return (
    <div>
      <KpiCards loading={isLoading} items={kpiItems} />
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <span>状态筛选：</span>
          <Select
            value={statusFilter}
            style={{ width: 160 }}
            onChange={(v) => setStatusFilter(v as BillStatus | 'ALL')}
            options={[
              { label: '全部', value: 'ALL' },
              { label: '待复核', value: 'PENDING' },
              { label: '已复核', value: 'REVIEWED' },
              { label: '有差异', value: 'DIFFERENCE' },
            ]}
          />
        </Space>
      </Card>
      <ChartCard title="平台 vs 系统金额对比" option={diffOption} loading={isLoading} height={360} />
      <Card size="small" title="平台账单复核明细" style={{ marginBottom: 16 }}>
        <Table<BillRow> rowKey="billNo" columns={columns} dataSource={bills} pagination={false} scroll={{ x: 'max-content' }} size="small" />
      </Card>
    </div>
  );
}
