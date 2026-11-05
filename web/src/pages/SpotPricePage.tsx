import { useCallback, useEffect, useState } from 'react';
import {
  Alert, App, Button, Card, Col, DatePicker, Descriptions, Empty, InputNumber, Popconfirm,
  Row, Space, Statistic, Table, Tag, Typography, Upload,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { DownloadOutlined, UploadOutlined, CheckCircleOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import {
  deleteSpotDate,
  downloadSpotTemplate,
  fetchSpotMonthly,
  fetchSpotRecords,
  importSpotFiles,
  previewSpotFiles,
  type SpotDayRow,
  type SpotPreviewResult,
} from '@/api/spotPrices';

const { Text } = Typography;

export default function SpotPricePage() {
  const { message } = App.useApp();
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [files, setFiles] = useState<File[]>([]);
  const [preview, setPreview] = useState<{ ok_count: number; fail_count: number; results: SpotPreviewResult[] } | null>(null);
  const [previewing, setPreviewing] = useState(false);
  const [importing, setImporting] = useState(false);
  const [rows, setRows] = useState<SpotDayRow[]>([]);
  const [loading, setLoading] = useState(false);
  const [statMonth, setStatMonth] = useState<string>(dayjs().format('YYYY-MM'));
  const [monthly, setMonthly] = useState<any>(null);

  const loadRecords = useCallback(() => {
    setLoading(true);
    fetchSpotRecords({})
      .then((r) => setRows(r.rows))
      .catch((e) => message.error(e?.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, [message]);

  const loadMonthly = useCallback(() => {
    fetchSpotMonthly(statMonth)
      .then((r) => setMonthly(r))
      .catch(() => setMonthly(null));
  }, [statMonth]);

  useEffect(() => { loadRecords(); }, [loadRecords]);
  useEffect(() => { loadMonthly(); }, [loadMonthly]);

  const handlePreview = async (fl: File[]) => {
    if (!fl.length) return;
    setFiles(fl);
    setPreview(null);
    setPreviewing(true);
    try {
      const r = await previewSpotFiles(fl, year);
      setPreview(r);
      if (r.ok_count) message.success(`${r.ok_count} 个文件校验通过`);
      if (r.fail_count) message.warning(`${r.fail_count} 个文件有问题`);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '校验失败');
    } finally { setPreviewing(false); }
  };

  const handleImport = async () => {
    if (!files.length) { message.warning('请先上传文件'); return; }
    setImporting(true);
    try {
      const r = await importSpotFiles(files, year);
      message.success(`导入完成：日前 ${r.inserted_day_ahead} 点，实时 ${r.inserted_real_time} 点，覆盖旧 ${r.deleted_old} 点`);
      setPreview(null); setFiles([]);
      loadRecords(); loadMonthly();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '导入失败');
    } finally { setImporting(false); }
  };

  const handleDelete = async (date: string) => {
    try {
      const r = await deleteSpotDate(date);
      message.success(`已删除 ${date}（日前 ${r.deleted_day_ahead} + 实时 ${r.deleted_real_time} 点）`);
      loadRecords(); loadMonthly();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || '删除失败');
    }
  };

  const previewCols: ColumnsType<SpotPreviewResult> = [
    { title: '文件', dataIndex: 'file', width: 180 },
    { title: '日期', dataIndex: 'date', width: 110, render: (v) => v || '—' },
    { title: '日前', width: 130, render: (_, r) => r.day_ahead_points ? `${r.day_ahead_points}点 均值${r.day_ahead_avg}` : <Tag color="orange">无</Tag> },
    { title: '实时', width: 130, render: (_, r) => r.real_time_points ? `${r.real_time_points}点 均值${r.real_time_avg}` : <Tag color="orange">无</Tag> },
    { title: '状态', dataIndex: 'ok', width: 90, render: (v, r) => (v ? <Tag color="green">通过</Tag> : <Tag color="red">失败</Tag>) },
    { title: '问题', dataIndex: 'problems', render: (v: string[]) => (v?.length ? <span style={{ color: '#cf1322' }}>{v.join('; ')}</span> : '—') },
  ];

  const recCols: ColumnsType<SpotDayRow> = [
    { title: '日期', dataIndex: 'date', width: 110 },
    { title: '日前均价', width: 100, render: (_, r) => r.day_ahead?.avg ?? '—' },
    { title: '日前范围', width: 140, render: (_, r) => r.day_ahead ? `${r.day_ahead.min} ~ ${r.day_ahead.max}` : '—' },
    { title: '实时均价', width: 100, render: (_, r) => r.real_time?.avg ?? '—' },
    { title: '实时范围', width: 140, render: (_, r) => r.real_time ? `${r.real_time.min} ~ ${r.real_time.max}` : '—' },
    { title: '点数', width: 80, render: (_, r) => `${r.day_ahead?.points ?? 0}/${r.real_time?.points ?? 0}` },
    {
      title: '操作', width: 80,
      render: (_, r) => (
        <Popconfirm title={`删除 ${r.date} 现货价格？`} onConfirm={() => handleDelete(r.date)}>
          <Button danger size="small">删除</Button>
        </Popconfirm>
      ),
    },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Card title="现货价格导入（日前 / 实时 96点）" style={{ marginBottom: 16 }}>
        <Alert
          type="info" showIcon style={{ marginBottom: 16 }}
          message="用于「套餐年度测算」自动合成批发分时价，让批发价假设有历史数据依据。"
          description="日文件格式：Excel「汇总」页，日前价格/实时价格两列 96 行（00:15~24:00，元/MWh）。日期从文件名解析（2027-01-06.xlsx / 1月6日.xlsx / 1-6.xlsx）。可一次上传多个日文件。"
        />
        <Row gutter={12} style={{ marginBottom: 12 }}>
          <Col xs={24} md={4}>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>年份（文件名无年份时用）</div>
            <InputNumber style={{ width: '100%' }} value={year} onChange={(v) => setYear(Number(v) || new Date().getFullYear())} />
          </Col>
          <Col xs={24} md={20} style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
            <Button icon={<DownloadOutlined />} onClick={() => { window.location.href = downloadSpotTemplate(); }}>下载模板</Button>
            <Upload
              accept=".xlsx,.xls"
              multiple
              showUploadList={false}
              beforeUpload={(f, fl) => { handlePreview(fl as File[]); return false; }}
            >
              <Button icon={<UploadOutlined />} loading={previewing}>上传校验（可多选）</Button>
            </Upload>
            <Button
              type="primary" icon={<CheckCircleOutlined />}
              disabled={!files.length || (preview ? preview.ok_count === 0 : true)}
              loading={importing}
              onClick={handleImport}
            >
              确认导入
            </Button>
          </Col>
        </Row>
        {preview && (
          <Table
            size="small" rowKey="file"
            columns={previewCols} dataSource={preview.results}
            pagination={false} style={{ marginTop: 8 }}
            locale={{ emptyText: <Empty /> }}
          />
        )}
      </Card>

      <Card title="月度现货统计" style={{ marginBottom: 16 }}>
        <Space wrap style={{ marginBottom: 12 }}>
          <DatePicker picker="month" value={dayjs(statMonth)} onChange={(v) => setStatMonth(v ? v.format('YYYY-MM') : statMonth)} />
        </Space>
        {monthly && (monthly.day_ahead || monthly.real_time) ? (
          <Row gutter={16}>
            <Col xs={24} md={12}>
              <Descriptions size="small" bordered column={1} title="日前">
                <Descriptions.Item label="均价">{monthly.day_ahead?.avg ?? '—'} 元/MWh</Descriptions.Item>
                <Descriptions.Item label="范围">{monthly.day_ahead ? `${monthly.day_ahead.min} ~ ${monthly.day_ahead.max}` : '—'}</Descriptions.Item>
                <Descriptions.Item label="点数">{monthly.day_ahead?.points ?? 0}</Descriptions.Item>
              </Descriptions>
            </Col>
            <Col xs={24} md={12}>
              <Descriptions size="small" bordered column={1} title="实时">
                <Descriptions.Item label="均价">{monthly.real_time?.avg ?? '—'} 元/MWh</Descriptions.Item>
                <Descriptions.Item label="范围">{monthly.real_time ? `${monthly.real_time.min} ~ ${monthly.real_time.max}` : '—'}</Descriptions.Item>
                <Descriptions.Item label="点数">{monthly.real_time?.points ?? 0}</Descriptions.Item>
              </Descriptions>
            </Col>
          </Row>
        ) : (
          <Empty description="该月无现货价格数据" />
        )}
      </Card>

      <Card
        title="已导入现货价格"
        extra={<Space><Text type="secondary">共 {rows.length} 天</Text></Space>}
      >
        <Table
          size="small" rowKey="date"
          columns={recCols} dataSource={rows}
          loading={loading}
          pagination={{ pageSize: 15 }}
          locale={{ emptyText: <Empty description="暂无数据，请上传日文件" /> }}
        />
      </Card>
    </div>
  );
}
