import { useCallback, useEffect, useState } from 'react';
import {
  Alert, App, Button, Card, Col, Descriptions, Empty, InputNumber, Popconfirm,
  Row, Select, Space, Statistic, Table, Tag, Typography, Upload,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { DownloadOutlined, UploadOutlined, CheckCircleOutlined } from '@ant-design/icons';
import {
  deleteMidLongRecords,
  downloadMidLongTemplate,
  fetchMidLongRecords,
  importMidLongExcel,
  previewMidLongExcel,
  type MidLongBlock,
  type MidLongGroup,
  type MidLongPreview,
} from '@/api/midLongContracts';
import { fetchCustomers, type CustomerListItem } from '@/api/customers';

const { Text } = Typography;

export default function MidLongContractPage() {
  const { message } = App.useApp();
  const [year, setYear] = useState<number>(new Date().getFullYear() + 1);
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [customerId, setCustomerId] = useState<string>(''); // 空=全市场统一
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<MidLongPreview | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [groups, setGroups] = useState<MidLongGroup[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);

  const loadCustomers = useCallback(() => {
    fetchCustomers({ page: 1, page_size: 200 })
      .then((r) => setCustomers(r.items as CustomerListItem[]))
      .catch(() => setCustomers([]));
  }, []);

  const loadRecords = useCallback(() => {
    setLoading(true);
    fetchMidLongRecords({ year, customer_id: customerId || undefined })
      .then((r) => { setTotal(r.total); setGroups(r.groups); })
      .catch((e) => message.error(e?.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, [year, customerId, message]);

  useEffect(() => { loadCustomers(); }, [loadCustomers]);
  useEffect(() => { loadRecords(); }, [loadRecords]);

  const handlePreview = async (f: File) => {
    setFile(f);
    setPreview(null);
    setPreviewing(true);
    try {
      const r = await previewMidLongExcel(f);
      setPreview(r);
      if (r.ok) message.success('校验通过，可导入');
      else message.warning(`校验发现 ${r.problems.length} 个问题`);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '校验失败');
    } finally {
      setPreviewing(false);
    }
  };

  const handleImport = async () => {
    if (!file) { message.warning('请先上传 Excel'); return; }
    setImporting(true);
    try {
      const r = await importMidLongExcel(file, {
        year,
        customer_id: customerId || undefined,
        customer_name: customers.find((c) => c.id === customerId)?.user_name,
      });
      message.success(`导入完成：新增 ${r.inserted} 条，清理旧数据 ${r.deleted} 条`);
      setPreview(null);
      setFile(null);
      loadRecords();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '导入失败');
    } finally {
      setImporting(false);
    }
  };

  const handleDelete = async () => {
    try {
      const r = await deleteMidLongRecords({ year, customer_id: customerId || undefined });
      message.success(`已删除 ${r.deleted} 条`);
      loadRecords();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '删除失败');
    }
  };

  const blockCols: ColumnsType<MidLongBlock> = [
    { title: '合同块', dataIndex: 'contract_type', width: 160 },
    { title: '1月电量(MWh)', dataIndex: 'jan_volume_mwh', width: 140, render: (v: number) => v?.toFixed(3) },
    { title: '首行价格(元/MWh)', dataIndex: 'first_price', width: 150, render: (v: number | null) => (v == null ? '—' : v) },
  ];

  const groupCols: ColumnsType<MidLongGroup> = [
    { title: '年份', dataIndex: 'year', width: 80, render: (v) => v ?? '—' },
    { title: '客户', dataIndex: 'customer_name', width: 220, render: (v, r) => v || (r.customer_id ? r.customer_id : <Tag color="blue">全市场统一</Tag>) },
    { title: '月份', dataIndex: 'month', width: 80, render: (v: number) => v + '月' },
    { title: '记录数', dataIndex: 'rows', width: 100 },
    { title: '电量合计(MWh)', dataIndex: 'volume_mwh', width: 140, render: (v: number) => v?.toFixed(3) },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Card title="中长期 / 绿电合同量价管理" style={{ marginBottom: 16 }}>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="用于套餐年度测算的逐点中长期价来源（对齐《套餐测算模板-新v2》）。"
          description="流程：① 下载模板 → ② 填写合同量价 → ③ 上传校验 → ④ 导入。客户级优先，无专属合同则用全市场统一价。"
        />
        <Row gutter={12} style={{ marginBottom: 12 }}>
          <Col xs={24} md={4}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>年份</div>
            <InputNumber style={{ width: '100%' }} value={year} onChange={(v) => setYear(Number(v) || new Date().getFullYear() + 1)} />
          </Col>
          <Col xs={24} md={8}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>归属客户（不选=全市场统一）</div>
            <Select
              style={{ width: '100%' }}
              allowClear
              value={customerId || undefined}
              onChange={(v) => setCustomerId(v || '')}
              placeholder="全市场统一合同价"
              options={customers.map((c) => ({ label: c.user_name, value: c.id }))}
            />
          </Col>
          <Col xs={24} md={12} style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
            <Button icon={<DownloadOutlined />} onClick={async () => { try { await downloadMidLongTemplate(); } catch (e: any) { message.error(e?.response?.data?.detail || e?.message || '下载模板失败'); } }}>
              下载模板
            </Button>
            <Upload
              accept=".xlsx,.xls"
              showUploadList={false}
              beforeUpload={(f) => { handlePreview(f as File); return false; }}
            >
              <Button icon={<UploadOutlined />} loading={previewing}>上传校验</Button>
            </Upload>
            <Button
              type="primary"
              icon={<CheckCircleOutlined />}
              disabled={!file || (preview ? !preview.ok : true)}
              loading={importing}
              onClick={handleImport}
            >
              确认导入
            </Button>
          </Col>
        </Row>

        {file && (
          <Alert
            type={preview ? (preview.ok ? 'success' : 'warning') : 'info'}
            showIcon
            style={{ marginBottom: 12 }}
            message={`已选文件：${file.name}`}
            description={
              preview
                ? (
                  <div>
                    {preview.ok
                      ? <div style={{ color: '#389e0d' }}>校验通过，点击"确认导入"落库</div>
                      : <div>{preview.problems.map((p, i) => <div key={i}>• {p}</div>)}</div>}
                    {(preview.warnings ?? []).map((w, i) => (
                      <div key={'w' + i} style={{ color: '#d46b08', marginTop: 4 }}>⚠ {w}</div>
                    ))}
                  </div>
                )
                : '正在校验…'
            }
          />
        )}

        {preview && preview.blocks.length > 0 && (
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Card size="small" title="合同块概览（1月）">
                <Table
                  size="small"
                  rowKey="contract_type"
                  columns={blockCols}
                  dataSource={preview.blocks}
                  pagination={false}
                  scroll={{ y: 360 }}
                />
              </Card>
            </Col>
            <Col xs={24} md={12}>
              <Card size="small" title="逐点中长期价预览（1月 24 时段）">
                <Table
                  size="small"
                  rowKey={(_, i) => String(i)}
                  pagination={false}
                  scroll={{ y: 360 }}
                  dataSource={preview.preview_prices.map((v, i) => ({ idx: i, price: v }))}
                  columns={[
                    { title: '时段', dataIndex: 'idx', width: 80, render: (i: number) => `${String(i).padStart(2, '0')}:00` },
                    { title: '中长期价(元/MWh)', dataIndex: 'price', render: (v: number | null) => (v == null ? '—' : v.toFixed(3)) },
                  ]}
                />
              </Card>
            </Col>
          </Row>
        )}
      </Card>

      <Card
        title="已导入的合同量价"
        extra={
          <Space>
            <Text type="secondary">共 {total} 条</Text>
            <Popconfirm
              title={`确认删除 ${year}年 ${customerId ? '该客户' : '全市场统一'} 的合同量价？`}
              onConfirm={handleDelete}
            >
              <Button danger size="small">删除当前筛选</Button>
            </Popconfirm>
          </Space>
        }
      >
        <Row gutter={16} style={{ marginBottom: 12 }}>
          <Col><Statistic title="总记录数" value={total} /></Col>
        </Row>
        <Table
          size="small"
          rowKey={(r) => `${r.year}-${r.customer_id || 'global'}-${r.month}`}
          columns={groupCols}
          dataSource={groups}
          loading={loading}
          pagination={{ pageSize: 24 }}
          locale={{ emptyText: <Empty description="暂无数据，请上传导入" /> }}
        />
      </Card>
    </div>
  );
}
