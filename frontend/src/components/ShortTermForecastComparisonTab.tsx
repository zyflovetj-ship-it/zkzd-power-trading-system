/**
 * 短期负荷预测 - 对比分析 Tab 组件
 *
 * 功能：
 * - 多预测曲线对比（d+1/d+2/d+3 可选择显示/隐藏）
 * - 与实际负荷曲线对比（如有实际数据）
 * - 精度指标对比表格（MAE、MAPE、RMSE）
 */

import React, { useState, useEffect, useRef } from 'react';
import {
    Box,
    Paper,
    IconButton,
    CircularProgress,
    Alert,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography,
    Checkbox,
    FormControlLabel,
    useTheme,
    useMediaQuery,
} from '@mui/material';
import { DatePicker, LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { zhCN } from 'date-fns/locale';
import ArrowLeftIcon from '@mui/icons-material/ArrowLeft';
import ArrowRightIcon from '@mui/icons-material/ArrowRight';
import { format, addDays } from 'date-fns';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
} from 'recharts';
import apiClient from '../api/client';
import { useChartFullscreen } from '../hooks/useChartFullscreen';
import { useSelectableSeries } from '../hooks/useSelectableSeries';

// 数据类型定义
interface ForecastDataPoint {
    time: string;
    forecast_value: number;
    actual_value?: number;
    timestamp: string;
}

interface ForecastCurveData {
    forecast_date: string;
    forecast_target_date: string;
    forecast_type: string;
    data: ForecastDataPoint[];
    total_points: number;
    completeness: number;
    has_actual: boolean;
}

interface AccuracyMetrics {
    forecast_date: string;
    forecast_target_date: string;
    forecast_type: string;
    mae?: number;
    mape?: number;
    rmse?: number;
    max_error?: number;
    max_error_time?: string;
}

type ForecastType = 'd+1' | 'd+2' | 'd+3';

// 曲线颜色配置
const CURVE_COLORS: Record<ForecastType | 'actual', string> = {
    'd+1': '#1976d2',   // 蓝色
    'd+2': '#388e3c',   // 绿色
    'd+3': '#f57c00',   // 橙色
    'actual': '#d32f2f', // 红色
};

// 曲线中文名称
const CURVE_NAMES: Record<ForecastType | 'actual', string> = {
    'd+1': 'D+1 预测',
    'd+2': 'D+2 预测',
    'd+3': 'D+3 预测',
    'actual': '实际负荷',
};

export const ShortTermForecastComparisonTab: React.FC = () => {
    const [selectedDate, setSelectedDate] = useState<Date | null>(addDays(new Date(), -1));
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // 存储各预测类型的曲线数据
    const [forecastData, setForecastData] = useState<Record<ForecastType, ForecastCurveData | null>>({
        'd+1': null,
        'd+2': null,
        'd+3': null,
    });

    // 存储各预测类型的精度指标
    const [accuracyData, setAccuracyData] = useState<Record<ForecastType, AccuracyMetrics | null>>({
        'd+1': null,
        'd+2': null,
        'd+3': null,
    });

    // 预测类型选择状态（用于显示/隐藏曲线）
    const [selectedTypes, setSelectedTypes] = useState<Record<ForecastType, boolean>>({
        'd+1': true,
        'd+2': true,
        'd+3': true,
    });

    // 是否显示实际负荷曲线（如果有数据）
    const [showActual, setShowActual] = useState(true);

    const chartRef = useRef<HTMLDivElement>(null);
    const dateStr = selectedDate ? format(selectedDate, 'yyyy-MM-dd') : '';
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // 全屏 Hook
    const { isFullscreen, FullscreenEnterButton, FullscreenExitButton, FullscreenTitle, NavigationButtons } =
        useChartFullscreen({
            chartRef,
            title: `短期负荷预测对比 (${dateStr})`,
            onPrevious: () => handleShiftDate(-1),
            onNext: () => handleShiftDate(1),
        });

    // 曲线选择 Hook
    const initialSeriesState: Record<string, boolean> = {
        'D+1 预测': selectedTypes['d+1'],
        'D+2 预测': selectedTypes['d+2'],
        'D+3 预测': selectedTypes['d+3'],
        '实际负荷': showActual,
    };

    const { seriesVisibility, handleLegendClick } = useSelectableSeries(initialSeriesState);

    // 更新预测类型选择状态（与 Legend 点击同步）
    useEffect(() => {
        setSelectedTypes({
            'd+1': seriesVisibility['D+1 预测'] ?? false,
            'd+2': seriesVisibility['D+2 预测'] ?? false,
            'd+3': seriesVisibility['D+3 预测'] ?? false,
        });
        setShowActual(seriesVisibility['实际负荷'] ?? false);
    }, [seriesVisibility]);

    // 获取单个预测类型的数据
    const fetchForecastData = async (date: Date, type: ForecastType) => {
        const formattedDate = format(date, 'yyyy-MM-dd');
        const encodedType = encodeURIComponent(type);

        try {
            const response = await apiClient.get(
                `/api/v1/short-term-load-forecast/curve?forecast_date=${formattedDate}&forecast_type=${encodedType}`
            );

            // 处理 API 返回数据
            const curveData: ForecastCurveData = response.data && response.data.data
                ? response.data
                : generateMockForecastData(formattedDate, type);

            setForecastData(prev => ({ ...prev, [type]: curveData }));

            // 如果有实际数据，获取精度指标
            if (curveData.has_actual) {
                try {
                    const accuracyResponse = await apiClient.get(
                        `/api/v1/short-term-load-forecast/accuracy?forecast_date=${formattedDate}&forecast_type=${encodedType}`
                    );
                    setAccuracyData(prev => ({ ...prev, [type]: accuracyResponse.data }));
                } catch (accError) {
                    console.warn(`获取 ${type} 精度指标失败:`, accError);
                    setAccuracyData(prev => ({ ...prev, [type]: null }));
                }
            } else {
                setAccuracyData(prev => ({ ...prev, [type]: null }));
            }
        } catch (err) {
            console.warn(`获取 ${type} 预测数据失败，使用演示数据:`, err);
            const mockData = generateMockForecastData(formattedDate, type);
            setForecastData(prev => ({ ...prev, [type]: mockData }));
            setAccuracyData(prev => ({ ...prev, [type]: null }));
        }
    };

    // 生成演示数据
    const generateMockForecastData = (date: string, type: ForecastType): ForecastCurveData => {
        const data: ForecastDataPoint[] = [];
        const startDate = new Date(date + 'T00:00:00');

        // 基础负荷模式
        const baseLoadProfile = {
            nightBase: 650,
            morningPeak: 1200,
            dayStable: 950,
            eveningPeak: 1350,
            eveningDecline: 800,
        };

        // 不同预测类型的不确定性
        const uncertainty = type === 'd+1' ? 0.02 : type === 'd+2' ? 0.05 : 0.08;

        for (let i = 0; i < 96; i++) {
            const timeObj = new Date(startDate.getTime() + i * 15 * 60 * 1000);
            const hour = timeObj.getHours();
            const minute = timeObj.getMinutes();

            let timeStr = `${hour.toString().padStart(2, '0')}:${minute.toString().padStart(2, '0')}`;
            if (timeStr === "00:00" && i > 0) {
                timeStr = "24:00";
            }

            let baseLoad: number;
            if (hour >= 0 && hour < 6) {
                baseLoad = baseLoadProfile.nightBase;
            } else if (hour >= 6 && hour < 9) {
                const progress = (hour - 6) + (minute / 60);
                baseLoad = baseLoadProfile.nightBase +
                          (baseLoadProfile.morningPeak - baseLoadProfile.nightBase) * progress / 3;
            } else if (hour >= 9 && hour < 17) {
                baseLoad = baseLoadProfile.dayStable;
            } else if (hour >= 17 && hour < 21) {
                const progress = (hour - 17) + (minute / 60);
                baseLoad = baseLoadProfile.dayStable +
                          (baseLoadProfile.eveningPeak - baseLoadProfile.dayStable) * progress / 4;
            } else {
                const progress = (hour - 21) + (minute / 60);
                baseLoad = baseLoadProfile.eveningPeak -
                          (baseLoadProfile.eveningPeak - baseLoadProfile.eveningDecline) * progress / 3;
            }

            const randomFactor = 0.95 + Math.random() * 0.1;
            const seasonalFactor = 1 + 0.1 * Math.sin((i / 96) * 2 * Math.PI);
            const predictionError = (Math.random() - 0.5) * uncertainty;

            const forecastValue = Math.round(
                baseLoad * randomFactor * seasonalFactor * (1 + predictionError)
            );

            data.push({
                time: timeStr,
                forecast_value: forecastValue,
                timestamp: timeObj.toISOString(),
            });
        }

        return {
            forecast_date: date,
            forecast_target_date: date,
            forecast_type: type,
            data,
            total_points: 96,
            completeness: 100.0,
            has_actual: false,
        };
    };

    // 获取所有选中的预测类型数据
    const fetchAllData = (date: Date | null) => {
        if (!date) return;
        setLoading(true);
        setError(null);

        const promises: Promise<void>[] = [];
        (Object.keys(selectedTypes) as ForecastType[]).forEach(type => {
            if (selectedTypes[type]) {
                promises.push(fetchForecastData(date, type));
            }
        });

        Promise.allSettled(promises).finally(() => setLoading(false));
    };

    // 自动加载
    useEffect(() => {
        fetchAllData(selectedDate);
    }, [selectedDate]);

    // 日期导航
    const handleShiftDate = (days: number) => {
        if (!selectedDate) return;
        const newDate = addDays(selectedDate, days);
        setSelectedDate(newDate);
    };

    // 预测类型选择切换
    const handleTypeToggle = (type: ForecastType) => {
        setSelectedTypes(prev => {
            const newSelected = { ...prev, [type]: !prev[type] };
            // 如果新选中了某个类型，获取其数据
            if (newSelected[type] && selectedDate) {
                fetchForecastData(selectedDate, type);
            }
            return newSelected;
        });
    };

    // 合并所有数据用于图表展示
    const mergedChartData = () => {
        if (!forecastData['d+1']?.data) return [];

        return forecastData['d+1']!.data.map(point => {
            const row: any = {
                time: point.time,
            };

            // 添加各预测类型的值
            (Object.keys(forecastData) as ForecastType[]).forEach(type => {
                if (forecastData[type]?.data) {
                    const dataPoint = forecastData[type]!.data.find(d => d.time === point.time);
                    row[CURVE_NAMES[type]] = dataPoint?.forecast_value;
                }
            });

            // 添加实际值（如果有）
            if (point.actual_value !== undefined) {
                row[CURVE_NAMES['actual']] = point.actual_value;
            }

            return row;
        });
    };

    // 渲染图表
    const renderChart = () => {
        const chartData = mergedChartData();
        if (chartData.length === 0) {
            return (
                <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
                    <Alert severity="info">无数据，请选择预测日期</Alert>
                </Box>
            );
        }

        return (
            <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                        dataKey="time"
                        interval="preserveStartEnd"
                        tick={{ fontSize: 12 }}
                        tickFormatter={(value, index) => {
                            if (index % 4 === 0) return value;
                            return '';
                        }}
                    />
                    <YAxis
                        label={{ value: '负荷 (MW)', angle: -90, position: 'insideLeft' }}
                    />
                    <Tooltip
                        contentStyle={{ backgroundColor: 'rgba(255, 255, 255, 0.95)' }}
                        formatter={(value: number) => `${value.toFixed(2)} MW`}
                    />
                    <Legend onClick={handleLegendClick} />

                    {/* 渲染选中的预测曲线 */}
                    {(Object.keys(selectedTypes) as ForecastType[]).map(type => {
                        if (!selectedTypes[type] || !forecastData[type]) return null;
                        return (
                            <Line
                                key={type}
                                type="monotone"
                                dataKey={CURVE_NAMES[type]}
                                stroke={CURVE_COLORS[type]}
                                strokeWidth={2}
                                dot={false}
                                isAnimationActive={false}
                                hide={!seriesVisibility[CURVE_NAMES[type]]}
                            />
                        );
                    })}

                    {/* 渲染实际负荷曲线（如果有数据） */}
                    {showActual && forecastData['d+1']?.has_actual && (
                        <Line
                            type="monotone"
                            dataKey={CURVE_NAMES['actual']}
                            stroke={CURVE_COLORS['actual']}
                            strokeWidth={2}
                            dot={false}
                            isAnimationActive={false}
                            hide={!seriesVisibility[CURVE_NAMES['actual']]}
                        />
                    )}
                </LineChart>
            </ResponsiveContainer>
        );
    };

    // 渲染精度指标表格
    const renderAccuracyTable = () => {
        const hasAccuracyData = (Object.keys(accuracyData) as ForecastType[]).some(
            type => accuracyData[type] !== null
        );

        if (!hasAccuracyData) {
            return (
                <Box sx={{ textAlign: 'center', py: 3 }}>
                    <Typography variant="body2" color="text.secondary">
                        当前预测目标日期尚无实际数据，无法计算精度指标
                    </Typography>
                </Box>
            );
        }

        return (
            <TableContainer component={Paper} variant="outlined" sx={{ mt: 2 }}>
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell>预测类型</TableCell>
                            <TableCell align="right">MAE (MW)</TableCell>
                            <TableCell align="right">MAPE (%)</TableCell>
                            <TableCell align="right">RMSE (MW)</TableCell>
                            <TableCell align="right">最大误差 (MW)</TableCell>
                            <TableCell align="right">最大误差时刻</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {(Object.keys(accuracyData) as ForecastType[]).map(type => {
                            const metrics = accuracyData[type];
                            if (!metrics) return null;

                            return (
                                <TableRow key={type}>
                                    <TableCell>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Box
                                                sx={{
                                                    width: 12,
                                                    height: 12,
                                                    backgroundColor: CURVE_COLORS[type],
                                                    borderRadius: '50%',
                                                }}
                                            />
                                            {CURVE_NAMES[type]}
                                        </Box>
                                    </TableCell>
                                    <TableCell align="right">{metrics.mae?.toFixed(2) || '-'}</TableCell>
                                    <TableCell align="right">{metrics.mape?.toFixed(2) || '-'}</TableCell>
                                    <TableCell align="right">{metrics.rmse?.toFixed(2) || '-'}</TableCell>
                                    <TableCell align="right">{metrics.max_error?.toFixed(2) || '-'}</TableCell>
                                    <TableCell align="right">{metrics.max_error_time || '-'}</TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </TableContainer>
        );
    };

    // 判断是否有任何数据
    const hasAnyData = (Object.keys(forecastData) as ForecastType[]).some(
        type => forecastData[type] !== null
    );

    return (
        <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={zhCN}>
            <Box>
                {/* 筛选条件 */}
                <Paper variant="outlined" sx={{ p: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                    <IconButton onClick={() => handleShiftDate(-1)} disabled={loading}>
                        <ArrowLeftIcon />
                    </IconButton>

                    <DatePicker
                        label="预测日期"
                        value={selectedDate}
                        onChange={(date) => setSelectedDate(date)}
                        disabled={loading}
                        slotProps={{
                            textField: {
                                sx: { width: { xs: '150px', sm: '200px' } }
                            }
                        }}
                    />

                    <IconButton onClick={() => handleShiftDate(1)} disabled={loading}>
                        <ArrowRightIcon />
                    </IconButton>

                    {/* 预测类型选择 */}
                    <Box sx={{ ml: { xs: 0, sm: 2 }, display: 'flex', gap: { xs: 0.5, sm: 1 }, flexWrap: 'wrap' }}>
                        {(Object.keys(selectedTypes) as ForecastType[]).map(type => (
                            <FormControlLabel
                                key={type}
                                control={
                                    <Checkbox
                                        checked={selectedTypes[type]}
                                        onChange={() => handleTypeToggle(type)}
                                        disabled={loading}
                                        sx={{
                                            color: CURVE_COLORS[type],
                                            '&.Mui-checked': { color: CURVE_COLORS[type] },
                                        }}
                                    />
                                }
                                label={CURVE_NAMES[type]}
                                sx={{ mr: { xs: 0, sm: 1 } }}
                            />
                        ))}
                    </Box>

                    {/* 显示信息 */}
                    {hasAnyData && (
                        <Box sx={{ ml: 'auto', fontSize: '0.875rem', color: '#666' }}>
                            {Object.values(forecastData).filter(d => d).length} 条预测曲线
                            {Object.values(forecastData).some(d => d?.has_actual) && ' | 含实际负荷'}
                        </Box>
                    )}
                </Paper>

                {/* 首次加载 */}
                {loading && !hasAnyData ? (
                    <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                        <CircularProgress />
                    </Box>
                ) : error ? (
                    <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>
                ) : hasAnyData ? (
                    <Box sx={{ position: 'relative' }}>
                        {/* 数据加载时的覆盖层 */}
                        {loading && (
                            <Box
                                sx={{
                                    position: 'absolute',
                                    top: 0,
                                    left: 0,
                                    right: 0,
                                    bottom: 0,
                                    display: 'flex',
                                    alignItems: 'center',
                                    justifyContent: 'center',
                                    backgroundColor: 'rgba(255, 255, 255, 0.7)',
                                    zIndex: 1000,
                                }}
                            >
                                <CircularProgress />
                            </Box>
                        )}

                        {/* 对比曲线图表 */}
                        <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
                            <Typography variant="h6" gutterBottom>预测曲线对比</Typography>
                            <Box
                                ref={chartRef}
                                sx={{
                                    height: { xs: 350, sm: 400 },
                                    position: 'relative',
                                    backgroundColor: isFullscreen ? 'background.paper' : 'transparent',
                                    p: isFullscreen ? 2 : 0,
                                    ...(isFullscreen && {
                                        position: 'fixed',
                                        top: 0,
                                        left: 0,
                                        width: '100vw',
                                        height: '100vh',
                                        zIndex: 1400,
                                    }),
                                }}
                            >
                                <FullscreenEnterButton />
                                <FullscreenExitButton />
                                <FullscreenTitle />
                                <NavigationButtons />
                                {renderChart()}
                            </Box>
                        </Paper>

                        {/* 精度指标表格 */}
                        <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
                            <Typography variant="h6" gutterBottom>精度指标对比</Typography>
                            {renderAccuracyTable()}
                        </Paper>
                    </Box>
                ) : (
                    <Alert severity="info" sx={{ mt: 2 }}>请选择至少一种预测类型进行对比</Alert>
                )}
            </Box>
        </LocalizationProvider>
    );
};
