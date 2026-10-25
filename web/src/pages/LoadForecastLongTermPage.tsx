import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Card, Select, Space } from 'antd';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { getMediumLongLatest, getMediumLongByDate, getMediumLongList } from '@/api/loadForecast';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';

// 中长期负荷预测：选择预测批次，查看月度预测与置信区间。
export default function LoadForecastLongTermPage() {
  const [selected, setSelected] = useState<string>('latest');
  const listQ = useQuery({ queryKey: ['mlListPage'], queryFn: () => getMediumLongList() });
  const dataQ = useQuery({
    queryKey: ['mlDataPage', selected],
    queryFn: () => (selected === 'latest' ? getMediumLongLatest() : getMediumLongByDate(selected)),
  });

  const data = dataQ.data?.data ?? [];
  const options: { value: string; label: string }[] = [
    { value: 'latest', label: '最新预测' },
    ...(listQ.data ?? []).map((r) => ({
      value: r.forecast_date,
      label: `${r.forecast_date}（${r.forecast_horizon_months}月）`,
    })),
  ];

  const option: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['预测值', '置信区间'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: data.map((p) => p.month), name: '月份' },
    yAxis: { type: 'value', name: '负荷 (MW)' },
    series: [
      {
        name: '下限',
        type: 'line',
        data: data.map((p) => p.lower_bound),
        lineStyle: { opacity: 0 },
        stack: 'band',
        symbol: 'none',
        areaStyle: { opacity: 0 },
      },
      {
        name: '置信区间',
        type: 'line',
        data: data.map((p) => p.upper_bound - p.lower_bound),
        lineStyle: { opacity: 0 },
        stack: 'band',
        symbol: 'none',
        areaStyle: { color: 'rgba(9,88,217,0.12)' },
      },
      {
        name: '预测值',
        type: 'line',
        data: data.map((p) => p.forecast_value),
        itemStyle: { color: CHART_COLORS[0] },
        symbol: 'circle',
        symbolSize: 6,
      },
    ],
  };

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select
            value={selected}
            onChange={setSelected}
            options={options}
            style={{ width: 260 }}
            placeholder="选择预测批次"
            loading={listQ.isLoading}
          />
        </Space>
      </Card>

      <KpiCards
        loading={dataQ.isLoading}
        items={[
          { label: '预测月份数', value: data.length, color: CHART_COLORS[0] },
          { label: '预测跨度(月)', value: dataQ.data?.forecast_horizon_months ?? '-', color: CHART_COLORS[1] },
          { label: '首月预测值', value: data[0]?.forecast_value ?? '-', precision: 1, suffix: 'MW', color: CHART_COLORS[2] },
          { label: '末月预测值', value: data[data.length - 1]?.forecast_value ?? '-', precision: 1, suffix: 'MW', color: CHART_COLORS[3] },
        ]}
      />

      {dataQ.isError && <Alert type="error" showIcon message="加载中长期负荷预测失败" style={{ marginBottom: 16 }} />}
      <ChartCard title="中长期负荷预测（月度，含置信区间）" option={option} loading={dataQ.isLoading} height={400} />
    </div>
  );
}
