import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Card, DatePicker, Segmented, Space } from 'antd';
import dayjs, { Dayjs } from 'dayjs';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import {
  getPriceTrend,
  getVolatility,
  getArbitrage,
  getAnomaly,
  getWeekdayPattern,
  getTimeslotStats,
} from '@/api/market';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';

type View = 'price-trend' | 'weekday' | 'volatility' | 'arbitrage' | 'anomaly' | 'timeslot';

const VIEWS = [
  { label: '价格趋势', value: 'price-trend' },
  { label: '星期规律', value: 'weekday' },
  { label: '波动率', value: 'volatility' },
  { label: '套利空间', value: 'arbitrage' },
  { label: '异常事件', value: 'anomaly' },
  { label: '时段统计', value: 'timeslot' },
];

// 现货趋势分析：按日期范围切换多种趋势子分析视图。
export default function SpotTrendPage() {
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs().subtract(30, 'day'), dayjs()]);
  const [view, setView] = useState<View>('price-trend');
  const start = range[0].format('YYYY-MM-DD');
  const end = range[1].format('YYYY-MM-DD');

  const priceTrendQ = useQuery({ queryKey: ['pt', start, end], enabled: view === 'price-trend', queryFn: () => getPriceTrend(start, end) });
  const volQ = useQuery({ queryKey: ['vol', start, end], enabled: view === 'volatility', queryFn: () => getVolatility(start, end) });
  const arbQ = useQuery({ queryKey: ['arb', start, end], enabled: view === 'arbitrage', queryFn: () => getArbitrage(start, end) });
  const anomQ = useQuery({ queryKey: ['anom', start, end], enabled: view === 'anomaly', queryFn: () => getAnomaly(start, end) });
  const weekQ = useQuery({ queryKey: ['week', start, end], enabled: view === 'weekday', queryFn: () => getWeekdayPattern(start, end) });
  const tsQ = useQuery({ queryKey: ['tsstats', start, end], enabled: view === 'timeslot', queryFn: () => getTimeslotStats(start, end) });

  const renderView = () => {
    if (view === 'price-trend') {
      const d = priceTrendQ.data?.daily_trends ?? [];
      const ss = priceTrendQ.data?.spread_stats;
      const option: EChartsOption = {
        color: CHART_COLORS,
        tooltip: { ...baseTooltip },
        legend: { ...baseLegend, data: ['日前VWAP', '实时VWAP', '价差VWAP'] },
        grid: baseGrid,
        xAxis: { type: 'category', data: d.map((p) => p.date), boundaryGap: false },
        yAxis: { type: 'value', name: 'VWAP(元/MWh)', scale: true },
        series: [
          { name: '日前VWAP', type: 'line', smooth: true, showSymbol: false, data: d.map((p) => p.vwap_da), itemStyle: { color: CHART_COLORS[0] } },
          { name: '实时VWAP', type: 'line', smooth: true, showSymbol: false, data: d.map((p) => p.vwap_rt), itemStyle: { color: CHART_COLORS[1] } },
          { name: '价差VWAP', type: 'line', smooth: true, showSymbol: false, data: d.map((p) => p.vwap_spread), itemStyle: { color: CHART_COLORS[2] } },
        ],
      };
      return (
        <>
          <KpiCards
            loading={priceTrendQ.isLoading}
            items={[
              { label: '平均价差', value: ss?.avgSpread ?? '-', precision: 1, color: CHART_COLORS[0] },
              { label: '最大价差', value: ss?.maxSpread ?? '-', precision: 1, color: CHART_COLORS[1] },
              { label: '最小价差', value: ss?.minSpread ?? '-', precision: 1, color: CHART_COLORS[2] },
              { label: '正价差占比', value: ss?.positiveSpreadRatio ?? '-', precision: 3, color: CHART_COLORS[3] },
            ]}
          />
          <ChartCard title="日度 VWAP 趋势" option={option} loading={priceTrendQ.isLoading} height={380} />
        </>
      );
    }

    if (view === 'volatility') {
      const d = volQ.data?.daily_volatility ?? [];
      const option: EChartsOption = {
        color: CHART_COLORS,
        tooltip: { ...baseTooltip },
        legend: { ...baseLegend, data: ['变异系数', '最大爬坡', '价差标准差'] },
        grid: baseGrid,
        xAxis: { type: 'category', data: d.map((p) => p.date), boundaryGap: false },
        yAxis: { type: 'value', name: '波动率指标', scale: true },
        series: [
          { name: '变异系数', type: 'line', smooth: true, showSymbol: false, data: d.map((p) => p.cv_rt), itemStyle: { color: CHART_COLORS[0] } },
          { name: '最大爬坡', type: 'line', smooth: true, showSymbol: false, data: d.map((p) => p.max_ramp), itemStyle: { color: CHART_COLORS[1] } },
          { name: '价差标准差', type: 'line', smooth: true, showSymbol: false, data: d.map((p) => p.spread_std), itemStyle: { color: CHART_COLORS[2] } },
        ],
      };
      return <ChartCard title="价格波动率（日度）" option={option} loading={volQ.isLoading} height={380} />;
    }

    if (view === 'arbitrage') {
      const d = arbQ.data?.daily_arbitrage ?? [];
      const s = arbQ.data?.summary;
      const option: EChartsOption = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: baseGrid,
        xAxis: { type: 'category', data: d.map((p) => p.date), name: '日期' },
        yAxis: { type: 'value', name: '最大价差(元/MWh)' },
        series: [{ name: '最大套利价差', type: 'bar', data: d.map((p) => p.max_spread), itemStyle: { color: CHART_COLORS[0] } }],
      };
      return (
        <>
          <KpiCards
            loading={arbQ.isLoading}
            items={[
              { label: '平均最大价差', value: s?.avg_max_spread ?? '-', precision: 1, suffix: '元/MWh', color: CHART_COLORS[0] },
              { label: '统计天数', value: s?.days_count ?? '-', color: CHART_COLORS[1] },
            ]}
          />
          <ChartCard title="日度最大套利价差" option={option} loading={arbQ.isLoading} height={380} />
        </>
      );
    }

    if (view === 'anomaly') {
      const ev = anomQ.data?.events;
      const d = anomQ.data?.daily_extremums ?? [];
      const option: EChartsOption = {
        color: CHART_COLORS,
        tooltip: { ...baseTooltip },
        legend: { ...baseLegend, data: ['最高价', '最低价'] },
        grid: baseGrid,
        xAxis: { type: 'category', data: d.map((p) => p.date), boundaryGap: false },
        yAxis: { type: 'value', name: '价格(元/MWh)', scale: true },
        series: [
          { name: '最高价', type: 'line', showSymbol: true, data: d.map((p) => p.max_price), itemStyle: { color: CHART_COLORS[3] } },
          { name: '最低价', type: 'line', showSymbol: true, data: d.map((p) => p.min_price), itemStyle: { color: CHART_COLORS[4] } },
        ],
      };
      return (
        <>
          <KpiCards
            loading={anomQ.isLoading}
            items={[
              { label: '负电价次数', value: ev?.negative_price?.count ?? '-', color: CHART_COLORS[4] },
              { label: '零电价次数', value: ev?.zero_price?.count ?? '-', color: CHART_COLORS[2] },
              { label: '高价次数', value: ev?.high_price?.count ?? '-', color: CHART_COLORS[3] },
            ]}
          />
          <ChartCard title="日度价格极值" option={option} loading={anomQ.isLoading} height={380} />
        </>
      );
    }

    if (view === 'weekday') {
      const d = weekQ.data?.distribution ?? [];
      const option: EChartsOption = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        grid: baseGrid,
        xAxis: { type: 'category', data: d.map((p) => p.weekday_name) },
        yAxis: { type: 'value', name: '价格中位数(元/MWh)' },
        series: [{ name: '价格中位数', type: 'bar', data: d.map((p) => p.stats.median), itemStyle: { color: CHART_COLORS[0] } }],
      };
      return <ChartCard title="星期规律（价格中位数）" option={option} loading={weekQ.isLoading} height={380} />;
    }

    // timeslot
    const d = tsQ.data?.box_plot_data ?? [];
    const option: EChartsOption = {
      tooltip: { trigger: 'item' },
      grid: baseGrid,
      xAxis: { type: 'category', data: d.map((p) => p.time_label), axisLabel: { rotate: 90, fontSize: 9 } },
      yAxis: { type: 'value', name: '价格(元/MWh)' },
      series: [
        {
          name: '时段价格分布',
          type: 'boxplot',
          data: d.map((p) => [p.min, p.q1, p.median, p.q3, p.max]),
          itemStyle: { color: CHART_COLORS[0] },
        },
      ],
    };
    return <ChartCard title="时段价格分布（箱线图）" option={option} loading={tsQ.isLoading} height={420} />;
  };

  const activeQ = { 'price-trend': priceTrendQ, volatility: volQ, arbitrage: arbQ, anomaly: anomQ, weekday: weekQ, timeslot: tsQ }[view];

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Segmented value={view} onChange={(v) => setView(v as View)} options={VIEWS} />
          {view === 'timeslot' && <DatePicker.RangePicker value={range} onChange={(r) => { const [a, b] = r ?? [null, null]; if (a && b) setRange([a, b]); }} />}
        </Space>
      </Card>

      {activeQ?.isError && <Alert type="error" showIcon message="加载趋势数据失败" style={{ marginBottom: 16 }} />}
      {renderView()}
    </div>
  );
}
