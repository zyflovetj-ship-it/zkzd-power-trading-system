import { useCallback, useEffect, useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import {
  Alert,
  Button,
  Card,
  Checkbox,
  DatePicker,
  Space,
  Spin,
  Table,
  Tabs,
  Tag,
  Typography,
} from 'antd';
import { LeftOutlined, RightOutlined } from '@ant-design/icons';
import dayjs, { Dayjs } from 'dayjs';
import type { EChartsOption } from 'echarts';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import {
  getForecastBaseAvailability,
  getForecastBaseCurves,
  type BaseAvailabilityMatrixCell,
  type BaseCurve,
  type BaseCurvePoint,
} from '@/api/loadForecast';
import { baseGrid, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';

type RangeKey = 'recent_3' | 'recent_7' | 'historical_10' | 'desktop_full_range';

const RANGE_OPTS: { key: RangeKey; label: string }[] = [
  { key: 'recent_3', label: '近3天' },
  { key: 'recent_7', label: '近7日' },
  { key: 'historical_10', label: '历史10日' },
  { key: 'desktop_full_range', label: '全部区间' },
];

// ============ 数据项配置 ============
const DATA_ITEMS_CONFIG = {
  weekly: [
    { id: 1, name: '次周系统负荷预测', shortName: '周负荷', unifiedName: '系统负荷' },
    { id: 3, name: '次周风电预测', shortName: '周风电', unifiedName: '风电出力' },
    { id: 2, name: '次周光伏预测', shortName: '周光伏', unifiedName: '光伏出力' },
    { id: 4, name: '次周水电(含抽蓄)预测', shortName: '周水电', unifiedName: '水电抽蓄' },
    { id: 5, name: '次周联络线可用容量', shortName: '周联络', unifiedName: '联络线' },
  ],
  daily: [
    { id: 6, name: '短期系统负荷预测', shortName: '日负荷', unifiedName: '系统负荷' },
    { id: 8, name: '短期风电预测', shortName: '日风电', unifiedName: '风电出力' },
    { id: 7, name: '短期光伏预测', shortName: '日光伏', unifiedName: '光伏出力' },
    { id: 9, name: '非市场化机组预测', shortName: '日水电', unifiedName: '水电抽蓄' },
    { id: 10, name: '联络线总计划', shortName: '日联络', unifiedName: '联络线' },
  ],
  realtime: [
    { id: 11, name: '实际系统负荷', shortName: '实负荷', unifiedName: '系统负荷' },
    { id: 12, name: '实际风电出力', shortName: '实风电', unifiedName: '风电出力' },
    { id: 13, name: '实际光伏出力', shortName: '实光伏', unifiedName: '光伏出力' },
    { id: 14, name: '实际水电(含抽蓄)出力', shortName: '实水电', unifiedName: '水电抽蓄' },
    { id: 15, name: '联络线潮流', shortName: '实联络', unifiedName: '联络线' },
  ],
};

const ALL_DATA_ITEMS = [
  ...DATA_ITEMS_CONFIG.weekly,
  ...DATA_ITEMS_CONFIG.daily,
  ...DATA_ITEMS_CONFIG.realtime,
];

interface AccuracyResult {
  key: string;
  name: string;
  value: string;
  sortKey: string;
}

// ============ 辅助函数 ============
const getUnifiedName = (dataItemId: number): string => {
  const item = ALL_DATA_ITEMS.find((i) => i.id === dataItemId);
  return item?.unifiedName ?? '';
};

const getForecastTypePrefix = (dataItemId: number): string => {
  if (DATA_ITEMS_CONFIG.weekly.some((i) => i.id === dataItemId)) return '周';
  if (DATA_ITEMS_CONFIG.daily.some((i) => i.id === dataItemId)) return '日';
  if (DATA_ITEMS_CONFIG.realtime.some((i) => i.id === dataItemId)) return '实';
  return '';
};

const getDataItemDisplayName = (dataItemId: number): string => {
  const item = ALL_DATA_ITEMS.find((i) => i.id === dataItemId);
  return item?.unifiedName ?? item?.name ?? `数据项${dataItemId}`;
};

const formatRelativeDate = (offset: number): string => {
  if (offset === 0) return 'D';
  if (offset > 0) return `D+${offset}`;
  return `D${offset}`;
};

const getDateOffset = (baseDate: Dayjs, actualDate: string): number => {
  return dayjs(actualDate).diff(baseDate.startOf('day'), 'day');
};

const isWeekend = (dateStr: string): boolean => {
  const d = dayjs(dateStr);
  return d.day() === 0 || d.day() === 6;
};

// ============ 准确率计算 ============
const calculateAccuracy = (curve1: BaseCurve, curve2: BaseCurve): number | null => {
  let sumDiff = 0;
  let sumBase = 0;
  let count = 0;
  const map1 = new Map(curve1.data.map((p) => [p.time, p.value]));
  curve2.data.forEach((p) => {
    if (map1.has(p.time)) {
      const val1 = map1.get(p.time)!;
      sumDiff += Math.abs(p.value - val1);
      sumBase += Math.abs(val1);
      count++;
    }
  });
  if (count > 0 && sumBase > 0) {
    return (1 - sumDiff / sumBase) * 100;
  }
  return null;
};

const computeAccuracyResults = (curvesData: BaseCurve[]): AccuracyResult[] => {
  const results: AccuracyResult[] = [];
  const actualCurves = curvesData.filter((c) => c.data_item_id >= 11 && c.data_item_id <= 15);
  const weeklyCurves = curvesData.filter((c) => c.data_item_id >= 1 && c.data_item_id <= 5);
  const dailyCurves = curvesData.filter((c) => c.data_item_id >= 6 && c.data_item_id <= 10);

  // 周预测 vs 实际
  actualCurves.forEach((actual) => {
    const aName = getUnifiedName(actual.data_item_id);
    weeklyCurves.forEach((forecast) => {
      const fName = getUnifiedName(forecast.data_item_id);
      if (actual.date === forecast.date && aName === fName) {
        const acc = calculateAccuracy(actual, forecast);
        if (acc !== null) {
          results.push({
            key: `周_${fName}_${forecast.date}`,
            name: `周${fName}准确率 (${forecast.date})`,
            value: `${acc.toFixed(2)}%`,
            sortKey: `${forecast.date.replace(/-/g, '')}_2_${forecast.data_item_id}`,
          });
        }
      }
    });
  });

  // 日预测 vs 实际
  actualCurves.forEach((actual) => {
    const aName = getUnifiedName(actual.data_item_id);
    dailyCurves.forEach((forecast) => {
      const fName = getUnifiedName(forecast.data_item_id);
      if (actual.date === forecast.date && aName === fName) {
        const acc = calculateAccuracy(actual, forecast);
        if (acc !== null) {
          results.push({
            key: `日_${fName}_${forecast.date}`,
            name: `日${fName}准确率 (${forecast.date})`,
            value: `${acc.toFixed(2)}%`,
            sortKey: `${forecast.date.replace(/-/g, '')}_1_${forecast.data_item_id}`,
          });
        }
      }
    });
  });

  // 周预测 vs 日预测
  weeklyCurves.forEach((weekly) => {
    const wName = getUnifiedName(weekly.data_item_id);
    dailyCurves.forEach((daily) => {
      const dName = getUnifiedName(daily.data_item_id);
      if (weekly.date === daily.date && wName === dName) {
        const acc = calculateAccuracy(daily, weekly);
        if (acc !== null) {
          results.push({
            key: `周日_${wName}_${weekly.date}`,
            name: `周日${wName}准确率 (${weekly.date})`,
            value: `${acc.toFixed(2)}%`,
            sortKey: `${weekly.date.replace(/-/g, '')}_3_${weekly.data_item_id}`,
          });
        }
      }
    });
  });

  return results;
};

// ============ 主组件 ============
export default function PriceForecastBaselinePage() {
  const [baseDate, setBaseDate] = useState<Dayjs>(dayjs().subtract(1, 'day'));
  const [range, setRange] = useState<RangeKey>('desktop_full_range');
  const [dataType, setDataType] = useState<number>(0); // 0:周预测, 1:日预测, 2:实际数据
  const [selectedItems, setSelectedItems] = useState<Record<string, boolean>>({});

  const baseDateStr = baseDate.format('YYYY-MM-DD');

  // ============ API 查询 ============
  const availQ = useQuery({
    queryKey: ['baseAvail', baseDateStr, range],
    queryFn: () => getForecastBaseAvailability(baseDateStr, range),
  });

  const matrix = availQ.data?.availability_matrix ?? [];
  const dateRange = availQ.data?.date_range ?? [];

  // 构建可用性查找表：dataItemId -> date -> cell
  const availMap = useMemo(() => {
    const m = new Map<number, Map<string, BaseAvailabilityMatrixCell>>();
    matrix.forEach((row) => {
      if (row.length === 0) return;
      const itemId = row[0].data_item_id;
      const dateMap = new Map<string, BaseAvailabilityMatrixCell>();
      row.forEach((cell) => dateMap.set(cell.date, cell));
      m.set(itemId, dateMap);
    });
    return m;
  }, [matrix]);

  // 当前 Tab 对应的数据项
  const currentItems = useMemo(() => {
    switch (dataType) {
      case 0:
        return DATA_ITEMS_CONFIG.weekly;
      case 1:
        return DATA_ITEMS_CONFIG.daily;
      case 2:
        return DATA_ITEMS_CONFIG.realtime;
      default:
        return DATA_ITEMS_CONFIG.weekly;
    }
  }, [dataType]);

  // 选中项转曲线请求
  const selectedKeys = Object.keys(selectedItems).filter((k) => selectedItems[k]);
  const curveRequests = useMemo(() => {
    return selectedKeys.map((key) => {
      const [dataItemId, offsetStr] = key.split('_');
      const offset = parseInt(offsetStr, 10);
      const actualDate = baseDate.add(offset, 'day').format('YYYY-MM-DD');
      return { data_item_id: parseInt(dataItemId, 10), date: actualDate };
    });
  }, [selectedKeys, baseDate]);

  const curvesQ = useQuery({
    queryKey: ['baseCurves', JSON.stringify(curveRequests)],
    enabled: curveRequests.length > 0,
    queryFn: () => getForecastBaseCurves(curveRequests),
  });

  const curvesData = curvesQ.data?.curves ?? [];

  // 准确率计算
  const accuracyResults = useMemo(() => {
    if (curvesData.length === 0) return [];
    return computeAccuracyResults(curvesData);
  }, [curvesData]);

  // ============ 图表数据 ============
  const chartData = useMemo(() => {
    if (curvesData.length === 0) return [];
    const timeMap: Record<string, any> = {};
    curvesData.forEach((curve, idx) => {
      curve.data.forEach((point) => {
        if (!timeMap[point.time]) {
          timeMap[point.time] = { time: point.time };
        }
        timeMap[point.time][`curve_${idx}`] = point.value;
      });
    });
    return Object.values(timeMap).sort((a: any, b: any) => {
      const tA = a.time === '24:00' ? '23:59:59' : a.time;
      const tB = b.time === '24:00' ? '23:59:59' : b.time;
      return tA.localeCompare(tB);
    });
  }, [curvesData]);

  // ============ 事件处理 ============
  const handleShiftDate = (days: number) => {
    setBaseDate((prev) => prev.add(days, 'day'));
  };

  const handleCheckboxToggle = (dataItemId: number, offset: number) => {
    const key = `${dataItemId}_${offset}`;
    setSelectedItems((prev) => ({ ...prev, [key]: !prev[key] }));
  };

  const handleClearSelection = () => {
    setSelectedItems({});
  };

  const getSelectedCount = () => Object.values(selectedItems).filter(Boolean).length;

  // ============ 可用性表格列定义 ============
  const availColumns = useMemo(() => {
    const cols: any[] = [
      {
        title: '数据项',
        dataIndex: 'name',
        key: 'name',
        fixed: 'left' as const,
        width: 140,
        render: (text: string) => (
          <Typography.Text strong style={{ color: '#0958d9' }}>
            {text}
          </Typography.Text>
        ),
      },
    ];

    dateRange.forEach((date) => {
      const offset = getDateOffset(baseDate, date);
      const isBase = offset === 0;
      const isWk = isWeekend(date);
      const relLabel = formatRelativeDate(offset);

      cols.push({
        title: (
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontWeight: 600 }}>{relLabel}</div>
            <div style={{ fontSize: 12, color: isWk ? '#ff4d4f' : undefined }}>
              {date.substring(5)}
            </div>
          </div>
        ),
        key: date,
        dataIndex: date,
        width: 72,
        align: 'center' as const,
        onHeaderCell: () => ({
          style: {
            backgroundColor: isBase ? 'rgba(22,119,255,0.12)' : isWk ? '#fafafa' : undefined,
          },
        }),
      });
    });

    return cols;
  }, [dateRange, baseDate]);

  // 可用性表格数据源
  const availDataSource = useMemo(() => {
    return currentItems.map((item) => {
      const row: Record<string, any> = { key: item.id, name: getDataItemDisplayName(item.id) };
      dateRange.forEach((date) => {
        const offset = getDateOffset(baseDate, date);
        const selKey = `${item.id}_${offset}`;
        const isSelected = !!selectedItems[selKey];
        const cell = availMap.get(item.id)?.get(date);
        const isAvailable = cell?.is_available ?? false;
        const isWk = isWeekend(date);
        const isBase = offset === 0;

        let bg: string | undefined;
        if (isSelected) bg = 'rgba(22,119,255,0.12)';
        else if (isBase) bg = 'rgba(22,119,255,0.06)';
        else if (isWk) bg = '#fafafa';

        row[date] = (
          <div
            style={{
              backgroundColor: bg,
              margin: -8,
              padding: 8,
              cursor: isAvailable ? 'pointer' : 'default',
              minHeight: 32,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
            }}
            onClick={() => isAvailable && handleCheckboxToggle(item.id, offset)}
          >
            {isAvailable ? (
              <Checkbox checked={isSelected} />
            ) : (
              <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                —
              </Typography.Text>
            )}
          </div>
        );
      });
      return row;
    });
  }, [currentItems, dateRange, baseDate, selectedItems, availMap]);

  // ============ ECharts 多曲线对比图 ============
  const curveOption: EChartsOption = useMemo(() => {
    if (curvesData.length === 0 || chartData.length === 0) {
      return { series: [] };
    }

    return {
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      grid: baseGrid,
      legend: {
        top: 10,
        type: 'scroll',
        icon: 'roundRect',
        formatter: (value: string) => {
          const idx = parseInt(value.split('_')[1], 10);
          const curve = curvesData[idx];
          if (curve) {
            const prefix = getForecastTypePrefix(curve.data_item_id);
            const displayName = getDataItemDisplayName(curve.data_item_id);
            return `${prefix}${displayName}(${curve.date.substring(5)})`;
          }
          return value;
        },
      },
      xAxis: {
        type: 'category',
        data: chartData.map((d: any) => d.time),
        name: '时刻',
        boundaryGap: false,
        axisLabel: { interval: 7 },
      },
      yAxis: { type: 'value', name: '数值' },
      series: curvesData.map((_, idx) => ({
        name: `curve_${idx}`,
        type: 'line',
        smooth: true,
        showSymbol: false,
        data: chartData.map((d: any) => d[`curve_${idx}`]),
        lineStyle: { width: 2 },
      })),
    };
  }, [curvesData, chartData]);

  // ============ KPI 数据 ============
  const availableCount = useMemo(() => {
    let count = 0;
    matrix.forEach((row) => row.forEach((cell) => cell.is_available && count++));
    return count;
  }, [matrix]);

  const totalCells = useMemo(() => {
    return matrix.reduce((sum, row) => sum + row.length, 0);
  }, [matrix]);

  const itemIds = useMemo(() => {
    return Array.from(new Set(matrix.map((row) => (row[0]?.data_item_id ?? 0)))).filter((id) => id > 0).sort((a, b) => a - b);
  }, [matrix]);

  // ============ 渲染 ============
  return (
    <div>
      {/* 日期选择器 + 日期范围选择 */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Space wrap>
          <Button icon={<LeftOutlined />} onClick={() => handleShiftDate(-1)} disabled={availQ.isLoading} />
          <DatePicker
            value={baseDate}
            onChange={(d) => d && setBaseDate(d)}
            allowClear={false}
          />
          <Button icon={<RightOutlined />} onClick={() => handleShiftDate(1)} disabled={availQ.isLoading} />
          <Tabs
            activeKey={range}
            onChange={(k) => setRange(k as RangeKey)}
            items={RANGE_OPTS.map((o) => ({ key: o.key, label: o.label }))}
            size="small"
            style={{ marginLeft: 8 }}
          />
          <Button onClick={handleClearSelection} disabled={getSelectedCount() === 0}>
            清空选择
          </Button>
        </Space>
      </Card>

      {/* KPI 卡片 */}
      <KpiCards
        loading={availQ.isLoading}
        items={[
          { label: '数据项数量', value: itemIds.length, color: CHART_COLORS[0] },
          { label: '日期列数', value: dateRange.length, color: CHART_COLORS[1] },
          { label: '可用单元格', value: availableCount, color: CHART_COLORS[2] },
          {
            label: '可用率',
            value: totalCells ? availableCount / totalCells : 0,
            precision: 3,
            color: CHART_COLORS[3],
          },
        ]}
      />

      {/* 数据类型 Tab */}
      <Card size="small" style={{ marginBottom: 16 }}>
        <Tabs
          activeKey={String(dataType)}
          onChange={(k) => setDataType(Number(k))}
          items={[
            { key: '0', label: '周预测' },
            { key: '1', label: '日预测' },
            { key: '2', label: '实际数据' },
          ]}
        />
      </Card>

      {/* 可用性矩阵表格 */}
      {availQ.isError && (
        <Alert type="error" showIcon message="加载数据可用性失败" style={{ marginBottom: 16 }} />
      )}

      {availQ.isLoading ? (
        <Spin style={{ display: 'block', margin: '40px auto' }} />
      ) : (
        <>
          <Card size="small" title="预测基础数据可用性矩阵" style={{ marginBottom: 16 }}>
            <Table
              columns={availColumns}
              dataSource={availDataSource}
              pagination={false}
              scroll={{ x: 'max-content' }}
              size="small"
              bordered
            />
            {/* 图例说明 */}
            <Space style={{ marginTop: 8 }} size="middle">
              <Space size={4}>
                <Checkbox checked />
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>已选中</Typography.Text>
              </Space>
              <Space size={4}>
                <Checkbox />
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>可选择</Typography.Text>
              </Space>
              <Space size={4}>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>—</Typography.Text>
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>无数据</Typography.Text>
              </Space>
              <Space size={4}>
                <div style={{ width: 16, height: 16, backgroundColor: '#fafafa', border: '1px solid #d9d9d9' }} />
                <Typography.Text type="secondary" style={{ fontSize: 12 }}>周末</Typography.Text>
              </Space>
            </Space>
            <Typography.Text style={{ marginTop: 8, display: 'block' }}>
              已选择 {getSelectedCount()} 项数据
            </Typography.Text>
          </Card>

          {/* 准确率显示区域 */}
          {accuracyResults.length > 0 && (
            <Card
              size="small"
              style={{ marginBottom: 16, backgroundColor: 'rgba(22,119,255,0.04)' }}
            >
              <Space wrap>
                {accuracyResults
                  .sort((a, b) => a.sortKey.localeCompare(b.sortKey))
                  .map((r) => (
                    <Tag key={r.key} color="blue" style={{ margin: 2 }}>
                      {r.name}: <strong>{r.value}</strong>
                    </Tag>
                  ))}
              </Space>
            </Card>
          )}

          {/* 96点曲线对比图 */}
          {curvesQ.isError && (
            <Alert type="error" showIcon message="加载曲线数据失败" style={{ marginBottom: 16 }} />
          )}
          <ChartCard
            title={`96点数据对比分析（已选 ${curvesData.length} 条曲线）`}
            option={curveOption}
            loading={curvesQ.isLoading}
            height={420}
          />
        </>
      )}
    </div>
  );
}
