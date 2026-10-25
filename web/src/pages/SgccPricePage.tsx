import { useCallback, useEffect, useState } from 'react';
import { App, Button, Card, Col, Empty, Row, Statistic, Table } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { FilePdfOutlined } from '@ant-design/icons';
import { EChart } from '@/components/charts/EChart';
import { fetchSgccPrices, getSgccPdfUrl, type SgccPriceData } from '@/api/sgcc';

const fmt6 = (v?: number) => (typeof v === 'number' ? v.toFixed(6) : '-');
const fmt2 = (v?: number) => (typeof v === 'number' ? v.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }) : '-');

const columns: ColumnsType<SgccPriceData> = [
  { title: '月份', dataIndex: '_id', width: 110, fixed: 'left' },
  { title: '代理购电规模(万kWh)', dataIndex: 'purchase_scale_kwh', width: 170, render: fmt2 },
  { title: '代理购电价格(元/kWh)', dataIndex: 'purchase_price', width: 180, render: fmt6 },
  { title: '平均上网电价(元/kWh)', dataIndex: 'avg_on_grid_price', width: 180, render: fmt6 },
  { title: '历史偏差折价(元/kWh)', dataIndex: 'historical_deviation_discount', width: 180, render: fmt6 },
  { title: '上网环节线损(元/kWh)', dataIndex: 'network_loss_price', width: 180, render: fmt6 },
  { title: '系统运行费折价(元/kWh)', dataIndex: 'system_op_cost_discount', width: 190, render: fmt6 },
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

  useEffect(() => {
    load();
  }, [load]);

  const latest = pageData[0];

  return (
    <div>
      {latest && (
        <Row gutter={16} style={{ marginBottom: 16 }}>
          <Col xs={24} md={8}>
            <Card>
              <Statistic title="数据月份" value={latest._id} />
              <Statistic title="代理购电价格(元/kWh)" value={latest.purchase_price ?? 0} precision={6} valueStyle={{ color: '#389e0d' }} />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card>
              <Statistic title="代理购电规模(万kWh)" value={latest.purchase_scale_kwh ?? 0} precision={2} />
              <Statistic title="平均上网电价(元/kWh)" value={latest.avg_on_grid_price ?? 0} precision={6} />
            </Card>
          </Col>
          <Col xs={24} md={8}>
            <Card>
              <Statistic title="上网环节线损(元/kWh)" value={latest.network_loss_price ?? 0} precision={6} valueStyle={{ color: '#d46b08' }} />
              <Statistic title="系统运行费折价(元/kWh)" value={latest.system_op_cost_discount ?? 0} precision={6} />
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
                { type: 'value', name: '价格(元/kWh)', axisLabel: { formatter: (v: number) => v.toFixed(3) } },
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
          locale={{ emptyText: <Empty description="暂无数据（代购电价仅支持读取，写入由数据脚本完成）" /> }}
        />
      </Card>
    </div>
  );
}
