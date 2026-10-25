import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import { getRiskPositionContracts, type PositionContract } from '@/api/risk';

function daysToEnd(end: string): number {
  const diff = new Date(end).getTime() - Date.now();
  return Math.ceil(diff / (1000 * 3600 * 24));
}

export default function RiskPositionContractsPage() {
  const q = useQuery({ queryKey: ['riskPositionContracts'], queryFn: () => getRiskPositionContracts() });
  const isLoading = q.isLoading;
  const contracts = q.data?.contracts ?? [];

  const expiringSoon = contracts.filter((c) => {
    const d = daysToEnd(c.endDate);
    return d <= 30 && d >= 0;
  }).length;

  const kpiItems = useMemo(
    () => [
      {
        label: '持仓总量',
        value: contracts.reduce((s, c) => s + c.volume, 0),
        precision: 0,
        suffix: 'MWh',
        color: CHART_COLORS[0],
      },
      { label: '合约数', value: contracts.length, precision: 0, suffix: '个', color: CHART_COLORS[1] },
      {
        label: '加权均价',
        value: contracts.length
          ? contracts.reduce((s, c) => s + c.avgPrice * c.volume, 0) / contracts.reduce((s, c) => s + c.volume, 0)
          : 0,
        precision: 1,
        suffix: '元/MWh',
        color: CHART_COLORS[2],
      },
      { label: '30天内到期数', value: expiringSoon, precision: 0, suffix: '个', color: CHART_COLORS[3] },
    ],
    [contracts, expiringSoon],
  );

  const coverageOption: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['合约覆盖率'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: contracts.map((c) => c.customer), name: '客户', axisLabel: { interval: 0, rotate: 20 } },
    yAxis: { type: 'value', name: '覆盖率(%)', max: 100 },
    series: [{ name: '合约覆盖率', type: 'bar', data: contracts.map((c) => c.coverage), itemStyle: { color: CHART_COLORS[0] } }],
  };

  const volumeOption: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['持仓电量'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: contracts.map((c) => c.customer), name: '客户', axisLabel: { interval: 0, rotate: 20 } },
    yAxis: { type: 'value', name: '持仓电量(MWh)' },
    series: [{ name: '持仓电量', type: 'bar', data: contracts.map((c) => c.volume), itemStyle: { color: CHART_COLORS[2] } }],
  };

  const columns: ColumnsType<PositionContract> = [
    { title: '客户名称', dataIndex: 'customer', width: 140 },
    { title: '合约编号', dataIndex: 'contractNo', width: 150 },
    { title: '持仓电量(MWh)', dataIndex: 'volume', width: 130, render: (v: number) => v.toLocaleString() },
    { title: '加权均价(元/MWh)', dataIndex: 'avgPrice', width: 150, render: (v: number) => v.toFixed(1) },
    { title: '起始日', dataIndex: 'startDate', width: 120 },
    {
      title: '到期日',
      dataIndex: 'endDate',
      width: 140,
      render: (v: string) => {
        const d = daysToEnd(v);
        if (d < 0) return <Tag color="default">{v}</Tag>;
        if (d <= 30) return <Tag color="error">{v}（剩{d}天）</Tag>;
        if (d <= 90) return <Tag color="warning">{v}（剩{d}天）</Tag>;
        return <Tag color="success">{v}</Tag>;
      },
    },
    {
      title: '覆盖率(%)',
      dataIndex: 'coverage',
      width: 110,
      render: (v: number) =>
        v >= 80 ? <Tag color="success">{v}%</Tag> : v >= 60 ? <Tag color="warning">{v}%</Tag> : <Tag color="error">{v}%</Tag>,
    },
  ];

  return (
    <div>
      <KpiCards loading={isLoading} items={kpiItems} />
      <ChartCard title="各客户合约覆盖率" option={coverageOption} loading={isLoading} height={360} />
      <ChartCard title="各客户持仓电量" option={volumeOption} loading={isLoading} height={360} />
      <Card size="small" title="持仓合约明细" style={{ marginBottom: 16 }}>
        <Table<PositionContract>
          rowKey="contractNo"
          columns={columns}
          dataSource={contracts}
          pagination={false}
          scroll={{ x: 'max-content' }}
          size="small"
        />
      </Card>
    </div>
  );
}
