import React, { useRef } from 'react';
import {
    Box,
    CircularProgress,
    Typography,
    Alert,
} from '@mui/material';
import {
    ResponsiveContainer,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    Area,
    AreaChart,
    ComposedChart,
    BarChart,
    Bar,
    ReferenceLine,
} from 'recharts';
import { useChartFullscreen } from '../hooks/useChartFullscreen';

interface ChartDataPoint {
    date: string;
    day: number;
    price_max: number;
    price_min: number;
    price_mean: number;
    price_peak: number;
    price_valley: number;
    price_spread: number;
    confidence_80_lower?: number;
    confidence_80_upper?: number;
    confidence_90_lower?: number;
    confidence_90_upper?: number;
    actual_mean?: number;
    actual_max?: number;
    actual_min?: number;
    actual_spread?: number;
}

interface ChartData {
    forecast_id: string;
    target_month: {
        year: number;
        month: number;
    };
    chart_type: string;
    data: ChartDataPoint[];
    has_actual: boolean;
    last_month_avg?: number;
}

interface MonthlyForecastChartProps {
    data: ChartData | null;
    loading: boolean;
}

export const MonthlyForecastChart: React.FC<MonthlyForecastChartProps> = ({
    data,
    loading,
}) => {
    const chartRef = useRef<HTMLDivElement>(null);

    const { isFullscreen, FullscreenEnterButton, FullscreenExitButton, FullscreenTitle } =
        useChartFullscreen({
            chartRef,
            title: data ? `月度价格预测 - ${data.target_month.year}年${data.target_month.month}月` : '月度价格预测',
        });

    if (loading && !data) {
        return (
            <Box
                display="flex"
                justifyContent="center"
                alignItems="center"
                minHeight={500}
            >
                <CircularProgress />
            </Box>
        );
    }

    if (!data || data.data.length === 0) {
        return (
            <Box
                display="flex"
                justifyContent="center"
                alignItems="center"
                minHeight={500}
            >
                <Typography color="text.secondary">暂无数据</Typography>
            </Box>
        );
    }

    // 根据图表类型渲染不同的图表
    const renderChart = () => {
        switch (data.chart_type) {
            case 'mean_trend':
                return renderMeanTrendChart();
            case 'price_spread':
                return renderPriceSpreadChart();
            case 'peak_valley':
                return renderPeakValleyChart();
            default:
                return renderMeanTrendChart();
        }
    };

    // 均价趋势图
    const renderMeanTrendChart = () => (
        <ComposedChart
            data={data.data}
            margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
        >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
                dataKey="day"
                tickFormatter={(value) => `${value}日`}
                angle={-45}
                textAnchor="end"
                height={80}
                interval={0}
                tick={{ fontSize: 12 }}
            />
            <YAxis
                label={{ value: '价格 (元/MWh)', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip
                content={(props) => {
                    if (props.active && props.payload && props.payload.length > 0) {
                        const point = props.payload[0].payload;
                        return (
                            <Box
                                sx={{
                                    bgcolor: 'background.paper',
                                    p: 1.5,
                                    border: '1px solid',
                                    borderColor: 'divider',
                                    borderRadius: 1
                                }}
                            >
                                <Typography variant="body2" gutterBottom>
                                    日期: {point.date}
                                </Typography>
                                <Typography variant="body2" sx={{ color: '#8884d8' }}>
                                    预测均价: {point.price_mean.toFixed(2)} 元/MWh
                                </Typography>
                                {point.actual_mean !== undefined && point.actual_mean !== null && (
                                    <>
                                        <Typography variant="body2" sx={{ color: '#ff7300' }}>
                                            实际均价: {point.actual_mean.toFixed(2)} 元/MWh
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            误差: {(point.actual_mean - point.price_mean).toFixed(2)} 元/MWh
                                        </Typography>
                                    </>
                                )}
                                {point.confidence_80_lower !== undefined && (
                                    <Typography variant="caption" color="text.secondary" display="block">
                                        80% 置信区间: [{point.confidence_80_lower.toFixed(2)}, {point.confidence_80_upper.toFixed(2)}]
                                    </Typography>
                                )}
                            </Box>
                        );
                    }
                    return null;
                }}
            />
            <Legend />

            {/* 上月均价参考线 */}
            {data.last_month_avg && (
                <ReferenceLine
                    y={data.last_month_avg}
                    stroke="#999"
                    strokeDasharray="5 5"
                    label={{ value: `上月均价: ${data.last_month_avg.toFixed(0)}`, position: 'right' }}
                />
            )}

            {/* 置信区间 */}
            {data.data.some(p => p.confidence_80_lower !== undefined && p.confidence_80_upper !== undefined) && (
                <>
                    <Area
                        type="monotone"
                        dataKey="confidence_80_upper"
                        stroke="#82ca9d"
                        strokeWidth={0}
                        fill="#82ca9d"
                        fillOpacity={0.2}
                        name="80%置信区间"
                    />
                    <Area
                        type="monotone"
                        dataKey="confidence_80_lower"
                        stroke="#82ca9d"
                        strokeWidth={0}
                        fill="#82ca9d"
                        fillOpacity={0.2}
                    />
                </>
            )}

            {/* 预测均价曲线 */}
            <Line
                type="monotone"
                dataKey="price_mean"
                stroke="#8884d8"
                strokeWidth={2}
                dot={false}
                name="预测均价"
            />

            {/* 实际均价曲线 */}
            {data.has_actual && (
                <Line
                    type="monotone"
                    dataKey="actual_mean"
                    stroke="#ff7300"
                    strokeWidth={2}
                    dot={false}
                    name="实际均价"
                    connectNulls={false}
                />
            )}
        </ComposedChart>
    );

    // 日内价差图
    const renderPriceSpreadChart = () => (
        <ComposedChart
            data={data.data}
            margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
        >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
                dataKey="day"
                tickFormatter={(value) => `${value}日`}
                angle={-45}
                textAnchor="end"
                height={80}
                interval={0}
                tick={{ fontSize: 12 }}
            />
            <YAxis
                label={{ value: '价差 (元/MWh)', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip
                content={(props) => {
                    if (props.active && props.payload && props.payload.length > 0) {
                        const point = props.payload[0].payload;
                        return (
                            <Box
                                sx={{
                                    bgcolor: 'background.paper',
                                    p: 1.5,
                                    border: '1px solid',
                                    borderColor: 'divider',
                                    borderRadius: 1
                                }}
                            >
                                <Typography variant="body2" gutterBottom>
                                    日期: {point.date}
                                </Typography>
                                <Typography variant="body2" sx={{ color: '#8884d8' }}>
                                    预测价差: {point.price_spread.toFixed(2)} 元/MWh
                                </Typography>
                                {point.actual_spread !== undefined && point.actual_spread !== null && (
                                    <>
                                        <Typography variant="body2" sx={{ color: '#ff7300' }}>
                                            实际价差: {point.actual_spread.toFixed(2)} 元/MWh
                                        </Typography>
                                        <Typography variant="caption" color="text.secondary">
                                            误差: {(point.actual_spread - point.price_spread).toFixed(2)} 元/MWh
                                        </Typography>
                                    </>
                                )}
                            </Box>
                        );
                    }
                    return null;
                }}
            />
            <Legend />

            {/* 预测价差柱状图 */}
            <Bar
                dataKey="price_spread"
                fill="#8884d8"
                name="预测价差"
                opacity={0.8}
            />

            {/* 实际价差折线 */}
            {data.has_actual && (
                <Line
                    type="monotone"
                    dataKey="actual_spread"
                    stroke="#ff7300"
                    strokeWidth={2}
                    dot={false}
                    name="实际价差"
                    connectNulls={false}
                />
            )}
        </ComposedChart>
    );

    // 峰谷价格图
    const renderPeakValleyChart = () => (
        <ComposedChart
            data={data.data}
            margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
        >
            <CartesianGrid strokeDasharray="3 3" />
            <XAxis
                dataKey="day"
                tickFormatter={(value) => `${value}日`}
                angle={-45}
                textAnchor="end"
                height={80}
                interval={0}
                tick={{ fontSize: 12 }}
            />
            <YAxis
                label={{ value: '价格 (元/MWh)', angle: -90, position: 'insideLeft' }}
            />
            <Tooltip
                content={(props) => {
                    if (props.active && props.payload && props.payload.length > 0) {
                        const point = props.payload[0].payload;
                        return (
                            <Box
                                sx={{
                                    bgcolor: 'background.paper',
                                    p: 1.5,
                                    border: '1px solid',
                                    borderColor: 'divider',
                                    borderRadius: 1
                                }}
                            >
                                <Typography variant="body2" gutterBottom>
                                    日期: {point.date}
                                </Typography>
                                <Typography variant="body2" sx={{ color: '#ff7300' }}>
                                    预测峰时: {point.price_peak.toFixed(2)} 元/MWh
                                </Typography>
                                <Typography variant="body2" sx={{ color: '#82ca9d' }}>
                                    预测谷时: {point.price_valley.toFixed(2)} 元/MWh
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                    峰谷价差: {(point.price_peak - point.price_valley).toFixed(2)} 元/MWh
                                </Typography>
                            </Box>
                        );
                    }
                    return null;
                }}
            />
            <Legend />

            {/* 峰时价格曲线 */}
            <Line
                type="monotone"
                dataKey="price_peak"
                stroke="#ff7300"
                strokeWidth={2}
                dot={false}
                name="预测峰时价格"
            />

            {/* 谷时价格曲线 */}
            <Line
                type="monotone"
                dataKey="price_valley"
                stroke="#82ca9d"
                strokeWidth={2}
                dot={false}
                name="预测谷时价格"
            />
        </ComposedChart>
    );

    return (
        <Box
            ref={chartRef}
            sx={{
                height: { xs: 350, sm: 500 },
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

            <ResponsiveContainer width="100%" height="100%">
                {renderChart()}
            </ResponsiveContainer>
        </Box>
    );
};
