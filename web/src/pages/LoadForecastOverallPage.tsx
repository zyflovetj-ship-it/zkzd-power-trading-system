import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Card, DatePicker, Segmented, Space, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs, { Dayjs } from 'dayjs';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import {
  getMediumLongLatest,
  getShortTermList,
  getForecastBaseAvailability,
  getTotalDailyEnergy,
} from '@/api/loadForecast';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import type { ShortTermListRow } from '@/api/loadForecast';

export default function LoadForecastOverallPage() {
  const today = dayjs();
  const [view, setView] = useState<'overview' | 'trend'>('overview');
  const [month, setMonth] = useState<Dayjs>(dayjs());
  const monthStr = month.format('YYYY-MM');

  const mlQ = useQuery({ queryKey: ['mlLatest'], queryFn: () => getMediumLongLatest() });
  const shortQ = useQuery({
    queryKey: ['shortList', 'overall'],
    queryFn: () => getShortTermList(today.subtract(30, 'day').format('YYYY-MM-DD'), today.format('YYYY-MM-DD')),
  });
  const baseQ = useQuery({
    queryKey: ['baseAvail', today.format('YYYY-MM-DD')],
    queryFn: () => getForecastBaseAvailability(today.format('YYYY-MM-DD'), 'recent_7'),
  });
  const trendQ = useQuery({
    queryKey: ['totalDailyEnergy', monthStr],
    enabled: view === 'trend',
    queryFn: () => getTotalDailyEnergy([monthStr]),
  });

  const mlData = mlQ.data?.data ?? [];
  const shortRows: ShortTermListRow[] = shortQ.data ?? [];
  const availDates = new Set(
    (baseQ.data?.availability_matrix ?? []).flat().filter((c) => c.is_available).map((c) => c.date),
  );
  const trendData = trendQ.data?.[monthStr] ?? [];

  const mlOption: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['预测值', '置信区间'] },
    grid: baseGrid,
    xAxis: { type: 'category', data: mlData.map((p) => p.month), name: '月份' },
    yAxis: { type: 'value', name: '负荷 (MW)' },
    series: [
      {
        name: '下限',
        type: 'line',
        data: mlData.map((p) => p.lower_bound),
        lineStyle: { opacity: 0 },
        stack: 'band',
        symbol: 'none',
        areaStyle: { opacity: 0 },
      },
      {
        name: '置信区间',
        type: 'line',
        data: mlData.map((p) => p.upper_bound - p.lower_bound),
        lineStyle: { opacity: 0 },
        stack: 'band',
        symbol: 'none',
        areaStyle: { color: 'rgba(9,88,217,0.12)' },
      },
      {
        name: '预测值',
        type: 'line',
        data: mlData.map((p) => p.forecast_value),
        itemStyle: { color: CHART_COLORS[0] },
        symbol: 'circle',
        symbolSize: 6,
      },
    ],
  };

  const trendOption: EChartsOption = {
    tooltip: { trigger: 'axis' },
    grid: baseGrid,
    xAxis: { type: 'category', data: trendData.map((p) => String(p.day)), name: '日' },
    yAxis: { type: 'value', name: '电量 (kWh)' },
    series: [
      {
        name: '总日电量',
        type: 'line',
        smooth: true,
        data: trendData.map((p) => p.energy),
        areaStyle: { opacity: 0.12 },
        itemStyle: { color: CHART_COLORS[1] },
      },
    ],
  };

  const columns: ColumnsType<ShortTermListRow> = [
    { title: '预测生成日期', dataIndex: 'forecast_date', key: 'forecast_date' },
    { title: '预测目标日期', dataIndex: 'forecast_target_date', key: 'forecast_target_date' },
    {
      title: '预测类型',
      dataIndex: 'forecast_types',
      key: 'forecast_types',
      render: (v: string[]) => v.map((t) => <Tag key={t}>{t}</Tag>),
    },
    {
      title: '含实际值',
      dataIndex: 'has_actual',
      key: 'has_actual',
      render: (v: boolean) => (v ? <Tag color="green">是</Tag> : <Tag>否</Tag>),
    },
  ];

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Segmented
            value={view}
            onChange={(v) => setView(v as 'overview' | 'trend')}
            options={[
              { label: '总体概览', value: 'overview' },
              { label: '电量趋势', value: 'trend' },
            ]}
          />
          {view === 'trend' && (
            <DatePicker picker="month" value={month} onChange={(d) => d && setMonth(d)} allowClear={false} />
          )}
        </Space>
      </Card>

      {view === 'overview' && (
        <>
          <KpiCards
            loading={mlQ.isLoading || shortQ.isLoading || baseQ.isLoading}
            items={[
              { label: '中长期预测月份数', value: mlData.length, color: CHART_COLORS[0] },
              { label: '短期近期批次（30天）', value: shortRows.length, color: CHART_COLORS[1] },
              { label: '基础数据可用天数（7天）', value: availDates.size, color: CHART_COLORS[2] },
            ]}
          />

          {mlQ.isError && <Alert type="error" showIcon message="加载中长期负荷预测失败" style={{ marginBottom: 16 }} />}
          <ChartCard title="中长期负荷预测（月度，含置信区间）" option={mlOption} loading={mlQ.isLoading} height={380} />

          {shortQ.isError && <Alert type="error" showIcon message="加载短期预测列表失败" style={{ marginBottom: 16 }} />}
          <Card size="small" title="短期负荷预测批次（近 30 天）" style={{ marginBottom: 16 }}>
            <Table
              rowKey="forecast_date"
              size="small"
              columns={columns}
              dataSource={shortRows}
              loading={shortQ.isLoading}
              pagination={{ pageSize: 8, hideOnSinglePage: true }}
            />
          </Card>
        </>
      )}

      {view === 'trend' && (
        <>
          {trendQ.isError && <Alert type="error" showIcon message="加载电量趋势失败" style={{ marginBottom: 16 }} />}
          <ChartCard title={`总电量趋势（${monthStr}）`} option={trendOption} loading={trendQ.isLoading} height={380} />
        </>
      )}
    </div>
  );
}
