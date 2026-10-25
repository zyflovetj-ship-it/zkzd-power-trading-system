import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import { getLoadValidation, type CheckStatus, type ValidationRecord } from '@/api/loadValidation';

const STATUS_META: Record<CheckStatus, { label: string; color: string }> = {
  pass: { label: '通过', color: 'success' },
  error: { label: '异常', color: 'error' },
  missing: { label: '缺失', color: 'warning' },
};

export default function LoadValidationPage() {
  const q = useQuery({ queryKey: ['loadValidation'], queryFn: () => getLoadValidation() });
  const isLoading = q.isLoading;
  const records = q.data?.records ?? [];

  const total = records.length;
  const errorCount = records.filter((r) => r.status === 'error').length;
  const missingCount = records.filter((r) => r.status === 'missing').length;
  const passRate = total ? (((total - errorCount - missingCount) / total) * 100).toFixed(1) : '0.0';

  const anomalyTypeCounts = useMemo(() => {
    const map: Record<string, number> = { 缺失: 0, 越界: 0, 跳变: 0, 重复: 0 };
    records.forEach((r) => {
      if (r.status === 'missing') map['缺失'] += 1;
      else if (r.status === 'error') {
        if (r.problem.includes('缺失')) map['缺失'] += 1;
        else if (r.problem.includes('越界')) map['越界'] += 1;
        else if (r.problem.includes('跳变')) map['跳变'] += 1;
        else if (r.problem.includes('重复')) map['重复'] += 1;
      }
    });
    return map;
  }, [records]);

  const anomalyLabels = Object.keys(anomalyTypeCounts);

  const barOption: EChartsOption = useMemo(
    () => ({
      color: CHART_COLORS,
      tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
      legend: { ...baseLegend, data: ['异常条数'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: anomalyLabels, name: '异常类型' },
      yAxis: { type: 'value', name: '条数', minInterval: 1 },
      series: [
        {
          name: '异常条数',
          type: 'bar',
          data: anomalyLabels.map((k) => anomalyTypeCounts[k]),
          itemStyle: { color: CHART_COLORS[2] },
        },
      ],
    }),
    [anomalyTypeCounts],
  );

  const columns: ColumnsType<ValidationRecord> = [
    { title: '日期', dataIndex: 'date', width: 120 },
    { title: '客户', dataIndex: 'customer', width: 140 },
    { title: '指标', dataIndex: 'metric', width: 90, render: (v: string) => <Tag>{v}</Tag> },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (s: CheckStatus) => <Tag color={STATUS_META[s].color}>{STATUS_META[s].label}</Tag>,
    },
    { title: '问题描述', dataIndex: 'problem', width: 240 },
    { title: '检测值', dataIndex: 'detectValue', width: 110 },
  ];

  return (
    <div>
      <KpiCards
        loading={isLoading}
        items={[
          { label: '校验总条数', value: total, suffix: '条', color: CHART_COLORS[0] },
          { label: '异常条数', value: errorCount, suffix: '条', color: CHART_COLORS[2] },
          { label: '缺失条数', value: missingCount, suffix: '条', color: CHART_COLORS[3] },
          { label: '通过率', value: passRate, precision: 1, suffix: '%', color: CHART_COLORS[1] },
        ]}
      />

      <ChartCard title="异常类型分布" option={barOption} loading={isLoading} height={340} />

      <Card size="small" title="校验记录明细" style={{ marginBottom: 16 }}>
        <Table<ValidationRecord>
          rowKey={(_, i) => String(i)}
          columns={columns}
          dataSource={records}
          pagination={false}
          scroll={{ x: 'max-content' }}
          size="small"
        />
      </Card>
    </div>
  );
}
