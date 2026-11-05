import { useCallback, useEffect, useState } from 'react';
import {
  Alert, App, Button, Card, Col, Empty, InputNumber, Popconfirm, Row, Select, Space,
  Statistic, Table, Tag, Typography, Upload,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { DownloadOutlined, UploadOutlined, CheckCircleOutlined, PlayCircleOutlined, FilePdfOutlined } from '@ant-design/icons';
import {
  batchCalcBills,
  deleteBillRecords,
  downloadBillTemplate,
  fetchBillRecords,
  importBillExcel,
  previewBillExcel,
  parseBillPdfs,
  importParsedBills,
  type BillRow,
  type ParsedBillRecord,
} from '@/api/dataImport';
import { fetchPackages, type RetailPackageListItem } from '@/api/packages';

const { Text } = Typography;

export default function BillVerificationPage() {
  const { message } = App.useApp();
  const [packages, setPackages] = useState<RetailPackageListItem[]>([]);
  const [packageId, setPackageId] = useState<string>('');
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<{ ok: boolean; problems: string[]; record_count: number; sample: BillRow[] } | null>(null);
  const [previewing, setPreviewing] = useState(false);
  // 账单PDF自动解析
  const [parsing, setParsing] = useState(false);
  const [parsed, setParsed] = useState<ParsedBillRecord[]>([]);
  const [parsedProblems, setParsedProblems] = useState<string[]>([]);
  const [importingParsed, setImportingParsed] = useState(false);
  const [importing, setImporting] = useState(false);
  const [rows, setRows] = useState<BillRow[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(false);
  // 批量测算
  const [market, setMarket] = useState<number>(330);
  const [pointwise, setPointwise] = useState<boolean>(true);
  const [holdingRatio, setHoldingRatio] = useState<number>(0.9);
  const [marketSource, setMarketSource] = useState<'manual' | 'system'>('manual');
  const [calcRows, setCalcRows] = useState<any[]>([]);
  const [summary, setSummary] = useState<Record<string, number> | null>(null);
  const [calculating, setCalculating] = useState(false);

  useEffect(() => {
    fetchPackages({ page: 1, page_size: 100 })
      .then((r) => setPackages(r.items))
      .catch(() => setPackages([]));
  }, []);

  const loadRecords = useCallback(() => {
    setLoading(true);
    fetchBillRecords({})
      .then((r) => { setTotal(r.total); setRows(r.rows); })
      .catch((e) => message.error(e?.response?.data?.detail || '加载失败'))
      .finally(() => setLoading(false));
  }, [message]);

  useEffect(() => { loadRecords(); }, [loadRecords]);

  const handlePreview = async (f: File) => {
    setFile(f); setPreview(null); setPreviewing(true);
    try {
      const r = await previewBillExcel(f);
      setPreview(r);
      if (r.ok) message.success(`解析到 ${r.record_count} 条核查联`);
      else message.warning('校验发现问题');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '校验失败');
    } finally { setPreviewing(false); }
  };

  const handleImport = async () => {
    if (!file) { message.warning('请先上传文件（Excel 或 国网电费账单 PDF）'); return; }
    setImporting(true);
    try {
      const r = await importBillExcel(file);
      message.success(`导入完成：新增 ${r.inserted} 条，更新 ${r.updated} 条`);
      setPreview(null); setFile(null); loadRecords();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '导入失败');
    } finally { setImporting(false); }
  };

  const handleParsePdfs = async (fl: File[]) => {
    if (!fl.length) return;
    setParsing(true); setParsed([]); setParsedProblems([]);
    try {
      const r = await parseBillPdfs(fl);
      const okRecs = r.results.filter((x) => x.ok && x.record).map((x) => x.record!);
      const probs = r.results.filter((x) => !x.ok).flatMap((x) => x.problems.map((p) => `${x.file}: ${p}`));
      setParsed(okRecs);
      setParsedProblems(probs);
      message.info(`解析完成：成功 ${r.ok_count} 份，失败 ${r.fail_count} 份`);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '解析失败');
    } finally { setParsing(false); }
  };

  const handleImportParsed = async () => {
    if (!parsed.length) { message.warning('无已解析数据'); return; }
    setImportingParsed(true);
    try {
      const r = await importParsedBills(parsed);
      message.success(`PDF数据入库：新增 ${r.inserted}，更新 ${r.updated}`);
      setParsed([]);
      setParsedProblems([]);
      loadRecords();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '入库失败');
    } finally { setImportingParsed(false); }
  };

  const handleDelete = async (r: BillRow) => {
    try {
      const res = await deleteBillRecords({ customer_id: r.customer_id, period: r.period });
      message.success(`已删除 ${res.deleted} 条`);
      loadRecords();
    } catch (e: any) { message.error(e?.response?.data?.detail || '删除失败'); }
  };

  const handleBatchCalc = async () => {
    if (!packageId) { message.warning('请先选择套餐'); return; }
    setCalculating(true);
    setCalcRows([]); setSummary(null);
    try {
      const r = await batchCalcBills({
        package_id: packageId,
        market: { wholesale_price: market },
        pointwise,
        holding_ratio: holdingRatio,
        market_source: marketSource,
      });
      setCalcRows(r.rows);
      setSummary(r.summary);
      message.success(`测算完成：${r.summary?.success ?? 0} 成功 / ${r.summary?.failed ?? 0} 失败`);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '测算失败');
    } finally { setCalculating(false); }
  };

  const billCols: ColumnsType<BillRow> = [
    { title: '客户', dataIndex: 'customer_name', width: 180 },
    { title: '月份', dataIndex: 'period', width: 100 },
    { title: '月总电量(MWh)', dataIndex: 'total_mwh', width: 130, render: (v) => v?.toFixed(2) },
    { title: '峰/平/谷', width: 160, render: (_, r) => `${r.peak_mwh ?? '-'}/${r.flat_mwh ?? '-'}/${r.valley_mwh ?? '-'}` },
    { title: '现状电费(元)', dataIndex: 'current_amount', width: 130, render: (v) => (v == null ? '—' : v.toFixed(2)) },
    { title: '用电类型', dataIndex: 'ktype', width: 150, render: (v) => v || '—' },
    {
      title: '操作', width: 90,
      render: (_, r) => (
        <Popconfirm title={`删除 ${r.period} 该核查联？`} onConfirm={() => handleDelete(r)}>
          <Button danger size="small">删除</Button>
        </Popconfirm>
      ),
    },
  ];

  const calcCols: ColumnsType<any> = [
    { title: '客户', dataIndex: 'customer', width: 150 },
    { title: '月份', dataIndex: 'period', width: 90 },
    { title: '电量', dataIndex: 'volume_mwh', width: 100, render: (v) => v?.toFixed?.(2) },
    { title: '峰价', dataIndex: 'peak_price', width: 90, render: (v) => v?.toFixed?.(2) },
    { title: '平价', dataIndex: 'flat_price', width: 90, render: (v) => v?.toFixed?.(2) },
    { title: '谷价', dataIndex: 'valley_price', width: 90, render: (v) => v?.toFixed?.(2) },
    { title: '零售均价', dataIndex: 'retail_avg', width: 100, render: (v) => v?.toFixed?.(2) },
    { title: '封顶价', dataIndex: 'cap_price', width: 100, render: (v) => <span style={{ color: '#d46b08' }}>{v?.toFixed?.(2)}</span> },
    { title: '封顶', dataIndex: 'capped', width: 70, render: (v) => (v ? <Tag color="red">触发</Tag> : '—') },
    { title: '最终电价', dataIndex: 'settle_price', width: 100, render: (v) => <b>{v?.toFixed?.(2)}</b> },
    { title: '套餐电费', dataIndex: 'package_amount', width: 110, render: (v) => v?.toFixed?.(2) },
    { title: '现状电费', dataIndex: 'current_amount', width: 110, render: (v) => (v == null ? '—' : v.toFixed(2)) },
    { title: '差额', dataIndex: 'diff', width: 100, render: (v) => (v == null ? '—' : <span style={{ color: v < 0 ? '#389e0d' : '#cf1322' }}>{v.toFixed(2)}</span>) },
    { title: '结论', dataIndex: 'verdict', width: 90 },
    { title: '错误', dataIndex: 'error', width: 120, render: (v) => (v ? <span style={{ color: 'red' }}>{v}</span> : '—') },
  ];

  const parsedCols: ColumnsType<ParsedBillRecord> = [
    { title: '月份', dataIndex: 'period', width: 90 },
    { title: '户名', dataIndex: 'customer_name', width: 190 },
    { title: '户号', dataIndex: 'account_id', width: 130 },
    { title: '总电量(MWh)', dataIndex: 'total_mwh', width: 110, render: (v?: number) => v?.toFixed(3) },
    { title: '峰', dataIndex: 'peak_mwh', width: 90, render: (v?: number) => v?.toFixed(3) },
    { title: '平', dataIndex: 'flat_mwh', width: 90, render: (v?: number) => v?.toFixed(3) },
    { title: '谷', dataIndex: 'valley_mwh', width: 90, render: (v?: number) => v?.toFixed(3) },
    { title: '账单电费(元)', dataIndex: 'current_amount', width: 120, render: (v?: number) => v?.toFixed(2) },
    { title: '市场化购电费', dataIndex: 'market_fee', width: 110, render: (v?: number) => v?.toFixed(2) },
    { title: '用电类型', dataIndex: 'ktype', width: 110 },
    { title: '客户匹配', dataIndex: 'customer_id', width: 90, render: (v) => (v ? <Tag color="green">已匹配</Tag> : <Tag color="red">未建档</Tag>) },
  ];

  return (
    <div style={{ padding: 16 }}>
      <Card title="账单 PDF 自动解析（推荐）" style={{ marginBottom: 16 }}>
        <Alert
          type="info" showIcon style={{ marginBottom: 12 }}
          message="直接上传国网电费账单 PDF，自动提取 月份/总电量/峰平谷/账单电费/市场化购电费/用电类型。"
          description="解析成功后点「PDF数据入库」直接生成核查联，无需手工填 Excel。"
        />
        <Space wrap>
          <Upload
            accept=".pdf"
            multiple
            showUploadList={false}
            beforeUpload={(f, fl) => { handleParsePdfs(fl as File[]); return false; }}
          >
            <Button icon={<FilePdfOutlined />} loading={parsing}>
              上传账单PDF（可多选）
            </Button>
          </Upload>
          <Button
            type="primary"
            icon={<CheckCircleOutlined />}
            disabled={!parsed.length}
            loading={importingParsed}
            onClick={handleImportParsed}
          >
            PDF数据入库（{parsed.length} 条）
          </Button>
        </Space>
        {parsedProblems.length > 0 && (
          <Alert
            type="warning" showIcon style={{ marginTop: 12 }}
            message="部分文件解析失败"
            description={<div>{parsedProblems.map((p, i) => <div key={i}>• {p}</div>)}</div>}
          />
        )}
        {parsed.length > 0 && (
          <Table
            size="small" rowKey={(r) => String(r.period) + String(r.account_id)}
            columns={parsedCols} dataSource={parsed}
            pagination={false} style={{ marginTop: 12 }}
            scroll={{ x: 1300 }}
          />
        )}
      </Card>

      <Card title="核查联批量导入" style={{ marginBottom: 16 }}>
        <Alert
          type="info" showIcon style={{ marginBottom: 16 }}
          message="核查联用于「路径B」测算：只需月度峰平谷电量 + 现状电费，无需96点负荷曲线。"
          description="批量导入多客户核查联后，可选定套餐一次性批量测算，输出每户每月电价与套餐vs现状对比。"
        />
        <Row gutter={12} style={{ marginBottom: 12 }}>
          <Col xs={24} md={16} style={{ display: 'flex', alignItems: 'flex-end', gap: 8 }}>
            <Button icon={<DownloadOutlined />} onClick={async () => { try { await downloadBillTemplate(); } catch (e: any) { message.error(e?.response?.data?.detail || e?.message || '下载模板失败'); } }}>下载模板</Button>
            <Upload accept=".xlsx,.xls,.pdf" showUploadList={false} beforeUpload={(f) => { handlePreview(f as File); return false; }}>
              <Button icon={<UploadOutlined />} loading={previewing}>上传校验</Button>
            </Upload>
            <Button type="primary" icon={<CheckCircleOutlined />} disabled={!file || (preview ? !preview.ok : true)} loading={importing} onClick={handleImport}>
              确认导入
            </Button>
          </Col>
        </Row>
        {file && (
          <Alert
            type={preview ? (preview.ok ? 'success' : 'warning') : 'info'} showIcon style={{ marginBottom: 12 }}
            message={`已选文件：${file.name}`}
            description={
              preview
                ? <div>
                    <div>{preview.ok ? `解析到 ${preview.record_count} 条核查联，可导入` : '校验未通过'}</div>
                    {preview.problems.map((p, i) => <div key={i} style={{ color: '#d46b08' }}>⚠ {p}</div>)}
                  </div>
                : '正在校验…'
            }
          />
        )}
      </Card>

      <Card
        title="已导入核查联"
        extra={<Text type="secondary">共 {total} 条</Text>}
        style={{ marginBottom: 16 }}
      >
        <Table
          size="small" rowKey={(r) => `${r.customer_id}-${r.period}`}
          columns={billCols} dataSource={rows} loading={loading}
          pagination={{ pageSize: 20 }}
          locale={{ emptyText: <Empty description="暂无核查联，请上传导入" /> }}
          scroll={{ x: 1000 }}
        />
      </Card>

      <Card title="批量测算（路径B）">
        <Space wrap style={{ marginBottom: 12 }}>
          <span>套餐：</span>
          <Select
            style={{ width: 240 }} value={packageId || undefined} onChange={setPackageId}
            placeholder="选择套餐"
            options={packages.map((p) => ({ label: p.package_name || p.id, value: p.id }))}
          />
          <span>批发价(元/MWh)：</span>
          <InputNumber value={market} onChange={(v) => setMarket(Number(v) || 0)} style={{ width: 120 }} />
          <span>算法：</span>
          <Select
            style={{ width: 190 }}
            value={pointwise ? 'pw' : 'seg'}
            onChange={(v) => setPointwise(v === 'pw')}
            options={[
              { label: '逐点（对齐Excel精度）', value: 'pw' },
              { label: '三段聚合（近似）', value: 'seg' },
            ]}
          />
          <span>持仓比例：</span>
          <InputNumber value={holdingRatio} onChange={(v) => setHoldingRatio(Number(v) || 0)} step={0.05} style={{ width: 90 }} />
          <span>行情来源：</span>
          <Select
            style={{ width: 190 }}
            value={marketSource}
            onChange={(v) => setMarketSource(v)}
            options={[
              { label: '手工填写批发价', value: 'manual' },
              { label: '成本基线（自动）', value: 'system' },
            ]}
          />
          <Button type="primary" icon={<PlayCircleOutlined />} loading={calculating} onClick={handleBatchCalc}>
            批量测算
          </Button>
        </Space>

        {summary && (
          <Row gutter={16} style={{ marginBottom: 12 }}>
            <Col><Statistic title="测算条数" value={summary.count} /></Col>
            <Col><Statistic title="成功" value={summary.success} valueStyle={{ color: '#389e0d' }} /></Col>
            <Col><Statistic title="失败" value={summary.failed} valueStyle={{ color: '#cf1322' }} /></Col>
            <Col><Statistic title="总电量(MWh)" value={summary.total_volume_mwh} precision={2} /></Col>
            <Col><Statistic title="套餐电费合计" value={summary.total_package_amount} precision={2} /></Col>
            <Col><Statistic title="现状电费合计" value={summary.total_current_amount} precision={2} /></Col>
          </Row>
        )}

        <Table
          size="small" rowKey={(r, i) => String(i)}
          columns={calcCols} dataSource={calcRows}
          pagination={{ pageSize: 20 }}
          locale={{ emptyText: <Empty description="选择套餐后点「批量测算」" /> }}
          scroll={{ x: 1600 }}
        />
      </Card>
    </div>
  );
}
