import { useState, useMemo } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Card, Table, Button, InputNumber, Space, Row, Col, message, Tag } from 'antd';
import { ReloadOutlined, DownloadOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import { runCustomerCluster, type ClusterResultItem, type ClusterSummaryItem } from '@/api/cluster';

const CLUSTER_COLORS = ['#1976d2', '#2e7d32', '#ed6c02', '#9c27b0', '#d32f2f', '#0097a7', '#7b1fa2', '#f57c00', '#388e3c', '#c62828'];

const FEATURE_LABELS: Record<string, string> = {
  peak_valley_ratio: '峰谷比',
  load_rate: '负荷率',
  volatility: '波动性',
};

export default function CustomerClusterPage() {
  const [nClusters, setNClusters] = useState(3);
  const mutation = useMutation({
    mutationFn: () => runCustomerCluster(nClusters),
    onError: () => message.error('聚类分析失败'),
  });

  const data = mutation.data;
  const isLoading = mutation.isPending;
  const results = data?.results ?? [];
  const summary = data?.summary ?? [];
  const totalCustomers = results.length;

  const clusterCustomers = useMemo(() => {
    const map: Record<number, ClusterResultItem[]> = {};
    results.forEach((r) => {
      if (!map[r.cluster]) map[r.cluster] = [];
      map[r.cluster].push(r);
    });
    return map;
  }, [results]);

  const scatterOption: EChartsOption = useMemo(() => {
    const series = Object.entries(clusterCustomers).map(([clusterId, items]) => ({
      name: `簇${clusterId}`,
      type: 'scatter' as const,
      data: items.map((i) => ({
        value: [i.features.peak_valley_ratio, i.features.load_rate],
        name: i.customer_name,
      })),
      symbolSize: 14,
      itemStyle: {
        color: CLUSTER_COLORS[Number(clusterId) % CLUSTER_COLORS.length],
        opacity: 0.85,
        borderColor: '#fff',
        borderWidth: 1,
      },
      emphasis: { itemStyle: { borderColor: '#333', borderWidth: 2, shadowBlur: 6 } },
    }));
    return {
      tooltip: {
        trigger: 'item',
        confine: true,
        formatter: (params: any) => {
          const d = params.data;
          return `<b>${d.name}</b><br/>簇${params.seriesName.replace('簇', '')}<br/>峰谷比: ${d.value[0].toFixed(4)}<br/>负荷率: ${d.value[1].toFixed(4)}`;
        },
      },
      legend: { ...baseLegend, data: Object.keys(clusterCustomers).map((k) => `簇${k}`) },
      grid: { ...baseGrid, top: 64 },
      xAxis: { type: 'value', name: '峰谷比', scale: true, nameLocation: 'middle', nameGap: 28 },
      yAxis: { type: 'value', name: '负荷率', scale: true, nameLocation: 'middle', nameGap: 40 },
      series,
    };
  }, [clusterCustomers]);

  const radarOption: EChartsOption = useMemo(() => {
    const indicators = [
      { name: '峰谷比', max: Math.max(0.01, ...summary.map((s) => s.avg_peak_valley_ratio)) * 1.2 },
      { name: '负荷率', max: 1 },
      { name: '波动性', max: Math.max(0.01, ...summary.map((s) => s.avg_volatility)) * 1.2 },
    ];
    const seriesData = summary.map((s) => ({
      name: `簇${s.cluster_id}（${s.count}户）`,
      value: [s.avg_peak_valley_ratio, s.avg_load_rate, s.avg_volatility],
      areaStyle: { opacity: 0.15 },
      lineStyle: { width: 2, color: CLUSTER_COLORS[s.cluster_id % CLUSTER_COLORS.length] },
      itemStyle: { color: CLUSTER_COLORS[s.cluster_id % CLUSTER_COLORS.length] },
    }));
    return {
      tooltip: { trigger: 'item' },
      legend: { ...baseLegend, data: summary.map((s) => `簇${s.cluster_id}（${s.count}户）`) },
      radar: {
        indicator: indicators,
        shape: 'polygon',
        splitNumber: 5,
        axisName: { color: '#666', fontSize: 12 },
        splitArea: { areaStyle: { color: ['rgba(25,118,210,0.02)', 'rgba(25,118,210,0.04)'] } },
      },
      series: [{ type: 'radar' as const, data: seriesData, symbol: 'circle', symbolSize: 6 }],
    };
  }, [summary]);

  const summaryColumns: ColumnsType<ClusterSummaryItem> = [
    {
      title: '簇ID',
      dataIndex: 'cluster_id',
      width: 80,
      render: (v: number) => <Tag color={CLUSTER_COLORS[v % CLUSTER_COLORS.length]}>簇{v}</Tag>,
    },
    { title: '客户数', dataIndex: 'count', width: 100 },
    { title: '平均峰谷比', dataIndex: 'avg_peak_valley_ratio', width: 120, render: (v: number) => v.toFixed(4) },
    { title: '平均负荷率', dataIndex: 'avg_load_rate', width: 120, render: (v: number) => v.toFixed(4) },
    { title: '平均波动性', dataIndex: 'avg_volatility', width: 120, render: (v: number) => v.toFixed(4) },
  ];

  const detailColumns: ColumnsType<ClusterResultItem> = [
    { title: '客户名称', dataIndex: 'customer_name', width: 150 },
    {
      title: '所属簇',
      dataIndex: 'cluster',
      width: 80,
      render: (v: number) => <Tag color={CLUSTER_COLORS[v % CLUSTER_COLORS.length]}>簇{v}</Tag>,
    },
    { title: '峰谷比', dataIndex: ['features', 'peak_valley_ratio'], width: 100, render: (v: number) => v?.toFixed(4) },
    { title: '负荷率', dataIndex: ['features', 'load_rate'], width: 100, render: (v: number) => v?.toFixed(4) },
    { title: '波动性', dataIndex: ['features', 'volatility'], width: 100, render: (v: number) => v?.toFixed(4) },
  ];

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <span>聚类数：</span>
          <InputNumber min={2} max={10} value={nClusters} onChange={(v) => setNClusters(v ?? 3)} disabled={isLoading} />
          <Button type="primary" icon={<ReloadOutlined />} onClick={() => mutation.mutate()} loading={isLoading}>
            {isLoading ? '聚类中...' : '执行聚类'}
          </Button>
          {data && (
            <Button icon={<DownloadOutlined />} onClick={() => window.open(`/api/v1/customer-cluster/export?n_clusters=${nClusters}`, '_blank')}>
              导出
            </Button>
          )}
        </Space>
      </Card>

      {data && (
        <>
          <KpiCards
            loading={false}
            items={[
              { label: '客户数', value: totalCustomers, suffix: '户', color: CHART_COLORS[0] },
              { label: '聚类簇数', value: summary.length, suffix: '簇', color: CHART_COLORS[1] },
              { label: '最大簇客户数', value: Math.max(0, ...summary.map((s) => s.count)), suffix: '户', color: CHART_COLORS[2] },
              { label: '平均负荷率', value: summary.reduce((s, c) => s + c.avg_load_rate, 0) / summary.length || 0, precision: 4, color: CHART_COLORS[3] },
            ]}
          />

          <Row gutter={[16, 16]}>
            <Col xs={24} lg={14}>
              <ChartCard title="聚类散点图（x=峰谷比 / y=负荷率）" option={scatterOption} height={440} />
            </Col>
            <Col xs={24} lg={10}>
              {summary.length > 1 && (
                <ChartCard title="特征对比雷达图" option={radarOption} height={440} />
              )}
            </Col>
          </Row>

          <Card size="small" title="簇摘要" style={{ marginTop: 16, marginBottom: 16 }}>
            <Table<ClusterSummaryItem>
              rowKey={(r) => String(r.cluster_id)}
              columns={summaryColumns}
              dataSource={summary}
              pagination={false}
              scroll={{ x: 'max-content' }}
              size="small"
            />
          </Card>

          <Card size="small" title="聚类明细">
            <Table<ClusterResultItem>
              rowKey={(r) => r.customer_id}
              columns={detailColumns}
              dataSource={results}
              pagination={{ pageSize: 10, hideOnSinglePage: true }}
              scroll={{ x: 'max-content' }}
              size="small"
            />
          </Card>
        </>
      )}
    </div>
  );
}
