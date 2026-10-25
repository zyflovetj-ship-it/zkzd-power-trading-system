import { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  DatePicker,
  Select,
  Space,
  Tag,
  Typography,
} from 'antd';
import { SearchOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { CustomerMeterSelect } from '@/components/filters/CustomerMeterSelect';
import {
  getLoadCurve,
  getDailyEnergy,
  getTotalDailyEnergy,
  getAvailableDates,
  getAvailableMonths,
  getMonthlyLoadCurve,
} from '@/api/loadForecast';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';

const MAX_DATES = 7;
const MAX_MONTHS = 4;
const LINE_COLORS = CHART_COLORS;

interface Sel {
  userName?: string;
  meterId?: string;
}

// ============ Tab: 日负荷曲线对比（多日） ============
function LoadCurveTab({ sel }: { sel: Sel }) {
  const [selectedDates, setSelectedDates] = useState<string[]>([]);
  const [queryDates, setQueryDates] = useState<string[]>([]);
  const [pickerDate, setPickerDate] = useState<Dayjs | null>(dayjs());

  const availDatesQ = useQuery({
    queryKey: ['availDates', sel.meterId],
    enabled: !!sel.meterId,
    queryFn: () => getAvailableDates(sel.meterId as string),
  });
  const availDates = availDatesQ.data ?? [];

  const curveQ = useQuery({
    queryKey: ['loadCurve', sel.meterId, queryDates],
    enabled: !!sel.meterId && queryDates.length > 0,
    queryFn: () => getLoadCurve(sel.meterId as string, queryDates),
  });

  const addDate = (d: Dayjs | null) => {
    if (!d) return;
    const ds = d.format('YYYY-MM-DD');
    if (selectedDates.includes(ds) || selectedDates.length >= MAX_DATES) return;
    setSelectedDates((prev) => [...prev, ds]);
  };

  const removeDate = (ds: string) => {
    setSelectedDates((prev) => prev.filter((d) => d !== ds));
  };

  const handleQuery = () => {
    if (selectedDates.length > 0) setQueryDates([...selectedDates]);
  };

  const chartData = useMemo(() => {
    if (!curveQ.data || queryDates.length === 0) return { times: [] as string[], series: [] as { name: string; data: (number | null)[] }[] };
    const allTimes = new Set<string>();
    queryDates.forEach((dateStr) => {
      const points = curveQ.data[dateStr] ?? [];
      points.forEach((p) => allTimes.add(p.time));
    });
    const times = Array.from(allTimes).sort((a, b) => {
      const ta = a === '24:00' ? '23:59:59' : a;
      const tb = b === '24:00' ? '23:59:59' : b;
      return ta.localeCompare(tb);
    });
    const series = queryDates.map((dateStr) => {
      const points = curveQ.data[dateStr] ?? [];
      const timeMap = new Map(points.map((p) => [p.time, p.value]));
      return { name: dateStr, data: times.map((t) => timeMap.get(t) ?? null) };
    });
    return { times, series };
  }, [curveQ.data, queryDates]);

  const option: EChartsOption = {
    color: LINE_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: chartData.series.map((s) => s.name) },
    grid: baseGrid,
    xAxis: { type: 'category', data: chartData.times, name: '时刻', boundaryGap: false, axisLabel: { interval: 7 } },
    yAxis: { type: 'value', name: '负荷 (kW)', scale: true },
    series: chartData.series.map((s, i) => ({
      name: s.name,
      type: 'line',
      smooth: true,
      showSymbol: false,
      data: s.data,
      lineStyle: { width: 2 },
      itemStyle: { color: LINE_COLORS[i % LINE_COLORS.length] },
    })),
  };

  const kpis = useMemo(() => {
    if (chartData.series.length === 0) return null;
    const allVals = chartData.series.flatMap((s) => s.data.filter((v): v is number => v != null));
    if (allVals.length === 0) return null;
    return { max: Math.max(...allVals), min: Math.min(...allVals), avg: allVals.reduce((a, b) => a + b, 0) / allVals.length };
  }, [chartData]);

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap direction="vertical" style={{ width: '100%' }}>
          <Space wrap>
            <DatePicker
              value={pickerDate}
              onChange={(d) => { setPickerDate(d); addDate(d); }}
              disabledDate={(d) => {
                const ds = d.format('YYYY-MM-DD');
                return selectedDates.includes(ds) || selectedDates.length >= MAX_DATES || (availDates.length > 0 && !availDates.includes(ds));
              }}
              allowClear={false}
            />
            <Typography.Text type="secondary">最多选{MAX_DATES}天</Typography.Text>
            <Button type="primary" icon={<SearchOutlined />} onClick={handleQuery} disabled={selectedDates.length === 0}>
              查询
            </Button>
          </Space>
          <Space wrap>
            {selectedDates.map((ds) => (
              <Tag key={ds} closable onClose={() => removeDate(ds)} color="blue">{ds}</Tag>
            ))}
          </Space>
        </Space>
      </Card>

      {kpis && (
        <KpiCards
          items={[
            { label: '最大负荷', value: kpis.max, precision: 1, suffix: 'kW', color: CHART_COLORS[0] },
            { label: '最小负荷', value: kpis.min, precision: 1, suffix: 'kW', color: CHART_COLORS[1] },
            { label: '平均负荷', value: kpis.avg, precision: 1, suffix: 'kW', color: CHART_COLORS[2] },
          ]}
        />
      )}

      {curveQ.isError && <Alert type="error" showIcon message="加载负荷曲线失败" style={{ marginBottom: 16 }} />}
      {queryDates.length > 0 && (
        <ChartCard title={`日负荷曲线对比（${queryDates.join(', ')}）`} option={option} loading={curveQ.isLoading} height={420} />
      )}
      {queryDates.length === 0 && (
        <Alert type="info" showIcon message="请选择日期后点击查询" style={{ marginBottom: 16 }} />
      )}
    </div>
  );
}

// ============ Tab: 月度电量对比（多月） ============
function MonthlyEnergyTab({ sel }: { sel: Sel }) {
  const [selectedMonths, setSelectedMonths] = useState<string[]>([]);
  const [queryMonths, setQueryMonths] = useState<string[]>([]);
  const [pickerMonth, setPickerMonth] = useState<Dayjs | null>(dayjs());

  const availMonthsQ = useQuery({
    queryKey: ['availMonths'],
    queryFn: () => getAvailableMonths(),
  });
  const availMonths = availMonthsQ.data ?? [];

  const energyQ = useQuery({
    queryKey: ['dailyEnergy', sel.meterId, queryMonths],
    enabled: !!sel.meterId && queryMonths.length > 0,
    queryFn: () => getDailyEnergy(sel.meterId as string, queryMonths),
  });

  const addMonth = (d: Dayjs | null) => {
    if (!d) return;
    const ms = d.format('YYYY-MM');
    if (selectedMonths.includes(ms) || selectedMonths.length >= MAX_MONTHS) return;
    setSelectedMonths((prev) => [...prev, ms]);
  };

  const removeMonth = (ms: string) => {
    setSelectedMonths((prev) => prev.filter((m) => m !== ms));
  };

  const handleQuery = () => {
    if (selectedMonths.length > 0) setQueryMonths([...selectedMonths]);
  };

  const chartData = useMemo(() => {
    if (!energyQ.data || queryMonths.length === 0) return { days: [] as number[], series: [] as { name: string; data: number[] }[] };
    const allDays = new Set<number>();
    queryMonths.forEach((monthStr) => {
      const points = energyQ.data[monthStr] ?? [];
      points.forEach((p) => allDays.add(p.day));
    });
    const days = Array.from(allDays).sort((a, b) => a - b);
    const series = queryMonths.map((monthStr) => {
      const points = energyQ.data[monthStr] ?? [];
      const dayMap = new Map(points.map((p) => [p.day, p.energy]));
      return { name: monthStr, data: days.map((d) => dayMap.get(d) ?? 0) };
    });
    return { days, series };
  }, [energyQ.data, queryMonths]);

  const option: EChartsOption = {
    color: LINE_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: chartData.series.map((s) => s.name) },
    grid: baseGrid,
    xAxis: { type: 'category', data: chartData.days.map(String), name: '日' },
    yAxis: { type: 'value', name: '电量 (kWh)' },
    series: chartData.series.map((s, i) => ({
      name: s.name,
      type: 'bar',
      data: s.data,
      itemStyle: { color: LINE_COLORS[i % LINE_COLORS.length] },
    })),
  };

  const kpis = useMemo(() => {
    if (chartData.series.length === 0) return null;
    return chartData.series.map((s, i) => ({
      label: `${s.name} 总电量`,
      value: s.data.reduce((a, b) => a + b, 0),
      precision: 0,
      suffix: 'kWh',
      color: LINE_COLORS[i % LINE_COLORS.length],
    }));
  }, [chartData]);

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap direction="vertical" style={{ width: '100%' }}>
          <Space wrap>
            <DatePicker
              picker="month"
              value={pickerMonth}
              onChange={(d) => { setPickerMonth(d); addMonth(d); }}
              disabledDate={(d) => {
                const ms = d.format('YYYY-MM');
                return selectedMonths.includes(ms) || selectedMonths.length >= MAX_MONTHS || (availMonths.length > 0 && !availMonths.includes(ms));
              }}
              allowClear={false}
            />
            <Typography.Text type="secondary">最多选{MAX_MONTHS}月</Typography.Text>
            <Button type="primary" icon={<SearchOutlined />} onClick={handleQuery} disabled={selectedMonths.length === 0}>
              查询
            </Button>
          </Space>
          <Space wrap>
            {selectedMonths.map((ms) => (
              <Tag key={ms} closable onClose={() => removeMonth(ms)} color="green">{ms}</Tag>
            ))}
          </Space>
        </Space>
      </Card>

      {kpis && kpis.length > 0 && <KpiCards items={kpis} />}

      {energyQ.isError && <Alert type="error" showIcon message="加载月电量失败" style={{ marginBottom: 16 }} />}
      {queryMonths.length > 0 && (
        <ChartCard title={`月度电量对比（${queryMonths.join(', ')}）`} option={option} loading={energyQ.isLoading} height={420} />
      )}
      {queryMonths.length === 0 && (
        <Alert type="info" showIcon message="请选择月份后点击查询" style={{ marginBottom: 16 }} />
      )}
    </div>
  );
}

// ============ Tab: 电量趋势（总聚合） ============
function TrendTab() {
  const [month, setMonth] = useState<Dayjs>(dayjs());
  const monthStr = month.format('YYYY-MM');

  const trendQ = useQuery({
    queryKey: ['totalDailyEnergy', monthStr],
    queryFn: () => getTotalDailyEnergy([monthStr]),
  });

  const trendData = trendQ.data?.[monthStr] ?? [];

  const option: EChartsOption = {
    color: [CHART_COLORS[1]],
    tooltip: { ...baseTooltip },
    grid: baseGrid,
    xAxis: { type: 'category', data: trendData.map((p) => String(p.day)), name: '日' },
    yAxis: { type: 'value', name: '电量 (kWh)' },
    series: [
      {
        name: '总日电量',
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: trendData.map((p) => p.energy),
        areaStyle: { opacity: 0.12 },
        itemStyle: { color: CHART_COLORS[1] },
      },
    ],
  };

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <DatePicker picker="month" value={month} onChange={(d) => d && setMonth(d)} allowClear={false} />
        </Space>
      </Card>
      {trendQ.isError && <Alert type="error" showIcon message="加载电量趋势失败" style={{ marginBottom: 16 }} />}
      <ChartCard title={`总电量趋势（${monthStr}）`} option={option} loading={trendQ.isLoading} height={420} />
    </div>
  );
}

// ============ Tab: 月度曲线分析 ============
function MonthlyCurveTab() {
  const [month, setMonth] = useState<Dayjs>(dayjs());
  const monthStr = month.format('YYYY-MM');

  const q = useQuery({
    queryKey: ['monthlyCurve', monthStr],
    queryFn: () => getMonthlyLoadCurve(monthStr),
  });

  const data = q.data?.data ?? [];

  const formatTick = (tick: number) => {
    const hour = Math.floor(tick / 4).toString().padStart(2, '0');
    const minute = ((tick % 4) * 15).toString().padStart(2, '0');
    return `${hour}:${minute}`;
  };

  const option: EChartsOption = {
    color: CHART_COLORS,
    tooltip: { ...baseTooltip },
    legend: { ...baseLegend, data: ['月平均负荷', '工作日平均', '周末平均', '节假日平均'] },
    grid: baseGrid,
    xAxis: {
      type: 'category',
      data: data.map((p) => formatTick(p.time_index)),
      name: '时刻',
      boundaryGap: false,
      axisLabel: { interval: 7 },
    },
    yAxis: { type: 'value', name: '负荷 (kW)', scale: true },
    series: [
      { name: '月平均负荷', type: 'line', smooth: true, showSymbol: false, data: data.map((p) => p.monthly_avg), lineStyle: { width: 2 } },
      { name: '工作日平均', type: 'line', smooth: true, showSymbol: false, data: data.map((p) => p.workday_avg), lineStyle: { type: 'dashed', width: 2 } },
      { name: '周末平均', type: 'line', smooth: true, showSymbol: false, data: data.map((p) => p.weekend_avg), lineStyle: { type: 'dashed', width: 2 } },
      { name: '节假日平均', type: 'line', smooth: true, showSymbol: false, data: data.map((p) => p.holiday_avg), lineStyle: { type: 'dotted', width: 2 } },
    ],
  };

  const hasWorkday = data.some((p) => p.workday_avg != null);
  const hasWeekend = data.some((p) => p.weekend_avg != null);
  const hasHoliday = data.some((p) => p.holiday_avg != null);

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <DatePicker picker="month" value={month} onChange={(d) => d && setMonth(d)} allowClear={false} />
          <Space size={4}>
            <Tag color="blue">月平均</Tag>
            {hasWorkday && <Tag color="green">工作日</Tag>}
            {hasWeekend && <Tag color="orange">周末</Tag>}
            {hasHoliday && <Tag color="red">节假日</Tag>}
          </Space>
        </Space>
      </Card>
      {q.isError && <Alert type="error" showIcon message="加载月度曲线失败" style={{ marginBottom: 16 }} />}
      <ChartCard title={`月度负荷曲线分析（${monthStr}）`} option={option} loading={q.isLoading} height={420} />
    </div>
  );
}

// ============ 主页面 ============
export default function CustomerLoadPage() {
  const [sel, setSel] = useState<Sel>({});
  const [tab, setTab] = useState('curve');

  const tabItems = [
    {
      key: 'curve',
      label: '日负荷曲线对比',
      children: sel.meterId ? <LoadCurveTab sel={sel} /> : <Alert type="info" showIcon message="请先选择企业简称与户号以查看负荷数据" />,
    },
    {
      key: 'monthly',
      label: '月度曲线分析',
      children: <MonthlyCurveTab />,
    },
    {
      key: 'energy',
      label: '月度电量对比',
      children: sel.meterId ? <MonthlyEnergyTab sel={sel} /> : <Alert type="info" showIcon message="请先选择企业简称与户号以查看电量数据" />,
    },
    {
      key: 'trend',
      label: '电量趋势',
      children: <TrendTab />,
    },
  ];

  return (
    <div>
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          {tab !== 'trend' && tab !== 'monthly' && <CustomerMeterSelect value={sel} onChange={setSel} />}
          <Select
            value={tab}
            onChange={setTab}
            style={{ width: 160 }}
            options={[
              { value: 'curve', label: '日负荷曲线对比' },
              { value: 'monthly', label: '月度曲线分析' },
              { value: 'energy', label: '月度电量对比' },
              { value: 'trend', label: '电量趋势' },
            ]}
          />
        </Space>
      </Card>
      {tabItems.find((t) => t.key === tab)?.children}
    </div>
  );
}
