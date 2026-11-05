import { useRef, useState } from 'react';
import dayjs from 'dayjs';
import { App, Button, Popconfirm, Space, Tag, Tooltip, Modal, Form, InputNumber, DatePicker, Select, Descriptions, Spin, Tabs, Input, Alert, Divider, Switch , List } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import {
  CopyOutlined,
  CheckCircleOutlined,
  InboxOutlined,
  DeleteOutlined,
  EditOutlined,
  CalculatorOutlined,
} from '@ant-design/icons';
import { CrudPage } from '@/components/crud/CrudPage';
import { ComplianceBanner } from '@/components/ComplianceBanner';
import { checkParams } from '@/utils/compliance';
import { fetchCustomers, type CustomerListItem } from '@/api/customers';
import type { CrudField, SearchField } from '@/components/crud/types';
import {
  MODEL_CODE_OPTIONS,
  PACKAGE_STATUS_OPTIONS,
  PACKAGE_TYPE_OPTIONS,
  fetchModelOptions,
  activatePackage,
  archivePackage,
  copyPackage,
  createPackage,
  deletePackage,
  fetchPackages,
  updatePackage,
  calculatePrice,
  getRiskWarning,
  legalConfirm,
  calcFromLoad,
  calcFromBill,
  type MarketContext,
  type CalcParams,
  type CalcResult,
  type PackageStatus,
  type RetailPackageListItem,
} from '@/api/packages';

const STATUS_COLOR: Record<PackageStatus, string> = {
  draft: 'default',
  active: 'green',
  archived: 'orange',
};
const STATUS_LABEL: Record<PackageStatus, string> = {
  draft: '草稿',
  active: '生效',
  archived: '归档',
};

const searchFields: SearchField[] = [
  { name: 'keyword', label: '套餐名称', type: 'text' },
  { name: 'package_type', label: '类型', type: 'select', options: PACKAGE_TYPE_OPTIONS },
  { name: 'is_green_power', label: '绿电', type: 'select', options: [
    { label: '是', value: 'true' },
    { label: '否', value: 'false' },
  ] },
  { name: 'model_code', label: '定价模型', type: 'select', options: MODEL_CODE_OPTIONS },
  { name: 'status', label: '状态', type: 'select', options: PACKAGE_STATUS_OPTIONS },
];

const formFields: CrudField[] = [
  { name: 'package_name', label: '套餐名称', type: 'text', required: true, span: 12 },
  { name: 'package_type', label: '套餐类型', type: 'select', required: true, options: PACKAGE_TYPE_OPTIONS, span: 12 },
  { name: 'model_code', label: '定价模型', type: 'select', required: true, options: MODEL_CODE_OPTIONS, dependsOn: 'package_type', fetchOptions: fetchModelOptions, span: 12 },
  { name: 'is_green_power', label: '绿电套餐', type: 'switch', span: 12 },
  { name: 'package_description', label: '套餐描述', type: 'textarea', span: 24 },
];

const columns: ColumnsType<RetailPackageListItem> = [
  { title: '套餐名称', dataIndex: 'package_name', width: 180, fixed: 'left' },
  {
    title: '类型',
    dataIndex: 'package_type',
    width: 100,
    render: (t: string) => (t === 'time_based' ? '分时段' : '不分时段'),
  },
  { title: '绿电', dataIndex: 'is_green_power', width: 80, render: (v: boolean) => (v ? <Tag color="green">是</Tag> : <Tag>否</Tag>) },
  { title: '定价模型', dataIndex: 'model_code', width: 180 },
  {
    title: '状态',
    dataIndex: 'status',
    width: 90,
    render: (s: PackageStatus) => <Tag color={STATUS_COLOR[s]}>{STATUS_LABEL[s]}</Tag>,
  },
  { title: '合同数', dataIndex: 'contract_count', width: 90 },
  { title: '创建时间', dataIndex: 'created_at', width: 170, render: (v: string) => v?.replace('T', ' ').slice(0, 19) },
];

export default function PackagePage() {
  const reloadRef = useRef(() => {});
  const editRef = useRef<(r: RetailPackageListItem) => void>(() => {});
  const { message, modal } = App.useApp();

  // ===== 套餐测算（江苏2027新规，对齐《套餐测算模板 新v2》） =====
  const [calcOpen, setCalcOpen] = useState(false);
  const [calcRecord, setCalcRecord] = useState<RetailPackageListItem | null>(null);
  const [calcLoading, setCalcLoading] = useState(false);
  const [calcTab, setCalcTab] = useState<'load' | 'bill'>('load');
  const [calcResult, setCalcResult] = useState<CalcResult | null>(null);
  const [calcForm] = Form.useForm();
  const [formVals, setFormVals] = useState<Record<string, any>>({});
  const autoMarket = Form.useWatch('auto_market', calcForm);
  const [customerOptions, setCustomerOptions] = useState<{ label: string; value: string }[]>([]);
  const [customerLoading, setCustomerLoading] = useState(false);

  const loadCustomers = async () => {
    if (customerOptions.length > 0) return;
    setCustomerLoading(true);
    try {
      const res = await fetchCustomers({ page: 1, page_size: 100 });
      const opts = (res.items as CustomerListItem[]).map((c) => ({
        label: c.short_name ? `${c.user_name}（${c.short_name}）` : c.user_name,
        value: c.id,
      }));
      setCustomerOptions(opts);
    } catch {
      // 静默失败，仍可手输
    } finally {
      setCustomerLoading(false);
    }
  };

  const openCalc = (r: RetailPackageListItem) => {
    setCalcRecord(r);
    setCalcResult(null);
    setCalcTab('load');
    calcForm.resetFields();
    const defaults = {
      period: dayjs(),
      auto_market: true,
      holding_ratio: 0.4,
      wholesale_price: 330,
      flat_base_price: 320,
      reference_price: 336,
      peak_coef: 1.6,
      valley_coef: 0.4,
      service_fee: 2,
      f_ratio: 0.05,
      k1_share: 100,
      k2_share: 100,
      k3_share: 100,
      green_mode: '否',
    };
    calcForm.setFieldsValue(defaults);
    setFormVals(defaults);
    loadCustomers();
    setCalcOpen(true);
  };

  const paramCheck = checkParams({
    peak_coef: Number(formVals.peak_coef ?? 1.6),
    valley_coef: Number(formVals.valley_coef ?? 0.4),
    service_fee: Number(formVals.service_fee ?? 2),
    k1_share: Number(formVals.k1_share ?? 100) / 100,
    k2_share: Number(formVals.k2_share ?? 100) / 100,
    k3_share: Number(formVals.k3_share ?? 100) / 100,
    f_ratio: Number(formVals.f_ratio ?? 0.05),
  });

  const handleCalc = async () => {
    if (!paramCheck.valid) {
      const ok = await new Promise<boolean>((resolve) => {
        modal.confirm({
          title: '⚠ 参数越界，触发风险预警',
          width: 560,
          content: (
            <div>
              <div style={{ marginBottom: 8 }}>以下 {paramCheck.violations.length} 项超出附件2 合规区间：</div>
              {paramCheck.violations.map((v) => (
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
    try {
      const v = await calcForm.validateFields();
      const market: MarketContext = {
        wholesale_price: Number(v.wholesale_price),
        flat_base_price: v.flat_base_price == null ? undefined : Number(v.flat_base_price),
        reference_price: v.reference_price == null ? undefined : Number(v.reference_price),
        share_cost_compensation: 0,
        share_imbalance: 0,
        share_market_adjust: 0,
      };
      const params: CalcParams = {
        peak_coef: Number(v.peak_coef),
        valley_coef: Number(v.valley_coef),
        service_fee: Number(v.service_fee),
        f_ratio: Number(v.f_ratio),
        k1_share: Number(v.k1_share ?? 100) / 100,
        k2_share: Number(v.k2_share ?? 100) / 100,
        k3_share: Number(v.k3_share ?? 100) / 100,
        green_mode: v.green_mode,
      };
      const period = dayjs(v.period).format('YYYY-MM');
      setCalcLoading(true);
      setCalcResult(null);
      let res: CalcResult;
      if (calcTab === 'load') {
        res = await calcFromLoad(calcRecord!.id, {
          customer_id: v.customer_id,
          period,
          market,
          params,
          auto_market: !!v.auto_market,
          holding_ratio: v.holding_ratio == null ? 0.4 : Number(v.holding_ratio),
          mid_long_price: v.mid_long_price == null ? undefined : Number(v.mid_long_price),
        });
      } else {
        res = await calcFromBill(calcRecord!.id, {
          bill: {
            period,
            total_mwh: Number(v.total_mwh),
            peak_mwh: v.peak_mwh == null ? undefined : Number(v.peak_mwh),
            flat_mwh: v.flat_mwh == null ? undefined : Number(v.flat_mwh),
            valley_mwh: v.valley_mwh == null ? undefined : Number(v.valley_mwh),
            current_amount: v.current_amount == null ? undefined : Number(v.current_amount),
            customer_name: v.customer_name,
          },
          market,
          params,
        });
      }
      setCalcResult(res);
      message.success('测算完成');
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || e?.message || '测算失败');
    } finally {
      setCalcLoading(false);
    }
  };

  const num = (v: any, d = 2) =>
    v == null || Number.isNaN(Number(v)) ? '—' : Number(v).toFixed(d);

  const renderResult = (r: CalcResult) => (
    <>
      {r.warning && <Alert type="warning" showIcon message={r.warning} style={{ marginBottom: 12 }} />}
      <Descriptions title="分时电量 (MWh)" column={3} bordered size="small">
        <Descriptions.Item label="峰">{num(r.volumes.peak_mwh, 3)}</Descriptions.Item>
        <Descriptions.Item label="平">{num(r.volumes.flat_mwh, 3)}</Descriptions.Item>
        <Descriptions.Item label="谷">{num(r.volumes.valley_mwh, 3)}</Descriptions.Item>
      </Descriptions>
      <Descriptions title="分时电价 (元/MWh)" column={3} bordered size="small" style={{ marginTop: 12 }}>
        <Descriptions.Item label="峰价">{num(r.prices.peak_price)}</Descriptions.Item>
        <Descriptions.Item label="平价">{num(r.prices.flat_price)}</Descriptions.Item>
        <Descriptions.Item label="谷价">{num(r.prices.valley_price)}</Descriptions.Item>
        <Descriptions.Item label="平段加权均价">{num(r.prices.flat_base_price)}</Descriptions.Item>
        <Descriptions.Item label="服务费">{num(r.prices.service_fee)}</Descriptions.Item>
        <Descriptions.Item label="分摊合计">{num(r.share.total)}</Descriptions.Item>
      </Descriptions>
      {r.wholesale_auto && (
        <Descriptions title="批发价自动合成" column={3} bordered size="small" style={{ marginTop: 12 }}>
          <Descriptions.Item label="方法">{r.wholesale_auto.method}</Descriptions.Item>
          <Descriptions.Item label="持仓比例">{r.wholesale_auto.holding_ratio}</Descriptions.Item>
          <Descriptions.Item label="K2">{r.wholesale_auto.k2_ratio}</Descriptions.Item>
          <Descriptions.Item label="中长期价">{num(r.wholesale_auto.mid_long_price)}</Descriptions.Item>
          <Descriptions.Item label="日前均价">{num(r.wholesale_auto.day_ahead_avg)}</Descriptions.Item>
          <Descriptions.Item label="实时均价">{num(r.wholesale_auto.real_time_avg)}</Descriptions.Item>
        </Descriptions>
      )}
      <Descriptions title="结算" column={2} bordered size="small" style={{ marginTop: 12 }}>
        <Descriptions.Item label="用户电价">{num(r.energy_avg_price)}</Descriptions.Item>
        <Descriptions.Item label="封顶价">{num(r.cap_price)}</Descriptions.Item>
        <Descriptions.Item label="最终电价">{num(r.settle_price)}</Descriptions.Item>
        <Descriptions.Item label="是否触发封顶">{r.capped ? '是' : '否'}</Descriptions.Item>
        <Descriptions.Item label="绿电环境价值">{num(r.green_add)}</Descriptions.Item>
        <Descriptions.Item label="总电费 (元)">{num(r.total_cost)}</Descriptions.Item>
      </Descriptions>
      {r.vs_sgcc && (
        <Descriptions title="套餐 vs 国网代购" column={2} bordered size="small" style={{ marginTop: 12 }}>
          <Descriptions.Item label="代购电均价">{num(r.vs_sgcc.sgcc_price)}</Descriptions.Item>
          <Descriptions.Item label="套餐电价">{num(r.vs_sgcc.package_price)}</Descriptions.Item>
          <Descriptions.Item label="差额">{num(r.vs_sgcc.diff)}</Descriptions.Item>
          <Descriptions.Item label="结论">
            <Tag color={r.vs_sgcc.diff < 0 ? 'green' : 'red'}>{r.vs_sgcc.verdict}</Tag>
          </Descriptions.Item>
        </Descriptions>
      )}
      {r.sgcc_warning && <Alert type="info" showIcon message={r.sgcc_warning} style={{ marginTop: 12 }} />}
    </>
  );

  // ===== 风险预警 / 法定代表人确认 =====
  const [riskOpen, setRiskOpen] = useState(false);
  const [riskRecord, setRiskRecord] = useState<RetailPackageListItem | null>(null);
  const [riskData, setRiskData] = useState<any>(null);
  const [riskSubmitting, setRiskSubmitting] = useState(false);
  const [riskForm] = Form.useForm();

  const handleActivate = async (r: RetailPackageListItem) => {
    try {
      await activatePackage(r.id);
      message.success('激活成功');
      reloadRef.current();
    } catch (e: any) {
      const detail = e?.response?.data?.detail;
      if (e?.response?.status === 409 && detail?.code === 'RISK_WARNING') {
        try {
          const rw = await getRiskWarning(r.id);
          setRiskRecord(r);
          setRiskData(rw);
          riskForm.resetFields();
          setRiskOpen(true);
        } catch {
          message.error(detail?.message || '存在风险预警');
        }
        return;
      }
      message.error(typeof detail === 'string' ? detail : detail?.message || e?.message || '激活失败');
    }
  };

  const submitLegalConfirm = async () => {
    try {
      const v = await riskForm.validateFields();
      setRiskSubmitting(true);
      await legalConfirm(riskRecord!.id, {
        confirmed_by: v.confirmed_by,
        note: v.note,
        attachment_name: v.attachment_name,
      });
      message.success('法定代表人确认已记录，正在重新激活…');
      try {
        await activatePackage(riskRecord!.id);
        message.success('套餐已激活');
      } catch (e2: any) {
        message.warning('确认已记录，但激活仍需在列表中手动执行');
      }
      setRiskOpen(false);
      reloadRef.current();
    } catch (e: any) {
      if (e?.errorFields) return;
      message.error(e?.response?.data?.detail || e?.message || '确认失败');
    } finally {
      setRiskSubmitting(false);
    }
  };

  const run = async (fn: () => Promise<unknown>, label: string) => {
    try {
      await fn();
      message.success(`${label}成功`);
      reloadRef.current();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || `${label}失败`);
    }
  };

  return (
    <>
      <CrudPage<RetailPackageListItem>
      title="零售套餐管理"
      rowKey="id"
      columns={columns}
      searchFields={searchFields}
      formFields={formFields}
      reloadRef={reloadRef}
      editRef={editRef}
      fetcher={async ({ page, pageSize, filters }) => {
        const res = await fetchPackages({ ...filters, page, page_size: pageSize });
        return { items: res.items, total: res.total };
      }}
      creator={async (v) => createPackage(v as any)}
      updater={async (id, v) => updatePackage(id, v as any)}
      remover={undefined}
      actions={(r) => {
        const canEdit = r.status === 'draft';
        const canActivate = r.status === 'draft';
        const canArchive = r.status === 'active';
        const canDelete = r.status === 'draft';
        return (
          <Space size="small">
            {canEdit && (
              <Button type="link" size="small" icon={<EditOutlined />} onClick={() => editRef.current(r)}>
                编辑
              </Button>
            )}
            <Button
              type="link"
              size="small"
              icon={<CopyOutlined />}
              onClick={() => run(() => copyPackage(r.id), '复制')}
            >
              复制
            </Button>
            {canActivate && (
              <Button
                type="link"
                size="small"
                icon={<CheckCircleOutlined />}
                onClick={() => handleActivate(r)}
              >
                激活
              </Button>
            )}
            {canArchive && (
              <Button
                type="link"
                size="small"
                icon={<InboxOutlined />}
                onClick={() => run(() => archivePackage(r.id), '归档')}
              >
                归档
              </Button>
            )}
            <Button
              type="link"
              size="small"
              icon={<CalculatorOutlined />}
              onClick={() => openCalc(r)}
            >
              套餐测算
            </Button>
            {canDelete && (
              <Popconfirm
                title="确认删除该套餐（仅草稿可删）？"
                onConfirm={() => run(() => deletePackage(r.id), '删除')}
                okText="删除"
                cancelText="取消"
              >
                <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                  删除
                </Button>
              </Popconfirm>
            )}
          </Space>
        );
      }}
    />

    <Modal
      title={'套餐测算 - ' + (calcRecord?.package_name ?? '')}
      open={calcOpen}
      onCancel={() => setCalcOpen(false)}
      onOk={handleCalc}
      okText="测算"
      cancelText="关闭"
      confirmLoading={calcLoading}
      width={780}
      destroyOnClose
    >
      <Tabs
        activeKey={calcTab}
        onChange={(k) => setCalcTab(k as 'load' | 'bill')}
        items={[
          { key: 'load', label: '历史负荷测算' },
          { key: 'bill', label: '核查联测算' },
        ]}
      />
      <Form
        form={calcForm}
        layout="vertical"
        onValuesChange={(_, all) => setFormVals(all)}
      >
        <Divider orientation="left" plain>数据源</Divider>
        {calcTab === 'load' ? (
          <>
            <Form.Item
              label="客户（客户档案管理录入，选中即取客户ID）"
              name="customer_id"
              rules={[{ required: true, message: '请选择客户' }]}
            >
              <Select
                showSearch
                allowClear
                loading={customerLoading}
                placeholder="按客户全称/简称搜索"
                optionFilterProp="label"
                options={customerOptions}
                notFoundContent={customerLoading ? '加载中…' : '无客户，请先到「客户管理→客户档案管理」新建'}
              />
            </Form.Item>
            <Form.Item label="测算月份" name="period" rules={[{ required: true, message: '请选择月份' }]}>
              <DatePicker picker="month" style={{ width: '100%' }} />
            </Form.Item>
          </>
        ) : (
          <>
            <Form.Item label="测算月份" name="period" rules={[{ required: true, message: '请选择月份' }]}>
              <DatePicker picker="month" style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="月总电量(MWh)" name="total_mwh" rules={[{ required: true, message: '请输入' }]}>
              <InputNumber style={{ width: '100%' }} min={0} />
            </Form.Item>
            <Space size="small" style={{ display: 'flex' }}>
              <Form.Item label="峰电量" name="peak_mwh" style={{ flex: 1 }}>
                <InputNumber style={{ width: '100%' }} min={0} />
              </Form.Item>
              <Form.Item label="平电量" name="flat_mwh" style={{ flex: 1 }}>
                <InputNumber style={{ width: '100%' }} min={0} />
              </Form.Item>
              <Form.Item label="谷电量" name="valley_mwh" style={{ flex: 1 }}>
                <InputNumber style={{ width: '100%' }} min={0} />
              </Form.Item>
            </Space>
            <Form.Item label="现状实收电费(元)" name="current_amount">
              <InputNumber style={{ width: '100%' }} min={0} />
            </Form.Item>
          </>
        )}

        <Divider orientation="left" plain>市场行情 (元/MWh)</Divider>
        {calcTab === 'load' && (
          <Form.Item label="自动取批发价（日前/实时/中长期合成）" name="auto_market" valuePropName="checked">
            <Switch />
          </Form.Item>
        )}
        {calcTab === 'load' && autoMarket ? (
          <Space size="small" style={{ display: 'flex' }}>
            <Form.Item label="持仓策略系数(考核线70%)" name="holding_ratio" style={{ flex: 1 }}>
              <InputNumber style={{ width: '100%' }} step={0.05} />
            </Form.Item>
            <Form.Item label="中长期价(空=用日前均价)" name="mid_long_price" style={{ flex: 1 }}>
              <InputNumber style={{ width: '100%' }} />
            </Form.Item>
          </Space>
        ) : (
          <Space size="small" style={{ display: 'flex' }}>
            <Form.Item label="批发价" name="wholesale_price" rules={[{ required: true, message: '必填' }]} style={{ flex: 1 }}>
              <InputNumber style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="平段加权均价" name="flat_base_price" style={{ flex: 1 }}>
              <InputNumber style={{ width: '100%' }} />
            </Form.Item>
            <Form.Item label="零售参考价" name="reference_price" style={{ flex: 1 }}>
              <InputNumber style={{ width: '100%' }} />
            </Form.Item>
          </Space>
        )}
        <Space size="small" style={{ display: 'flex' }}>
          <Form.Item label="K1 成本补偿(%)" name="k1_share" style={{ flex: 1 }}>
            <InputNumber style={{ width: '100%' }} step={1} />
          </Form.Item>
          <Form.Item label="K2 不平衡(%)" name="k2_share" style={{ flex: 1 }}>
            <InputNumber style={{ width: '100%' }} step={1} />
          </Form.Item>
          <Form.Item label="K3 市场调节(%)" name="k3_share" style={{ flex: 1 }}>
            <InputNumber style={{ width: '100%' }} step={1} />
          </Form.Item>
        </Space>
        <div style={{ fontSize: 12, color: 'rgba(0,0,0,0.45)', marginBottom: 8 }}>
          分摊系数默认均 100%（K1 须 100%，K2 70~100%，K3 0~100%）
        </div>

        <Divider orientation="left" plain>套餐参数</Divider>
        <Space size="small" style={{ display: 'flex' }}>
          <Form.Item label="峰段系数(≥1.6)" name="peak_coef" style={{ flex: 1 }}>
            <InputNumber style={{ width: '100%' }} step={0.01} />
          </Form.Item>
          <Form.Item label="谷段系数(≤0.4)" name="valley_coef" style={{ flex: 1 }}>
            <InputNumber style={{ width: '100%' }} step={0.01} />
          </Form.Item>
          <Form.Item label="服务费" name="service_fee" style={{ flex: 1 }}>
            <InputNumber style={{ width: '100%' }} step={1} addonAfter="元/MWh" />
          </Form.Item>
          <Form.Item label="F系数" name="f_ratio" style={{ flex: 1 }}>
            <InputNumber style={{ width: '100%' }} step={0.01} />
          </Form.Item>
          <Form.Item label="绿电" name="green_mode" style={{ flex: 1 }}>
            <Select
              options={[
                { label: '否', value: '否' },
                { label: '普通绿电', value: '普通绿电' },
                { label: '小时级绿电', value: '小时级绿电' },
              ]}
            />
          </Form.Item>
        </Space>
        <ComplianceBanner result={paramCheck} compact />
      </Form>

      <Spin spinning={calcLoading}>
        {calcResult && <div style={{ marginTop: 8 }}>{renderResult(calcResult)}</div>}
      </Spin>
    </Modal>

    <Modal
      title={'风险预警 · 法定代表人确认 - ' + (riskRecord?.package_name ?? '')}
      open={riskOpen}
      onCancel={() => setRiskOpen(false)}
      onOk={submitLegalConfirm}
      okText="提交确认并激活"
      cancelText="取消"
      confirmLoading={riskSubmitting}
      width={680}
      destroyOnClose
    >
      <Alert
        type="error"
        showIcon
        style={{ marginBottom: 12 }}
        message="套餐参数越界，触发风险预警"
        description={riskData?.notice}
      />
      <List
        size="small"
        bordered
        dataSource={riskData?.items ?? []}
        renderItem={(it: any) => (
          <List.Item>
            <Tag color="red">{it.name}</Tag>
            <span>要求 <b>{it.rule}</b>，当前 <b>{it.value}{it.unit}</b></span>
            <span style={{ color: '#8c8c8c', marginLeft: 8 }}>{it.ref}</span>
          </List.Item>
        )}
        style={{ marginBottom: 16 }}
      />
      <Form form={riskForm} layout="vertical">
        <Form.Item
          label="法定代表人姓名"
          name="confirmed_by"
          rules={[{ required: true, message: '请填写法定代表人姓名' }]}
        >
          <Input placeholder="确认人姓名（用于审计留痕）" />
        </Form.Item>
        <Form.Item label="确认说明" name="note">
          <Input.TextArea rows={3} placeholder="如：已知悉参数越界风险，同意执行" />
        </Form.Item>
        <Form.Item label="授权书/附件名（可选）" name="attachment_name">
          <Input placeholder="如：法定代表人授权书.pdf" />
        </Form.Item>
      </Form>
    </Modal>
    </>
  );
}
