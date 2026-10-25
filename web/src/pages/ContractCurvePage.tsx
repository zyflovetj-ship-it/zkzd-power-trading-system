import { useMemo, useState } from 'react';
import { useQuery, useMutation } from '@tanstack/react-query';
import { Alert, Button, Card, Col, DatePicker, InputNumber, Row, Select, Space, Table, App } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { EChartsOption } from 'echarts';
import dayjs, { type Dayjs } from 'dayjs';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { CustomerSelect } from '@/components/CustomerSelect';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import {
  generateContractCurve,
  getContractCurve,
  getContractCurveScenarios,
  listContractCurves,
  type ContractCurveDaily,
  type ContractCurveResp,
} from '@/api/trading';

const OBJECTIVE_OPTS = [
  { label: '成本最低', value: 'cost_min' },
  { label: '风险最小', value: 'risk_min' },
  { label: '均衡', value: 'balanced' },
];

export default function ContractCurvePage() {
  const { message } = App.useApp();
  const [customerId, setCustomerId] = useState('');
  const [month, setMonth] = useState<Dayjs>(dayjs().date(1));
  const [objective, setObjective] = useState<'cost_min' | 'risk_min' | 'balanced'>('balanced');
  const [coverage, setCoverage] = useState<number>(0.7);
  const [curveId, setCurveId] = useState<string | undefined>();
  const [result, setResult] = useState<ContractCurveResp | null>(null);
  const [scenarioType, setScenarioType] = useState<'price_sensitivity' | 'load_sensitivity'>('price_sensitivity');
  const [scenarioData, setScenarioData] = useState<Array<Record<string, unknown>>>([]);

  const ym = month.format('YYYY-MM');
  const year = month.year();
  const m = month.month() + 1;

  const listQ = useQuery({
    queryKey: ['contractCurves', customerId, ym],
    queryFn: () => listContractCurves(customerId, year, m),
    enabled: !!customerId,
  });

  const genMut = useMutation({
    mutationFn: () => generateContractCurve({ customer_id: customerId, target_year: year, target_month: m, objective, contract_coverage: coverage }),
    onSuccess: (d) => {
      setResult(d);
      setCurveId(d.curve_id);
      message.success('合同曲线已生成');
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || e?.message || '生成失败'),
  });

  const loadExisting = async (id: string) => {
    try {
      const d = await getContractCurve(id);
      setResult(d);
      message.success('已加载已有曲线');
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '加载失败');
    }
  };

  const loadScenario = async () => {
    if (!result) return;
    try {
      const d = await getContractCurveScenarios(result.curve_id, scenarioType);
      setScenarioData(d.data ?? []);
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '加载敏感性分析失败');
    }
  };

  const daily = result?.daily_contracts ?? [];
  const s = result?.summary;

  const loadOption: EChartsOption = useMemo(
    () => ({
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: ['预测负荷', '合约电量', '现货电量'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: daily.map((d) => d.date.slice(5)), name: '日', boundaryGap: false },
      yAxis: { type: 'value', name: '电量(MWh)' },
      series: [
        { name: '预测负荷', type: 'line', smooth: true, showSymbol: false, data: daily.map((d) => d.predicted_load), itemStyle: { color: CHART_COLORS[0] } },
        { name: '合约电量', type: 'line', smooth: true, showSymbol: false, data: daily.map((d) => d.contract_amount), itemStyle: { color: CHART_COLORS[1] } },
        { name: '现货电量', type: 'line', smooth: true, showSymbol: false, data: daily.map((d) => d.spot_amount), itemStyle: { color: CHART_COLORS[2] } },
      ],
    }),
    [daily],
  );

  const costOption: EChartsOption = useMemo(
    () => ({
      tooltip: { trigger: 'item', formatter: '{b}: {c} 元 ({d}%)' },
      legend: { ...baseLegend, top: 'bottom' },
      series: [
        {
          type: 'pie',
          radius: ['40%', '68%'],
          data: [
            { name: '合约成本', value: s?.contract_cost ?? 0, itemStyle: { color: CHART_COLORS[1] } },
            { name: '现货成本', value: s ? s.spot_cost : 0, itemStyle: { color: CHART_COLORS[2] } },
          ],
        },
      ],
    }),
    [s],
  );

  const scenarioColumns: ColumnsType<Record<string, unknown>> = useMemo(() => {
    if (!scenarioData.length) return [];
    return Object.keys(scenarioData[0]).map((k) => ({
      title: k,
      dataIndex: k,
      key: k,
      render: (v: unknown) => (typeof v === 'number' ? v.toFixed?.(2) ?? v : String(v ?? '-')),
    }));
  }, [scenarioData]);

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle" wrap>
          <Col><CustomerSelect value={customerId} onChange={(v) => { setCustomerId(v); setResult(null); setCurveId(undefined); }} /></Col>
          <Col><DatePicker picker="month" value={month} onChange={(d) => d && setMonth(d)} allowClear={false} /></Col>
          <Col><Select value={objective} onChange={setObjective} options={OBJECTIVE_OPTS} style={{ width: 140 }} /></Col>
          <Col>
            <Space size={4}>
              <span>合约覆盖率</span>
              <InputNumber min={0} max={1} step={0.05} value={coverage} onChange={(v) => setCoverage(v ?? 0.7)} style={{ width: 90 }} />
            </Space>
          </Col>
          <Col>
            <Button type="primary" loading={genMut.isPending} disabled={!customerId} onClick={() => genMut.mutate()}>
              生成合同曲线
            </Button>
          </Col>
          <Col>
            <Select
              allowClear
              placeholder="加载已有曲线"
              value={curveId}
              style={{ width: 220 }}
              loading={listQ.isLoading}
              onChange={(v) => { if (v) { setCurveId(v); loadExisting(v); } else setCurveId(undefined); }}
              options={(listQ.data ?? []).map((c) => ({ value: c.curve_id, label: `${c.contract_month.year}-${String(c.contract_month.month).padStart(2, '0')}` }))}
            />
          </Col>
        </Row>
      </Card>

      {!result && (
        <Card><Alert type="info" showIcon message="请选择客户与月份后生成合同曲线" description="生成后将展示逐日合约/现货电量分解、成本构成与风险指标。" /></Card>
      )}

      {result && (
        <>
          <KpiCards
            items={[
              { label: '综合成本', value: s?.total_cost ?? '-', precision: 0, suffix: '元', color: CHART_COLORS[0] },
              { label: '度电成本', value: s?.blended_cost ?? '-', precision: 2, suffix: '元/MWh', color: CHART_COLORS[1] },
              { label: '合约覆盖率', value: ((s?.contract_coverage ?? 0) * 100).toFixed(1), suffix: '%', color: CHART_COLORS[2] },
              { label: 'VaR(95%)', value: s?.value_at_risk_95 ?? '-', precision: 0, suffix: '元', color: CHART_COLORS[3] },
              { label: '夏普比率', value: s?.sharpe_ratio ?? '-', precision: 2, color: CHART_COLORS[4] },
              { label: '较纯现货', value: ((s?.vs_pure_spot?.cost_percentage ?? 0) * 100).toFixed(1), suffix: '%', prefix: s && s.vs_pure_spot.cost_percentage < 0 ? '省' : '', color: CHART_COLORS[5] },
            ]}
          />
          <ChartCard title={`逐日电量分解（${result.customer_name} · ${ym}）`} option={loadOption} height={360} />
          <Row gutter={16}>
            <Col xs={24} md={12}><ChartCard title="成本构成" option={costOption} height={320} /></Col>
            <Col xs={24} md={12}>
              <Card size="small" title="敏感性分析" style={{ marginBottom: 16 }}>
                <Space wrap style={{ marginBottom: 12 }}>
                  <Select value={scenarioType} onChange={(v) => setScenarioType(v)} style={{ width: 160 }}
                    options={[{ label: '价格敏感性', value: 'price_sensitivity' }, { label: '负荷敏感性', value: 'load_sensitivity' }]} />
                  <Button onClick={loadScenario}>加载</Button>
                </Space>
                {scenarioData.length ? (
                  <Table size="small" rowKey={(_, i) => String(i)} columns={scenarioColumns} dataSource={scenarioData} pagination={false} scroll={{ x: 'max-content' }} />
                ) : (
                  <Alert type="info" showIcon message="点击“加载”查看敏感性情景" />
                )}
              </Card>
            </Col>
          </Row>
        </>
      )}
    </div>
  );
}
