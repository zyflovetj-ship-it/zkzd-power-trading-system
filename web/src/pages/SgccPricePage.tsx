import { useCallback, useEffect, useState } from 'react';
import { Alert, App, Button, Card, Col, Empty, Input, InputNumber, Row, Space, Statistic, Table, Upload } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { FilePdfOutlined, UploadOutlined } from '@ant-design/icons';
import { EChart } from '@/components/charts/EChart';
import {
  fetchSgccPrices,
  getMissingMonths,
  getSgccPdfUrl,
  importSgccExcel,
  importSgccPdf,
  type SgccPriceData,
} from '@/api/sgcc';

const fmt2 = (v?: number) =>
  typeof v === 'number'
    ? v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
    : '-';

const columns: ColumnsType<SgccPriceData> = [
  { title: '月份', dataIndex: '_id', width: 110, fixed: 'left' },
  { title: '代理购电规模(万kWh)', dataIndex: 'purchase_scale_kwh', width: 170, render: fmt2 },
  { title: '代理购电价格(元/MWh)', dataIndex: 'purchase_price', width: 180, render: fmt2 },
  { title: '平均上网电价(元/MWh)', dataIndex: 'avg_on_grid_price', width: 180, render: fmt2 },
  { title: '历史偏差折价(元/MWh)', dataIndex: 'historical_deviation_discount', width: 180, render: fmt2 },
  { title: '上网环节线损(元/MWh)', dataIndex: 'network_loss_price', width: 180, render: fmt2 },
  { title: '系统运行费折价(元/MWh)', dataIndex: 'system_op_cost_discount', width: 190, render: fmt2 },
  {
    title: '操作',
    key: 'op',
    width: 120,
    fixed: 'right',
    render: (_: unknown, r: SgccPriceData) => (
      <Button size="small" icon={<FilePdfOutlined />} onClick={() => window.open(getSgccPdfUrl(r._id), '_blank')}>
        查看公告
      </Button>
    ),
  },
];

export default function SgccPricePage() {
  const { message } = App.useApp();
  const [loading, setLoading] = useState(false);
  const [pageData, setPageData] = useState<SgccPriceData[]>([]);
  const [chartData, setChartData] = useState<SgccPriceData[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [year, setYear] = useState<number>(new Date().getFullYear());
  const [missing, setMissing] = useState<string[]>([]);
  const [pdfMonth, setPdfMonth] = useState<string>('');
  const [importing, setImporting] = useState(false);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const res = await fetchSgccPrices({ page, pageSize });
      setPageData(res.pageData ?? []);
      setTotal(res.total ?? 0);
      if (page === 1) setChartData(res.chartData ?? []);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '加载失败');
    } finally {
      setLoading(false);
    }
  }, [page, pageSize, message]);

  const loadMissing = useCallback(async () => {
    try {
      const r = await getMissingMonths(year);
      setMissing(r.missing ?? []);
    } catch {
      setMissing([]);
    }
  }, [year]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    loadMissing();
  }, [loadMissing]);

  const handleExcel = async (file: File) => {
    setImporting(true);
    try {
      const res: any = await importSgccExcel(file, year);
      message.success(`导入完成：新增 ${res.inserted ?? 0}，更新 ${res.updated ?? 0}`);
      await load();
      await loadMissing();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '导入失败');
    } finally {
      setImporting(false);
    }
    return false;
  };

  const handlePdf = async (file: File) => {
    if (!pdfMonth) {
      message.warning('请先填写归属月份（如 2027-11）');
      return false;
    }
    setImporting(true);
    try {
      const res: any = await importSgccPdf(file, pdfMonth);
      message.success(res?.message || 'PDF 已上传');
      await load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '上传失败');
    } finally {
      setImporting(false);
    }
    return false;
  };

  const latest = pageData[0];

  return (
    <div>
      {missing.length > 0 && (
        <Alert
          type="warning"
          showIcon
          style={{ marginBottom: 16 }}
          message={`${year} 年还有 ${missing.length} 个月未录入代购电价（代理购电价格按月调整）`}
          description={`缺失月份：${missing.join('、')}`}
        />
      )}

      <Card title="数据导入（代理购电价格按月更新）" style={{ marginBottom: 16 }}>
        <Space wrap size="middle">
          <span>年份</span>
          <InputNumber min={2000} max={2100} value={year} onChange={(v) => setYear(Number(v) || year)} />
          <Upload showUploadList={false} beforeUpload={(f) => handleExcel(f as File)}>
            <Button icon={<UploadOutlined />} loading={importing}>
              导入 Excel
            </Button>
          </Upload>
          <span style={{ marginLeft: 16 }}>PDF 归属月份</span>
          <Input
            placeholder="YYYY-MM"
            value={pdfMonth}
            onChange={(e) => setPdfMonth(e.target.value)}
            style={{ width: 120 }}
          />
          <Upload showUploadList={false} beforeUpload={(f) => handlePdf(f as File)}>
            <Button icon={<FilePdfOutlined />} loading={importing}>
              上传 PDF 公告
            </Button>
          </Upload>
        </Space>
      </Card>

      {latest && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col xs={24} md={8}>
            <Card>
              <Statistic title="数据月份" value={latest._id} />
              <Statistic title="代理购电价格(元/MWh)" value={latest.purchase_price ?? 0} precision={2} valueStyle={{ color: '#389e0d' }} />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card>
              <Statistic title="代理购电规模(万kWh)" value={latest.purchase_scale_kwh ?? 0} precision={2} />
              <Statistic title="平均上网电价(元/MWh)" value={latest.avg_on_grid_price ?? 0} precision={2} />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card>
              <Statistic title="上网环节线损(元/MWh)" value={latest.network_loss_price ?? 0} precision={2} valueStyle={{ color: '#d46b08' }} />
              <Statistic title="系统运行费折价(元/MWh)" value={latest.system_op_cost_discount ?? 0} precision={2} />
            </Card>
          </Col>
        </Row>
      )}

      {chartData.length > 0 && (
        <Card title="历史趋势" style={{ marginBottom: 16 }}>
          <EChart
            height={380}
            option={{
              tooltip: { trigger: 'axis' },
              legend: { data: ['代理购电价格', '平均上网电价', '代理购电规模'] },
              grid: { left: 60, right: 60, bottom: 40, top: 50 },
              xAxis: { type: 'category', data: chartData.map((d) => d._id) },
              yAxis: [
                { type: 'value', name: '价格(元/MWh)', axisLabel: { formatter: (v: number) => v.toFixed(0) } },
                { type: 'value', name: '规模(万kWh)' },
              ],
              series: [
                { name: '代理购电规模', type: 'bar', yAxisIndex: 1, data: chartData.map((d) => d.purchase_scale_kwh), itemStyle: { color: '#8884d8' } },
                { name: '代理购电价格', type: 'line', yAxisIndex: 0, data: chartData.map((d) => d.purchase_price), itemStyle: { color: '#82ca9d' } },
                { name: '平均上网电价', type: 'line', yAxisIndex: 0, data: chartData.map((d) => d.avg_on_grid_price), itemStyle: { color: '#ffc658' } },
              ],
            }}
          />
        </Card>
      )}

      <Card title="历史数据详情">
        <Table<SgccPriceData>
          rowKey="_id"
          columns={columns}
          dataSource={pageData}
          loading={loading}
          scroll={{ x: 'max-content' }}
          pagination={{
            current: page,
            pageSize,
            total,
            showSizeChanger: true,
            showTotal: (t) => `共 ${t} 条`,
            onChange: (p, ps) => {
              setPage(p);
              setPageSize(ps);
            },
          }}
          locale={{ emptyText: <Empty description="暂无数据，请用上方「导入 Excel」录入代购电价" /> }}
        />
      </Card>
    </div>
  );
}
