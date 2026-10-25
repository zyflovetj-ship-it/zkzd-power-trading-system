import { useRef, useState } from 'react';
import dayjs from 'dayjs';
import { App, Button, Popconfirm, Space, Tag, Tooltip, Modal, Form, InputNumber, DatePicker, Select, Descriptions, Spin } from 'antd';
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
import type { CrudField, SearchField } from '@/components/crud/types';
import {
  MODEL_CODE_OPTIONS,
  PACKAGE_STATUS_OPTIONS,
  PACKAGE_TYPE_OPTIONS,
  activatePackage,
  archivePackage,
  copyPackage,
  createPackage,
  deletePackage,
  fetchPackages,
  updatePackage,
  calculatePrice,
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
  { name: 'model_code', label: '定价模型', type: 'select', required: true, options: MODEL_CODE_OPTIONS, span: 12 },
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
  const { message } = App.useApp();

  // ===== 价格试算 =====
  const [calcOpen, setCalcOpen] = useState(false);
  const [calcRecord, setCalcRecord] = useState<RetailPackageListItem | null>(null);
  const [calcLoading, setCalcLoading] = useState(false);
  const [calcResult, setCalcResult] = useState<Record<string, any> | null>(null);
  const [calcForm] = Form.useForm();

  const openCalc = (r: RetailPackageListItem) => {
    setCalcRecord(r);
    setCalcResult(null);
    calcForm.resetFields();
    calcForm.setFieldsValue({ date: dayjs(), time_period: 'flat', volume_mwh: 1 });
    setCalcOpen(true);
  };

  const handleCalc = async () => {
    try {
      const v = await calcForm.validateFields();
      setCalcLoading(true);
      setCalcResult(null);
      const res = await calculatePrice({
        package_id: calcRecord!.id,
        date: dayjs(v.date).format('YYYY-MM-DD'),
        time_period: v.time_period,
        volume_mwh: Number(v.volume_mwh),
      });
      setCalcResult(res as Record<string, any>);
      message.success('试算完成');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '价格试算失败');
    } finally {
      setCalcLoading(false);
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
                onClick={() => run(() => activatePackage(r.id), '激活')}
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
              价格试算
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
      title={`价格试算 - ${calcRecord?.package_name ?? ''}`}
      open={calcOpen}
      onCancel={() => setCalcOpen(false)}
      onOk={handleCalc}
      okText="试算"
      cancelText="关闭"
      confirmLoading={calcLoading}
      destroyOnClose
    >
      <Form form={calcForm} layout="vertical">
        <Form.Item
          label="试算日期"
          name="date"
          rules={[{ required: true, message: '请选择试算日期' }]}
        >
          <DatePicker style={{ width: '100%' }} />
        </Form.Item>
        <Form.Item
          label="时段"
          name="time_period"
          rules={[{ required: true, message: '请选择时段' }]}
        >
          <Select
            options={[
              { label: '尖峰', value: 'peak' },
              { label: '峰', value: 'high' },
              { label: '平', value: 'flat' },
              { label: '谷', value: 'valley' },
              { label: '深谷', value: 'deep_valley' },
            ]}
          />
        </Form.Item>
        <Form.Item
          label="电量 (MWh)"
          name="volume_mwh"
          rules={[{ required: true, message: '请输入电量' }]}
        >
          <InputNumber style={{ width: '100%' }} min={0} step={0.1} />
        </Form.Item>
      </Form>

      <Spin spinning={calcLoading}>
        {calcResult && (
          <Descriptions column={1} bordered size="small" style={{ marginTop: 16 }}>
            {Object.entries(calcResult).map(([k, v]) => (
              <Descriptions.Item key={k} label={k}>
                {typeof v === 'number' ? v : String(v)}
              </Descriptions.Item>
            ))}
          </Descriptions>
        )}
      </Spin>
      </Modal>
    </>
  );
}
