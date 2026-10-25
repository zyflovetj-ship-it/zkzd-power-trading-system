import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Button, Card, Col, DatePicker, Descriptions, Empty, Row, Space, Table, Tag, message } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import dayjs, { type Dayjs } from 'dayjs';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import {
  createSnapshot,
  getAlerts,
  getEngineBacktest,
  getEngineExposure,
  getEngineLimits,
  getEngineVar,
  getValidate,
  runStressSuite,
  type AlertItem,
  type StressScenarioResult,
} from '@/api/riskEngine';

const LEVEL_TAG: Record<string, string> = {
  ok: 'success',
  warn: 'warning',
  fail: 'error',
  low: 'green',
  medium: 'orange',
  high: 'red',
  info: 'blue',
  warning: 'orange',
  critical: 'red',
};

const fmt = (v: number | undefined, digits = 2) =>
  (v ?? 0).toLocaleString('zh-CN', { maximumFractionDigits: digits });

/**
 * 风险驾驶舱。
 *
 * 数据链路：数据校验 → 96 点敞口 → VaR/CVaR → 回测 → 限额 → 压力测试 → 预警
 * 对应后端 /api/v1/risk-engine/*（webapp/api/v1_risk_engine.py）
 */
export default function RiskDashboardPage() {
  const [date, setDate] = useState<Dayjs>(dayjs().subtract(1, 'day'));
  const dateStr = date.format('YYYY-MM-DD');

  const validateQ = useQuery({ queryKey: ['riskEngineValidate', dateStr], queryFn: () => getValidate(dateStr) });
  const exposureQ = useQuery({ queryKey: ['riskEngineExposure', dateStr], queryFn: () => getEngineExposure(dateStr) });
  const varQ = useQuery({ queryKey: ['riskEngineVar', dateStr], queryFn: () => getEngineVar(dateStr) });
  const limitsQ = useQuery({ queryKey: ['riskEngineLimits', dateStr], queryFn: () => getEngineLimits(dateStr) });
  const backtestQ = useQuery({ queryKey: ['riskEngineBacktest', dateStr], queryFn: () => getEngineBacktest(dateStr) });
  const stressQ = useQuery({ queryKey: ['riskEngineStress', dateStr], queryFn: () => runStressSuite(dateStr) });
  const alertsQ = useQuery({ queryKey: ['riskEngineAlerts'], queryFn: () => getAlerts('open') });

  const loading =
    validateQ.isLoading || exposureQ.isLoading || varQ.isLoading || limitsQ.isLoading ||
    backtestQ.isLoading || stressQ.isLoading || alertsQ.isLoading;

  const validate = validateQ.data;
  const summary = exposureQ.data?.summary;
  const curve = exposureQ.data?.curve ?? [];
  const varData = varQ.data;
  const limits = limitsQ.data;
  const backtest = backtestQ.data;
  const stress = stressQ.data;
  const alerts = alertsQ.data?.items ?? [];

  const refreshAll = () => {
    validateQ.refetch(); exposureQ.refetch(); varQ.refetch(); limitsQ.refetch();
    backtestQ.refetch(); stressQ.refetch(); alertsQ.refetch();
  };

  const onSnapshot = async () => {
    try {
      const r = await createSnapshot(dateStr);
      message.success('快照已保存：' + String(r?.snapshot_id ?? ''));
    } catch (e: unknown) {
      message.error('保存快照失败');
    }
  };

  // ---- 96 点敞口：柱=净敞口(MWh)，线=电价(元/MWh)
  const exposureOption: EChartsOption = useMemo(
    () => ({
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: ['净敞口', '电价'] },
      grid: baseGrid,
      xAxis: {
        type: 'category',
        data: curve.map((p) => p.period_label),
        axisLabel: { interval: 11, fontSize: 11 },
      },
      yAxis: [
        { type: 'value', name: 'MWh', axisLabel: { fontSize: 11 } },
        { type: 'value', name: '元/MWh', position: 'right', splitLine: { show: false }, axisLabel: { fontSize: 11 } },
      ],
      series: [
        {
          name: '净敞口',
          type: 'bar',
          data: curve.map((p) => Number(p.net_position_mwh.toFixed(4))),
          itemStyle: { color: CHART_COLORS[0] },
        },
        {
          name: '电价',
          type: 'line',
          yAxisIndex: 1,
          smooth: true,
          showSymbol: false,
          data: curve.map((p) => Number(p.fwd_price.toFixed(2))),
          itemStyle: { color: CHART_COLORS[2] },
          lineStyle: { width: 2 },
        },
      ],
    }),
    [curve],
  );

  // ---- 压力测试：横向条形，负冲击标红
  const stressOption: EChartsOption = useMemo(() => {
    const list = [...(stress?.scenarios ?? [])].sort((a, b) => a.pnl_impact - b.pnl_impact);
    return {
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      grid: { ...baseGrid, left: 180 },
      xAxis: { type: 'value', name: '冲击(元)' },
      yAxis: { type: 'category', data: list.map((s) => s.name), axisLabel: { fontSize: 11 } },
      series: [
        {
          type: 'bar',
          data: list.map((s) => ({
            value: Number(s.pnl_impact.toFixed(2)),
            itemStyle: { color: s.pnl_impact < 0 ? CHART_COLORS[7] : CHART_COLORS[3] },
          })),
          label: {
            show: true,
            position: 'right',
            // ECharts 的 formatter 入参是 CallbackDataParams，value 可能非 number，这里显式收窄
            formatter: (p: unknown) => fmt(Number((p as { value: number }).value), 0),
          },
        },
      ],
    };
  }, [stress]);

  const kpiItems = useMemo(
    () => [
      { label: '价格敞口(元)', value: fmt(summary?.price_exposure_yuan), color: CHART_COLORS[2] },
      { label: '净敞口(MWh)', value: fmt(summary?.total_net_mwh, 3), color: CHART_COLORS[0] },
      { label: 'VaR 95%(元)', value: fmt(varData?.var_yuan), color: CHART_COLORS[1] },
      { label: 'CVaR 95%(元)', value: fmt(varData?.cvar_yuan), color: CHART_COLORS[5] },
      { label: '覆盖率', value: ((summary?.coverage_ratio ?? 0) * 100).toFixed(1) + '%', color: CHART_COLORS[3] },
      { label: '风险等级', value: summary?.risk_level === 'high' ? '高' : summary?.risk_level === 'medium' ? '中' : '低', color: CHART_COLORS[7] },
    ],
    [summary, varData],
  );

  const stressColumns: ColumnsType<StressScenarioResult> = [
    { title: '场景', dataIndex: 'name', width: 200 },
    { title: '类别', dataIndex: 'category', width: 80 },
    {
      title: '冲击(元)', dataIndex: 'pnl_impact', width: 130, align: 'right',
      render: (v: number) => <span style={{ color: v < 0 ? '#f5222d' : '#52c41a', fontWeight: 600 }}>{fmt(v)}</span>,
    },
    {
      title: '占名义规模', dataIndex: 'impact_ratio', width: 110, align: 'right',
      render: (v: number) => (v * 100).toFixed(1) + '%',
    },
    { title: '最不利时段', dataIndex: 'worst_period_label', width: 110 },
    {
      title: '追加保证金(元)', dataIndex: 'margin_call_estimate', width: 140, align: 'right',
      render: (v: number) => fmt(v),
    },
  ];

  const alertColumns: ColumnsType<AlertItem> = [
    {
      title: '级别', dataIndex: 'severity', width: 90,
      render: (v: string) => <Tag color={LEVEL_TAG[v] ?? 'default'}>{v}</Tag>,
    },
    { title: '标题', dataIndex: 'title', width: 260 },
    { title: '说明', dataIndex: 'message' },
    { title: '来源', dataIndex: 'source', width: 180 },
    { title: '类型', dataIndex: 'alert_type', width: 90 },
  ];

  return (
    <Space direction="vertical" size={16} style={{ width: '100%' }}>
      <Card
        size="small"
        title="风险驾驶舱"
        extra={
          <Space>
            <DatePicker
              value={date}
              onChange={(d) => d && setDate(d)}
              allowClear={false}
              placeholder="交割日"
            />
            <Button onClick={refreshAll} loading={loading}>刷新</Button>
            <Button type="primary" onClick={onSnapshot}>保存快照</Button>
          </Space>
        }
      >
        {validate && validate.overall !== 'ok' ? (
          <Alert
            type={validate.overall === 'warn' ? 'warning' : 'error'}
            showIcon
            message={'数据校验：' + (validate.overall === 'warn' ? '有告警' : '未通过')}
            description={
              <ul style={{ margin: 0, paddingLeft: 20 }}>
                {validate.checks.filter((c) => c.level !== 'ok').map((c) => (
                  <li key={c.name}>{c.name}：{c.detail}</li>
                ))}
              </ul>
            }
          />
        ) : (
          <Alert type="success" showIcon message="数据校验通过" />
        )}
      </Card>

      <KpiCards items={kpiItems} loading={loading} columns={6} />

      <ChartCard
        title="分时段敞口（96 点）· 柱=净敞口 MWh，线=电价 元/MWh"
        option={exposureOption}
        height={340}
        loading={exposureQ.isLoading}
      />

      <Row gutter={[16, 16]}>
        <Col xs={24} md={8}>
          <Card size="small" title="VaR 度量" loading={varQ.isLoading}>
            <Descriptions column={1} size="small">
              <Descriptions.Item label="方法">
                {varData?.method === 'historical' ? '历史模拟' : '参数法'}
              </Descriptions.Item>
              <Descriptions.Item label="置信度/持有期">
                {((varData?.confidence ?? 0.95) * 100).toFixed(0)}% / {varData?.horizon_days ?? 1} 日
              </Descriptions.Item>
              <Descriptions.Item label="组合 σ">{fmt(varData?.portfolio_sigma_yuan)} 元</Descriptions.Item>
              <Descriptions.Item label="样本天数">{varData?.sample_days ?? 0}</Descriptions.Item>
            </Descriptions>
            {varData?.warnings && varData.warnings.length > 0 && (
              <Alert type="warning" showIcon message={varData.warnings[varData.warnings.length - 1]} />
            )}
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card
            size="small"
            title="VaR 回测"
            loading={backtestQ.isLoading}
            extra={<Tag color={backtest?.passed ? 'success' : 'error'}>{backtest?.passed ? '通过' : '未通过'}</Tag>}
          >
            <Descriptions column={1} size="small">
              <Descriptions.Item label="样本/突破">
                {(backtest?.samples ?? 0)} 天 / {(backtest?.exceptions ?? 0)} 次（期望 {backtest?.expected_exceptions ?? 0}）
              </Descriptions.Item>
              <Descriptions.Item label="Kupiec p">{fmt(backtest?.kupiec_pvalue, 4)}</Descriptions.Item>
              <Descriptions.Item label="独立性 p">{fmt(backtest?.christoffersen_pvalue, 4)}</Descriptions.Item>
              <Descriptions.Item label="条件覆盖 p">{fmt(backtest?.cc_pvalue, 4)}</Descriptions.Item>
            </Descriptions>
            <Alert type={backtest?.passed ? 'success' : 'warning'} showIcon message={backtest?.verdict ?? '-'} />
          </Card>
        </Col>

        <Col xs={24} md={8}>
          <Card
            size="small"
            title="限额状态"
            loading={limitsQ.isLoading}
            extra={
              <Tag color={limits?.max_severity === 'breach' ? 'error' : limits?.max_severity === 'warning' ? 'warning' : 'success'}>
                {limits?.max_severity === 'breach' ? '突破' : limits?.max_severity === 'warning' ? '预警' : '正常'}
              </Tag>
            }
          >
            {!limits?.breaches || limits.breaches.length === 0 ? (
              <Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="全部限额正常" />
            ) : (
              <Space direction="vertical" style={{ width: '100%' }}>
                {limits.breaches.map((b) => (
                  <div key={b.limit_id}>
                    <Tag color={b.severity === 'breach' ? 'error' : 'warning'}>
                      {b.severity === 'breach' ? '突破' : '预警'}
                    </Tag>
                    {b.limit_type}：{fmt(b.actual)} / {fmt(b.threshold)}（{(b.usage_ratio * 100).toFixed(0)}%）
                  </div>
                ))}
              </Space>
            )}
          </Card>
        </Col>
      </Row>

      <ChartCard
        title={'压力测试（' + (stress?.scenarios.length ?? 0) + ' 个场景）· 最差 ' + fmt(stress?.worst_pnl_impact) + ' 元'}
        option={stressOption}
        height={320}
        loading={stressQ.isLoading}
      />

      <Card size="small" title="压力测试明细" loading={stressQ.isLoading}>
        <Table
          size="small"
          rowKey="scenario_id"
          columns={stressColumns}
          dataSource={stress?.scenarios ?? []}
          pagination={false}
          scroll={{ x: 900 }}
        />
      </Card>

      <Card size="small" title={'未处理预警（' + alerts.length + '）'} loading={alertsQ.isLoading}>
        <Table
          size="small"
          rowKey="alert_id"
          columns={alertColumns}
          dataSource={alerts}
          pagination={{ pageSize: 8, hideOnSinglePage: true }}
          scroll={{ x: 900 }}
        />
      </Card>
    </Space>
  );
}
