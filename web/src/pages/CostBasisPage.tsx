import { useCallback, useEffect, useState } from 'react';
import {
  Alert, App, Button, Card, Col, DatePicker, Empty, InputNumber, Row, Select, Space,
  Statistic, Table, Tag, Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { ReloadOutlined, CalculatorOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  fetchCostBasis,
  fetchCostBasisList,
  recomputeCostBasis,
  type CostBasis,
  type CostBasisMonthRow,
  type CostComponent,
} from '@/api/costBasis';
import { fetchCustomers, type CustomerListItem } from '@/api/customers';

const { Text } = Typography;

const fmt = (v: number | null | undefined, d = 2) => (v == null ? '—' : Number(v).toFixed(d));

export default function CostBasisPage() {
  const { message } = App.useApp();
  const [month, setMonth] = useState<string>(dayjs().format('YYYY-MM'));
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [customerId, setCustomerId] = useState<string>('');
  const [cc, setCc] = useState<number>(0);
  const [imb, setImb] = useState<number>(0);
  const [ma, setMa] = useState<number>(0);
  const [data, setData] = useState<CostBasis | null>(null);
  const [rows, setRows] = useState<CostBasisMonthRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [computing, setComputing] = useState(false);

  useEffect(() => {
    fetchCustomers({ page: 1, page_size: 200 })
      .then((r) => setCustomers(r.items as CustomerListItem[]))
      .catch(() => setCustomers([]));
  }, []);

  const load = useCallback(() => {
    setLoading(true);
    fetchCostBasis({ month, customer_id: customerId || undefined })
      .then((r) => setData(r))
      .catch((e) => message.error(e?.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, [month, customerId, message]);

  const loadList = useCallback(() => {
    fetchCostBasisList(24).then((r) => setRows(r.rows)).catch(() => setRows([]));
  }, []);

  useEffect(() => { load(); }, [load]);
  useEffect(() => { loadList(); }, [loadList]);

  const handleRecompute = async () => {
    setComputing(true);
    try {
      const r = await recomputeCostBasis({
        month,
        customer_id: customerId || undefined,
        share: { cost_compensation: cc, imbalance: imb, market_adjust: ma },
      });
      setData(r);
      message.success('成本基线已重算');
      loadList();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '计算失败');
    } finally {
      setComputing(false);
    }
  };

  const compCols: ColumnsType<CostComponent> = [
    { title: '成本项', dataIndex: 'name', width: 140 },
    { title: '电量(MWh)', dataIndex: 'mwh', width: 130, render: (v: number) => fmt(v, 2) },
    { title: '单价(元/MWh)', dataIndex: 'price', width: 140, render: (v: number | null) => fmt(v, 3) },
    { title: '金额(元)', dataIndex: 'amount', width: 150, render: (v: number) => fmt(v, 2) },
    { title: '占比', width: 100, render: (_, r) => {
        const total = data?.total_cost || 0;
        return total > 0 ? `${((r.amount / total) * 100).toFixed(1)}%` : '—';
      } },
    { title: '数据源', dataIndex: 'source', width: 190, render: (v: string) => <Tag>{v}</Tag> },
  ];

  const histCols: ColumnsType<CostBasisMonthRow> = [
    { title: '月份', dataIndex: 'month', width: 100 },
    { title: '客户', dataIndex: 'customer_id', width: 200, render: (v) => v ? v : <Tag color="blue">全部汇总</Tag> },
    { title: '总电量(MWh)', dataIndex: 'total_mwh', width: 130, render: (v: number) => fmt(v, 2) },
    { title: '成本单价(元/MWh)', dataIndex: 'unit_cost', width: 160, render: (v: number | null) => <b>{fmt(v, 3)}</b> },
    { title: '覆盖率', dataIndex: 'coverage_ratio', width: 100, render: (v: number | null) =>
        v == null ? '—' : <span style={{ color: v < 0.7 ? '#cf1322' : (v > 1 ? '#d46b08' : '#389e0d') }}>{(v * 100).toFixed(1)}%</span> },
    { title: '计算时间', dataIndex: 'computed_at', width: 170, render: (v?: string) => (v ? dayjs(v).format('MM-DD HH:mm') : '—') },
  ];

  const cov = data?.coverage_ratio;

  return (
    <div style={{ padding: 16 }}>
      <Card title="成本基线（事前综合购电成本）" style={{ marginBottom: 16 }}>
        <Alert
          type="info" showIcon style={{ marginBottom: 16 }}
          message="打通「合约 + 现货 + 分摊 → 综合成本」，为报价策略提供成本底线。"
          description="成本 = 中长期合约成本 + 现货采购成本（敞口×日前现货均价）+ 三类分摊。现货成本默认用日前现货均价口径。"
        />
        <Row gutter={12} style={{ marginBottom: 12 }}>
          <Col xs={24} md={4}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>月份</div>
            <DatePicker
              picker="month" style={{ width: '100%' }}
              value={dayjs(month)}
              onChange={(v) => setMonth(v ? v.format('YYYY-MM') : month)}
            />
          </Col>
          <Col xs={24} md={6}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>客户（不选=全部汇总）</div>
            <Select
              style={{ width: '100%' }} allowClear
              value={customerId || undefined}
              onChange={(v) => setCustomerId(v || '')}
              placeholder="全部客户汇总"
              options={customers.map((c) => ({ label: c.user_name, value: c.id }))}
            />
          </Col>
          <Col xs={8} md={3}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>成本补偿</div>
            <InputNumber style={{ width: '100%' }} value={cc} onChange={(v) => setCc(Number(v) || 0)} step={0.1} />
          </Col>
          <Col xs={8} md={3}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>不平衡</div>
            <InputNumber style={{ width: '100%' }} value={imb} onChange={(v) => setImb(Number(v) || 0)} step={0.1} />
          </Col>
          <Col xs={8} md={3}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>市场调节</div>
            <InputNumber style={{ width: '100%' }} value={ma} onChange={(v) => setMa(Number(v) || 0)} step={0.1} />
          </Col>
          <Col xs={24} md={5} style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
            <Button icon={<ReloadOutlined />} onClick={load} loading={loading}>刷新</Button>
            <Button type="primary" icon={<CalculatorOutlined />} onClick={handleRecompute} loading={computing}>
              重算成本
            </Button>
          </Col>
        </Row>
        <Text type="secondary" style={{ fontSize: 12 }}>分摊单位：元/MWh；默认 0（不臆造，请按实际行情填写）</Text>
      </Card>

      {data && (
        <>
          <Card title={`${data.month} 成本基线`} style={{ marginBottom: 16 }}>
            <Row gutter={16} style={{ marginBottom: 16 }}>
              <Col xs={12} md={4}><Statistic title="总电量(MWh)" value={data.total_mwh} precision={2} /></Col>
              <Col xs={12} md={4}><Statistic title="持仓(MWh)" value={data.position_mwh} precision={2} /></Col>
              <Col xs={12} md={4}><Statistic title="敞口(MWh)" value={data.exposure_mwh} precision={2} /></Col>
              <Col xs={12} md={4}>
                <Statistic
                  title="覆盖率" value={cov == null ? 0 : cov * 100} precision={1} suffix="%"
                  valueStyle={{ color: cov == null ? undefined : (cov < 0.7 ? '#cf1322' : (cov > 1 ? '#d46b08' : '#389e0d')) }}
                />
              </Col>
              <Col xs={12} md={4}>
                <Statistic
                  title="成本单价(元/MWh)" value={data.unit_cost ?? 0} precision={3}
                  valueStyle={{ color: '#1F8FD0', fontWeight: 700 }}
                />
              </Col>
              <Col xs={12} md={4}><Statistic title="总成本(元)" value={data.total_cost} precision={2} /></Col>
            </Row>

            {data.warnings.length > 0 && (
              <Alert
                type="warning" showIcon style={{ marginBottom: 12 }}
                message={`数据提示 ${data.warnings.length} 条`}
                description={<div>{data.warnings.map((w, i) => <div key={i}>• {w}</div>)}</div>}
              />
            )}

            <Table
              size="small" rowKey="name"
              columns={compCols} dataSource={data.components}
              pagination={false}
              summary={() => (
                <Table.Summary.Row>
                  <Table.Summary.Cell index={0}><b>合计</b></Table.Summary.Cell>
                  <Table.Summary.Cell index={1}><b>{fmt(data.total_mwh, 2)}</b></Table.Summary.Cell>
                  <Table.Summary.Cell index={2}><b>{fmt(data.unit_cost, 3)}</b></Table.Summary.Cell>
                  <Table.Summary.Cell index={3}><b>{fmt(data.total_cost, 2)}</b></Table.Summary.Cell>
                  <Table.Summary.Cell index={4}>100%</Table.Summary.Cell>
                  <Table.Summary.Cell index={5} />
                </Table.Summary.Row>
              )}
            />
          </Card>
        </>
      )}

      <Card title="成本基线月度概览" extra={<Text type="secondary">最近 24 条</Text>}>
        <Table
          size="small" rowKey={(r) => `${r.month}-${r.customer_id || 'all'}`}
          columns={histCols} dataSource={rows}
          pagination={{ pageSize: 12 }}
          locale={{ emptyText: <Empty description="暂无成本基线，请选择月份后点「重算成本」" /> }}
        />
      </Card>
    </div>
  );
}
