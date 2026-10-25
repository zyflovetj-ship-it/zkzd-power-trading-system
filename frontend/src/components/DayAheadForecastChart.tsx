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
} from 'recharts';
import { useChartFullscreen } from '../hooks/useChartFullscreen';

interface ChartDataPoint {
    datetime: string;
    time: string;
    predicted: number;
    actual: number | null;
    error?: number;
    confidence_80_lower?: number;
    confidence_80_upper?: number;
    confidence_90_lower?: number;
    confidence_90_upper?: number;
}

interface ChartData {
    forecast_id: string;
    target_date: string;
    data: ChartDataPoint[];
    has_actual: boolean;
}

interface DayAheadForecastChartProps {
    data: ChartData | null;
    loading: boolean;
}

export const DayAheadForecastChart: React.FC<DayAheadForecastChartProps> = ({
    data,
    loading,
}) => {
    const chartRef = useRef<HTMLDivElement>(null);

    const { isFullscreen, FullscreenEnterButton, FullscreenExitButton, FullscreenTitle } =
        useChartFullscreen({
            chartRef,
            title: data ? `日前价格预测 - ${data.target_date}` : '日前价格预测',
        });

    if (loading && !data) {
        return (
            <Box
                display="flex"
                justifyContent="center"
                alignItems="center"
                minHeight={450}
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
                minHeight={450}
            >
                <Typography color="text.secondary">暂无数据</Typography>
            </Box>
        );
    }

    return (
        <Box
            ref={chartRef}
            sx={{
                height: { xs: 350, sm: 450 },
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
                <ComposedChart
                    data={data.data}
                    margin={{ top: 20, right: 30, left: 20, bottom: 60 }}
                >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                        dataKey="time"
                        angle={-45}
                        textAnchor="end"
                        height={80}
                        interval={3}
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
                                            时间: {point.time}
                                        </Typography>
                                        <Typography variant="body2" sx={{ color: '#8884d8' }}>
                                            预测: {point.predicted.toFixed(2)} 元/MWh
                                        </Typography>
                                        {point.actual !== null && point.actual !== undefined && (
                                            <>
                                                <Typography variant="body2" sx={{ color: '#ff7300' }}>
                                                    实际: {point.actual.toFixed(2)} 元/MWh
                                                </Typography>
                                                {point.error !== undefined && (
                                                    <Typography variant="caption" color="text.secondary">
                                                        误差: {point.error.toFixed(2)} 元/MWh
                                                    </Typography>
                                                )}
                                            </>
                                        )}
                                    </Box>
                                );
                            }
                            return null;
                        }}
                    />
                    <Legend />

                    {/* 置信区间 - 仅在有数据时显示 */}
                    {data.data.some(p => p.confidence_80_lower !== undefined && p.confidence_80_upper !== undefined) && (
                        <Area
                            type="monotone"
                            dataKey="confidence_80_upper"
                            stroke="#82ca9d"
                            strokeWidth={0}
                            fill="#82ca9d"
                            fillOpacity={0.2}
                            name="80%置信区间"
                        />
                    )}
                    {data.data.some(p => p.confidence_80_lower !== undefined && p.confidence_80_upper !== undefined) && (
                        <Area
                            type="monotone"
                            dataKey="confidence_80_lower"
                            stroke="#82ca9d"
                            strokeWidth={0}
                            fill="#82ca9d"
                            fillOpacity={0.2}
                        />
                    )}

                    {/* 预测价格曲线 */}
                    <Line
                        type="monotone"
                        dataKey="predicted"
                        stroke="#8884d8"
                        strokeWidth={2}
                        dot={false}
                        name="预测价格"
                    />

                    {/* 实际价格曲线 - 仅在有实际数据时显示 */}
                    {data.has_actual && (
                        <Line
                            type="monotone"
                            dataKey="actual"
                            stroke="#ff7300"
                            strokeWidth={2}
                            dot={false}
                            name="实际价格"
                            connectNulls={false}
                        />
                    )}
                </ComposedChart>
            </ResponsiveContainer>
        </Box>
    );
};
