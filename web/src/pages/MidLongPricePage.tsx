import { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Card, Select, Segmented, Space } from 'antd';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { getMonthlyForecastVersions, getMonthlyForecastData, getMonthlyForecastAccuracy } from '@/api/market';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';

type ChartType = 'mean_trend' | 'price_spread' | 'peak_valley';

const YEAR_OPTS = Array.from({ length: 11 }, (_, i) => ({ value: 2020 + i, label: String(2020 + i) }));
const MONTH_OPTS = Array.from({ length: 12 }, (_, i) => ({ value: i + 1, label: `${i + 1}月` }));

// 中长期价格分析：按月度预测版本查看价格预测（均值趋势/价差/峰谷）+ 预测精度。
export default function MidLongPricePage() {
  const [year, setYear] = useState<number>(2025);
  const [month, setMonth] = useState<number>(6);
  const [chartType, setChartType] = useState<ChartType>('mean_trend');
  const [forecastId, setForecastId] = useState<string>('');

  const versionsQ = useQuery({
    queryKey: ['mfVers', year, month],
    queryFn: () => getMonthlyForecastVersions(year, month),
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
    queryKey: ['mfData', forecastId, chartType],
    enabled: !!forecastId,
    queryFn: () => getMonthlyForecastData(forecastId, chartType),
  });
  const accQ = useQuery({
    queryKey: ['mfAcc', forecastId],
    enabled: !!forecastId,
    queryFn: () => getMonthlyForecastAccuracy(forecastId),
  });

  const d = dataQ.data?.data ?? [];
  const hasActual = d.some((p) => p.actual_mean != null);

  let option: EChartsOption = {};
  if (chartType === 'mean_trend') {
    option = {
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: ['预测均值', '实际均值', '置信区间'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: d.map((p) => p.date), name: '日期', boundaryGap: false },
      yAxis: { type: 'value', name: '价格(元/MWh)' },
      series: [
        { name: '下限', type: 'line', data: d.map((p) => p.confidence_90_lower), lineStyle: { opacity: 0 }, stack: 'band', symbol: 'none', areaStyle: { opacity: 0 } },
        { name: '置信区间', type: 'line', data: d.map((p) => p.confidence_90_upper - p.confidence_90_lower), lineStyle: { opacity: 0 }, stack: 'band', symbol: 'none', areaStyle: { color: 'rgba(9,88,217,0.12)' } },
        { name: '预测均值', type: 'line', data: d.map((p) => p.price_mean), itemStyle: { color: CHART_COLORS[0] }, symbol: 'circle', symbolSize: 5 },
        { name: '实际均值', type: 'line', connectNulls: false, data: d.map((p) => (p.actual_mean != null ? p.actual_mean : null)), itemStyle: { color: CHART_COLORS[2] } },
      ],
    };
  } else if (chartType === 'price_spread') {
    option = {
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: ['预测价差', '实际价差'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: d.map((p) => p.date), boundaryGap: false },
      yAxis: { type: 'value', name: '价差(元/MWh)' },
      series: [
        { name: '预测价差', type: 'line', smooth: true, showSymbol: false, data: d.map((p) => p.price_spread), itemStyle: { color: CHART_COLORS[0] } },
        { name: '实际价差', type: 'line', connectNulls: false, data: d.map((p) => (p.actual_spread != null ? p.actual_spread : null)), itemStyle: { color: CHART_COLORS[2] } },
      ],
    };
  } else {
    option = {
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: ['峰值', '谷值'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: d.map((p) => p.date), boundaryGap: false },
      yAxis: { type: 'value', name: '价格(元/MWh)' },
      series: [
        { name: '峰值', type: 'line', showSymbol: false, data: d.map((p) => p.price_peak), itemStyle: { color: CHART_COLORS[3] } },
        { name: '谷值', type: 'line', showSymbol: false, data: d.map((p) => p.price_valley), itemStyle: { color: CHART_COLORS[1] } },
      ],
    };
  }

  const acc = accQ.data;

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Select value={year} onChange={setYear} options={YEAR_OPTS} style={{ width: 110 }} />
          <Select value={month} onChange={setMonth} options={MONTH_OPTS} style={{ width: 100 }} />
          <Select
            value={forecastId || undefined}
            onChange={setForecastId}
            placeholder="预测版本"
            loading={versionsQ.isLoading}
            options={(versionsQ.data ?? []).map((v) => ({ value: v.forecast_id, label: `${v.model_type} · ${v.created_at.slice(0, 10)}` }))}
            style={{ width: 240 }}
          />
          <Segmented
            value={chartType}
            onChange={(v) => setChartType(v as ChartType)}
            options={[
              { label: '均值趋势', value: 'mean_trend' },
              { label: '价差', value: 'price_spread' },
              { label: '峰谷', value: 'peak_valley' },
            ]}
          />
        </Space>
      </Card>

      {acc && (
        <KpiCards
          loading={accQ.isLoading}
          items={[
            { label: 'MAPE', value: acc.mape, precision: 2, suffix: '%', color: CHART_COLORS[0] },
            { label: 'WMAPE精度', value: acc.wmape_accuracy, precision: 2, suffix: '%', color: CHART_COLORS[1] },
            { label: 'MAE', value: acc.mae, precision: 2, color: CHART_COLORS[2] },
            { label: 'RMSE', value: acc.rmse, precision: 2, color: CHART_COLORS[3] },
            { label: 'R²', value: acc.r2_score, precision: 3, color: CHART_COLORS[4] },
          ]}
        />
      )}

      {dataQ.isError && <Alert type="error" showIcon message="加载月度价格预测失败（该月可能无预测版本）" style={{ marginBottom: 16 }} />}
      <ChartCard
        title={`月度价格预测（${year}-${String(month).padStart(2, '0')} · ${chartType}）${hasActual ? '' : ' · 暂无实际值'}`}
        option={option}
        loading={dataQ.isLoading}
        height={400}
      />
    </div>
  );
}
