import { useEffect, useState } from 'react';
import { PageContainer } from '@ant-design/pro-components';
import {
  Card,
  Col,
  Row,
  Spin,
  Table,
  Tag,
  Typography,
  Space,
} from 'antd';
import {
  TeamOutlined,
  FileTextOutlined,
  ThunderboltOutlined,
  RiseOutlined,
} from '@ant-design/icons';
import apiClient from '@/api/client';
import { KpiCards, type KpiItem } from '@/components/charts/KpiCards';
import { ChartCard } from '@/components/charts/ChartCard';
import { CHART_COLORS } from '@/components/charts/chartTheme';
import type { EChartsOption } from 'echarts';

/* ---------- 类型 ---------- */
interface DashboardData {
  kpi: {
    customer_count: number;
    active_customer_count: number;
    contract_count: number;
    active_contract_count: number;
    today_electricity: number;
    total_cost: number;
    saving_rate: number;
  };
  daily_electricity: { date: string; value: number }[];
  contract_status: { status: string; count: number }[];
  recent_activities: {
    id: string;
    type: string;
    description: string;
    timestamp: string;
  }[];
}

const STATUS_COLOR_MAP: Record<string, string> = {
  active: 'green',
  pending: 'orange',
  expired: 'default',
  prospect: 'blue',
  suspended: 'red',
  terminated: 'default',
};

const STATUS_LABEL_MAP: Record<string, string> = {
  active: '生效中',
  pending: '待生效',
  expired: '已过期',
  prospect: '意向',
  suspended: '已暂停',
  terminated: '已终止',
};

/* ---------- 组件 ---------- */
export function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setLoading(true);
    apiClient
      .get('/api/v1/dashboard')
      .then((res) => setData(res.data))
      .catch((err) =>
        setError(err.response?.data?.detail || err.message || '加载失败'),
      )
      .finally(() => setLoading(false));
  }, []);

  if (error) {
    return (
      <PageContainer header={{ title: '交易总览' }}>
        <Card>
          <Typography.Text type="danger">{error}</Typography.Text>
        </Card>
      </PageContainer>
    );
  }

  const kpi = data?.kpi;
  const kpiItems: KpiItem[] = [
    {
      label: '客户总数',
      value: kpi?.customer_count ?? 0,
      suffix: '户',
      color: '#0958d9',
    },
    {
      label: '合同总数',
      value: kpi?.contract_count ?? 0,
      suffix: '份',
      color: '#52c41a',
    },
    {
      label: '今日电量',
      value: kpi?.today_electricity ?? 0,
      precision: 2,
      suffix: 'kWh',
      color: '#fa8c16',
    },
    {
      label: '节省率',
      value: kpi?.saving_rate ?? 0,
      precision: 2,
      suffix: '%',
      color: '#722ed1',
    },
  ];

  /* --- 近30天电量趋势折线图 --- */
  const lineOption: EChartsOption = {
    tooltip: {
      trigger: 'axis',
      axisPointer: { type: 'shadow' },
    },
    grid: { left: 60, right: 20, top: 30, bottom: 36, containLabel: true },
    xAxis: {
      type: 'category',
      data: (data?.daily_electricity || []).map((d) => d.date.slice(5)),
      axisLabel: { fontSize: 11 },
    },
    yAxis: {
      type: 'value',
      name: 'kWh',
      axisLabel: { fontSize: 11 },
    },
    series: [
      {
        type: 'line',
        name: '电量',
        data: (data?.daily_electricity || []).map((d) => d.value),
        smooth: true,
        symbol: 'none',
        lineStyle: { width: 2, color: CHART_COLORS[0] },
        areaStyle: {
          color: {
            type: 'linear',
            x: 0,
            y: 0,
            x2: 0,
            y2: 1,
            colorStops: [
              { offset: 0, color: 'rgba(9,88,217,0.25)' },
              { offset: 1, color: 'rgba(9,88,217,0.02)' },
            ],
          },
        },
      },
    ],
  };

  /* --- 合同状态分布饼图 --- */
  const contractStatusData = (data?.contract_status || []).map((item) => ({
    name: STATUS_LABEL_MAP[item.status] || item.status,
    value: item.count,
  }));
  const pieOption: EChartsOption = {
    tooltip: { trigger: 'item', formatter: '{b}: {c} ({d}%)' },
    legend: { bottom: 0, type: 'scroll' },
    series: [
      {
        type: 'pie',
        radius: ['40%', '70%'],
        center: ['50%', '45%'],
        avoidLabelOverlap: true,
        itemStyle: { borderRadius: 4, borderColor: '#fff', borderWidth: 2 },
        label: { show: true, formatter: '{b}\n{d}%' },
        data: contractStatusData,
      },
    ],
    color: CHART_COLORS,
  };

  /* --- 最近动态表格 --- */
  const activityColumns = [
    {
      title: '类型',
      dataIndex: 'type',
      width: 80,
      render: (v: string) => <Tag color="blue">{v}</Tag>,
    },
    {
      title: '描述',
      dataIndex: 'description',
      ellipsis: true,
    },
    {
      title: '时间',
      dataIndex: 'timestamp',
      width: 180,
      render: (v: string) =>
        v ? new Date(v).toLocaleString('zh-CN') : '—',
    },
  ];

  return (
    <PageContainer
      header={{ title: '交易总览', subTitle: '系统核心指标与数据概览' }}
    >
      <Spin spinning={loading}>
        {/* KPI 卡片 */}
        <KpiCards items={kpiItems} loading={loading} columns={4} />

        {/* 辅助信息行 */}
        <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
          <Col xs={24} sm={12}>
            <Card size="small">
              <Space>
                <TeamOutlined style={{ color: '#0958d9' }} />
                <span>
                  执行中客户{' '}
                  <Typography.Text strong>
                    {kpi?.active_customer_count ?? 0}
                  </Typography.Text>{' '}
                  户
                </span>
              </Space>
            </Card>
          </Col>
          <Col xs={24} sm={12}>
            <Card size="small">
              <Space>
                <FileTextOutlined style={{ color: '#52c41a' }} />
                <span>
                  生效中合同{' '}
                  <Typography.Text strong>
                    {kpi?.active_contract_count ?? 0}
                  </Typography.Text>{' '}
                  份
                </span>
                <span style={{ marginLeft: 16 }}>
                  <ThunderboltOutlined style={{ color: '#fa8c16' }} />
                  {' '}累计成本 ¥
                  <Typography.Text strong>
                    {(kpi?.total_cost ?? 0).toLocaleString()}
                  </Typography.Text>
                </span>
              </Space>
            </Card>
          </Col>
        </Row>

        {/* 图表行：电量趋势 + 合同饼图 */}
        <Row gutter={[16, 16]}>
          <Col xs={24} lg={16}>
            <ChartCard
              title="近30天电量趋势"
              option={lineOption}
              height={320}
              loading={loading}
            />
          </Col>
          <Col xs={24} lg={8}>
            <ChartCard
              title="合同状态分布"
              option={pieOption}
              height={320}
              loading={loading}
            />
          </Col>
        </Row>

        {/* 最近动态表格 */}
        <Card
          title="最近动态"
          size="small"
          style={{ marginTop: 16 }}
        >
          <Table
            rowKey="id"
            size="small"
            pagination={false}
            columns={activityColumns}
            dataSource={data?.recent_activities || []}
            loading={loading}
            locale={{ emptyText: '暂无动态' }}
          />
        </Card>
      </Spin>
    </PageContainer>
  );
}
