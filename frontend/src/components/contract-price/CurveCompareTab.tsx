/**
 * 中长期日内分析 - Tab2: 曲线对比
 * 
 * 功能：
 * 1. 蓝色渐变消息提示框（曲线对比汇总）
 * 2. 筛选控件（紧凑按钮式布局）
 * 3. 多曲线叠加图表
 */
import React, { useState, useRef } from 'react';
import {
    Box,
    Paper,
    Typography,
    CircularProgress,
    Alert,
    Chip
} from '@mui/material';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer
} from 'recharts';
import { useChartFullscreen } from '../../hooks/useChartFullscreen';
import { DailySummaryResponse, CurvePoint } from '../../api/contractPrice';

// Props 接口
interface CurveCompareTabProps {
    data: DailySummaryResponse | null;
    loading: boolean;
    error: string | null;
    dateStr: string;
    selectedBenchmark: 'day_ahead' | 'real_time';
}

// 曲线定义
interface CurveOption {
    key: string;
    shortLabel: string;
    fullLabel: string;
    type: string;
    period: string;
    color: string;
}

// 所有可选曲线配置
const CURVE_OPTIONS: CurveOption[] = [
    // 市场化
    { key: '市场化-整体', shortLabel: '整体', fullLabel: '市场化整体', type: '市场化', period: '整体', color: '#0d47a1' },
    { key: '市场化-年度', shortLabel: '年度', fullLabel: '市场化年度', type: '市场化', period: '年度', color: '#1565c0' },
    { key: '市场化-月度', shortLabel: '月度', fullLabel: '市场化月度', type: '市场化', period: '月度', color: '#1976d2' },
    { key: '市场化-月内', shortLabel: '月内', fullLabel: '市场化月内', type: '市场化', period: '月内', color: '#42a5f5' },
    // 绿电
    { key: '绿电-整体', shortLabel: '整体', fullLabel: '绿电整体', type: '绿电', period: '整体', color: '#1b5e20' },
    { key: '绿电-年度', shortLabel: '年度', fullLabel: '绿电年度', type: '绿电', period: '年度', color: '#2e7d32' },
    { key: '绿电-月度', shortLabel: '月度', fullLabel: '绿电月度', type: '绿电', period: '月度', color: '#43a047' },
    { key: '绿电-月内', shortLabel: '月内', fullLabel: '绿电月内', type: '绿电', period: '月内', color: '#66bb6a' },
    // 代购电
    { key: '代理购电-整体', shortLabel: '整体', fullLabel: '代购电整体', type: '代购电', period: '整体', color: '#bf360c' },
    { key: '代理购电-年度', shortLabel: '年度', fullLabel: '代购电年度', type: '代购电', period: '年度', color: '#e65100' },
    { key: '代理购电-月度', shortLabel: '月度', fullLabel: '代购电月度', type: '代购电', period: '月度', color: '#ff9800' }
];

// 类型分组配置
const TYPE_CONFIG: { [key: string]: { label: string; color: string } } = {
    '市场化': { label: '市场化', color: '#1976d2' },
    '绿电': { label: '绿电', color: '#43a047' },
    '代购电': { label: '代购电', color: '#ff9800' }
};

// 蓝色渐变消息提示框
const SummaryPanel: React.FC<{
    selectedCurves: string[];
    selectedBenchmark: 'day_ahead' | 'real_time';
}> = ({ selectedCurves, selectedBenchmark }) => {
    const spotLabel = selectedBenchmark === 'day_ahead' ? '日前现货' : '实时现货';
    const curveCount = selectedCurves.length + 1;  // 始终包含现货曲线

    return (
        <Paper
            variant="outlined"
            sx={{
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                color: 'white',
                p: 2,
                borderRadius: 2,
                boxShadow: '0 4px 20px rgba(102, 126, 234, 0.3)',
                border: 'none'
            }}
        >
            <Typography variant="body1" sx={{ fontWeight: 500 }}>
                <Box component="span" sx={{ fontWeight: 'bold', mr: 1 }}>[曲线对比]</Box>
                当前显示 {curveCount} 条曲线 (含{spotLabel}基准)
            </Typography>
        </Paper>
    );
};

// 紧凑筛选面板
const FilterPanel: React.FC<{
    selectedCurves: string[];
    onSelectedCurvesChange: (curves: string[]) => void;
    availableCurves: string[];
}> = ({ selectedCurves, onSelectedCurvesChange, availableCurves }) => {


    const toggleCurve = (key: string) => {
        if (selectedCurves.includes(key)) {
            onSelectedCurvesChange(selectedCurves.filter(k => k !== key));
        } else {
            onSelectedCurvesChange([...selectedCurves, key]);
        }
    };

    // 按类型分组曲线
    const groupedCurves = CURVE_OPTIONS.reduce((acc, curve) => {
        if (!acc[curve.type]) acc[curve.type] = [];
        if (availableCurves.includes(curve.key)) {
            acc[curve.type].push(curve);
        }
        return acc;
    }, {} as { [key: string]: CurveOption[] });

    return (
        <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
            {/* 第一行：所有合同类型（桌面端一排，移动端分行） */}
            <Box sx={{
                display: 'flex',
                flexDirection: { xs: 'column', md: 'row' },
                gap: { xs: 1.5, md: 3 },
                flexWrap: 'wrap'
            }}>
                {Object.entries(groupedCurves).map(([typeName, curves]) => {
                    if (curves.length === 0) return null;
                    const typeConfig = TYPE_CONFIG[typeName];

                    return (
                        <Box
                            key={typeName}
                            sx={{ display: 'flex', alignItems: 'center', gap: 1, flexWrap: 'wrap' }}
                        >
                            <Typography
                                variant="body2"
                                sx={{
                                    fontWeight: 'bold',
                                    color: typeConfig.color,
                                    minWidth: { xs: 55, md: 'auto' },
                                    flexShrink: 0
                                }}
                            >
                                {typeConfig.label}
                            </Typography>

                            <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                                {curves.map(curve => {
                                    const isSelected = selectedCurves.includes(curve.key);
                                    return (
                                        <Chip
                                            key={curve.key}
                                            label={curve.shortLabel}
                                            size="small"
                                            onClick={() => toggleCurve(curve.key)}
                                            sx={{
                                                backgroundColor: isSelected ? curve.color : 'transparent',
                                                color: isSelected ? 'white' : 'text.primary',
                                                border: `1px solid ${isSelected ? curve.color : '#ccc'}`,
                                                fontWeight: isSelected ? 'bold' : 'normal',
                                                cursor: 'pointer',
                                                '&:hover': {
                                                    backgroundColor: isSelected ? curve.color : 'action.hover',
                                                    opacity: isSelected ? 0.9 : 1
                                                }
                                            }}
                                        />
                                    );
                                })}
                            </Box>
                        </Box>
                    );
                })}
            </Box>

        </Paper>
    );
};

// 多曲线图表
const MultiCurveChart: React.FC<{
    curvesByPeriod: { [key: string]: CurvePoint[] };
    spotCurves: CurvePoint[];
    selectedCurves: string[];
    selectedBenchmark: 'day_ahead' | 'real_time';
    dateStr: string;
}> = ({ curvesByPeriod, spotCurves, selectedCurves, selectedBenchmark, dateStr }) => {
    const chartRef = useRef<HTMLDivElement>(null);
    const spotLabel = selectedBenchmark === 'day_ahead' ? '日前现货' : '实时现货';

    const { isFullscreen, FullscreenEnterButton, FullscreenExitButton, FullscreenTitle } =
        useChartFullscreen({
            chartRef,
            title: `曲线对比 (${dateStr})`
        });

    // 合并所有曲线数据
    const allPeriods = new Set<number>();
    selectedCurves.forEach(key => {
        const curves = curvesByPeriod[key] || [];
        curves.forEach(p => allPeriods.add(p.period));
    });
    // 始终包含现货曲线
    spotCurves.forEach(p => allPeriods.add(p.period));

    const chartData = Array.from(allPeriods).sort((a, b) => a - b).map(period => {
        const dataPoint: any = { period };

        selectedCurves.forEach(key => {
            const curves = curvesByPeriod[key] || [];
            const point = curves.find(p => p.period === period);
            dataPoint[key] = point?.price ?? null;
            if (!dataPoint.time_str && point?.time_str) {
                dataPoint.time_str = point.time_str;
            }
        });

        // 始终包含现货数据
        const spotPoint = spotCurves.find(p => p.period === period);
        dataPoint['现货'] = spotPoint?.price ?? null;
        if (!dataPoint.time_str && spotPoint?.time_str) {
            dataPoint.time_str = spotPoint.time_str;
        }

        return dataPoint;
    });

    // 计算Y轴范围
    const allPrices = chartData.flatMap(d => {
        const prices: number[] = [];
        selectedCurves.forEach(key => {
            if (d[key] !== null && d[key] !== undefined) prices.push(d[key]);
        });
        // 始终包含现货价格
        if (d['现货'] !== null && d['现货'] !== undefined) {
            prices.push(d['现货']);
        }
        return prices;
    });
    const minPrice = allPrices.length > 0 ? Math.min(...allPrices) : 0;
    const maxPrice = allPrices.length > 0 ? Math.max(...allPrices) : 500;

    const hasData = chartData.length > 0;  // 始终有现货曲线

    const getCurveName = (key: string) => {
        const curve = CURVE_OPTIONS.find(c => c.key === key);
        return curve?.fullLabel || key;
    };

    const getCurveColor = (key: string) => {
        const curve = CURVE_OPTIONS.find(c => c.key === key);
        return curve?.color || '#999';
    };

    return (
        <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
            <Box
                ref={chartRef}
                sx={{
                    height: { xs: 400, sm: 450 },
                    position: 'relative',
                    backgroundColor: isFullscreen ? 'background.paper' : 'transparent',
                    p: isFullscreen ? 2 : 0,
                    ...(isFullscreen && {
                        position: 'fixed',
                        top: 0,
                        left: 0,
                        width: '100vw',
                        height: '100vh',
                        zIndex: 1400
                    })
                }}
            >
                <FullscreenEnterButton />
                <FullscreenExitButton />
                <FullscreenTitle />

                {!hasData ? (
                    <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
                        <Typography color="text.secondary">请选择至少一条曲线</Typography>
                    </Box>
                ) : (
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="time_str" tick={{ fontSize: 12 }} interval={5} />
                            <YAxis
                                domain={[Math.floor(minPrice * 0.95), Math.ceil(maxPrice * 1.05)]}
                                label={{ value: '价格 (元/MWh)', angle: -90, position: 'insideLeft' }}
                                tick={{ fontSize: 12 }}
                            />
                            <Tooltip
                                content={({ active, payload, label }) => {
                                    if (active && payload && payload.length) {
                                        return (
                                            <Paper sx={{ p: 1.5, backgroundColor: 'rgba(255, 255, 255, 0.95)', border: '1px solid #ccc', borderRadius: '4px' }}>
                                                <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
                                                    时间: {label}
                                                </Typography>
                                                {payload.map((pld: any) => (
                                                    <Typography key={pld.dataKey} variant="body2" sx={{ color: pld.color }}>
                                                        {pld.name}: {pld.value !== null ? `${Number(pld.value).toFixed(2)} 元/MWh` : 'N/A'}
                                                    </Typography>
                                                ))}
                                            </Paper>
                                        );
                                    }
                                    return null;
                                }}
                            />
                            <Legend />

                            {selectedCurves.map(key => (
                                <Line
                                    key={key}
                                    type="monotone"
                                    dataKey={key}
                                    stroke={getCurveColor(key)}
                                    strokeWidth={2}
                                    name={getCurveName(key)}
                                    dot={false}
                                />
                            ))}

                            {/* 始终显示现货曲线 */}
                            <Line
                                type="monotone"
                                dataKey="现货"
                                stroke="#f44336"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                name={spotLabel}
                                dot={false}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                )}
            </Box>
        </Paper>
    );
};

// 主组件
export const CurveCompareTab: React.FC<CurveCompareTabProps> = ({
    data,
    loading,
    error,
    dateStr,
    selectedBenchmark
}) => {
    const [selectedCurves, setSelectedCurves] = useState<string[]>(['市场化-月内']);

    const availableCurves = data?.curves_by_period
        ? Object.keys(data.curves_by_period).filter(k =>
            data.curves_by_period[k] && data.curves_by_period[k].length > 0
        )
        : [];

    if (loading && !data) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                <CircularProgress />
            </Box>
        );
    }

    if (error) {
        return <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>;
    }

    if (!data) {
        return <Alert severity="info" sx={{ mt: 2 }}>请选择日期查看数据</Alert>;
    }

    return (
        <Box sx={{ position: 'relative' }}>
            {loading && (
                <Box
                    sx={{
                        position: 'absolute',
                        top: 0, left: 0, right: 0, bottom: 0,
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'center',
                        backgroundColor: 'rgba(255, 255, 255, 0.7)',
                        zIndex: 1000
                    }}
                >
                    <CircularProgress />
                </Box>
            )}


            <SummaryPanel
                selectedCurves={selectedCurves}
                selectedBenchmark={selectedBenchmark}
            />


            <FilterPanel
                selectedCurves={selectedCurves}
                onSelectedCurvesChange={setSelectedCurves}
                availableCurves={availableCurves}
            />

            <MultiCurveChart
                curvesByPeriod={data.curves_by_period || {}}
                spotCurves={data.spot_curves}
                selectedCurves={selectedCurves.filter(k => availableCurves.includes(k))}
                selectedBenchmark={selectedBenchmark}
                dateStr={dateStr}
            />
        </Box>
    );
};
