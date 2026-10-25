import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Card, DatePicker, Select, Space } from 'antd';
import dayjs, { Dayjs } from 'dayjs';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { getDayAheadVersions, getDayAheadData, getDayAheadAccuracy } from '@/api/priceForecast';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';

// 日前价格预测：选目标日→版本，查看预测曲线（含置信带）、实际值（若有）与精度指标。
export default function PriceForecastDayAheadPage() {
  const [targetDate, setTargetDate] = useState<Dayjs>(dayjs().subtract(1, 'day'));
  const [forecastId, setForecastId] = useState<string>('');
  const tdStr = targetDate.format('YYYY-MM-DD');

  const versionsQ = useQuery({
    queryKey: ['daVers', tdStr],
    queryFn: () => getDayAheadVersions(tdStr),
  });
  useEffect(() => {
    if (versionsQ.data && versionsQ.data.length) {
      if (!forecastId || !versionsQ.data.find((v) => v.forecast_id === forecastId)) {
        setForecastId(versionsQ.data[0].forecast_id);
      }
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [versionsQ.data]);

  const dataQ = useQuery({
    queryKey: ['daData', forecastId, tdStr],
    enabled: !!forecastId,
    queryFn: () => getDayAheadData(forecastId, tdStr),
  });
  const accQ = useQuery({
    queryKey: ['daAcc', forecastId],
    enabled: !!forecastId,
    queryFn: () => getDayAheadAccuracy(forecastId),
  });

  const d = dataQ.data?.data ?? [];
  const hasActual = dataQ.data?.has_actual ?? false;
  const acc = accQ.data;

  const option: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['预测', '实际', '90%置信', '80%置信'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: d.map((p) => p.time), name: '时刻', boundaryGap: false },
    yAxis: { type: 'value', name: '价格(元/MWh)', scale: true },
    series: [
      {
        name: '90%下限',
        type: 'line',
        data: d.map((p) => p.confidence_90_lower),
        lineStyle: { opacity: 0 },
        stack: 'c90',
        symbol: 'none',
        areaStyle: { opacity: 0 },
      },
      {
        name: '90%置信',
        type: 'line',
        data: d.map((p) => p.confidence_90_upper - p.confidence_90_lower),
        lineStyle: { opacity: 0 },
        stack: 'c90',
        symbol: 'none',
        areaStyle: { color: 'rgba(9,88,217,0.08)' },
      },
      {
        name: '80%下限',
        type: 'line',
        data: d.map((p) => p.confidence_80_lower),
        lineStyle: { opacity: 0 },
        stack: 'c80',
        symbol: 'none',
        areaStyle: { opacity: 0 },
      },
      {
        name: '80%置信',
        type: 'line',
        data: d.map((p) => p.confidence_80_upper - p.confidence_80_lower),
        lineStyle: { opacity: 0 },
        stack: 'c80',
        symbol: 'none',
        areaStyle: { color: 'rgba(19,194,194,0.14)' },
      },
      {
        name: '预测',
        type: 'line',
        data: d.map((p) => p.predicted),
        symbol: 'circle',
        symbolSize: 5,
        itemStyle: { color: CHART_COLORS[0] },
        z: 3,
      },
      {
        name: '实际',
        type: 'line',
        connectNulls: false,
        data: d.map((p) => (p.actual != null ? p.actual : null)),
        itemStyle: { color: CHART_COLORS[2] },
        z: 2,
      },
    ],
  };

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <DatePicker value={targetDate} onChange={(d) => d && setTargetDate(d)} allowClear={false} />
          <Select
            value={forecastId || undefined}
            onChange={setForecastId}
            placeholder="预测版本"
            loading={versionsQ.isLoading}
            options={(versionsQ.data ?? []).map((v) => ({
              value: v.forecast_id,
              label: `${v.model_type} · ${v.model_version} · ${v.created_at.slice(0, 10)}`,
            }))}
            style={{ width: 300 }}
          />
        </Space>
      </Card>

      <KpiCards
        loading={accQ.isLoading}
        items={[
          { label: 'WMAPE精度', value: acc?.wmape_accuracy ?? '-', precision: 2, suffix: '%', color: CHART_COLORS[0] },
          { label: 'MAE', value: acc?.mae ?? '-', precision: 2, color: CHART_COLORS[1] },
          { label: 'RMSE', value: acc?.rmse ?? '-', precision: 2, color: CHART_COLORS[2] },
          { label: 'MAPE', value: acc?.mape ?? '-', precision: 2, suffix: '%', color: CHART_COLORS[3] },
          { label: '方向精度', value: acc?.direction_accuracy ?? '-', precision: 2, suffix: '%', color: CHART_COLORS[4] },
          { label: 'R²', value: acc?.r2_score ?? '-', precision: 3, color: CHART_COLORS[5] },
        ]}
      />

      {versionsQ.isError && <Alert type="error" showIcon message="加载日前预测版本失败" style={{ marginBottom: 16 }} />}
      {dataQ.isError && <Alert type="error" showIcon message="加载日前预测数据失败（该目标日可能无预测）" style={{ marginBottom: 16 }} />}
      <ChartCard
        title={`日前价格预测（${tdStr}${hasActual ? ' · 含实际值' : ' · 暂无实际值'}）`}
        option={option}
        loading={dataQ.isLoading}
        height={420}
      />
    </div>
  );
}
