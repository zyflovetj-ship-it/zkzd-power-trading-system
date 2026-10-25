import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Descriptions,
  Select,
  Space,
  Spin,
  Statistic,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import {
  getSpotDashboard,
  getSpreadAttribution,
  getDayAhead,
  getRealTime,
  type SpotTimePoint,
  type SpreadTimePoint,
} from '@/api/market';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';

// ============ 辅助函数 ============
const fmt = (v: number | null | undefined, p = 1, suffix = '') =>
  v != null ? `${v.toFixed(p)}${suffix}` : '-';

const spreadColor = (v: number | null) => {
  if (v == null) return CHART_COLORS[2];
  return v >= 0 ? '#ff4d4f' : '#52c41a';
};

// ============ Tab1: 现货价格总览 ============
function DashboardTab({ dateStr, loading: parentLoading }: { dateStr: string; loading: boolean }) {
  const dashQ = useQuery({ queryKey: ['spotDash', dateStr], queryFn: () => getSpotDashboard(dateStr) });
  const spreadQ = useQuery({ queryKey: ['spreadAttr', dateStr], queryFn: () => getSpreadAttribution(dateStr) });

  const ts = dashQ.data?.time_series ?? [];
  const periodSummary = dashQ.data?.period_summary ?? [];
  const fk = dashQ.data?.financial_kpis;
  const rk = dashQ.data?.risk_kpis;
  const dist = spreadQ.data?.price_distribution ?? [];
  const spreadTs = spreadQ.data?.time_series ?? [];
  const systematicBias = spreadQ.data?.systematic_bias ?? [];

  // 策略建议
  const strategyHint = useMemo(() => {
    if (!fk) return null;
    const rate = fk.vwap_spread / fk.vwap_rt;
    if (rate < 0) return { text: '建议多报实时市场', color: 'green' };
    if (rate > 0) return { text: '建议多报日前市场', color: 'red' };
    return null;
  }, [fk]);

  // 时段分析表格 - 计算正差率
  const periodTableData = useMemo(() => {
    return periodSummary.map((p) => {
      const periodPoints = ts.filter((t) => t.period_type === p.period_name);
      const validPoints = periodPoints.filter((t) => t.price_rt != null && t.price_da != null);
      const positiveSpreads = validPoints.filter((t) => (t.price_rt ?? 0) > (t.price_da ?? 0));
      const positiveRate = validPoints.length > 0 ? (positiveSpreads.length / validPoints.length) * 100 : 0;
      let suggestion = '观望';
      if (positiveRate > 70 && (p.vwap_spread ?? 0) > 50) suggestion = '做多';
      else if (positiveRate < 30 && (p.vwap_spread ?? 0) < -50) suggestion = '做空';
      return { ...p, positiveRate, suggestion, key: p.period_name };
    });
  }, [periodSummary, ts]);

  // 图表: 96点价格曲线
  const tsOption: EChartsOption = {
    color: [CHART_COLORS[0], CHART_COLORS[1]],
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['日前价格', '实时价格'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: ts.map((p) => p.time_str), name: '时刻', boundaryGap: false },
    yAxis: { type: 'value', name: '价格(元/MWh)', scale: true },
    series: [
      { name: '日前价格', type: 'line', smooth: true, showSymbol: false, data: ts.map((p) => p.price_da), itemStyle: { color: CHART_COLORS[0] } },
      { name: '实时价格', type: 'line', smooth: true, showSymbol: false, data: ts.map((p) => p.price_rt), itemStyle: { color: CHART_COLORS[1] } },
    ],
  };

  // 图表: 价格偏差柱状图
  const spreadBarOption: EChartsOption = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: baseGrid,
    xAxis: { type: 'category', data: ts.map((p) => p.time_str), name: '时刻', boundaryGap: true, axisLabel: { interval: 7 } },
    yAxis: { type: 'value', name: '价差(元/MWh)', scale: true },
    series: [{
      name: '价差',
      type: 'bar',
      data: ts.map((p) => ({
        value: p.spread,
        itemStyle: { color: spreadColor(p.spread) },
      })),
    }],
  };

  // 图表: 价差分布直方图
  const distOption: EChartsOption = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: baseGrid,
    xAxis: { type: 'category', data: dist.map((p) => p.range_label), name: '价差区间' },
    yAxis: { type: 'value', name: '频次' },
    series: [{ name: '频次', type: 'bar', data: dist.map((p) => p.count), itemStyle: { color: CHART_COLORS[0] } }],
  };

  // 图表: 各时段 VWAP 对比
  const periodOption: EChartsOption = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    legend: { ...baseLegend, data: ['日前VWAP', '实时VWAP', '价差VWAP'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: periodSummary.map((p) => p.period_name) },
    yAxis: { type: 'value', name: 'VWAP(元/MWh)' },
    series: [
      { name: '日前VWAP', type: 'bar', data: periodSummary.map((p) => p.vwap_da), itemStyle: { color: CHART_COLORS[0] } },
      { name: '实时VWAP', type: 'bar', data: periodSummary.map((p) => p.vwap_rt), itemStyle: { color: CHART_COLORS[1] } },
      { name: '价差VWAP', type: 'bar', data: periodSummary.map((p) => p.vwap_spread), itemStyle: { color: CHART_COLORS[2] } },
    ],
  };

  const isLoading = dashQ.isLoading || parentLoading;

  return (
    <div>
      <KpiCards
        loading={isLoading}
        items={[
          { label: '日前VWAP', value: fk?.vwap_da ?? '-', precision: 1, suffix: '元/MWh', color: CHART_COLORS[0] },
          { label: '实时VWAP', value: fk?.vwap_rt ?? '-', precision: 1, suffix: '元/MWh', color: CHART_COLORS[1] },
          { label: '加权价差', value: fk?.vwap_spread ?? '-', precision: 1, suffix: '元/MWh', color: CHART_COLORS[2] },
          { label: '日前TWAP', value: fk?.twap_da ?? '-', precision: 1, suffix: '元/MWh', color: CHART_COLORS[3] },
          { label: '实时TWAP', value: fk?.twap_rt ?? '-', precision: 1, suffix: '元/MWh', color: CHART_COLORS[4] },
        ]}
      />

      {/* 风险指标 + 策略建议 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Descriptions column={{ xs: 1, sm: 2, md: 4 }} size="small">
          <Descriptions.Item label="最大正价差(亏损)">{fmt(rk?.max_positive_spread?.value)} ({rk?.max_positive_spread?.time_str})</Descriptions.Item>
          <Descriptions.Item label="最大负价差(盈利)">{fmt(rk?.max_negative_spread?.value)} ({rk?.max_negative_spread?.time_str})</Descriptions.Item>
          <Descriptions.Item label="实时最高价">{fmt(rk?.max_rt_price?.value)} ({rk?.max_rt_price?.time_str})</Descriptions.Item>
          <Descriptions.Item label="实时最低价">{fmt(rk?.min_rt_price?.value)} ({rk?.min_rt_price?.time_str})</Descriptions.Item>
        </Descriptions>
        {strategyHint && (
          <div style={{ marginTop: 8 }}>
            <Tag color={strategyHint.color}>{strategyHint.text}</Tag>
          </div>
        )}
      </Card>

      {dashQ.isError && <Alert type="error" showIcon message="加载现货价格总览失败" style={{ marginBottom: 16 }} />}
      <ChartCard title={`日前/实时价格曲线（${dateStr}）`} option={tsOption} loading={isLoading} height={380} />
      <ChartCard title="价格偏差（实时-日前）" option={spreadBarOption} loading={isLoading} height={320} />
      <ChartCard title="各时段 VWAP 对比" option={periodOption} loading={isLoading} height={320} />

      {spreadQ.isError && <Alert type="error" showIcon message="加载价差归因失败" style={{ marginBottom: 16 }} />}
      <ChartCard title="价差分布直方图" option={distOption} loading={spreadQ.isLoading} height={320} />

      {/* 时段分析表格 */}
      <Card size="small" title="时段价格分析" style={{ marginBottom: 16 }}>
        <Table
          dataSource={periodTableData}
          pagination={false}
          size="small"
          rowKey="key"
          columns={[
            { title: '时段', dataIndex: 'period_name', key: 'period_name' },
            { title: '日前均价', dataIndex: 'vwap_da', key: 'vwap_da', render: (v: number) => fmt(v) },
            { title: '实时均价', dataIndex: 'vwap_rt', key: 'vwap_rt', render: (v: number) => fmt(v) },
            { title: '价差', dataIndex: 'vwap_spread', key: 'vwap_spread', render: (v: number) => <span style={{ color: spreadColor(v) }}>{fmt(v)}</span> },
            { title: '正差率(%)', dataIndex: 'positiveRate', key: 'positiveRate', render: (v: number) => `${v.toFixed(1)}%` },
            { title: '建议', dataIndex: 'suggestion', key: 'suggestion', render: (v: string) => {
              const color = v === '做多' ? 'red' : v === '做空' ? 'green' : 'default';
              return <Tag color={color}>{v}</Tag>;
            }},
          ]}
        />
      </Card>
    </div>
  );
}

// ============ Tab2: 日前现货分析 ============
function DayAheadTab({ dateStr }: { dateStr: string }) {
  const daQ = useQuery({ queryKey: ['spotDA', dateStr], queryFn: () => getDayAhead(dateStr) });
  const data = daQ.data?.data ?? [];
  const corr = daQ.data?.metadata?.correlation;

  // 图表: 日前价格与市场竞价空间
  const priceSpaceOption: EChartsOption = {
    color: [CHART_COLORS[0], CHART_COLORS[1]],
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['日前价格', '市场竞价空间'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: data.map((p) => p.time_str), name: '时刻', boundaryGap: false },
    yAxis: [
      { type: 'value', name: '价格(元/MWh)', scale: true },
      { type: 'value', name: '竞价空间(MW)', position: 'right', scale: true },
    ],
    series: [
      { name: '日前价格', type: 'line', smooth: true, showSymbol: false, data: data.map((p) => p.avg_clearing_price), yAxisIndex: 0 },
      { name: '市场竞价空间', type: 'line', smooth: true, showSymbol: false, data: data.map((p) => p.market_bidding_space), yAxisIndex: 1, areaStyle: { opacity: 0.15 } },
    ],
  };

  // 图表: 日前供给堆栈
  const hasGeneration = data.some((p) => p.wind_clearing_power != null);
  const stackOption: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: hasGeneration ? ['火电', '水电', '风电', '光伏', '储能'] : [] },
    grid: baseGrid,
    xAxis: { type: 'category', data: data.map((p) => p.time_str), name: '时刻', boundaryGap: false, axisLabel: { interval: 7 } },
    yAxis: { type: 'value', name: '出清电量(MWh)' },
    series: hasGeneration ? [
      { name: '火电', type: 'line', stack: 'supply', areaStyle: { opacity: 0.3 }, showSymbol: false, data: data.map((p: any) => p.thermal_clearing_power) },
      { name: '水电', type: 'line', stack: 'supply', areaStyle: { opacity: 0.3 }, showSymbol: false, data: data.map((p: any) => p.hydro_clearing_power) },
      { name: '风电', type: 'line', stack: 'supply', areaStyle: { opacity: 0.3 }, showSymbol: false, data: data.map((p) => p.wind_clearing_power) },
      { name: '光伏', type: 'line', stack: 'supply', areaStyle: { opacity: 0.3 }, showSymbol: false, data: data.map((p) => p.solar_clearing_power) },
      { name: '储能', type: 'line', stack: 'supply', areaStyle: { opacity: 0.3 }, showSymbol: false, data: data.map((p: any) => (p.pumped_storage_clearing_power ?? 0) + (p.battery_storage_generation ?? 0)) },
    ] : [],
  };

  // 图表: 供给曲线 (Scatter)
  const scatterOption: EChartsOption = {
    color: [CHART_COLORS[0]],
    tooltip: { trigger: 'item' },
    grid: baseGrid,
    xAxis: { type: 'value', name: '总电量(MWh)', scale: true },
    yAxis: { type: 'value', name: '价格(元/MWh)', scale: true },
    series: [{
      type: 'scatter',
      data: data.map((p) => [p.total_clearing_power, p.avg_clearing_price]),
      symbolSize: 6,
    }],
  };

  return (
    <div>
      {corr != null && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Statistic title="价格与竞价空间相关系数" value={corr} precision={1} suffix="%" />
        </Card>
      )}
      {daQ.isError && <Alert type="error" showIcon message="加载日前分析失败" style={{ marginBottom: 16 }} />}
      <ChartCard title="日前价格与市场竞价空间" option={priceSpaceOption} loading={daQ.isLoading} height={380} />
      {hasGeneration && <ChartCard title="日前供给堆栈" option={stackOption} loading={daQ.isLoading} height={360} />}
      <ChartCard title="日前供给曲线" option={scatterOption} loading={daQ.isLoading} height={360} />
    </div>
  );
}

// ============ Tab3: 实时现货复盘 ============
function RealTimeTab({ dateStr }: { dateStr: string }) {
  const rtQ = useQuery({ queryKey: ['spotRT', dateStr], queryFn: () => getRealTime(dateStr) });
  const data = rtQ.data?.data ?? [];
  const corr = rtQ.data?.metadata?.correlation;

  // 价格爬坡
  const priceRamp = useMemo(() => {
    return data.map((p, i) => i === 0 ? 0 : p.avg_clearing_price - data[i - 1].avg_clearing_price);
  }, [data]);

  // 图表: 实时价格与市场竞价空间
  const priceSpaceOption: EChartsOption = {
    color: ['#ff4d4f', CHART_COLORS[1]],
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['实时价格', '市场竞价空间'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: data.map((p) => p.time_str), name: '时刻', boundaryGap: false },
    yAxis: [
      { type: 'value', name: '价格(元/MWh)', scale: true },
      { type: 'value', name: '竞价空间(MW)', position: 'right', scale: true },
    ],
    series: [
      { name: '实时价格', type: 'line', smooth: true, showSymbol: false, data: data.map((p) => p.avg_clearing_price), yAxisIndex: 0 },
      { name: '市场竞价空间', type: 'line', smooth: true, showSymbol: false, data: data.map((p) => p.market_bidding_space), yAxisIndex: 1, areaStyle: { opacity: 0.15 } },
    ],
  };

  // 图表: 价格波动
  const rampOption: EChartsOption = {
    tooltip: { trigger: 'axis', axisPointer: { type: 'shadow' } },
    grid: baseGrid,
    xAxis: { type: 'category', data: data.map((p) => p.time_str), name: '时刻', boundaryGap: true, axisLabel: { interval: 7 } },
    yAxis: { type: 'value', name: '价格波动(元/MWh)', scale: true },
    series: [{
      name: '价格波动',
      type: 'bar',
      data: priceRamp.map((v) => ({
        value: v,
        itemStyle: { color: v >= 0 ? '#ff4d4f' : '#52c41a' },
      })),
    }],
  };

  // 图表: 供给堆栈
  const hasGeneration = data.some((p) => p.wind_clearing_power != null);
  const stackOption: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: hasGeneration ? ['火电', '水电', '风电', '光伏', '储能'] : [] },
    grid: baseGrid,
    xAxis: { type: 'category', data: data.map((p) => p.time_str), name: '时刻', boundaryGap: false, axisLabel: { interval: 7 } },
    yAxis: { type: 'value', name: '出清电量(MWh)' },
    series: hasGeneration ? [
      { name: '火电', type: 'line', stack: 'supply', areaStyle: { opacity: 0.3 }, showSymbol: false, data: data.map((p: any) => p.thermal_clearing_power) },
      { name: '水电', type: 'line', stack: 'supply', areaStyle: { opacity: 0.3 }, showSymbol: false, data: data.map((p: any) => p.hydro_clearing_power) },
      { name: '风电', type: 'line', stack: 'supply', areaStyle: { opacity: 0.3 }, showSymbol: false, data: data.map((p) => p.wind_clearing_power) },
      { name: '光伏', type: 'line', stack: 'supply', areaStyle: { opacity: 0.3 }, showSymbol: false, data: data.map((p) => p.solar_clearing_power) },
      { name: '储能', type: 'line', stack: 'supply', areaStyle: { opacity: 0.3 }, showSymbol: false, data: data.map((p: any) => (p.pumped_storage_clearing_power ?? 0) + (p.battery_storage_generation ?? 0)) },
    ] : [],
  };

  // 图表: 供给曲线
  const scatterOption: EChartsOption = {
    color: ['#ff4d4f'],
    tooltip: { trigger: 'item' },
    grid: baseGrid,
    xAxis: { type: 'value', name: '总电量(MWh)', scale: true },
    yAxis: { type: 'value', name: '价格(元/MWh)', scale: true },
    series: [{
      type: 'scatter',
      data: data.map((p) => [p.total_clearing_power, p.avg_clearing_price]),
      symbolSize: 6,
    }],
  };

  return (
    <div>
      {corr != null && (
        <Card size="small" style={{ marginBottom: 16 }}>
          <Statistic title="价格与竞价空间相关系数" value={corr} precision={1} suffix="%" />
        </Card>
      )}
      {rtQ.isError && <Alert type="error" showIcon message="加载实时分析失败" style={{ marginBottom: 16 }} />}
      <ChartCard title="实时价格与市场竞价空间" option={priceSpaceOption} loading={rtQ.isLoading} height={380} />
      {hasGeneration && <ChartCard title="现货供给堆栈" option={stackOption} loading={rtQ.isLoading} height={360} />}
      <ChartCard title="实时价格波动" option={rampOption} loading={rtQ.isLoading} height={320} />
      <ChartCard title="现货供给曲线" option={scatterOption} loading={rtQ.isLoading} height={360} />
    </div>
  );
}

// ============ Tab4: 价差归因分析 ============
const DEVIATION_OPTIONS = [
  { value: 'total_volume_deviation', label: '市场竞价空间偏差' },
  { value: 'system_load_deviation', label: '系统负荷偏差' },
  { value: 'renewable_deviation', label: '新能源偏差' },
  { value: 'nonmarket_unit_deviation', label: '非市场化机组偏差' },
  { value: 'tieline_deviation', label: '联络线偏差' },
];

function SpreadAnalysisTab({ dateStr }: { dateStr: string }) {
  const [deviationType, setDeviationType] = useState('total_volume_deviation');
  const spreadQ = useQuery({ queryKey: ['spreadAttr', dateStr], queryFn: () => getSpreadAttribution(dateStr) });

  const spreadTs = spreadQ.data?.time_series ?? [];
  const systematicBias = spreadQ.data?.systematic_bias ?? [];

  // 图表: 核心偏差归因
  const spreadAttrOption: EChartsOption = {
    color: [CHART_COLORS[2], '#fa8c16'],
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['价差', DEVIATION_OPTIONS.find((o) => o.value === deviationType)?.label ?? ''] },
    grid: baseGrid,
    xAxis: { type: 'category', data: spreadTs.map((p) => p.time_str), name: '时刻', boundaryGap: true, axisLabel: { interval: 7 } },
    yAxis: [
      { type: 'value', name: '价差(元/MWh)', scale: true },
      { type: 'value', name: '偏差', position: 'right', scale: true },
    ],
    series: [
      {
        name: '价差',
        type: 'bar',
        yAxisIndex: 0,
        data: spreadTs.map((p) => ({
          value: p.price_spread,
          itemStyle: { color: p.price_spread >= 0 ? 'rgba(255,77,79,0.6)' : 'rgba(82,196,26,0.6)' },
        })),
      },
      {
        name: DEVIATION_OPTIONS.find((o) => o.value === deviationType)?.label ?? '',
        type: 'line',
        smooth: true,
        showSymbol: false,
        yAxisIndex: 1,
        data: spreadTs.map((p) => (p as any)[deviationType]),
      },
    ],
  };

  // 图表: 数据维度曲线对比
  const daRtFieldMap: Record<string, { da: string; rt: string }> = {
    total_volume_deviation: { da: 'volume_da', rt: 'volume_rt' },
    system_load_deviation: { da: 'system_load_da', rt: 'system_load_rt' },
    renewable_deviation: { da: 'renewable_da', rt: 'renewable_rt' },
    nonmarket_unit_deviation: { da: 'nonmarket_unit_da', rt: 'nonmarket_unit_rt' },
    tieline_deviation: { da: 'tieline_da', rt: 'tieline_rt' },
  };

  const dimOption: EChartsOption = {
    color: ['#fa8c16', CHART_COLORS[1]],
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['实时', '日前'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: spreadTs.map((p) => p.time_str), name: '时刻', boundaryGap: false },
    yAxis: { type: 'value', name: '数值', scale: true },
    series: [
      { name: '实时', type: 'line', smooth: true, showSymbol: false, data: spreadTs.map((p) => (p as any)[daRtFieldMap[deviationType]?.rt]) },
      { name: '日前', type: 'line', smooth: true, showSymbol: false, lineStyle: { type: 'dashed' }, data: spreadTs.map((p) => (p as any)[daRtFieldMap[deviationType]?.da]) },
    ],
  };

  // 系统性偏差表格
  const biasColumns = [
    { title: '时段', dataIndex: 'period_name', key: 'period_name' },
    { title: '平均价差', dataIndex: 'avg_price_spread', key: 'avg_price_spread', render: (v: number) => fmt(v) },
    { title: '竞价空间偏差', dataIndex: 'avg_total_volume_deviation', key: 'avg_total_volume_deviation', render: (v: number) => fmt(v, 0) },
    { title: '系统负荷偏差', dataIndex: 'avg_system_load_deviation', key: 'avg_system_load_deviation', render: (v: number) => fmt(v, 0) },
    { title: '新能源偏差', dataIndex: 'avg_renewable_deviation', key: 'avg_renewable_deviation', render: (v: number) => fmt(v, 0) },
    { title: '非市场化偏差', dataIndex: 'avg_nonmarket_unit_deviation', key: 'avg_nonmarket_unit_deviation', render: (v: number) => fmt(v, 0) },
    { title: '联络线偏差', dataIndex: 'avg_tieline_deviation', key: 'avg_tieline_deviation', render: (v: number) => fmt(v, 0) },
  ];

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space>
          <Typography.Text>偏差维度:</Typography.Text>
          <Select value={deviationType} onChange={setDeviationType} options={DEVIATION_OPTIONS} style={{ width: 200 }} />
        </Space>
      </Card>

      {spreadQ.isError && <Alert type="error" showIcon message="加载价差归因失败" style={{ marginBottom: 16 }} />}
      <ChartCard title="核心偏差归因" option={spreadAttrOption} loading={spreadQ.isLoading} height={380} />
      <ChartCard title="数据维度曲线对比" option={dimOption} loading={spreadQ.isLoading} height={360} />

      <Card size="small" title="系统性偏差分析" style={{ marginBottom: 16 }}>
        <Table
          dataSource={systematicBias.map((b, i) => ({ ...b, key: i }))}
          columns={biasColumns}
          pagination={false}
          size="small"
        />
      </Card>
    </div>
  );
}

// ============ 主页面 ============
export default function SpotMarketPage() {
  const [date, setDate] = useState<Dayjs>(dayjs());
  const [tab, setTab] = useState('0');
  const dateStr = date.format('YYYY-MM-DD');

  const handleShiftDate = (days: number) => setDate((prev) => prev.add(days, 'day'));

  const tabItems = [
    { key: '0', label: '现货价格总览', children: <DashboardTab dateStr={dateStr} loading={false} /> },
    { key: '1', label: '日前现货分析', children: <DayAheadTab dateStr={dateStr} /> },
    { key: '2', label: '实时现货复盘', children: <RealTimeTab dateStr={dateStr} /> },
    { key: '3', label: '价差归因分析', children: <SpreadAnalysisTab dateStr={dateStr} /> },
  ];

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Button icon={<LeftOutlined />} onClick={() => handleShiftDate(-1)} />
          <DatePicker value={date} onChange={(d) => d && setDate(d)} allowClear={false} />
          <Button icon={<RightOutlined />} onClick={() => handleShiftDate(1)} />
        </Space>
      </Card>
      <Tabs activeKey={tab} onChange={setTab} items={tabItems} />
    </div>
  );
}
