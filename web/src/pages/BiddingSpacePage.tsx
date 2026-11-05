import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Card, Descriptions, Select, Space, Statistic, Table, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import {
  fetchBiddingDates,
  fetchBiddingSpace,
  verifyBiddingSpace,
  type BiddingPoint,
} from '@/api/biddingSpace';

const { Text, Paragraph } = Typography;

const fmt = (v: number | null | undefined, p = 0) => (v == null ? '-' : v.toFixed(p));

export default function BiddingSpacePage() {
  const datesQ = useQuery({ queryKey: ['biddingDates'], queryFn: () => fetchBiddingDates(120) });
  const dates = datesQ.data?.dates ?? [];
  const rtDates = datesQ.data?.dates_with_realtime ?? [];
  const [picked, setPicked] = useState<string | undefined>();
  // 优先默认到「有实时数据」的最新日期，避免默认落在实时缺失的日子
  const current = picked ?? rtDates[0] ?? dates[0];
  const hasRealtime = !!current && rtDates.includes(current);

  const spaceQ = useQuery({
    queryKey: ['biddingSpace', current],
    queryFn: () => fetchBiddingSpace(current as string),
    enabled: !!current,
  });
  const verifyQ = useQuery({
    queryKey: ['biddingVerify', current],
    queryFn: () => verifyBiddingSpace(current as string),
    enabled: !!current,
  });

  const points = spaceQ.data?.points ?? [];

  const chartOption: EChartsOption = useMemo(() => ({
    tooltip: { ...baseTooltip, trigger: 'axis' },
    legend: { ...baseLegend, data: ['日前竞价空间', '实时竞价空间', '偏差(实时-日前)'] },
    grid: { ...baseGrid, left: 70, right: 70 },
    xAxis: { type: 'category', data: points.map((p) => p.time_str), axisLabel: { interval: 7 } },
    yAxis: [
      { type: 'value', name: '竞价空间(MW)', scale: true },
      { type: 'value', name: '偏差(MW)', scale: true },
    ],
    series: [
      { name: '日前竞价空间', type: 'line', smooth: true, showSymbol: false,
        data: points.map((p) => p.bidding_space_da), itemStyle: { color: CHART_COLORS[0] } },
      { name: '实时竞价空间', type: 'line', smooth: true, showSymbol: false,
        data: points.map((p) => p.bidding_space_rt), itemStyle: { color: CHART_COLORS[1] } },
      { name: '偏差(实时-日前)', type: 'bar', yAxisIndex: 1,
        data: points.map((p) => p.deviation), itemStyle: { color: CHART_COLORS[2], opacity: 0.45 } },
    ],
  }), [points]);

  const columns: ColumnsType<BiddingPoint> = [
    { title: '时段', dataIndex: 'time_str', width: 80, fixed: 'left' },
    { title: '负荷', key: 'load', width: 100, render: (_: unknown, r) => fmt(r.components_da?.load) },
    { title: '光伏', key: 'pv', width: 90, render: (_: unknown, r) => fmt(r.components_da?.pv) },
    { title: '风电', key: 'wind', width: 90, render: (_: unknown, r) => fmt(r.components_da?.wind) },
    { title: '受电', key: 'tieline', width: 90, render: (_: unknown, r) => fmt(r.components_da?.tieline) },
    { title: '储能', key: 'storage', width: 90, render: (_: unknown, r) => fmt(r.components_da?.storage) },
    { title: '燃机', key: 'gas', width: 90, render: (_: unknown, r) => fmt(r.components_da?.gas) },
    { title: '煤电', key: 'coal', width: 90, render: (_: unknown, r) => fmt(r.components_da?.coal) },
    { title: '竞价空间(日前)', dataIndex: 'bidding_space_da', width: 130,
      render: (v: number | null) => <b>{fmt(v, 2)}</b> },
    { title: '竞价空间(实时)', dataIndex: 'bidding_space_rt', width: 130,
      render: (v: number | null) => fmt(v, 2) },
    { title: '偏差(实时-日前)', dataIndex: 'deviation', width: 140,
      render: (v: number | null) => (
        <span style={{ color: v == null ? undefined : v >= 0 ? '#cf1322' : '#389e0d' }}>{fmt(v, 2)}</span>
      ) },
  ];

  const v = verifyQ.data;
  const verifiedOk = !!v && v.day_ahead.mismatch === 0 && v.real_time.mismatch === 0;
  const avgDa = points.length
    ? points.reduce((s, p) => s + (p.bidding_space_da ?? 0), 0) / points.length : null;
  const avgRt = points.length
    ? points.reduce((s, p) => s + (p.bidding_space_rt ?? 0), 0) / points.length : null;

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space size="large" wrap>
          <Space>
            <Text type="secondary">日期</Text>
            <Select
              style={{ width: 180 }}
              value={current}
              placeholder={datesQ.isLoading ? '加载中…' : '选择日期'}
              options={dates.map((d) => ({
                label: rtDates.includes(d) ? d : d + '（无实时）',
                value: d,
              }))}
              onChange={setPicked}
              showSearch
            />
          </Space>
          <Text type="secondary">
            数据覆盖：{datesQ.data?.total ?? 0} 天（其中有实时竞价：{datesQ.data?.total_with_realtime ?? 0} 天）
          </Text>
        </Space>
      </Card>

      <Card title="计算规则与口径" size="small" style={{ marginBottom: 16 }}>
        <Descriptions column={1} size="small" bordered>
          <Descriptions.Item label="竞价空间（日前）">
            <Paragraph style={{ margin: 0 }}>
              <Text code>短期系统负荷 − 光伏 − 风电 − 受电计划 − 储能发电计划 − 燃机固定出力 − 煤电发电计划</Text>
            </Paragraph>
          </Descriptions.Item>
          <Descriptions.Item label="竞价空间（实时）">
            <Paragraph style={{ margin: 0 }}>
              <Text code>实际系统负荷 − 光伏 − 风电 − 受电潮流 − 储能 − 燃机 − 煤电</Text>（同一口径，数据取实时页）
            </Paragraph>
          </Descriptions.Item>
          <Descriptions.Item label="偏差">
            <Text code>偏差 = 实时竞价空间 − 日前竞价空间</Text>
          </Descriptions.Item>
          <Descriptions.Item label="数据来源">
            交易中心/调度日文件「日前」「实时」页 → 表 <Text code>daily_release</Text> /{' '}
            <Text code>actual_operation</Text> / <Text code>real_time_generation</Text>
          </Descriptions.Item>
          <Descriptions.Item label="校验规则">
            用上述公式重算，与文件发布值逐点比对，误差阈值 <Text code>0.05 MW</Text>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card size="small" style={{ marginBottom: 16 }}>
        <Space size="large" wrap>
          <Statistic title="日前竞价空间均值(MW)" value={avgDa ?? 0} precision={2} />
          <Statistic title="实时竞价空间均值(MW)" value={avgRt ?? 0} precision={2} />
          <Statistic title="96点数据" value={points.length} />
          <div>
            <Text type="secondary">公式校验：</Text>
            {verifyQ.isLoading ? (
              <Tag>校验中…</Tag>
            ) : verifiedOk ? (
              <Tag color="green">通过（日前 {v?.day_ahead.checked} 点 / 实时 {v?.real_time.checked} 点，0 处不符）</Tag>
            ) : (
              <Tag color="red">
                不符：日前 {v?.day_ahead.mismatch} 点 / 实时 {v?.real_time.mismatch} 点
              </Tag>
            )}
          </div>
        </Space>
      </Card>

      {current && !hasRealtime && !datesQ.isLoading && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message={'该日（' + current + '）无实时竞价空间数据'}
          description="源文件「实时」页当日数据未发布（全为 0），实时曲线与偏差将显示为 0；可切换到上方「有实时数据」的其他日期。"
        />
      )}

      {spaceQ.isError && (
        <Alert type="error" showIcon style={{ marginBottom: 16 }}
          message="该日期无竞价空间数据（请先在日文件中导入）" />
      )}

      <ChartCard title="96 点竞价空间（日前 / 实时 / 偏差）" option={chartOption}
        loading={spaceQ.isLoading} height={380} />

      <Card title="成分明细（96 点，日前口径展开）" size="small">
        <Table<BiddingPoint>
          rowKey="time_str"
          size="small"
          columns={columns}
          dataSource={points}
          loading={spaceQ.isLoading}
          pagination={false}
          scroll={{ x: 'max-content', y: 460 }}
        />
      </Card>
    </div>
  );
}
