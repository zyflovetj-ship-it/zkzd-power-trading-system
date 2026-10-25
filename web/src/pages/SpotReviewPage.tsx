import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Col, DatePicker, Empty, Row, Select, Space, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import dayjs, { type Dayjs } from 'dayjs';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import { fetchCustomers } from '@/api/customers';
import {
  get96PointData,
  getReviewForecastAccuracy,
  getTimeSlotAnalysis,
  type NinetySixPointRow,
  type TimeSlotRow,
} from '@/api/spotReview';

/** 现货交易复盘：96 点实际 vs 预测对比 + 时段分析 + 预测精度 */
export default function SpotReviewPage() {
  const [customerId, setCustomerId] = useState<string | undefined>();
  const [date, setDate] = useState<Dayjs>(dayjs().subtract(1, 'day'));
  const dateStr = date.format('YYYY-MM-DD');

  const customersQ = useQuery({
    queryKey: ['spotReviewCustomers'],
    queryFn: () => fetchCustomers({ page: 1, page_size: 100 }),
  });

  const enabled = !!customerId;
  const pointsQ = useQuery({
    queryKey: ['spot96', customerId, dateStr],
    queryFn: () => get96PointData(customerId as string, dateStr),
    enabled,
  });
  const slotsQ = useQuery({
    queryKey: ['spotSlots', customerId, dateStr],
    queryFn: () => getTimeSlotAnalysis(customerId as string, dateStr),
    enabled,
  });
  const accQ = useQuery({
    queryKey: ['spotAcc', customerId, dateStr],
    queryFn: () => getReviewForecastAccuracy(customerId as string, dateStr),
    enabled,
  });

  const rows = pointsQ.data?.data ?? [];
  const slots = slotsQ.data?.time_slot_analysis ?? [];
  const acc = accQ.data?.forecast_accuracy;

  // 电量对比：实际 vs 预测（柱）
  const volumeOption: EChartsOption = useMemo(
    () => ({
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: ['实际电量', '预测电量'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: rows.map((r) => r.time), axisLabel: { interval: 11, fontSize: 11 } },
      yAxis: { type: 'value', name: 'MWh' },
      series: [
        { name: '实际电量', type: 'bar', data: rows.map((r) => r.actual_volume), itemStyle: { color: CHART_COLORS[0] } },
        { name: '预测电量', type: 'bar', data: rows.map((r) => r.forecast_volume), itemStyle: { color: CHART_COLORS[2] } },
      ],
    }),
    [rows],
  );

  // 价格对比：实际 vs 预测（线）
  const priceOption: EChartsOption = useMemo(
    () => ({
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: ['实际电价', '预测电价'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: rows.map((r) => r.time), axisLabel: { interval: 11, fontSize: 11 } },
      yAxis: { type: 'value', name: '元/MWh' },
      series: [
        { name: '实际电价', type: 'line', smooth: true, showSymbol: false, data: rows.map((r) => r.actual_price), itemStyle: { color: CHART_COLORS[1] } },
        { name: '预测电价', type: 'line', smooth: true, showSymbol: false, data: rows.map((r) => r.forecast_price), itemStyle: { color: CHART_COLORS[6] } },
      ],
    }),
    [rows],
  );

  const pointColumns: ColumnsType<NinetySixPointRow> = [
    { title: '时刻', dataIndex: 'time', width: 80 },
    { title: '实际电量', dataIndex: 'actual_volume', width: 110, align: 'right', render: (v: number) => v.toFixed(4) },
    { title: '预测电量', dataIndex: 'forecast_volume', width: 110, align: 'right', render: (v: number) => v.toFixed(4) },
    {
      title: '电量偏差率', dataIndex: 'volume_deviation_rate', width: 120, align: 'right',
      render: (v: number) => <span style={{ color: Math.abs(v) > 0.05 ? '#f5222d' : undefined }}>{(v * 100).toFixed(2)}%</span>,
    },
    { title: '实际电价', dataIndex: 'actual_price', width: 110, align: 'right', render: (v: number) => v.toFixed(2) },
    { title: '预测电价', dataIndex: 'forecast_price', width: 110, align: 'right', render: (v: number) => v.toFixed(2) },
    { title: '电价偏差', dataIndex: 'price_deviation', width: 110, align: 'right', render: (v: number) => v.toFixed(2) },
    { title: '实际费用', dataIndex: 'actual_cost', width: 120, align: 'right', render: (v: number) => v.toFixed(2) },
  ];

  const slotColumns: ColumnsType<TimeSlotRow> = [
    { title: '时段', dataIndex: 'slot_name', width: 100, render: (v: string) => <Tag color="blue">{v}</Tag> },
    { title: '电量占比', dataIndex: 'volume_ratio', align: 'right', render: (v: number) => (v * 100).toFixed(2) + '%' },
    { title: '费用占比', dataIndex: 'cost_ratio', align: 'right', render: (v: number) => (v * 100).toFixed(2) + '%' },
    { title: '均价(元/MWh)', dataIndex: 'avg_price', align: 'right', render: (v: number) => v.toFixed(2) },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card
        size="small"
        title="现货交易复盘"
        extra={
          <Space>
            <Select
              style={{ width: 260 }}
              placeholder="选择客户"
              loading={customersQ.isLoading}
              value={customerId}
              onChange={setCustomerId}
              options={(customersQ.data?.items ?? []).map((c) => ({
                label: c.user_name + (c.short_name ? '(' + c.short_name + ')' : ''),
                value: c.id,
              }))}
            />
            <DatePicker value={date} onChange={(d) => d && setDate(d)} allowClear={false} />
          </Space>
        }
      >
        {!enabled ? (
          <Empty description="请先选择客户" />
        ) : (
          <KpiCards
            columns={4}
            loading={accQ.isLoading}
            items={[
              { label: 'MAE', value: (acc?.mae ?? 0).toFixed(4), color: CHART_COLORS[0] },
              { label: 'MAPE', value: ((acc?.mape ?? 0) * 100).toFixed(2) + '%', color: CHART_COLORS[2] },
              { label: 'RMSE', value: (acc?.rmse ?? 0).toFixed(4), color: CHART_COLORS[5] },
              { label: '5% 以内命中率', value: ((acc?.within_5pct_rate ?? 0) * 100).toFixed(2) + '%', color: CHART_COLORS[3] },
            ]}
          />
        )}
      </Card>

      {enabled && (
        <>
          <Row gutter={[16, 16]}>
            <Col xs={24} xl={12}>
              <ChartCard title="96 点电量：实际 vs 预测" option={volumeOption} height={320} loading={pointsQ.isLoading} />
            </Col>
            <Col xs={24} xl={12}>
              <ChartCard title="96 点电价：实际 vs 预测" option={priceOption} height={320} loading={pointsQ.isLoading} />
            </Col>
          </Row>

          <Card size="small" title="时段分析" loading={slotsQ.isLoading}>
            <Table
              size="small"
              rowKey="slot_name"
              columns={slotColumns}
              dataSource={slots}
              pagination={false}
            />
          </Card>

          <Card size="small" title={'96 点明细（' + rows.length + ' 点）'} loading={pointsQ.isLoading}>
            <Table
              size="small"
              rowKey="time"
              columns={pointColumns}
              dataSource={rows}
              pagination={{ pageSize: 12, size: 'small' }}
              scroll={{ x: 1000 }}
            />
          </Card>
        </>
      )}
    </Space>
  );
}
