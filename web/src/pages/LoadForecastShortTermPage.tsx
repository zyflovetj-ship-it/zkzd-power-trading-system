import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Card, DatePicker, Select, Space } from 'antd';
import dayjs, { Dayjs } from 'dayjs';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { getShortTermCurve, getShortTermAccuracy } from '@/api/loadForecast';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';

const TYPES = [
  { value: 'd+1', label: 'D+1（次日）' },
  { value: 'd+2', label: 'D+2' },
  { value: 'd+3', label: 'D+3' },
];

// 短期负荷预测：选预测日期与预测类型，查看 96 点预测/实际曲线与精度指标。
export default function LoadForecastShortTermPage() {
  const [date, setDate] = useState<Dayjs>(dayjs());
  const [type, setType] = useState<string>('d+1');
  const dateStr = date.format('YYYY-MM-DD');

  const curveQ = useQuery({
    queryKey: ['shortTermCurve', dateStr, type],
    queryFn: () => getShortTermCurve(dateStr, type),
  });
  const accQ = useQuery({
    queryKey: ['shortTermAcc', dateStr, type],
    queryFn: () => getShortTermAccuracy(dateStr, type),
  });

  const data = (curveQ.data?.data ?? []).filter((p) => p.forecast_value != null);
  const hasActual = data.some((p) => p.actual_value != null);

  const option: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['预测负荷', '实际负荷'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: data.map((p) => p.time), name: '时刻', boundaryGap: false },
    yAxis: { type: 'value', name: '负荷 (MW)' },
    series: [
      {
        name: '预测负荷',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: data.map((p) => p.forecast_value),
        itemStyle: { color: CHART_COLORS[0] },
      },
      {
        name: '实际负荷',
        type: 'line',
        smooth: true,
        showSymbol: false,
        connectNulls: false,
        data: data.map((p) => (p.actual_value != null ? p.actual_value : null)),
        itemStyle: { color: CHART_COLORS[2] },
      },
    ],
  };

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <DatePicker value={date} onChange={(d) => d && setDate(d)} allowClear={false} placeholder="预测生成日期" />
          <Select value={type} onChange={setType} options={TYPES} style={{ width: 160 }} />
        </Space>
      </Card>

      {accQ.data && (
        <KpiCards
          loading={accQ.isLoading}
          items={[
            { label: 'MAE', value: accQ.data.mae, precision: 2, suffix: 'MW', color: CHART_COLORS[0] },
            { label: 'MAPE', value: accQ.data.mape, precision: 2, suffix: '%', color: CHART_COLORS[1] },
            { label: 'RMSE', value: accQ.data.rmse, precision: 2, suffix: 'MW', color: CHART_COLORS[2] },
            { label: '最大误差', value: accQ.data.max_error, precision: 2, suffix: 'MW', color: CHART_COLORS[3] },
            { label: '最大误差时刻', value: accQ.data.max_error_time || '-' },
          ]}
        />
      )}

      {curveQ.isError && <Alert type="error" showIcon message="加载短期负荷预测失败（该日期可能无预测数据）" style={{ marginBottom: 16 }} />}

      <ChartCard
        title={`短期负荷预测曲线（${dateStr} / ${type}）${hasActual ? '' : ' · 暂无实际值'}`}
        option={option}
        loading={curveQ.isLoading}
        height={400}
      />
    </div>
  );
}
