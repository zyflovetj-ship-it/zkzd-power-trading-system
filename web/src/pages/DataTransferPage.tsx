import { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { Alert, App as AntdApp, Button, Card, DatePicker, InputNumber, Select, Space, Table, Tag, Tooltip, Upload } from 'antd';
import { DownloadOutlined, UploadOutlined, DatabaseOutlined } from '@ant-design/icons';
import type { ColumnsType } from 'antd/es/table';
import dayjs from 'dayjs';
import apiClient from '@/api/client';

interface TransferModule {
  key: string;
  name: string;
  category: string;
  exportUrl: string;
  exportParams?: { key: string; label: string; type: 'date' | 'month' | 'number' | 'select'; options?: { label: string; value: string }[] }[];
  importUrl?: string;
  importAccept?: string;
}

const MODULES: TransferModule[] = [
  { key: 'wholesale', name: '批发侧预结算', category: '结算管理', exportUrl: '/api/v1/settlement/wholesale/export', exportParams: [{ key: 'date', label: '日期', type: 'date' }] },
  { key: 'retail', name: '零售用户结算', category: '结算管理', exportUrl: '/api/v1/settlement/retail/export', exportParams: [{ key: 'month', label: '月份', type: 'month' }] },
  { key: 'profit', name: '经营利润分析', category: '结算管理', exportUrl: '/api/v1/settlement/profit/export', exportParams: [{ key: 'months', label: '月数', type: 'number' }] },
  { key: 'bills', name: '平台账单复核', category: '结算管理', exportUrl: '/api/v1/settlement/bill-review/export' },
  { key: 'risk', name: '风险敞口分析', category: '风险管理', exportUrl: '/api/v1/risk/exposure/export' },
  { key: 'position', name: '持仓合约管理', category: '风险管理', exportUrl: '/api/v1/risk/position-contracts/export' },
  { key: 'forecast_accuracy', name: '预测精度分析', category: '负荷预测', exportUrl: '/api/v1/forecast-accuracy/export', exportParams: [
    { key: 'forecast_type', label: '预测类型', type: 'select', options: [{ label: '短期负荷', value: 'short_term_load' }, { label: '中长期负荷', value: 'medium_long_term_load' }, { label: '价格预测', value: 'price' }] },
    { key: 'days', label: '天数', type: 'number' },
  ] },
  { key: 'cluster', name: '客户聚类分析', category: '客户管理', exportUrl: '/api/v1/customer-cluster/export', exportParams: [{ key: 'n_clusters', label: '聚类数', type: 'number' }] },
  { key: 'contracts', name: '零售合同管理', category: '客户管理', exportUrl: '/api/v1/retail-contracts/export', importUrl: '/api/v1/retail-contracts/import', importAccept: '.xlsx,.xls' },
  { key: 'customers', name: '客户档案', category: '客户管理', exportUrl: '/api/v1/customers/export' },
  { key: 'forecast_base', name: '预测基础数据', category: '价格预测', exportUrl: '/api/v1/forecast-base-data/export', importUrl: '/api/v1/forecast-base-data/import', importAccept: '.xlsx,.xls,.csv' },
  { key: 'load_validation', name: '负荷数据校验', category: '基础数据', exportUrl: '/api/v1/basic-data/load-validation/export', importUrl: '/api/v1/basic-data/load-validation/import', importAccept: '.xlsx,.xls,.csv' },
  { key: 'tou_rules', name: '时段电价分布', category: '基础数据', exportUrl: '/api/v1/tou-rules/export' },
  { key: 'spot_review', name: '现货交易复盘', category: '交易复盘', exportUrl: '/api/v1/review/spot/export' },
  { key: 'ml_review', name: '中长期交易复盘', category: '交易复盘', exportUrl: '/api/v1/review/medium-long-term/export' },
];

const CATEGORY_COLORS: Record<string, string> = {
  '结算管理': 'blue', '风险管理': 'red', '负荷预测': 'orange',
  '客户管理': 'green', '价格预测': 'cyan', '基础数据': 'default', '交易复盘': 'purple',
};

export default function DataTransferPage() {
  const { message } = AntdApp.useApp();
  const [categoryFilter, setCategoryFilter] = useState<string>('');
  const [params, setParams] = useState<Record<string, Record<string, any>>>({});
  const [exportLoading, setExportLoading] = useState<string | null>(null);

  const categories = Array.from(new Set(MODULES.map(m => m.category)));
  const filtered = categoryFilter ? MODULES.filter(m => m.category === categoryFilter) : MODULES;

  const getParam = (modKey: string, paramKey: string) => params[modKey]?.[paramKey];
  const setParam = (modKey: string, paramKey: string, value: any) => {
    setParams(prev => ({ ...prev, [modKey]: { ...prev[modKey], [paramKey]: value } }));
  };

  const handleExport = async (mod: TransferModule) => {
    setExportLoading(mod.key);
    try {
      const queryParams: Record<string, any> = {};
      if (mod.exportParams) {
        for (const p of mod.exportParams) {
          const val = getParam(mod.key, p.key);
          if (val) {
            queryParams[p.key] = p.type === 'date' || p.type === 'month' ? dayjs(val).format('YYYY-MM-DD') : val;
          }
        }
      }
      const res = await apiClient.get(mod.exportUrl, { params: queryParams, responseType: 'blob' });
      const disposition = res.headers['content-disposition'];
      let filename = `${mod.name}.xlsx`;
      if (disposition) {
        const match = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (match) filename = match[1].replace(/['"]/g, '');
      }
      const url = window.URL.createObjectURL(new Blob([res.data]));
      const a = document.createElement('a'); a.href = url; a.download = filename; a.click();
      window.URL.revokeObjectURL(url);
      message.success(`"${mod.name}" 导出成功`);
    } catch (err: any) {
      message.error(err.response?.data?.detail || err.message || '导出失败');
    } finally {
      setExportLoading(null);
    }
  };

  const importMut = useMutation({
    mutationFn: ({ mod, file }: { mod: TransferModule; file: File }) => {
      if (!mod.importUrl) throw new Error('no import url');
      const fd = new FormData(); fd.append('file', file);
      return apiClient.post(mod.importUrl, fd, { headers: { 'Content-Type': 'multipart/form-data' } });
    },
    onSuccess: (data, { mod }) => {
      const r = data.data;
      message.success(`"${mod.name}" 导入完成: 成功 ${r.success || 0} 条, 失败 ${r.failed || 0} 条`);
    },
    onError: (err: any, { mod }) => {
      message.error(`"${mod.name}" 导入失败: ${err.response?.data?.detail || err.message}`);
    },
  });

  const renderExportParams = (mod: TransferModule) => {
    if (!mod.exportParams?.length) return <span style={{ color: '#999', fontSize: 12 }}>无参数</span>;
    return (
      <Space size="small" wrap>
        {mod.exportParams.map(p => {
          if (p.type === 'date') return <DatePicker key={p.key} size="small" placeholder={p.label} value={getParam(mod.key, p.key) ? dayjs(getParam(mod.key, p.key)) : null} onChange={(d) => setParam(mod.key, p.key, d?.toISOString())} style={{ width: 140 }} />;
          if (p.type === 'month') return <DatePicker key={p.key} size="small" picker="month" placeholder={p.label} value={getParam(mod.key, p.key) ? dayjs(getParam(mod.key, p.key)) : null} onChange={(d) => setParam(mod.key, p.key, d?.toISOString())} style={{ width: 140 }} />;
          if (p.type === 'number') return <InputNumber key={p.key} size="small" placeholder={p.label} value={getParam(mod.key, p.key) || undefined} onChange={(v) => setParam(mod.key, p.key, v)} style={{ width: 100 }} />;
          if (p.type === 'select') return <Select key={p.key} size="small" placeholder={p.label} value={getParam(mod.key, p.key) || undefined} onChange={(v) => setParam(mod.key, p.key, v)} options={p.options} style={{ width: 130 }} />;
          return null;
        })}
      </Space>
    );
  };

  const columns: ColumnsType<TransferModule> = [
    { title: '分类', dataIndex: 'category', width: 100, render: (c: string) => <Tag color={CATEGORY_COLORS[c] || 'default'}>{c}</Tag> },
    { title: '模块名称', dataIndex: 'name', width: 160, render: (n: string) => <><DatabaseOutlined style={{ marginRight: 6, color: '#999' }} />{n}</> },
    { title: '参数', dataIndex: 'exportParams', width: 360, render: (_: any, mod: TransferModule) => renderExportParams(mod) },
    {
      title: '导出', width: 72,
      render: (_: any, mod: TransferModule) => (
        <Tooltip title="导出 Excel">
          <Button type="link" size="small" icon={<DownloadOutlined />} loading={exportLoading === mod.key} onClick={() => handleExport(mod)} disabled={exportLoading === mod.key} />
        </Tooltip>
      ),
    },
    {
      title: '导入', width: 72,
      render: (_: any, mod: TransferModule) => mod.importUrl ? (
        <Upload accept={mod.importAccept || '.xlsx,.xls'} showUploadList={false} beforeUpload={(file) => { importMut.mutate({ mod, file }); return false; }} disabled={importMut.isPending}>
          <Tooltip title="导入 Excel/CSV">
            <Button type="link" size="small" icon={<UploadOutlined />} loading={importMut.isPending && importMut.variables?.mod.key === mod.key} />
          </Tooltip>
        </Upload>
      ) : <span style={{ color: '#ccc', fontSize: 12 }}>—</span>,
    },
  ];

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <span style={{ fontWeight: 500 }}>统一管理所有业务模块的数据导入与导出操作，支持 Excel/CSV 格式</span>
          <Select
            size="small"
            placeholder="按分类筛选"
            allowClear
            value={categoryFilter || undefined}
            onChange={(v) => setCategoryFilter(v || '')}
            options={categories.map(c => ({ value: c, label: c }))}
            style={{ width: 160 }}
          />
        </div>
      </Card>

      <Table
        rowKey="key"
        columns={columns}
        dataSource={filtered}
        pagination={false}
        size="small"
        scroll={{ x: 'max-content' }}
      />

      <Card size="small" style={{ marginTop: 16 }}>
        <div style={{ fontSize: 13, color: '#666' }}>
          <b>使用说明：</b>
          <ul style={{ margin: '8px 0 0', paddingLeft: 20 }}>
            <li><b>导出</b>：点击下载图标，系统将生成 Excel 文件并下载到本地</li>
            <li><b>导入</b>：点击上传图标选择文件，系统将批量导入数据并返回结果</li>
            <li>需要参数的模块请先填写参数再点击导出</li>
            <li>日期格式：YYYY-MM-DD，月份格式：YYYY-MM</li>
          </ul>
        </div>
      </Card>
    </div>
  );
}
