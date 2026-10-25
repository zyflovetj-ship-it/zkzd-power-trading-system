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
    ReferenceLine,
} from 'recharts';
import apiClient from '../api/client';
import { useChartFullscreen } from '../hooks/useChartFullscreen';

// ============ 类型定义 ============
interface PriceForecastData {
    datetime: string;
    target_date: string;
    predicted_price: number;
    confidence_80_lower: number;
    confidence_80_upper: number;
    confidence_90_lower: number;
    confidence_90_upper: number;
}

interface ForecastBatch {
    forecast_id: string;
    forecast_date: string;
    target_dates: string[];
    data: PriceForecastData[];
}

// ============ 主组件 ============
export const D2ForecastCurveTab: React.FC = () => {
    const [forecastDate, setForecastDate] = useState<Date | null>(subDays(new Date(), 2)); // 默认D-2
    const [confidenceLevel, setConfidenceLevel] = useState<'80' | '90'>('80');
    const [forecastBatch, setForecastBatch] = useState<ForecastBatch | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const chartRef = useRef<HTMLDivElement>(null);
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('md'));

    // 全屏 Hook
    const { isFullscreen, FullscreenEnterButton, FullscreenExitButton, FullscreenTitle } =
        useChartFullscreen({
            chartRef,
            title: `D-2价格预测 - ${forecastDate ? format(forecastDate, 'yyyy-MM-dd') : ''}`,
        });

    // 加载预测数据
    useEffect(() => {
        if (forecastDate) {
            fetchForecastData(forecastDate);
        }
    }, [forecastDate]);

    const fetchForecastData = async (date: Date) => {
        setLoading(true);
        setError(null);
        const dateStr = format(date, 'yyyy-MM-dd');

        try {
            const response = await apiClient.get(`/api/v1/price-forecast/d2/by-date`, {
                params: { forecast_date: dateStr }
            });
            setForecastBatch(response.data);
        } catch (err: any) {
            console.error('加载预测数据失败:', err);
            setError(err.response?.data?.detail || err.message || '加载预测数据失败');
            setForecastBatch(null);
        } finally {
            setLoading(false);
        }
    };

    // 日期导航
    const shiftDate = (days: number) => {
        if (!forecastDate) return;
        const newDate = addDays(forecastDate, days);
        setForecastDate(newDate);
    };

    // 处理图表数据 - 连续排列所有天数
    const processChartData = () => {
        if (!forecastBatch || !forecastBatch.data) return { chartData: [], dayBoundaries: [], series: [] };

        // 按目标日期分组
        const dataByTargetDate: Record<string, PriceForecastData[]> = {};
        forecastBatch.data.forEach(point => {
            if (!dataByTargetDate[point.target_date]) {
                dataByTargetDate[point.target_date] = [];
            }
            dataByTargetDate[point.target_date].push(point);
        });

        const targetDates = Object.keys(dataByTargetDate).sort();
        // 只显示前5天的数据
        const displayDates = targetDates.slice(0, 5);

        // 预定义颜色
        const colors = ['#8884d8', '#82ca9d', '#ffc658', '#ff7300', '#0088fe'];

        // 创建连续的数据集，每天的价格存储在独立的字段中
        const chartData: any[] = [];
        const dayBoundaries: number[] = [];
        const series: Array<{ key: string; name: string; color: string; dataKey: string }> = [];

        let globalIndex = 0;

        displayDates.forEach((targetDate, dayIndex) => {
            const points = dataByTargetDate[targetDate];
            if (!points || points.length === 0) return;

            const dayName = format(new Date(targetDate), 'MM-dd');
            const dayKey = `day_${dayIndex}`;

            // 将这一天的所有点添加到chartData
            points.forEach((point, pointIndex) => {
                const timeLabel = format(new Date(point.datetime), 'HH:mm');
                // 每天的第一个点显示日期
                const label = pointIndex === 0 ? `${dayName}\n${timeLabel}` : timeLabel;

                // 创建新的记录（不查找已存在的）
                const record: any = {
                    index: globalIndex,
                    label,
                    time: timeLabel,
                };

                // 只添加这一天的价格数据到独立字段
                record[dayKey] = point.predicted_price;
                record[`${dayKey}_lower`] = confidenceLevel === '80' ? point.confidence_80_lower : point.confidence_90_lower;
                record[`${dayKey}_upper`] = confidenceLevel === '80' ? point.confidence_80_upper : point.confidence_90_upper;

                chartData.push(record);
                globalIndex++;
            });

            // 记录这一天的结束位置（用于分隔线）
            if (dayIndex < displayDates.length - 1) {
                dayBoundaries.push(globalIndex - 1);
            }

            // 记录这一天的信息
            series.push({
                key: dayKey,
                name: dayName,
                color: colors[dayIndex % colors.length],
                dataKey: dayKey
            });
        });

        return { chartData, dayBoundaries, series };
    };

    const { chartData, dayBoundaries, series } = processChartData();

    return (
        <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={zhCN}>
            <Box>
                {/* 日期选择器 */}
                <Paper variant="outlined" sx={{ p: 2, display: 'flex', gap: 1, alignItems: 'center', flexWrap: 'wrap' }}>
                    <Typography variant="body2" sx={{ mr: 1 }}>
                        预测执行日期:
                    </Typography>
                    <IconButton onClick={() => shiftDate(-1)} disabled={loading} size="small">
                        <ArrowLeftIcon />
                    </IconButton>
                    <DatePicker
                        value={forecastDate}
                        onChange={(date) => setForecastDate(date)}
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

                    <Box sx={{ flexGrow: 1 }} />

                    <FormControl size="small" sx={{ minWidth: 120 }}>
                        <InputLabel>置信区间</InputLabel>
                        <Select
                            value={confidenceLevel}
                            label="置信区间"
                            onChange={(e) => setConfidenceLevel(e.target.value as '80' | '90')}
                        >
                            <MenuItem value="80">80%</MenuItem>
                            <MenuItem value="90">90%</MenuItem>
                        </Select>
                    </FormControl>
                </Paper>

                {/* 首次加载显示完整的 loading */}
                {loading && !forecastBatch && !error && (
                    <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                        <CircularProgress />
                    </Box>
                )}

                {error && (
                    <Alert severity="error" sx={{ mt: 2 }}>
                        {error}
                    </Alert>
                )}

                {/* 图表容器 */}
                {(!loading || forecastBatch) && (
                    <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
                        <Typography variant="h6" gutterBottom>
                            D-2 价格预测曲线（未来5天）
                        </Typography>

                        {forecastBatch && (
                            <Typography variant="body2" color="text.secondary" gutterBottom>
                                预测批次: {forecastBatch.forecast_id} |
                                预测日期: {forecastBatch.forecast_date} |
                                目标日期: {forecastBatch.target_dates.slice(0, 5).join(', ')}
                            </Typography>
                        )}

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

                            {!chartData || chartData.length === 0 ? (
                                <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
                                    <Typography>暂无预测数据</Typography>
                                </Box>
                            ) : (
                                <ResponsiveContainer width="100%" height="100%">
                                    <LineChart
                                        data={chartData}
                                        margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
                                    >
                                        <CartesianGrid strokeDasharray="3 3" />
                                        <XAxis
                                            dataKey="index"
                                            interval={isMobile ? 47 : 23}
                                            angle={-45}
                                            textAnchor="end"
                                            height={80}
                                            tick={{ fontSize: isMobile ? 10 : 12 }}
                                            tickFormatter={(value) => {
                                                const point = chartData[value];
                                                return point ? point.label : value;
                                            }}
                                        />
                                        <YAxis
                                            label={{ value: '价格 (元/MWh)', angle: -90, position: 'insideLeft' }}
                                        />
                                        <Tooltip
                                            content={(props) => {
                                                if (props.active && props.payload && props.payload.length > 0) {
                                                    const data = props.payload[0].payload;
                                                    const entry = props.payload[0];

                                                    // 找到有值的日期和价格
                                                    let dayName = '';
                                                    let price = 0;
                                                    let lower = 0;
                                                    let upper = 0;

                                                    // 从series中找到对应的天
                                                    for (let i = 0; i < series.length; i++) {
                                                        const dayKey = series[i].dataKey;
                                                        if (data[dayKey] !== undefined) {
                                                            dayName = series[i].name;
                                                            price = data[dayKey];
                                                            lower = data[`${dayKey}_lower`] || 0;
                                                            upper = data[`${dayKey}_upper`] || 0;
                                                            break;
                                                        }
                                                    }

                                                    return (
                                                        <Paper sx={{ p: 1 }}>
                                                            <Typography variant="body2">
                                                                日期: {dayName}
                                                            </Typography>
                                                            <Typography variant="body2">
                                                                时间: {data.time}
                                                            </Typography>
                                                            <Typography variant="body2" sx={{ color: entry.color || 'primary.main' }}>
                                                                预测价格: {typeof price === 'number' ? price.toFixed(2) : price} 元/MWh
                                                            </Typography>
                                                            <Typography variant="caption" color="text.secondary">
                                                                置信区间: [{typeof lower === 'number' ? lower.toFixed(2) : lower}, {typeof upper === 'number' ? upper.toFixed(2) : upper}]
                                                            </Typography>
                                                        </Paper>
                                                    );
                                                }
                                                return null;
                                            }}
                                        />
                                        <Legend />

                                        {/* 绘制每天的垂直分隔线 */}
                                        {dayBoundaries.map((boundary, index) => (
                                            <ReferenceLine
                                                key={index}
                                                x={boundary}
                                                stroke="#999"
                                                strokeDasharray="5 5"
                                                strokeWidth={1.5}
                                            />
                                        ))}

                                        {/* 为每天绘制独立的线段 */}
                                        {series.map((s) => (
                                            <Line
                                                key={s.key}
                                                type="monotone"
                                                dataKey={s.dataKey}
                                                stroke={s.color}
                                                strokeWidth={2}
                                                dot={false}
                                                name={s.name}
                                                connectNulls={false}
                                            />
                                        ))}
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
