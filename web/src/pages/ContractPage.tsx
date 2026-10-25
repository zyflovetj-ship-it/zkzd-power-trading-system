import { useEffect, useRef, useState } from 'react';
import { App, Button, Space, Tag, Upload } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { DownloadOutlined, UploadOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { CrudPage } from '@/components/crud/CrudPage';
import type { CrudField, SearchField } from '@/components/crud/types';
import {
  createContract,
  deleteContract,
  exportContracts,
  fetchContracts,
  importContracts,
  updateContract,
  type Contract,
  type ContractStatus,
} from '@/api/contracts';
import apiClient from '@/api/client';

const STATUS_COLOR: Record<ContractStatus, string> = {
  pending: 'blue',
  active: 'green',
  expired: 'default',
};
const STATUS_LABEL: Record<ContractStatus, string> = {
  pending: '待生效',
  active: '生效',
  expired: '已过期',
};

const searchFields: SearchField[] = [
  { name: 'contract_name', label: '合同名称', type: 'text' },
  { name: 'package_name', label: '套餐名称', type: 'text' },
  { name: 'customer_name', label: '客户名称', type: 'text' },
  {
    name: 'status',
    label: '状态',
    type: 'select',
    options: [
      { label: '待生效', value: 'pending' },
      { label: '生效', value: 'active' },
      { label: '已过期', value: 'expired' },
    ],
  },
];

const columns: ColumnsType<Contract> = [
  { title: '合同名称', dataIndex: 'contract_name', width: 160, fixed: 'left' },
  { title: '套餐', dataIndex: 'package_name', width: 140 },
  { title: '客户', dataIndex: 'customer_name', width: 140 },
  { title: '购买电量(MWh)', dataIndex: 'purchasing_electricity_quantity', width: 130 },
  { title: '开始月份', dataIndex: 'purchase_start_month', width: 110 },
  { title: '结束月份', dataIndex: 'purchase_end_month', width: 110 },
  {
    title: '状态',
    dataIndex: 'status',
    width: 90,
    render: (s: ContractStatus) => <Tag color={STATUS_COLOR[s]}>{STATUS_LABEL[s]}</Tag>,
  },
  { title: '创建时间', dataIndex: 'created_at', width: 170, render: (v: string) => v?.replace('T', ' ').slice(0, 19) },
];

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

export default function ContractPage() {
  const reloadRef = useRef(() => {});
  const { message } = App.useApp();

  const [customerOptions, setCustomerOptions] = useState<{ label: string; value: string }[]>([]);
  const [packageOptions, setPackageOptions] = useState<{ label: string; value: string }[]>([]);

  useEffect(() => {
    apiClient.get('/api/v1/customers', { params: { status: 'active', page_size: 100 } })
      .then((res) => {
        const opts = (res.data.items ?? []).map((c: any) => ({ label: c.user_name, value: c.user_name }));
        console.log('[ContractPage] customerOptions loaded:', opts.length);
        setCustomerOptions(opts);
      })
      .catch((err) => console.error('[ContractPage] customerOptions error:', err));

    apiClient.get('/api/v1/retail-packages', { params: { status: 'active', page_size: 100 } })
      .then((res) => {
        const opts = (res.data.items ?? []).map((p: any) => ({ label: p.package_name, value: p.package_name }));
        console.log('[ContractPage] packageOptions loaded:', opts.length);
        setPackageOptions(opts);
      })
      .catch((err) => console.error('[ContractPage] packageOptions error:', err));
  }, []);

  const formFields: CrudField[] = [
    { name: 'contract_name', label: '合同名称', type: 'text', span: 12 },
    { name: 'customer_name', label: '客户名称', type: 'select', required: true, span: 12, options: customerOptions },
    { name: 'package_name', label: '套餐名称', type: 'select', required: true, span: 12, options: packageOptions },
    { name: 'purchasing_electricity_quantity', label: '购买电量(MWh)', type: 'number', required: true, span: 12 },
    { name: 'purchase_start_month', label: '购买开始月份', type: 'month', required: true, span: 12 },
    { name: 'purchase_end_month', label: '购买结束月份', type: 'month', required: true, span: 12 },
  ];

  const handleImport = async (file: File) => {
    try {
      const res = await importContracts(file);
      message.success(`导入完成：成功 ${res.success} 条，失败 ${res.failed} 条`);
      if (res.failed > 0) console.warn('导入失败明细', res.errors);
      reloadRef.current();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '导入失败');
    }
  };

  const handleExport = async () => {
    try {
      const blob = await exportContracts();
      downloadBlob(blob, `零售合同_${dayjs().format('YYYYMMDD')}.xlsx`);
      message.success('导出成功');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '导出失败');
    }
  };

  const toolbarExtra = (
    <Space>
      <Upload beforeUpload={(file) => { handleImport(file); return false; }} showUploadList={false} accept=".xlsx,.xls">
        <Button icon={<UploadOutlined />}>导入Excel</Button>
      </Upload>
      <Button icon={<DownloadOutlined />} onClick={handleExport}>
        导出Excel
      </Button>
    </Space>
  );

  const resolveIds = async (v: Record<string, any>) => {
    const vals = { ...v };
    if (vals.customer_name && !vals.customer_id) {
      const res = await apiClient.get('/api/v1/customers', { params: { keyword: vals.customer_name, status: 'active', page_size: 1 } });
      const item = (res.data.items ?? [])[0];
      if (item) vals.customer_id = item.id;
    }
    if (vals.package_name && !vals.package_id) {
      const res = await apiClient.get('/api/v1/retail-packages', { params: { keyword: vals.package_name, status: 'active', page_size: 1 } });
      const item = (res.data.items ?? [])[0];
      if (item) vals.package_id = item.id;
    }
    return vals;
  };

  return (
    <CrudPage<Contract>
      title="零售合同管理"
      rowKey="id"
      columns={columns}
      searchFields={searchFields}
      formFields={formFields}
      reloadRef={reloadRef}
      toolbarExtra={toolbarExtra}
      fetcher={async ({ page, pageSize, filters }) => {
        const res = await fetchContracts({ ...filters, page, page_size: pageSize });
        return { items: res.items, total: res.total };
      }}
      creator={async (v) => { const d = await resolveIds(v); return createContract(d as any); }}
      updater={async (id, v) => { const d = await resolveIds(v); return updateContract(id, d as any); }}
      remover={async (id) => deleteContract(id)}
      toFormValues={(r) => ({
        ...r,
        purchase_start_month: r.purchase_start_month ? dayjs(r.purchase_start_month) : null,
        purchase_end_month: r.purchase_end_month ? dayjs(r.purchase_end_month) : null,
      })}
      fromFormValues={(v) => ({
        ...v,
        purchase_start_month: v.purchase_start_month ? dayjs(v.purchase_start_month).format('YYYY-MM') : '',
        purchase_end_month: v.purchase_end_month ? dayjs(v.purchase_end_month).format('YYYY-MM') : '',
      })}
    />
  );
}
