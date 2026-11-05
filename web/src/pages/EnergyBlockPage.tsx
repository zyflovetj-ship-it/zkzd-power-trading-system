import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  DatePicker,
  Divider,
  InputNumber,
  Popconfirm,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import { DeleteOutlined, PlusOutlined, ThunderboltOutlined } from '@ant-design/icons';
import dayjs, { type Dayjs } from 'dayjs';
import type { ColumnsType } from 'antd/es/table';
import { fetchCustomers, type CustomerListItem } from '@/api/customers';
import {
  TIME_OPTIONS,
  createBlocks,
  deleteBlockSet,
  fetchBlockSets,
  validateBlocks,
  type BlockSetListItem,
  type EnergyBlockItem,
  type EnergyBlockSetCreate,
  type MarketType,
  type PeriodType,
  type ValidateResult,
} from '@/api/energyBlock';

const { Text } = Typography;

const MARKET_OPTIONS = [
  { label: '中长期', value: 'mid_long' },
  { label: '日前现货', value: 'day_ahead' },
  { label: '实时现货', value: 'real_time' },
];

const PERIOD_OPTIONS = [
  { label: '峰', value: 'peak' },
  { label: '平', value: 'flat' },
  { label: '谷', value: 'valley' },
  { label: '时刻', value: 'time' },
];

export default function EnergyBlockPage() {
  const { message } = App.useApp();
  const [marketType, setMarketType] = useState<MarketType>('day_ahead');
  const [subjectId, setSubjectId] = useState<string>();
  const [subjectName, setSubjectName] = useState<string>();
  const [startDate, setStartDate] = useState<Dayjs>(dayjs());
  const [direction, setDirection] = useState<'buy' | 'sell'>('buy');
  const [priceCap, setPriceCap] = useState<number>(1500);
  const [totalVolume, setTotalVolume] = useState<number | null>(null);
  const [ratio, setRatio] = useState<{ peak: number; flat: number; valley: number }>({
    peak: 0.3, flat: 0.4, valley: 0.3,
  });
  const [blocks, setBlocks] = useState<EnergyBlockItem[]>([]);
  const [result, setResult] = useState<ValidateResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [history, setHistory] = useState<BlockSetListItem[]>([]);

  const loadHistory = async () => {
    try {
      const r = await fetchBlockSets({ market_type: marketType });
      setHistory(r.items ?? []);
    } catch {
      setHistory([]);
    }
  };

  useEffect(() => {
    fetchCustomers({ page: 1, page_size: 100 })
      .then((r) => setCustomers(r.items as CustomerListItem[]))
      .catch(() => setCustomers([]));
    loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [marketType]);

  const addBlock = () => {
    setBlocks((b) => [
      ...b,
      { period_type: marketType === 'mid_long' ? 'peak' : 'time',
        time_str: marketType === 'mid_long' ? null : '00:00',
        segment: 1, volume_mwh: 1, price: 400 },
    ]);
  };

  const gen96 = () => {
    const v = totalVolume && totalVolume > 0 ? Number((totalVolume / 96).toFixed(4)) : 1;
    setBlocks(TIME_OPTIONS.map((t) => ({
      period_type: 'time' as PeriodType,
      time_str: t.value,
      segment: 1,
      volume_mwh: v,
      price: 400,
    })));
  };

  const updateBlock = (idx: number, patch: Partial<EnergyBlockItem>) => {
    setBlocks((b) => b.map((x, i) => (i === idx ? { ...x, ...patch } : x)));
  };

  const payload = useMemo<EnergyBlockSetCreate>(() => ({
    market_type: marketType,
    subject_type: 'customer',
    subject_id: subjectId ?? '',
    subject_name: subjectName,
    trade_period: marketType === 'mid_long' ? 'monthly' : 'daily',
    start_date: startDate.format('YYYY-MM-DD'),
    end_date: startDate.format('YYYY-MM-DD'),
    total_volume_mwh: totalVolume ?? undefined,
    expected_ratio: { peak: ratio.peak, flat: ratio.flat, valley: ratio.valley },
    direction,
    price_cap: priceCap,
    blocks,
  }), [marketType, subjectId, subjectName, startDate, totalVolume, ratio, direction, priceCap, blocks]);

  const handleValidate = async () => {
    setLoading(true);
    try {
      const r = await validateBlocks(payload);
      setResult(r);
      if (r.valid) message.success('校验通过');
      else message.error('校验未通过，见下方提示');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '校验失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!subjectId) {
      message.warning('请先选择标的客户');
      return;
    }
    setLoading(true);
    try {
      const r: any = await createBlocks(payload);
      message.success('申报成功：' + (r?.block_set_id ?? ''));
      setResult(null);
      await loadHistory();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '申报失败');
    } finally {
      setLoading(false);
    }
  };

  const columns: ColumnsType<EnergyBlockItem> = [
    {
      title: '时段类型', dataIndex: 'period_type', width: 120,
      render: (v: PeriodType, _r, i) => (
        <Select
          size="small" style={{ width: 90 }} value={v}
          options={PERIOD_OPTIONS}
          onChange={(nv) => updateBlock(i, { period_type: nv, time_str: nv === 'time' ? '00:00' : null })}
        />
      ),
    },
    {
      title: '时刻', dataIndex: 'time_str', width: 120,
      render: (v: string | null | undefined, r, i) => (
        <Select
          size="small" style={{ width: 100 }} value={v ?? undefined}
          placeholder="-" disabled={r.period_type !== 'time'}
          options={TIME_OPTIONS}
          showSearch
          onChange={(nv) => updateBlock(i, { time_str: nv })}
        />
      ),
    },
    {
      title: '段序', dataIndex: 'segment', width: 90,
      render: (v: number, _r, i) => (
        <InputNumber size="small" min={1} max={10} value={v}
          onChange={(nv) => updateBlock(i, { segment: Number(nv) || 1 })} />
      ),
    },
    {
      title: '电量(MWh)', dataIndex: 'volume_mwh', width: 130,
      render: (v: number, _r, i) => (
        <InputNumber size="small" min={0} value={v}
          onChange={(nv) => updateBlock(i, { volume_mwh: Number(nv) || 0 })} />
      ),
    },
    {
      title: '价格(元/MWh)', dataIndex: 'price', width: 140,
      render: (v: number, _r, i) => (
        <InputNumber size="small" min={0} value={v}
          onChange={(nv) => updateBlock(i, { price: Number(nv) || 0 })} />
      ),
    },
    {
      title: '操作', key: 'op', width: 80,
      render: (_: unknown, _r, i) => (
        <Button size="small" danger type="link" icon={<DeleteOutlined />}
          onClick={() => setBlocks((b) => b.filter((_, k) => k !== i))} />
      ),
    },
  ];

  const histColumns: ColumnsType<BlockSetListItem> = [
    { title: '申报批次', dataIndex: 'block_set_id', width: 160 },
    { title: '市场', dataIndex: 'market_type', width: 100, render: (v: MarketType) => MARKET_OPTIONS.find((m) => m.value === v)?.label ?? v },
    { title: '标的', dataIndex: 'subject_name', render: (v, r) => v ?? r.subject_id },
    { title: '执行日期', dataIndex: 'start_date', width: 120 },
    { title: '块数', dataIndex: 'block_count', width: 80 },
    { title: '总电量(MWh)', dataIndex: 'total_volume_mwh', width: 130, render: (v: number) => v?.toFixed(2) },
    { title: '状态', dataIndex: 'status', width: 90, render: (v: string) => <Tag>{v}</Tag> },
    { title: '创建时间', dataIndex: 'created_at', width: 170 },
    {
      title: '操作', key: 'op', width: 90,
      render: (_: unknown, r) => (
        <Popconfirm title="确认删除该申报？" onConfirm={async () => {
          try { await deleteBlockSet(r.block_set_id); message.success('已删除'); await loadHistory(); }
          catch (e: any) { message.error(e?.response?.data?.detail || '删除失败'); }
        }}>
          <Button size="small" type="link" danger>删除</Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div>
      <Card title="能量块申报（中长期 / 日前 / 实时 共用）" size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col xs={24} md={4}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>市场类型</div>
            <Select style={{ width: '100%' }} value={marketType} options={MARKET_OPTIONS}
              onChange={(v) => setMarketType(v as MarketType)} />
          </Col>
          <Col xs={24} md={6}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>标的客户</div>
            <Select
              style={{ width: '100%' }} showSearch optionFilterProp="label"
              value={subjectId} placeholder="选择客户"
              options={customers.map((c) => ({
                label: c.short_name ? c.user_name + '（' + c.short_name + '）' : c.user_name,
                value: c.id,
              }))}
              onChange={(v) => {
                setSubjectId(v);
                const c = customers.find((x) => x.id === v);
                setSubjectName(c?.user_name);
              }}
            />
          </Col>
          <Col xs={24} md={4}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>执行日期</div>
            <DatePicker style={{ width: '100%' }} value={startDate} onChange={(d) => d && setStartDate(d)} />
          </Col>
          <Col xs={24} md={3}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>方向</div>
            <Select style={{ width: '100%' }} value={direction}
              options={[{ label: '买电', value: 'buy' }, { label: '卖电', value: 'sell' }]}
              onChange={(v) => setDirection(v as 'buy' | 'sell')} />
          </Col>
          <Col xs={24} md={3}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>价格上限</div>
            <InputNumber style={{ width: '100%' }} min={0} value={priceCap}
              onChange={(v) => setPriceCap(Number(v) || 0)} />
          </Col>
          <Col xs={24} md={4}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>申报总电量(MWh)</div>
            <InputNumber style={{ width: '100%' }} min={0} value={totalVolume ?? undefined}
              placeholder="用于总量守恒校验"
              onChange={(v) => setTotalVolume(v == null ? null : Number(v))} />
          </Col>
        </Row>
        <Divider style={{ margin: '12px 0' }} />
        <Space wrap>
          <Text type="secondary">期望峰/平/谷占比</Text>
          <InputNumber size="small" min={0} max={1} step={0.05} value={ratio.peak}
            onChange={(v) => setRatio((r) => ({ ...r, peak: Number(v) || 0 }))} addonBefore="峰" />
          <InputNumber size="small" min={0} max={1} step={0.05} value={ratio.flat}
            onChange={(v) => setRatio((r) => ({ ...r, flat: Number(v) || 0 }))} addonBefore="平" />
          <InputNumber size="small" min={0} max={1} step={0.05} value={ratio.valley}
            onChange={(v) => setRatio((r) => ({ ...r, valley: Number(v) || 0 }))} addonBefore="谷" />
        </Space>
      </Card>

      <Card
        title={'能量块明细（' + blocks.length + ' 块）'}
        size="small"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button size="small" icon={<PlusOutlined />} onClick={addBlock}>添加能量块</Button>
            <Button size="small" icon={<ThunderboltOutlined />} onClick={gen96}>按96点均分</Button>
            <Button size="small" onClick={handleValidate} loading={loading}>校验</Button>
            <Button size="small" type="primary" onClick={handleSubmit} loading={loading}>提交申报</Button>
          </Space>
        }
      >
        <Table<EnergyBlockItem>
          rowKey={(_, i) => String(i)}
          size="small"
          columns={columns}
          dataSource={blocks}
          pagination={false}
          scroll={{ y: 380 }}
          locale={{ emptyText: '暂无能量块，点击「添加能量块」或「按96点均分」' }}
        />
      </Card>

      {result && (
        <Card title="校验结果" size="small" style={{ marginBottom: 16 }}>
          <Alert
            type={result.valid ? 'success' : 'error'}
            showIcon
            message={result.valid ? '校验通过' : '校验未通过'}
            description={
              <div>
                {result.errors.length > 0 && (
                  <div>{result.errors.map((e, i) => <div key={i}>• {e}</div>)}</div>
                )}
                {result.warnings.length > 0 && (
                  <div style={{ marginTop: 6, color: '#d46b08' }}>
                    {result.warnings.map((w, i) => <div key={i}>⚠ {w}</div>)}
                  </div>
                )}
              </div>
            }
            style={{ marginBottom: 12 }}
          />
          <Row gutter={16}>
            <Col xs={12} md={5}><Statistic title="能量块数" value={result.summary.block_count} /></Col>
            <Col xs={12} md={5}><Statistic title="总电量(MWh)" value={result.summary.total_volume_mwh} precision={2} /></Col>
            <Col xs={12} md={5}><Statistic title="总金额(元)" value={result.summary.total_amount} precision={0} /></Col>
            <Col xs={12} md={5}><Statistic title="加权均价(元/MWh)" value={result.summary.avg_price} precision={2} /></Col>
          </Row>
          <div style={{ marginTop: 12 }}>
            <Text type="secondary">分时段占比：</Text>
            {Object.entries(result.summary.ratio_by_period).map(([k, v]) => (
              <Tag key={k} color="blue">{k} {(v * 100).toFixed(1)}%</Tag>
            ))}
          </div>
        </Card>
      )}

      <Card title="申报历史" size="small">
        <Table<BlockSetListItem>
          rowKey="block_set_id"
          size="small"
          columns={histColumns}
          dataSource={history}
          pagination={{ pageSize: 10 }}
          scroll={{ x: 'max-content' }}
        />
      </Card>
    </div>
  );
}
