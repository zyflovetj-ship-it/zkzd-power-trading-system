import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Card, DatePicker, Segmented, Space } from 'antd';
import dayjs, { Dayjs } from 'dayjs';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { getContractPriceTrend, getContractQuantityStructure, getContractCurveAnalysis } from '@/api/market';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';

type View = 'price-trend' | 'quantity' | 'curve';

const VIEWS = [
  { label: '价格趋势', value: 'price-trend' },
  { label: '电量结构', value: 'quantity' },
  { label: '曲线分析', value: 'curve' },
];

// 中长期趋势分析：合同价格 vs 现货的价格趋势、签约电量结构、各类型曲线。
export default function MidLongTrendPage() {
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs().subtract(30, 'day'), dayjs()]);
  const [view, setView] = useState<View>('price-trend');
  const start = range[0].format('YYYY-MM-DD');
  const end = range[1].format('YYYY-MM-DD');

  const trendQ = useQuery({ queryKey: ['cpt', start, end], enabled: view === 'price-trend', queryFn: () => getContractPriceTrend(start, end) });
  const qtyQ = useQuery({ queryKey: ['cpq', start, end], enabled: view === 'quantity', queryFn: () => getContractQuantityStructure(start, end) });
  const curveQ = useQuery({ queryKey: ['cpc', start, end], enabled: view === 'curve', queryFn: () => getContractCurveAnalysis(start, end) });

  const renderView = () => {
    if (view === 'price-trend') {
      const d = trendQ.data?.daily_trends ?? [];
      const ss = trendQ.data?.spread_stats;
      const option: EChartsOption = {
        color: CHART_COLORS,
        tooltip: { ...baseTooltip },
        legend: { ...baseLegend, data: ['合同VWAP', '现货VWAP', '价差VWAP'] },
        grid: baseGrid,
        xAxis: { type: 'category', data: d.map((p) => p.date), boundaryGap: false },
        yAxis: [
          { type: 'value', name: 'VWAP(元/MWh)', scale: true },
          { type: 'value', name: '价差', position: 'right', scale: true },
        ],
        series: [
          { name: '合同VWAP', type: 'line', smooth: true, showSymbol: false, data: d.map((p) => p.contract_vwap), yAxisIndex: 0, itemStyle: { color: CHART_COLORS[0] } },
          { name: '现货VWAP', type: 'line', smooth: true, showSymbol: false, data: d.map((p) => p.spot_vwap), yAxisIndex: 0, itemStyle: { color: CHART_COLORS[1] } },
          { name: '价差VWAP', type: 'line', showSymbol: false, data: d.map((p) => p.vwap_spread), yAxisIndex: 1, itemStyle: { color: CHART_COLORS[2] } },
        ],
      };
      return (
        <>
          <KpiCards
            loading={trendQ.isLoading}
            items={[
              { label: '平均价差', value: ss?.avgSpread ?? '-', precision: 1, color: CHART_COLORS[0] },
              { label: '最大价差', value: ss?.maxSpread ?? '-', precision: 1, color: CHART_COLORS[1] },
              { label: '正价差占比', value: ss?.positiveSpreadRatio ?? '-', precision: 3, color: CHART_COLORS[2] },
            ]}
          />
          <ChartCard title="合同与现货价格趋势" option={option} loading={trendQ.isLoading} height={380} />
        </>
      );
    }

    if (view === 'quantity') {
      const d = qtyQ.data?.daily_quantities ?? [];
      const option: EChartsOption = {
        tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
        legend: { ...baseLegend, data: ['年度', '月度', '月内', '市场', '绿电', '代理'] },
        grid: baseGrid,
        xAxis: { type: 'category', data: d.map((p) => p.date) },
        yAxis: { type: 'value', name: '电量' },
        series: [
          { name: '年度', type: 'bar', stack: 'q', data: d.map((p) => p.yearly_qty), itemStyle: { color: CHART_COLORS[0] } },
          { name: '月度', type: 'bar', stack: 'q', data: d.map((p) => p.monthly_qty), itemStyle: { color: CHART_COLORS[1] } },
          { name: '月内', type: 'bar', stack: 'q', data: d.map((p) => p.within_month_qty), itemStyle: { color: CHART_COLORS[2] } },
          { name: '市场', type: 'bar', stack: 'q', data: d.map((p) => p.market_qty), itemStyle: { color: CHART_COLORS[3] } },
          { name: '绿电', type: 'bar', stack: 'q', data: d.map((p) => p.green_qty), itemStyle: { color: CHART_COLORS[4] } },
          { name: '代理', type: 'bar', stack: 'q', data: d.map((p) => p.agency_qty), itemStyle: { color: CHART_COLORS[5] } },
        ],
      };
      return <ChartCard title="签约电量结构（堆叠）" option={option} loading={qtyQ.isLoading} height={400} />;
    }

    // curve
    const curves = curveQ.data?.curves ?? [];
    const spot = curveQ.data?.spot_curve;
    const allDates = Array.from(new Set(curves.flatMap((c) => c.points.map((p) => p.date)))).sort();
    const curveSeries = curves.map((c, i) => ({
      name: c.label,
      type: 'line' as const,
      smooth: true,
      showSymbol: false,
      data: allDates.map((date) => {
        const pt = c.points.find((p) => p.date === date);
        return pt ? pt.vwap : null;
      }),
      itemStyle: { color: CHART_COLORS[i % CHART_COLORS.length] },
    }));
    const spotSeries = spot
      ? [
          {
            name: spot.label,
            type: 'line' as const,
            smooth: true,
            showSymbol: false,
            lineStyle: { type: 'dashed' },
            data: allDates.map((date) => {
              const pt = spot.points.find((p) => p.date === date);
              return pt ? pt.vwap : null;
            }),
            itemStyle: { color: '#000' },
          },
        ]
      : [];
    const series = [...curveSeries, ...spotSeries];
    const option: EChartsOption = {
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: [...curves.map((c) => c.label), ...(spot ? [spot.label] : [])] },
      grid: baseGrid,
      xAxis: { type: 'category', data: allDates, boundaryGap: false },
      yAxis: { type: 'value', name: 'VWAP(元/MWh)', scale: true },
      series,
    };
    return <ChartCard title="各类型合同价格曲线" option={option} loading={curveQ.isLoading} height={400} />;
  };

  const activeQ = { 'price-trend': trendQ, quantity: qtyQ, curve: curveQ }[view];

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Segmented value={view} onChange={(v) => setView(v as View)} options={VIEWS} />
          <DatePicker.RangePicker value={range} onChange={(r) => { const [a, b] = r ?? [null, null]; if (a && b) setRange([a, b]); }} />
        </Space>
      </Card>

      {activeQ?.isError && <Alert type="error" showIcon message="加载中长期趋势数据失败" style={{ marginBottom: 16 }} />}
      {renderView()}
    </div>
  );
}
