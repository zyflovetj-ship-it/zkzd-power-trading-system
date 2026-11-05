import { useCallback, useEffect, useState } from 'react';
import {
  Alert, App, Button, Card, Col, Empty, Popconfirm, Row, Select, Space,
  Statistic, Table, Tag, Typography, Upload,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { DownloadOutlined, UploadOutlined, CheckCircleOutlined } from '@ant-design/icons';
import {
  deleteLoadRecords,
  downloadLoadTemplate,
  fetchLoadRecords,
  importLoadExcel,
  previewLoadExcel,
  type LoadMonthGroup,
} from '@/api/dataImport';
import { fetchCustomers, type CustomerListItem } from '@/api/customers';

const { Text } = Typography;

export default function LoadDataPage() {
  const { message } = App.useApp();
  const [customers, setCustomers] = useState<CustomerListItem[]>([]);
  const [customerId, setCustomerId] = useState<string>('');
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{ ok: boolean; problems: string[]; record_count: number; months: LoadMonthGroup[] } | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [groups, setGroups] = useState<LoadMonthGroup[]>([]);
  const [totalPoints, setTotalPoints] = useState(0);
  const [bySource, setBySource] = useState<Record<string, number>>({});
  const [sourceFilter, setSourceFilter] = useState<string>('');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchCustomers({ page: 1, page_size: 200 })
      .then((r) => setCustomers(r.items as CustomerListItem[]))
      .catch(() => setCustomers([]));
  }, []);

  const loadRecords = useCallback(() => {
    setLoading(true);
    fetchLoadRecords({ customer_id: customerId || undefined, source: sourceFilter || undefined })
      .then((r) => { setTotalPoints(r.total_points); setGroups(r.groups); setBySource(r.by_source || {}); })
      .catch((e) => message.error(e?.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, [customerId, sourceFilter, message]);

  useEffect(() => { loadRecords(); }, [loadRecords]);

  const handlePreview = async (f: File) => {
    setFile(f);
    setPreview(null);
    setPreviewing(true);
    try {
      const r = await previewLoadExcel(f);
      setPreview(r);
      if (r.ok) message.success(`解析到 ${r.record_count} 个负荷点，可导入`);
      else message.warning('校验发现问题');
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
      const r = await importLoadExcel(file, true);
      message.success(`导入完成：新增 ${r.inserted} 点，覆盖旧数据 ${r.deleted} 点`);
      setPreview(null);
      setFile(null);
      loadRecords();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '导入失败');
    } finally {
      setImporting(false);
    }
  };

  const handleDelete = async (g: LoadMonthGroup) => {
    try {
      const r = await deleteLoadRecords({ customer_id: g.customer_id, month: g.month, source: g.source });
      message.success(`已删除 ${r.deleted} 点`);
      loadRecords();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  const nameOf = (cid: string) => customers.find((c) => c.id === cid)?.user_name || cid;

  const SOURCE_LABEL: Record<string, { text: string; color: string }> = {
    excel_import: { text: '页面导入', color: 'green' },
    system_simulation: { text: '系统模拟', color: 'orange' },
    market_published: { text: '市场发布', color: 'blue' },
    unknown: { text: '未标注', color: 'default' },
  };

  const cols: ColumnsType<LoadMonthGroup> = [
    { title: '客户', dataIndex: 'customer_id', render: (v, r) => r.user_name || nameOf(v) },
    { title: '月份', dataIndex: 'month', width: 100 },
    {
      title: '数据来源', dataIndex: 'source', width: 110,
      render: (v?: string) => {
        const m = SOURCE_LABEL[v || 'unknown'] || { text: v || '未标注', color: 'default' };
        return <Tag color={m.color}>{m.text}</Tag>;
      },
    },
    { title: '天数', dataIndex: 'days', width: 80 },
    { title: '负荷点数', dataIndex: 'points', width: 100 },
    {
      title: '操作', width: 100,
      render: (_, r) => (
        <Popconfirm title={`删除 ${r.month} 该客户负荷？`} onConfirm={() => handleDelete(r)}>
          <Button danger size="small">删除</Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Card title="96 点负荷数据导入" style={{ marginBottom: 16 }}>
        <Alert
          type="info"
          showIcon
          style={{ marginBottom: 16 }}
          message="用于「历史负荷测算」与「套餐年度测算」的负荷数据来源。"
          description="支持宽表（客户+日期+96时段）或长表（客户+时间+功率）。单位 kW，15分钟一点。可一次导入多客户、多月。"
        />
        <Row gutter={12} style={{ marginBottom: 12 }}>
          <Col xs={24} md={6}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>按客户筛选</div>
            <Select
              style={{ width: '100%' }}
              allowClear
              value={customerId || undefined}
              onChange={(v) => setCustomerId(v || '')}
              placeholder="全部客户"
              options={customers.map((c) => ({ label: c.user_name, value: c.id }))}
            />
          </Col>
          <Col xs={24} md={4}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>数据来源</div>
            <Select
              style={{ width: '100%' }}
              allowClear
              value={sourceFilter || undefined}
              onChange={(v) => setSourceFilter(v || '')}
              placeholder="全部来源"
              options={[
                { label: '页面导入', value: 'excel_import' },
                { label: '系统模拟', value: 'system_simulation' },
                { label: '市场发布', value: 'market_published' },
              ]}
            />
          </Col>
          <Col xs={24} md={14} style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
            <Button icon={<DownloadOutlined />} onClick={async () => { try { await downloadLoadTemplate(); } catch (e: any) { message.error(e?.response?.data?.detail || e?.message || '下载模板失败'); } }}>
              下载模板
            </Button>
            <Upload accept=".xlsx,.xls" showUploadList={false} beforeUpload={(f) => { handlePreview(f as File); return false; }}>
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
                ? <div>
                    <div>{preview.ok ? `解析到 ${preview.record_count} 个负荷点，可导入` : '校验未通过'}</div>
                    {preview.problems.map((p, i) => <div key={i} style={{ color: '#d46b08' }}>⚠ {p}</div>)}
                  </div>
                : '正在校验…'
            }
          />
        )}
      </Card>

      <Card title="已导入的负荷数据" extra={<Text type="secondary">共 {totalPoints} 个负荷点</Text>}>
        <Row gutter={16} style={{ marginBottom: 12 }}>
          <Col><Statistic title="总负荷点数" value={totalPoints} /></Col>
          {Object.entries(bySource).map(([src, n]) => {
            const m = SOURCE_LABEL[src] || { text: src, color: 'default' };
            return (
              <Col key={src}>
                <Statistic
                  title={<span>其中 <Tag color={m.color} style={{ marginLeft: 2 }}>{m.text}</Tag></span>}
                  value={n}
                />
              </Col>
            );
          })}
        </Row>
        <Table
          size="small"
          rowKey={(r) => `${r.customer_id}-${r.month}-${r.source || 'na'}`}
          columns={cols}
          dataSource={groups}
          loading={loading}
          pagination={{ pageSize: 24 }}
          locale={{ emptyText: <Empty description="暂无数据，请上传导入" /> }}
        />
      </Card>
    </div>
  );
}
