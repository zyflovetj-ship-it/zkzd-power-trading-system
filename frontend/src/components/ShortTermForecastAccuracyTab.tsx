/**
 * 短期负荷预测 - 精度统计 Tab 组件
 *
 * 功能：
 * - 显示各预测类型的精度指标统计（MAE、MAPE、RMSE）
 * - 精度趋势图表（随时间变化）
 * - 日期范围筛选
 */

import React, { useState, useEffect, useRef } from 'react';
import {
    Box,
    Paper,
    CircularProgress,
    Alert,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Typography,
    useTheme,
    useMediaQuery,
} from '@mui/material';
import { DatePicker, LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { zhCN } from 'date-fns/locale';
import { format, subDays } from 'date-fns';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    BarChart,
    Bar,
} from 'recharts';
import apiClient from '../api/client';
import { useChartFullscreen } from '../hooks/useChartFullscreen';

// 数据类型定义
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

// 预测类型配置
const FORECAST_TYPES: ForecastType[] = ['d+1', 'd+2', 'd+3'];

const FORECAST_TYPE_NAMES: Record<ForecastType, string> = {
    'd+1': 'D+1 (次日)',
    'd+2': 'D+2 (第三日)',
    'd+3': 'D+3 (第四日)',
};

const FORECAST_TYPE_COLORS: Record<ForecastType, string> = {
    'd+1': '#1976d2',
    'd+2': '#388e3c',
    'd+3': '#f57c00',
};

export const ShortTermForecastAccuracyTab: React.FC = () => {
    const [startDate, setStartDate] = useState<Date | null>(subDays(new Date(), 6));
    const [endDate, setEndDate] = useState<Date | null>(new Date());
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // 存储各预测类型的精度数据
    const [accuracyData, setAccuracyData] = useState<Record<ForecastType, AccuracyMetrics[]>>({
        'd+1': [],
        'd+2': [],
        'd+3': [],
    });

    // 图表类型切换
    const [chartType, setChartType] = useState<'mae' | 'mape' | 'rmse'>('mae');

    const chartRef = useRef<HTMLDivElement>(null);
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // 全屏 Hook
    const { isFullscreen, FullscreenEnterButton, FullscreenExitButton, FullscreenTitle } =
        useChartFullscreen({
            chartRef,
            title: '精度趋势分析',
        });

    // 获取精度数据
    const fetchAccuracyData = async () => {
        if (!startDate || !endDate) return;

        setLoading(true);
        setError(null);

        const results: Record<ForecastType, AccuracyMetrics[]> = {
            'd+1': [],
            'd+2': [],
            'd+3': [],
        };

        // 生成日期范围内的所有日期
        const dates: Date[] = [];
        let currentDate = new Date(startDate);
        while (currentDate <= endDate) {
            dates.push(new Date(currentDate));
            currentDate.setDate(currentDate.getDate() + 1);
        }

        // 为每个预测类型和日期获取精度数据
        const promises: Promise<void>[] = [];
        FORECAST_TYPES.forEach(type => {
            dates.forEach(date => {
                const promise = (async () => {
                    try {
                        const formattedDate = format(date, 'yyyy-MM-dd');
                        const encodedType = encodeURIComponent(type);
                        const response = await apiClient.get(
                            `/api/v1/short-term-load-forecast/accuracy?forecast_date=${formattedDate}&forecast_type=${encodedType}`
                        );
                        if (response.data && response.data.mae !== undefined) {
                            results[type].push(response.data);
                        }
                    } catch (err) {
                        // 某些日期可能没有精度数据（无实际数据），忽略错误
                        console.debug(`获取 ${type} ${format(date, 'yyyy-MM-dd')} 精度失败:`, err);
                    }
                })();
                promises.push(promise);
            });
        });

        try {
            await Promise.all(promises);
            setAccuracyData(results);
        } catch (err) {
            console.error('获取精度数据失败:', err);
            setError('获取精度数据失败');
        } finally {
            setLoading(false);
        }
    };

    // 自动加载
    useEffect(() => {
        fetchAccuracyData();
    }, [startDate, endDate]);

    // 计算汇总统计
    const getSummaryStats = () => {
        const summary: Record<ForecastType, { avgMae: number; avgMape: number; avgRmse: number; count: number }> = {
            'd+1': { avgMae: 0, avgMape: 0, avgRmse: 0, count: 0 },
            'd+2': { avgMae: 0, avgMape: 0, avgRmse: 0, count: 0 },
            'd+3': { avgMae: 0, avgMape: 0, avgRmse: 0, count: 0 },
        };

        FORECAST_TYPES.forEach(type => {
            const data = accuracyData[type];
            if (data.length === 0) return;

            const validData = data.filter(d => d.mae !== undefined);
            if (validData.length === 0) return;

            summary[type].avgMae = validData.reduce((sum, d) => sum + (d.mae || 0), 0) / validData.length;
            summary[type].avgMape = validData.reduce((sum, d) => sum + (d.mape || 0), 0) / validData.filter(d => d.mape !== undefined).length;
            summary[type].avgRmse = validData.reduce((sum, d) => sum + (d.rmse || 0), 0) / validData.length;
            summary[type].count = validData.length;
        });

        return summary;
    };

    // 准备趋势图表数据
    const getTrendChartData = () => {
        // 找出所有有数据的日期
        const allDates = new Set<string>();
        FORECAST_TYPES.forEach(type => {
            accuracyData[type].forEach(d => {
                allDates.add(d.forecast_target_date);
            });
        });

        const sortedDates = Array.from(allDates).sort();

        return sortedDates.map(date => {
            const row: any = { date };
            FORECAST_TYPES.forEach(type => {
                const data = accuracyData[type].find(d => d.forecast_target_date === date);
                row[FORECAST_TYPE_NAMES[type]] = data?.[chartType] || null;
            });
            return row;
        });
    };

    // 渲染汇总统计表格
    const renderSummaryTable = () => {
        const summary = getSummaryStats();
        const hasData = Object.values(summary).some(s => s.count > 0);

        if (!hasData) {
            return (
                <Box sx={{ textAlign: 'center', py: 3 }}>
                    <Typography variant="body2" color="text.secondary">
                        所选日期范围内暂无精度数据
                    </Typography>
                </Box>
            );
        }

        return (
            <TableContainer component={Paper} variant="outlined">
                <Table size="small">
                    <TableHead>
                        <TableRow>
                            <TableCell>预测类型</TableCell>
                            <TableCell align="right">平均 MAE (MW)</TableCell>
                            <TableCell align="right">平均 MAPE (%)</TableCell>
                            <TableCell align="right">平均 RMSE (MW)</TableCell>
                            <TableCell align="right">统计天数</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {FORECAST_TYPES.map(type => {
                            const stats = summary[type];
                            if (stats.count === 0) return null;

                            return (
                                <TableRow key={type}>
                                    <TableCell>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                            <Box
                                                sx={{
                                                    width: 12,
                                                    height: 12,
                                                    backgroundColor: FORECAST_TYPE_COLORS[type],
                                                    borderRadius: '50%',
                                                }}
                                            />
                                            {FORECAST_TYPE_NAMES[type]}
                                        </Box>
                                    </TableCell>
                                    <TableCell align="right">{stats.avgMae.toFixed(2)}</TableCell>
                                    <TableCell align="right">{stats.avgMape.toFixed(2)}</TableCell>
                                    <TableCell align="right">{stats.avgRmse.toFixed(2)}</TableCell>
                                    <TableCell align="right">{stats.count}</TableCell>
                                </TableRow>
                            );
                        })}
                    </TableBody>
                </Table>
            </TableContainer>
        );
    };

    // 渲染趋势图表
    const renderTrendChart = () => {
        const chartData = getTrendChartData();
        const hasData = chartData.length > 0;

        if (!hasData) {
            return (
                <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
                    <Alert severity="info">所选日期范围内暂无精度数据</Alert>
                </Box>
            );
        }

        const chartTypeLabels: Record<typeof chartType, string> = {
            mae: 'MAE (MW)',
            mape: 'MAPE (%)',
            rmse: 'RMSE (MW)',
        };

        return (
            <ResponsiveContainer width="100%" height="100%">
                <LineChart data={chartData} margin={{ top: 10, right: 30, left: 0, bottom: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                        dataKey="date"
                        tick={{ fontSize: 12 }}
                        tickFormatter={(value) => {
                            // 只显示月-日
                            const parts = value.split('-');
                            return `${parts[1]}-${parts[2]}`;
                        }}
                    />
                    <YAxis
                        label={{ value: chartTypeLabels[chartType], angle: -90, position: 'insideLeft' }}
                    />
                    <Tooltip
                        contentStyle={{ backgroundColor: 'rgba(255, 255, 255, 0.95)' }}
                        formatter={(value: number) => value?.toFixed(2) || '-'}
                        labelFormatter={(label) => `日期: ${label}`}
                    />
                    <Legend />
                    {FORECAST_TYPES.map(type => (
                        <Line
                            key={type}
                            type="monotone"
                            dataKey={FORECAST_TYPE_NAMES[type]}
                            stroke={FORECAST_TYPE_COLORS[type]}
                            strokeWidth={2}
                            dot={{ r: 4 }}
                            isAnimationActive={false}
                            connectNulls={false}
                        />
                    ))}
                </LineChart>
            </ResponsiveContainer>
        );
    };

    // 渲染图表类型选择按钮
    const renderChartTypeButtons = () => {
        const buttons: { key: typeof chartType; label: string }[] = [
            { key: 'mae', label: 'MAE' },
            { key: 'mape', label: 'MAPE' },
            { key: 'rmse', label: 'RMSE' },
        ];

        return (
            <Box sx={{ display: 'flex', gap: 1 }}>
                {buttons.map(btn => (
                    <Typography
                        key={btn.key}
                        sx={{
                            px: 2,
                            py: 1,
                            cursor: 'pointer',
                            backgroundColor: chartType === btn.key ? 'primary.main' : 'action.hover',
                            color: chartType === btn.key ? 'primary.contrastText' : 'text.primary',
                            borderRadius: 1,
                            fontSize: '0.875rem',
                            transition: 'all 0.2s',
                            '&:hover': {
                                backgroundColor: chartType === btn.key ? 'primary.dark' : 'action.selected',
                            },
                        }}
                        onClick={() => setChartType(btn.key)}
                    >
                        {btn.label}
                    </Typography>
                ))}
            </Box>
        );
    };

    const hasAnyData = Object.values(accuracyData).some(arr => arr.length > 0);

    return (
        <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={zhCN}>
            <Box>
                {/* 筛选条件 */}
                <Paper variant="outlined" sx={{ p: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                    <DatePicker
                        label="开始日期"
                        value={startDate}
                        onChange={(date) => setStartDate(date)}
                        disabled={loading}
                        slotProps={{
                            textField: {
                                sx: { width: { xs: '140px', sm: '180px' } }
                            }
                        }}
                    />

                    <Typography variant="body2" sx={{ mx: 1 }}>至</Typography>

                    <DatePicker
                        label="结束日期"
                        value={endDate}
                        onChange={(date) => setEndDate(date)}
                        disabled={loading}
                        maxDate={new Date()}
                        slotProps={{
                            textField: {
                                sx: { width: { xs: '140px', sm: '180px' } }
                            }
                        }}
                    />

                    <Box sx={{ ml: 'auto', fontSize: '0.875rem', color: '#666' }}>
                        {hasAnyData && Object.values(accuracyData).filter(arr => arr.length > 0).length} 个预测类型有数据
                    </Box>
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

                        {/* 汇总统计表格 */}
                        <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
                            <Typography variant="h6" gutterBottom>精度汇总统计</Typography>
                            {renderSummaryTable()}
                        </Paper>

                        {/* 趋势图表 */}
                        <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
                            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2 }}>
                                <Typography variant="h6">精度趋势分析</Typography>
                                {renderChartTypeButtons()}
                            </Box>
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
                                {renderTrendChart()}
                            </Box>
                        </Paper>
                    </Box>
                ) : (
                    <Alert severity="info" sx={{ mt: 2 }}>
                        请选择日期范围查看精度统计数据
                    </Alert>
                )}
            </Box>
        </LocalizationProvider>
    );
};
