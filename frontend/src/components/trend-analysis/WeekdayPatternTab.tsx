import React, { useRef } from 'react';
import {
    Box,
    Typography,
    Paper,
    CircularProgress,
    Alert,
    Grid,
    Card,
    CardContent,
    useTheme,
    useMediaQuery
} from '@mui/material';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    ResponsiveContainer,
    Legend,
    ErrorBar,
    Cell
} from 'recharts';
import { useChartFullscreen } from '../../hooks/useChartFullscreen';

interface WeekdayData {
    weekday: number;
    weekday_name: string;
    stats: {
        min: number;
        q1: number;
        median: number;
        q3: number;
        max: number;
    };
    outliers: number[];
}

interface WeekdayPatternData {
    distribution: WeekdayData[];
    heatmap_data: any[];
}

interface WeekdayPatternTabProps {
    data: WeekdayPatternData | null;
    loading: boolean;
    error: string | null;
}

export const WeekdayPatternTab: React.FC<WeekdayPatternTabProps> = ({
    data,
    loading,
    error
}) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const chartRef = useRef<HTMLDivElement>(null);

    // 全屏功能
    const {
        isFullscreen,
        FullscreenEnterButton,
        FullscreenExitButton,
        FullscreenTitle
    } = useChartFullscreen({
        chartRef,
        title: '周内价格分布（箱线图）'
    });

    // 准备图表数据
    const chartData = data?.distribution?.map((item) => ({
        name: item.weekday_name,
        median: item.stats.median,
        min: item.stats.min,
        max: item.stats.max,
        error: [item.stats.min, item.stats.max]
    })) || [];

    // 首次加载或错误状态
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

    if (!data || chartData.length === 0) {
        return (
            <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                <Typography color="text.secondary">无数据</Typography>
            </Box>
        );
    }

    // 计算Y轴范围
    const allValues = chartData.flatMap(d => [d.min, d.median, d.max]);
    const yMin = Math.min(...allValues) * 0.95;
    const yMax = Math.max(...allValues) * 1.05;

    // 自定义Tooltip
    const CustomTooltip = ({ active, payload }: any) => {
        if (active && payload && payload.length) {
            const data = payload[0].payload;
            // 从原始数据中获取完整的统计信息
            const originalData = data?.distribution?.find((d: any) => d.weekday_name === data.name);

            return (
                <Paper sx={{ p: 1.5, bgcolor: 'background.paper' }}>
                    <Typography variant="subtitle2" gutterBottom>
                        {data.name}
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        中位数: {data.median.toFixed(2)} 元/MWh
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        最小值: {data.min.toFixed(2)} 元/MWh
                    </Typography>
                    <Typography variant="body2" color="text.secondary">
                        最大值: {data.max.toFixed(2)} 元/MWh
                    </Typography>
                    {originalData && (
                        <>
                            <Typography variant="body2" color="text.secondary">
                                Q1: {originalData.stats.q1.toFixed(2)} 元/MWh
                            </Typography>
                            <Typography variant="body2" color="text.secondary">
                                Q3: {originalData.stats.q3.toFixed(2)} 元/MWh
                            </Typography>
                        </>
                    )}
                </Paper>
            );
        }
        return null;
    };

    return (
        <Box>
            {/* 标题卡片 */}
            <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                <Typography variant="h6">
                    周内特性分析
                </Typography>
                <Typography variant="body2" color="text.secondary" sx={{ mt: 1 }}>
                    展示一周七天的实时价格分布情况，帮助识别不同工作日与周末的价格模式
                </Typography>
            </Paper>

            {/* 箱线图 */}
            <Paper variant="outlined" sx={{ p: 2 }}>
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

                    <ResponsiveContainer width="100%" height="100%">
                        <BarChart
                            data={chartData}
                            margin={{ top: 20, right: 30, left: 20, bottom: 20 }}
                        >
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis
                                dataKey="name"
                                tick={{ fontSize: isMobile ? 10 : 12 }}
                                interval={0}
                            />
                            <YAxis
                                domain={[yMin, yMax]}
                                tick={{ fontSize: isMobile ? 10 : 12 }}
                                label={{ value: '价格 (元/MWh)', angle: -90, position: 'insideLeft' }}
                            />
                            <Tooltip content={<CustomTooltip />} />
                            <Legend />

                            {/* 中位数柱状图 */}
                            <Bar
                                dataKey="median"
                                fill={theme.palette.primary.main}
                                name="中位数价格"
                                barSize={40}
                            >
                                {chartData.map((entry, index) => (
                                    <Cell
                                        key={`cell-${index}`}
                                        fill={index % 2 === 0 ? theme.palette.primary.main : theme.palette.primary.dark}
                                    />
                                ))}
                                {/* 误差线（最小值到最大值） */}
                                <ErrorBar
                                    dataKey="error"
                                    width={0}
                                    strokeWidth={2}
                                    stroke={theme.palette.error.main}
                                    direction="y"
                                />
                            </Bar>
                        </BarChart>
                    </ResponsiveContainer>
                </Box>
            </Paper>

            {/* 统计摘要 */}
            <Grid container spacing={2} sx={{ mt: 2 }}>
                {data?.distribution?.map((item) => (
                    <Grid size={{ xs: 12, sm: 6, md: 3 }} key={item.weekday_name}>
                        <Card variant="outlined">
                            <CardContent>
                                <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                    {item.weekday_name}
                                </Typography>
                                <Typography variant="h6">
                                    {item.stats.median.toFixed(2)}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                    中位数 (元/MWh)
                                </Typography>
                                <Box sx={{ mt: 1, display: 'flex', justifyContent: 'space-between', fontSize: '0.75rem' }}>
                                    <span>范围: {item.stats.min.toFixed(0)}-{item.stats.max.toFixed(0)}</span>
                                    <span>IQR: {(item.stats.q3 - item.stats.q1).toFixed(0)}</span>
                                </Box>
                            </CardContent>
                        </Card>
                    </Grid>
                ))}
            </Grid>
        </Box>
    );
};
