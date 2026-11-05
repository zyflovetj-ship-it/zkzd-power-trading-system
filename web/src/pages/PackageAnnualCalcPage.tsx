import { useEffect, useMemo, useState } from 'react';
import {
  Alert,
  App,
  Button,
  Card,
  Col,
  Divider,
  InputNumber,
  Row,
  Select,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { ComplianceBanner } from '@/components/ComplianceBanner';
import { checkParams } from '@/utils/compliance';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import { fetchCustomers, type CustomerListItem } from '@/api/customers';
import {
  calcAnnual,
  fetchPackages,
  validateCompliance,
  type AnnualCalcResult,
  type AnnualDetailRow,
  type ComplianceResult,
  type RetailPackageListItem,
} from '@/api/packages';

const { Text } = Typography;
const fmt = (v: number | null | undefined, d = 2) => (v == null ? '-' : Number(v).toFixed(d));

const GREEN_OPTS = [
  { label: '否', value: '否' },
  { label: '普通绿电', value: '普通绿电' },
  { label: '小时级绿电', value: '小时级绿电' },
];

export default function PackageAnnualCalcPage() {
  const { message, modal } = App.useApp();
  const [packages, setPackages] = useState<RetailPackageListItem[]>([]);
  const [packageId, setPackageId] = useState<string>();
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [customerIds, setCustomerIds] = useState<string[]>([]);
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [autoMarket, setAutoMarket] = useState(true);
  const [holdingRatio, setHoldingRatio] = useState(0.4);
  const [peakCoef, setPeakCoef] = useState(1.6);
  const [valleyCoef, setValleyCoef] = useState(0.4);
  const [serviceFee, setServiceFee] = useState(2);
  const [fRatio, setFRatio] = useState(0.05);
  const [k1, setK1] = useState(100);
  const [k2, setK2] = useState(100);
  const [k3, setK3] = useState(100);
  const [greenMode, setGreenMode] = useState('否');
  const [ktype, setKtype] = useState('单一制-100千伏安以下');
  const [marketSource, setMarketSource] = useState<'manual' | 'system'>('manual');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<AnnualCalcResult | null>(null);
  const [compliance, setCompliance] = useState<ComplianceResult | null>(null);

  useEffect(() => {
    fetchPackages({ page: 1, page_size: 100 })
      .then((r) => {
        setPackages(r.items);
        if (r.items.length) setPackageId(r.items[0].id);
      })
      .catch(() => setPackages([]));
    fetchCustomers({ page: 1, page_size: 100 })
      .then((r) => setCustomers(r.items as CustomerListItem[]))
      .catch(() => setCustomers([]));
  }, []);

  const check = useMemo(
    () =>
      checkParams({
        peak_coef: peakCoef,
        valley_coef: valleyCoef,
        service_fee: serviceFee,
        k1_share: k1 / 100,
        k2_share: k2 / 100,
        k3_share: k3 / 100,
        f_ratio: fRatio,
      }),
    [peakCoef, valleyCoef, serviceFee, k1, k2, k3, fRatio],
  );

  const params = useMemo(
    () => ({
      peak_coef: peakCoef,
      valley_coef: valleyCoef,
      service_fee: serviceFee,
      f_ratio: fRatio,
      k1_share: k1 / 100,
      k2_share: k2 / 100,
      k3_share: k3 / 100,
      green_mode: greenMode,
    }),
    [peakCoef, valleyCoef, serviceFee, fRatio, k1, k2, k3, greenMode],
  );

  const handleValidate = async () => {
    try {
      const r = await validateCompliance(params);
      setCompliance(r);
      message[r.valid ? 'success' : 'warning'](r.valid ? '合规校验通过' : '存在越界项');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '校验失败');
    }
  };

  const handleCalc = async () => {
    if (!packageId) {
      message.warning('请先选择套餐');
      return;
    }
    if (!check.valid) {
      const ok = await new Promise<boolean>((resolve) => {
        modal.confirm({
          title: '⚠ 参数越界，触发风险预警',
          width: 560,
          content: (
            <div>
              <div style={{ marginBottom: 8 }}>
                以下 {check.violations.length} 项超出附件2 合规区间：
              </div>
              {check.violations.map((v) => (
                <div key={v.key} style={{ color: '#cf1322', marginBottom: 2 }}>
                  • {v.name}：要求 {v.rule}，当前 {v.display}{v.unit}
                </div>
              ))}
              <div style={{ marginTop: 8, color: '#d46b08' }}>
                按《江苏电力交易工作指引》第五条，须经法定代表人确认后方可执行。是否继续测算？
              </div>
            </div>
          ),
          okText: '继续测算',
          cancelText: '返回修改',
          onOk: () => resolve(true),
          onCancel: () => resolve(false),
        });
      });
      if (!ok) return;
    }
    setLoading(true);
    try {
      const r = await calcAnnual(packageId, {
        year,
        customer_ids: customerIds,
        auto_market: autoMarket,
        holding_ratio: holdingRatio,
        ktype,
        market_source: marketSource,
        market: { wholesale_price: 0 },
        params,
      });
      setResult(r);
      setCompliance(r.compliance);
      if (!r.details.length) message.warning('所选客户在该年度无可用负荷数据');
      else message.success('年度测算完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '测算失败');
    } finally {
      setLoading(false);
    }
  };

  const kpi = result?.kpi;
  const monthly = result?.monthly ?? [];

  const volumeOption: EChartsOption = useMemo(
    () => ({
      color: CHART_COLORS,
      tooltip: { ...baseTooltip, trigger: 'axis' },
      legend: { ...baseLegend, data: ['电量(MWh)', '收益(万元)'] },
      grid: { ...baseGrid, right: 70 },
      xAxis: { type: 'category', data: monthly.map((m) => m.month + '月') },
      yAxis: [
        { type: 'value', name: '电量(MWh)' },
        { type: 'value', name: '收益(万元)' },
      ],
      series: [
        { name: '电量(MWh)', type: 'bar', data: monthly.map((m) => m.volume_mwh), itemStyle: { color: CHART_COLORS[0] } },
        { name: '收益(万元)', type: 'line', yAxisIndex: 1, smooth: true, data: monthly.map((m) => m.profit_wan), itemStyle: { color: CHART_COLORS[2] } },
      ],
    }),
    [monthly],
  );

  const touOption: EChartsOption = useMemo(
    () => ({
      color: CHART_COLORS,
      tooltip: { ...baseTooltip, trigger: 'axis' },
      legend: { ...baseLegend, data: ['峰', '平', '谷'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: monthly.map((m) => m.month + '月') },
      yAxis: { type: 'value', name: '电量(MWh)' },
      series: [
        { name: '峰', type: 'bar', stack: 'tou', data: monthly.map((m) => m.peak_mwh), itemStyle: { color: '#cf1322' } },
        { name: '平', type: 'bar', stack: 'tou', data: monthly.map((m) => m.flat_mwh), itemStyle: { color: '#595959' } },
        { name: '谷', type: 'bar', stack: 'tou', data: monthly.map((m) => m.valley_mwh), itemStyle: { color: '#08979c' } },
      ],
    }),
    [monthly],
  );

  const columns: ColumnsType<AnnualDetailRow> = [
    { title: '用户', dataIndex: 'user', width: 160, fixed: 'left' },
    { title: '类型', dataIndex: 'ktype', width: 90 },
    { title: '月', dataIndex: 'month', width: 60, render: (v: number) => v + '月' },
    {
      title: '数据源', dataIndex: 'data_source', width: 100,
      render: (v?: string) => {
        if (v === 'bill_verification') return <Tag color="orange">核查联</Tag>;
        if (v === 'load_curve') return <Tag color="green">负荷曲线</Tag>;
        return <Tag>{v || '—'}</Tag>;
      },
    },
    { title: '电量(MWh)', dataIndex: 'volume_mwh', width: 110, render: (v: number) => fmt(v, 2) },
    { title: 'P批发', dataIndex: 'p_wholesale', width: 100, render: (v: number) => fmt(v) },
    { title: 'P分摊', dataIndex: 'p_share', width: 90, render: (v: number) => fmt(v) },
    { title: 'P参考', dataIndex: 'p_reference', width: 100, render: (v: number) => fmt(v) },
    { title: 'P封顶', dataIndex: 'p_cap', width: 100, render: (v: number) => <span style={{ color: '#d46b08' }}>{fmt(v)}</span> },
    { title: '峰价', dataIndex: 'peak_price', width: 100, render: (v: number) => fmt(v) },
    { title: '平价', dataIndex: 'flat_price', width: 100, render: (v: number) => fmt(v) },
    { title: '谷价', dataIndex: 'valley_price', width: 100, render: (v: number) => fmt(v) },
    { title: '零售均价', dataIndex: 'retail_avg', width: 100, render: (v: number) => fmt(v) },
    { title: '封顶', dataIndex: 'capped', width: 80, render: (v: boolean) => (v ? <Tag color="red">触发</Tag> : '—') },
    { title: '结算价', dataIndex: 'settle_price', width: 100, render: (v: number) => <b>{fmt(v)}</b> },
    { title: '绿电', dataIndex: 'green_add', width: 90, render: (v: number) => (v > 0 ? '+' + fmt(v) : '—') },
    { title: '售电价', dataIndex: 'sell_price', width: 100, render: (v: number) => fmt(v) },
    { title: '代购峰价', dataIndex: 'sgcc_peak_price', width: 100, render: (v?: number) => (v == null ? '—' : fmt(v)) },
    { title: '代购平价', dataIndex: 'sgcc_flat_price', width: 100, render: (v?: number) => (v == null ? '—' : fmt(v)) },
    { title: '代购谷价', dataIndex: 'sgcc_valley_price', width: 100, render: (v?: number) => (v == null ? '—' : fmt(v)) },
    { title: '代购加权', dataIndex: 'sgcc_weighted', width: 100, render: (v?: number) => (v == null ? '—' : <span style={{ color: '#096dd9' }}>{fmt(v)}</span>) },
    { title: '成本', dataIndex: 'cost', width: 100, render: (v: number) => fmt(v) },
    {
      title: '收益(元/MWh)',
      dataIndex: 'profit_per_mwh',
      width: 130,
      render: (v: number) => <span style={{ color: v >= 0 ? '#389e0d' : '#cf1322' }}>{fmt(v)}</span>,
    },
    {
      title: '收益(万元)',
      dataIndex: 'profit_wan',
      width: 110,
      render: (v: number) => <span style={{ color: v >= 0 ? '#389e0d' : '#cf1322' }}>{fmt(v, 4)}</span>,
    },
  ];

  return (
    <div>
      <Card title="套餐年度测算（2027 新规全链路）" size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col xs={24} md={5}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>套餐</div>
            <Select
              style={{ width: '100%' }}
              value={packageId}
              onChange={setPackageId}
              options={packages.map((p) => ({ label: p.package_name, value: p.id }))}
              placeholder="选择套餐"
            />
          </Col>
          <Col xs={24} md={3}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>年份</div>
            <InputNumber style={{ width: '100%' }} min={2020} max={2100} value={year} onChange={(v) => setYear(Number(v) || year)} />
          </Col>
          <Col xs={24} md={9}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>客户（不选=全部）</div>
            <Select
              mode="multiple"
              allowClear
              style={{ width: '100%' }}
              value={customerIds}
              onChange={setCustomerIds}
              optionFilterProp="label"
              placeholder="默认全部客户"
              options={customers.map((c) => ({ label: c.short_name ? c.user_name + '（' + c.short_name + '）' : c.user_name, value: c.id }))}
            />
          </Col>
          <Col xs={24} md={4}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>自动取批发价</div>
            <Select
              style={{ width: '100%' }}
              value={autoMarket ? 'yes' : 'no'}
              onChange={(v) => setAutoMarket(v === 'yes')}
              options={[{ label: '是（现货合成）', value: 'yes' }, { label: '否（手工）', value: 'no' }]}
            />
          </Col>
          <Col xs={24} md={3}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>持仓策略系数<span style={{ color: '#d46b08', marginLeft: 4 }}>考核线70%</span></div>
            <InputNumber style={{ width: '100%' }} step={0.05} value={holdingRatio} onChange={(v) => setHoldingRatio(Number(v) || 0)} />
          </Col>
          <Col xs={24} md={4}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>行情来源<span style={{ color: '#8c8c8c', marginLeft: 4 }}>批发价</span></div>
            <Select
              style={{ width: '100%' }}
              value={marketSource}
              onChange={(v) => setMarketSource(v)}
              options={[
                { label: '手工/自动取现货', value: 'manual' },
                { label: '成本基线（逐月自动）', value: 'system' },
              ]}
            />
          </Col>
          <Col xs={24} md={4}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>用电类型<span style={{ color: '#8c8c8c', marginLeft: 4 }}>代购电峰谷系数</span></div>
            <Select
              style={{ width: '100%' }}
              value={ktype}
              onChange={setKtype}
              options={[
                { label: '两部制（峰1.8/平1.0/谷0.35）', value: '两部制' },
                { label: '单一制-100kVA及以上（峰1.7）', value: '单一制-100千伏安及以上' },
                { label: '单一制-100kVA以下（峰1.6）', value: '单一制-100千伏安以下' },
              ]}
            />
          </Col>
        </Row>

        <Divider style={{ margin: '12px 0' }} />
        <Space wrap size="middle">
          <Text type="secondary">分摊系数</Text>
          <InputNumber size="small" step={1} value={k1} onChange={(v) => setK1(Number(v) || 0)} addonBefore="K1 成本补偿" addonAfter="%" style={{ width: 235 }} />
          <InputNumber size="small" step={1} value={k2} onChange={(v) => setK2(Number(v) || 0)} addonBefore="K2 不平衡" addonAfter="%" style={{ width: 225 }} />
          <InputNumber size="small" step={1} value={k3} onChange={(v) => setK3(Number(v) || 0)} addonBefore="K3 市场调节" addonAfter="%" style={{ width: 235 }} />
          <Text type="secondary" style={{ fontSize: 12 }}>默认均 100%（K1 须 100%，K2 70~100%，K3 0~100%）</Text>
        </Space>
        <Divider style={{ margin: '12px 0' }} />
        <Space wrap size="middle">
          <Text type="secondary">套餐参数</Text>
          <InputNumber size="small" step={0.01} value={peakCoef} onChange={(v) => setPeakCoef(Number(v) || 0)} addonBefore="峰系数" style={{ width: 150 }} />
          <InputNumber size="small" step={0.01} value={valleyCoef} onChange={(v) => setValleyCoef(Number(v) || 0)} addonBefore="谷系数" style={{ width: 150 }} />
          <InputNumber size="small" step={1} value={serviceFee} onChange={(v) => setServiceFee(Number(v) || 0)} addonBefore="服务费" addonAfter="元/MWh" style={{ width: 200 }} />
          <InputNumber size="small" step={0.01} value={fRatio} onChange={(v) => setFRatio(Number(v) || 0)} addonBefore="F系数" style={{ width: 140 }} />
          <Select size="small" style={{ width: 140 }} value={greenMode} onChange={setGreenMode} options={GREEN_OPTS} />
          <Button onClick={handleValidate}>合规校验</Button>
          <Button type="primary" loading={loading} onClick={handleCalc}>
            开始测算
          </Button>
        </Space>
        <ComplianceBanner result={check} />
      </Card>

      {compliance && (
        <Card size="small" title="2027 新规合规校验" style={{ marginBottom: 16 }}>
          {compliance.valid ? (
            <Alert
              type="success"
              showIcon
              message="全部合规"
              style={{ marginBottom: 12 }}
            />
          ) : (
            <Alert
              type="warning"
              showIcon
              message="存在越界项 —— 已弹窗提示，须经法定代表人确认"
              style={{ marginBottom: 12 }}
            />
          )}
          <Space wrap>
            {compliance.items.map((it) => (
              <Tag key={it.key} color={it.pass ? 'green' : 'red'}>
                {it.name} = {it.value} {it.unit}（{it.rule}）
              </Tag>
            ))}
          </Space>
        </Card>
      )}

      {kpi && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col xs={12} md={4}><Card><Statistic title="年电量合计" value={kpi.total_volume_mwh} precision={2} suffix="MWh" /></Card></Col>
          <Col xs={12} md={4}><Card><Statistic title="平均售电收益" value={kpi.avg_profit_per_mwh ?? 0} precision={2} suffix="元/MWh" valueStyle={{ color: (kpi.avg_profit_per_mwh ?? 0) >= 0 ? '#389e0d' : '#cf1322' }} /></Card></Col>
          <Col xs={12} md={4}><Card><Statistic title="年售电收益" value={kpi.total_profit_wan} precision={4} suffix="万元" valueStyle={{ color: kpi.total_profit_wan >= 0 ? '#389e0d' : '#cf1322' }} /></Card></Col>
          <Col xs={12} md={4}><Card><Statistic title="封顶触发" value={kpi.capped_count + '/' + kpi.user_month_count} suffix="用户月数" /></Card></Col>
          <Col xs={12} md={4}><Card><Statistic title={<span>F系数 <span style={{ fontSize: 12, color: '#bfbfbf' }}>· 上限5%</span></span>} value={(kpi.f_ratio * 100).toFixed(1)} suffix="%" /></Card></Col>
          <Col xs={12} md={4}><Card><Statistic title="kP浮动" value={kpi.kp} precision={3} suffix="元/kWh" /></Card></Col>
        </Row>
      )}

      {result && (
        <>
          <ChartCard title="月度电量与收益" option={volumeOption} height={320} />
          <ChartCard title="月度峰平谷电量结构" option={touOption} height={320} />
          <Card size="small" title={'逐月测算明细（' + (result.package_name ?? '') + ' · ' + result.year + ' 年）'}>
            <Table<AnnualDetailRow>
              rowKey={(r) => r.customer_id + '-' + r.month}
              size="small"
              columns={columns}
              dataSource={result.details}
              pagination={{ pageSize: 20 }}
              scroll={{ x: 'max-content', y: 480 }}
              locale={{ emptyText: '所选客户在该年度无可用负荷数据' }}
            />
          </Card>
        </>
      )}
    </div>
  );
}
