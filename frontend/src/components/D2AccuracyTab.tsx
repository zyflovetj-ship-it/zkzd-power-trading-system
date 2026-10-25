import React, { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    CircularProgress,
    Alert,
    useMediaQuery,
    useTheme,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Grid,
} from '@mui/material';
import { DatePicker, LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { zhCN } from 'date-fns/locale';
import { format, startOfMonth, endOfMonth, subMonths } from 'date-fns';

import {
    ResponsiveContainer,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
} from 'recharts';
import apiClient from '../api/client';

// ============ 类型定义 ============
interface AccuracyRecord {
    target_date: string;
    wmape_accuracy: number;
    mae: number;
    rmse: number;
    mape: number;
    direction_accuracy: number;
}

interface AccuracyStats {
    monthly_avg: number;
    best_day: { date: string; accuracy: number };
    worst_day: { date: string; accuracy: number };
    pass_90_count: number;
    total_days: number;
    records: AccuracyRecord[];
}

// ============ 主组件 ============
export const D2AccuracyTab: React.FC = () => {
    const [selectedMonth, setSelectedMonth] = useState<Date | null>(subMonths(new Date(), 1)); // 默认上个月
    const [accuracyStats, setAccuracyStats] = useState<AccuracyStats | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('md'));

    // 加载精度统计数据
    useEffect(() => {
        if (selectedMonth) {
            fetchAccuracyStats(selectedMonth);
        }
    }, [selectedMonth]);

    const fetchAccuracyStats = async (month: Date) => {
        setLoading(true);
        setError(null);
        const monthStart = format(startOfMonth(month), 'yyyy-MM-dd');
        const monthEnd = format(endOfMonth(month), 'yyyy-MM-dd');

        try {
            const response = await apiClient.get(`/api/v1/price-forecast/d2/accuracy-stats`, {
                params: {
                    start_date: monthStart,
                    end_date: monthEnd
                }
            });
            setAccuracyStats(response.data);
        } catch (err: any) {
            console.error('加载精度统计失败:', err);
            setError(err.response?.data?.detail || err.message || '加载精度统计失败');
            setAccuracyStats(null);
        } finally {
            setLoading(false);
        }
    };

    // 准备图表数据
    const prepareChartData = () => {
        if (!accuracyStats || !accuracyStats.records) return [];
        return accuracyStats.records.map(record => ({
            date: format(new Date(record.target_date), 'MM-dd'),
            wmape: record.wmape_accuracy,
            mape: record.mape,
            direction: record.direction_accuracy,
        }));
    };

    const chartData = prepareChartData();

    return (
        <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={zhCN}>
            <Box>
                {/* 月份选择器 */}
                <Paper variant="outlined" sx={{ p: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Typography variant="body2" sx={{ mr: 1 }}>
                        统计月份:
                    </Typography>
                    {/* 注意：这里应该使用月份选择器，但 MUI x-date-pickers 需要 Pro 版本才有 MonthPicker */}
                    <DatePicker
                        views={['year', 'month']}
                        label="选择月份"
                        value={selectedMonth}
                        onChange={(date) => setSelectedMonth(date)}
                        disabled={loading}
                        slotProps={{
                            textField: {
                                sx: { width: { xs: '150px', sm: '200px' } }
                            }
                        }}
                    />
                </Paper>

                {/* 首次加载显示完整的 loading */}
                {loading && !accuracyStats && !error && (
                    <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                        <CircularProgress />
                    </Box>
                )}

                {error && (
                    <Alert severity="error" sx={{ mt: 2 }}>
                        {error}
                    </Alert>
                )}

                {/* 统计指标卡片 */}
                {(!loading || accuracyStats) && accuracyStats && (
                    <Grid container spacing={2} sx={{ mt: 2 }}>
                        <Grid size={{ xs: 6, md: 3 }}>
                            <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                                <Typography variant="caption" color="text.secondary">
                                    月平均准确度
                                </Typography>
                                <Typography variant="h5" color="primary">
                                    {accuracyStats.monthly_avg.toFixed(1)}%
                                </Typography>
                            </Paper>
                        </Grid>
                        <Grid size={{ xs: 6, md: 3 }}>
                            <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                                <Typography variant="caption" color="text.secondary">
                                    最佳准确度
                                </Typography>
                                <Typography variant="h5" color="success.main">
                                    {accuracyStats.best_day.accuracy.toFixed(1)}%
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                    {format(new Date(accuracyStats.best_day.date), 'yyyy-MM-dd')}
                                </Typography>
                            </Paper>
                        </Grid>
                        <Grid size={{ xs: 6, md: 3 }}>
                            <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                                <Typography variant="caption" color="text.secondary">
                                    最低准确度
                                </Typography>
                                <Typography variant="h5" color="error.main">
                                    {accuracyStats.worst_day.accuracy.toFixed(1)}%
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                    {format(new Date(accuracyStats.worst_day.date), 'yyyy-MM-dd')}
                                </Typography>
                            </Paper>
                        </Grid>
                        <Grid size={{ xs: 6, md: 3 }}>
                            <Paper variant="outlined" sx={{ p: 2, textAlign: 'center' }}>
                                <Typography variant="caption" color="text.secondary">
                                    达标率 (≥90%)
                                </Typography>
                                <Typography variant="h5" color="info.main">
                                    {accuracyStats.pass_90_count}/{accuracyStats.total_days}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                    ({(accuracyStats.pass_90_count / accuracyStats.total_days * 100).toFixed(0)}%)
                                </Typography>
                            </Paper>
                        </Grid>
                    </Grid>
                )}

                {/* 图表 */}
                {(!loading || accuracyStats) && accuracyStats && (
                    <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            准确度趋势图
                        </Typography>

                        <Box sx={{ height: { xs: 300, sm: 350 } }}>
                            {chartData.length === 0 ? (
                                <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
                                    <Typography>暂无统计数据</Typography>
                                </Box>
                            ) : (
                                <ResponsiveContainer width="100%" height="100%">
                                    <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis
                                            dataKey="date"
                                            interval={isMobile ? 4 : 0}
                                            angle={-45}
                                            textAnchor="end"
                                            height={60}
                                        />
                                        <YAxis
                                            label={{ value: '准确度 (%)', angle: -90, position: 'insideLeft' }}
                                            domain={[0, 100]}
                                        />
                                        <Tooltip
                                            content={(props) => {
                                                if (props.active && props.payload && props.payload.length > 0) {
                                                    const data = props.payload[0].payload;
                                                    return (
                                                        <Paper sx={{ p: 1 }}>
                                                            <Typography variant="body2">
                                                                日期: {data.date}
                                                            </Typography>
                                                            <Typography variant="body2" color="#8884d8">
                                                                WMAPE: {data.wmape.toFixed(1)}%
                                                            </Typography>
                                                            <Typography variant="body2" color="#82ca9d">
                                                                MAPE: {data.mape.toFixed(1)}%
                                                            </Typography>
                                                            <Typography variant="body2" color="#ffc658">
                                                                方向准确度: {data.direction.toFixed(1)}%
                                                            </Typography>
                                                        </Paper>
                                                    );
                                                }
                                                return null;
                                            }}
                                        />
                                        <Legend />
                                        <Bar dataKey="wmape" fill="#8884d8" name="WMAPE准确度" />
                                        <Bar dataKey="direction" fill="#ffc658" name="方向准确度" />
                                    </BarChart>
                                </ResponsiveContainer>
                            )}
                        </Box>
                    </Paper>
                )}

                {/* 详细数据表格 */}
                {(!loading || accuracyStats) && accuracyStats && (
                    <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            每日准确度明细
                        </Typography>

                        <TableContainer sx={{ overflowX: 'auto' }}>
                            <Table
                                sx={{
                                    '& .MuiTableCell-root': {
                                        fontSize: { xs: '0.75rem', sm: '0.875rem' },
                                        px: { xs: 0.5, sm: 2 },
                                    }
                                }}
                            >
                                <TableHead>
                                    <TableRow>
                                        <TableCell>日期</TableCell>
                                        <TableCell align="right">WMAPE准确度</TableCell>
                                        <TableCell align="right">MAE (元/MWh)</TableCell>
                                        <TableCell align="right">RMSE (元/MWh)</TableCell>
                                        <TableCell align="right">MAPE (%)</TableCell>
                                        <TableCell align="right">方向准确度 (%)</TableCell>
                                    </TableRow>
                                </TableHead>
                                <TableBody>
                                    {accuracyStats.records.map((record) => (
                                        <TableRow
                                            key={record.target_date}
                                            sx={{
                                                backgroundColor: record.wmape_accuracy >= 90 ? 'success.50' : 'inherit'
                                            }}
                                        >
                                            <TableCell>{format(new Date(record.target_date), 'yyyy-MM-dd')}</TableCell>
                                            <TableCell align="right">{record.wmape_accuracy.toFixed(1)}%</TableCell>
                                            <TableCell align="right">{record.mae.toFixed(2)}</TableCell>
                                            <TableCell align="right">{record.rmse.toFixed(2)}</TableCell>
                                            <TableCell align="right">{record.mape.toFixed(2)}</TableCell>
                                            <TableCell align="right">{record.direction_accuracy.toFixed(1)}%</TableCell>
                                        </TableRow>
                                    ))}
                                </TableBody>
                            </Table>
                        </TableContainer>
                    </Paper>
                )}
            </Box>
        </LocalizationProvider>
    );
};
