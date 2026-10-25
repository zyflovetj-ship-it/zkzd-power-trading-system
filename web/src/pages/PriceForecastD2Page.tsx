import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Card, DatePicker, Segmented, Space, Table } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs, { Dayjs } from 'dayjs';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { getD2ByDate, getD2Comparison, getD2AccuracyStats, type D2AccRecord } from '@/api/priceForecast';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';

type View = 'forecast' | 'compare' | 'accuracy';

const VIEWS = [
  { label: '预测曲线', value: 'forecast' },
  { label: '预测对比', value: 'compare' },
  { label: '精度统计', value: 'accuracy' },
];

// D-2 价格预测：按预测日查预测曲线（含置信带）/ 按目标日查预测vs实际 / 区间精度统计。
export default function PriceForecastD2Page() {
  const [view, setView] = useState<View>('forecast');
  const [forecastDate, setForecastDate] = useState<Dayjs>(dayjs().subtract(2, 'day'));
  const [targetDate, setTargetDate] = useState<Dayjs>(dayjs().subtract(1, 'day'));
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs().subtract(30, 'day'), dayjs()]);

  const fdStr = forecastDate.format('YYYY-MM-DD');
  const tdStr = targetDate.format('YYYY-MM-DD');
  const start = range[0].format('YYYY-MM-DD');
  const end = range[1].format('YYYY-MM-DD');

  const fcQ = useQuery({ queryKey: ['d2fc', fdStr], enabled: view === 'forecast', queryFn: () => getD2ByDate(fdStr) });
  const cmpQ = useQuery({ queryKey: ['d2cmp', tdStr], enabled: view === 'compare', queryFn: () => getD2Comparison(tdStr) });
  const accQ = useQuery({ queryKey: ['d2acc', start, end], enabled: view === 'accuracy', queryFn: () => getD2AccuracyStats(start, end) });

  const fcData = fcQ.data?.data ?? [];
  const targets = fcQ.data?.target_dates ?? [];

  const renderView = () => {
    if (view === 'forecast') {
      const option: EChartsOption = {
        color: CHART_COLORS,
        tooltip: { ...baseTooltip },
        legend: { ...baseLegend, data: ['预测价', '90%置信', '80%置信'] },
        grid: baseGrid,
        xAxis: { type: 'category', data: fcData.map((p) => p.datetime.slice(11, 16)), name: '时刻', boundaryGap: false },
        yAxis: { type: 'value', name: '价格(元/MWh)', scale: true },
        series: [
          {
            name: '90%下限',
            type: 'line',
            data: fcData.map((p) => p.confidence_90_lower),
            lineStyle: { opacity: 0 },
            stack: 'c90',
            symbol: 'none',
            areaStyle: { opacity: 0 },
          },
          {
            name: '90%置信',
            type: 'line',
            data: fcData.map((p) => p.confidence_90_upper - p.confidence_90_lower),
            lineStyle: { opacity: 0 },
            stack: 'c90',
            symbol: 'none',
            areaStyle: { color: 'rgba(9,88,217,0.08)' },
          },
          {
            name: '80%下限',
            type: 'line',
            data: fcData.map((p) => p.confidence_80_lower),
            lineStyle: { opacity: 0 },
            stack: 'c80',
            symbol: 'none',
            areaStyle: { opacity: 0 },
          },
          {
            name: '80%置信',
            type: 'line',
            data: fcData.map((p) => p.confidence_80_upper - p.confidence_80_lower),
            lineStyle: { opacity: 0 },
            stack: 'c80',
            symbol: 'none',
            areaStyle: { color: 'rgba(19,194,194,0.14)' },
          },
          {
            name: '预测价',
            type: 'line',
            data: fcData.map((p) => p.predicted_price),
            symbol: 'circle',
            symbolSize: 5,
            itemStyle: { color: CHART_COLORS[0] },
            z: 3,
          },
        ],
      };
      return (
        <>
          <KpiCards
            loading={fcQ.isLoading}
            items={[
              { label: '目标日数量', value: targets.length, color: CHART_COLORS[0] },
              { label: '预测点数', value: fcData.length, color: CHART_COLORS[1] },
              { label: '预测均值', value: fcData.length ? fcData.reduce((s, p) => s + p.predicted_price, 0) / fcData.length : '-', precision: 1, suffix: '元/MWh', color: CHART_COLORS[2] },
            ]}
          />
          <ChartCard title={`D-2 价格预测曲线（预测日 ${fdStr}）`} option={option} loading={fcQ.isLoading} height={400} />
        </>
      );
    }

    if (view === 'compare') {
      const d = cmpQ.data?.data ?? [];
      const m = cmpQ.data?.metrics;
      const option: EChartsOption = {
        color: CHART_COLORS,
        tooltip: { ...baseTooltip },
        legend: { ...baseLegend, data: ['预测', '实际', '偏差'] },
        grid: baseGrid,
        xAxis: { type: 'category', data: d.map((p) => p.time), name: '时刻', boundaryGap: false },
        yAxis: [
          { type: 'value', name: '价格(元/MWh)', scale: true },
          { type: 'value', name: '偏差', position: 'right', scale: true },
        ],
        series: [
          { name: '预测', type: 'line', smooth: true, showSymbol: false, data: d.map((p) => p.predicted), yAxisIndex: 0, itemStyle: { color: CHART_COLORS[0] } },
          { name: '实际', type: 'line', smooth: true, showSymbol: false, connectNulls: false, data: d.map((p) => p.actual), yAxisIndex: 0, itemStyle: { color: CHART_COLORS[2] } },
          { name: '偏差', type: 'bar', data: d.map((p) => p.difference), yAxisIndex: 1, itemStyle: { color: CHART_COLORS[3], opacity: 0.5 } },
        ],
      };
      return (
        <>
          <KpiCards
            loading={cmpQ.isLoading}
            items={[
              { label: 'MAE', value: m?.mae ?? '-', precision: 2, color: CHART_COLORS[0] },
              { label: 'RMSE', value: m?.rmse ?? '-', precision: 2, color: CHART_COLORS[1] },
              { label: 'MAPE', value: m?.mape ?? '-', precision: 2, suffix: '%', color: CHART_COLORS[2] },
              { label: '准确率', value: m?.accuracy ?? '-', precision: 2, suffix: '%', color: CHART_COLORS[3] },
            ]}
          />
          <ChartCard title={`D-2 预测 vs 实际（目标日 ${tdStr}）`} option={option} loading={cmpQ.isLoading} height={400} />
        </>
      );
    }

    // accuracy
    const records: D2AccRecord[] = accQ.data?.records ?? [];
    const columns: ColumnsType<D2AccRecord> = [
      { title: '目标日', dataIndex: 'target_date', key: 'target_date' },
      { title: 'WMAPE精度', dataIndex: 'wmape_accuracy', key: 'wmape_accuracy', render: (v: number) => `${v.toFixed(2)}%` },
      { title: 'MAE', dataIndex: 'mae', key: 'mae', render: (v: number) => v.toFixed(2) },
      { title: 'RMSE', dataIndex: 'rmse', key: 'rmse', render: (v: number) => v.toFixed(2) },
      { title: 'MAPE', dataIndex: 'mape', key: 'mape', render: (v: number) => `${v.toFixed(2)}%` },
      { title: '方向精度', dataIndex: 'direction_accuracy', key: 'direction_accuracy', render: (v: number) => `${v.toFixed(2)}%` },
    ];
    const accOption: EChartsOption = {
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      grid: baseGrid,
      xAxis: { type: 'category', data: records.map((r) => r.target_date), name: '目标日', axisLabel: { rotate: 60, fontSize: 9 } },
      yAxis: { type: 'value', name: 'WMAPE精度', scale: true },
      series: [
        {
          name: 'WMAPE精度',
          type: 'bar',
          data: records.map((r) => r.wmape_accuracy),
          itemStyle: { color: CHART_COLORS[0] },
        },
      ],
    };
    return (
      <>
        <KpiCards
          loading={accQ.isLoading}
          items={[
            { label: '月度均值', value: accQ.data?.monthly_avg ?? '-', precision: 2, color: CHART_COLORS[0] },
            { label: '达标(90%)天数', value: `${accQ.data?.pass_90_count ?? '-'}/${accQ.data?.total_days ?? '-'}`, color: CHART_COLORS[2] },
            { label: '最佳日', value: accQ.data?.best_day?.date ?? '-', color: CHART_COLORS[3] },
            { label: '最差日', value: accQ.data?.worst_day?.date ?? '-', color: CHART_COLORS[4] },
          ]}
        />
        <ChartCard title="D-2 预测每日精度（WMAPE）" option={accOption} loading={accQ.isLoading} height={340} />
        <Card size="small" title="精度明细" style={{ marginTop: 16 }}>
          <Table
            rowKey="target_date"
            size="small"
            columns={columns}
            dataSource={records}
            loading={accQ.isLoading}
            pagination={{ pageSize: 10, hideOnSinglePage: true }}
          />
        </Card>
      </>
    );
  };

  const activeQ = { forecast: fcQ, compare: cmpQ, accuracy: accQ }[view];

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Segmented value={view} onChange={(v) => setView(v as View)} options={VIEWS} />
          {view === 'forecast' && (
            <DatePicker value={forecastDate} onChange={(d) => d && setForecastDate(d)} allowClear={false} />
          )}
          {view === 'compare' && (
            <DatePicker value={targetDate} onChange={(d) => d && setTargetDate(d)} allowClear={false} />
          )}
          {view === 'accuracy' && (
            <DatePicker.RangePicker
              value={range}
              onChange={(r) => {
                const [a, b] = r ?? [null, null];
                if (a && b) setRange([a, b]);
              }}
            />
          )}
        </Space>
      </Card>

      {activeQ?.isError && <Alert type="error" showIcon message="加载 D-2 价格预测数据失败" style={{ marginBottom: 16 }} />}
      {renderView()}
    </div>
  );
}
