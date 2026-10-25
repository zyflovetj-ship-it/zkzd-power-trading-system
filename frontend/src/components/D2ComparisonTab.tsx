import React, { useState, useEffect, useRef } from 'react';
import {
    Box,
    Paper,
    Typography,
    IconButton,
    CircularProgress,
    Alert,
    useMediaQuery,
    useTheme,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    Grid,
} from '@mui/material';
import { DatePicker, LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { zhCN } from 'date-fns/locale';
import ArrowLeftIcon from '@mui/icons-material/ArrowLeft';
import ArrowRightIcon from '@mui/icons-material/ArrowRight';
import { addDays, format, subDays } from 'date-fns';

import {
    ResponsiveContainer,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
} from 'recharts';
import apiClient from '../api/client';
import { useChartFullscreen } from '../hooks/useChartFullscreen';

// ============ 类型定义 ============
interface ComparisonData {
    time: string;
    predicted: number;
    actual: number | null;
    difference: number | null;
}

// ============ 主组件 ============
export const D2ComparisonTab: React.FC = () => {
    const [targetDate, setTargetDate] = useState<Date | null>(subDays(new Date(), 1)); // 默认昨天
    const [comparisonData, setComparisonData] = useState<ComparisonData[]>([]);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [metrics, setMetrics] = useState({
        mae: 0,
        rmse: 0,
        mape: 0,
        accuracy: 0,
    });

    const chartRef = useRef<HTMLDivElement>(null);
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('md'));

    // 全屏 Hook
    const { isFullscreen, FullscreenEnterButton, FullscreenExitButton, FullscreenTitle } =
        useChartFullscreen({
            chartRef,
            title: `D-2价格对比分析 - ${targetDate ? format(targetDate, 'yyyy-MM-dd') : ''}`,
        });

    // 加载对比数据
    useEffect(() => {
        if (targetDate) {
            fetchComparisonData(targetDate);
        }
    }, [targetDate]);

    const fetchComparisonData = async (date: Date) => {
        setLoading(true);
        setError(null);
        const dateStr = format(date, 'yyyy-MM-dd');

        try {
            const response = await apiClient.get(`/api/v1/price-forecast/d2/comparison`, {
                params: { target_date: dateStr }
            });

            setComparisonData(response.data.data);
            setMetrics(response.data.metrics);
        } catch (err: any) {
            console.error('加载对比数据失败:', err);
            setError(err.response?.data?.detail || err.message || '加载对比数据失败');
            setComparisonData([]);
            setMetrics({ mae: 0, rmse: 0, mape: 0, accuracy: 0 });
        } finally {
            setLoading(false);
        }
    };

    // 日期导航
    const shiftDate = (days: number) => {
        if (!targetDate) return;
        const newDate = addDays(targetDate, days);
        setTargetDate(newDate);
    };

    return (
        <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={zhCN}>
            <Box>
                {/* 日期选择器 */}
                <Paper variant="outlined" sx={{ p: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Typography variant="body2" sx={{ mr: 1 }}>
                        目标日期:
                    </Typography>
                    <IconButton onClick={() => shiftDate(-1)} disabled={loading} size="small">
                        <ArrowLeftIcon />
                    </IconButton>
                    <DatePicker
                        value={targetDate}
                        onChange={(date) => setTargetDate(date)}
                        disabled={loading}
                        slotProps={{
                            textField: {
                                sx: { width: { xs: '150px', sm: '200px' } }
                            }
                        }}
                    />
                    <IconButton onClick={() => shiftDate(1)} disabled={loading} size="small">
                        <ArrowRightIcon />
                    </IconButton>
                </Paper>

                {/* 首次加载显示完整的 loading */}
                {loading && !comparisonData.length && !error && (
                    <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                        <CircularProgress />
                    </Box>
                )}

                {error && (
                    <Alert severity="error" sx={{ mt: 2 }}>
                        {error}
                    </Alert>
                )}

                {/* 指标卡片 */}
                {(!loading || comparisonData.length > 0) && (
                    <Grid container spacing={2} sx={{ mt: 2 }}>
                        <Grid size={{ xs: 6, md: 3 }}>
                            <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                                <Typography variant="caption" color="text.secondary">
                                    平均绝对误差
                                </Typography>
                                <Typography variant="h6" color="primary">
                                    {metrics.mae.toFixed(2)}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                    元/MWh
                                </Typography>
                            </Paper>
                        </Grid>
                        <Grid size={{ xs: 6, md: 3 }}>
                            <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                                <Typography variant="caption" color="text.secondary">
                                    均方根误差
                                </Typography>
                                <Typography variant="h6" color="primary">
                                    {metrics.rmse.toFixed(2)}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                    元/MWh
                                </Typography>
                            </Paper>
                        </Grid>
                        <Grid size={{ xs: 6, md: 3 }}>
                            <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                                <Typography variant="caption" color="text.secondary">
                                    平均百分比误差
                                </Typography>
                                <Typography variant="h6" color="primary">
                                    {metrics.mape.toFixed(2)}%
                                </Typography>
                            </Paper>
                        </Grid>
                        <Grid size={{ xs: 6, md: 3 }}>
                            <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                                <Typography variant="caption" color="text.secondary">
                                    预测准确度
                                </Typography>
                                <Typography variant="h6" color="success.main">
                                    {metrics.accuracy.toFixed(1)}%
                                </Typography>
                            </Paper>
                        </Grid>
                    </Grid>
                )}

                {/* 图表容器 */}
                {(!loading || comparisonData.length > 0) && (
                    <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            预测值 vs 实际值对比
                        </Typography>

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
                                    zIndex: 1400
                                })
                            }}
                        >
                            <FullscreenEnterButton />
                            <FullscreenExitButton />
                            <FullscreenTitle />

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
                                        zIndex: 1000
                                    }}
                                >
                                    <CircularProgress />
                                </Box>
                            )}

                            {!comparisonData || comparisonData.length === 0 ? (
                                <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
                                    <Typography>暂无对比数据</Typography>
                                </Box>
                            ) : (
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart data={comparisonData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis
                                            dataKey="time"
                                            interval={isMobile ? 11 : 3}
                                            angle={-45}
                                            textAnchor="end"
                                            height={60}
                                        />
                                        <YAxis
                                            label={{ value: '价格 (元/MWh)', angle: -90, position: 'insideLeft' }}
                                        />
                                        <Tooltip
                                            content={(props) => {
                                                if (props.active && props.payload && props.payload.length > 0) {
                                                    const data = props.payload[0].payload;
                                                    return (
                                                        <Paper sx={{ p: 1 }}>
                                                            <Typography variant="body2">
                                                                时间: {data.time}
                                                            </Typography>
                                                            <Typography variant="body2" color="#8884d8">
                                                                预测值: {data.predicted.toFixed(2)} 元/MWh
                                                            </Typography>
                                                            <Typography variant="body2" color="#82ca9d">
                                                                实际值: {data.actual !== null ? data.actual.toFixed(2) + ' 元/MWh' : '暂无'}
                                                            </Typography>
                                                            {data.difference !== null && (
                                                                <Typography variant="caption" color={data.difference >= 0 ? 'error.main' : 'success.main'}>
                                                                    偏差: {data.difference >= 0 ? '+' : ''}{data.difference.toFixed(2)} 元/MWh
                                                                </Typography>
                                                            )}
                                                        </Paper>
                                                    );
                                                }
                                                return null;
                                            }}
                                        />
                                        <Legend />
                                        <Line
                                            type="monotone"
                                            dataKey="predicted"
                                            stroke="#8884d8"
                                            strokeWidth={2}
                                            dot={false}
                                            name="预测值"
                                        />
                                        <Line
                                            type="monotone"
                                            dataKey="actual"
                                            stroke="#82ca9d"
                                            strokeWidth={2}
                                            dot={false}
                                            name="实际值"
                                            connectNulls={false}
                                        />
                                    </LineChart>
                                </ResponsiveContainer>
                            )}
                        </Box>
                    </Paper>
                )}
            </Box>
        </LocalizationProvider>
    );
};
