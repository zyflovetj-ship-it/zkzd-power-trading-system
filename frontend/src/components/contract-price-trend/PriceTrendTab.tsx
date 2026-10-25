/**
 * 中长期趋势分析 - 价格走势 Tab
 * 
 * 对比中长期合同价格与现货价格的趋势
 */
import React, { useRef, useMemo } from 'react';
import {
    Box, Paper, Typography, Grid,
    CircularProgress, Alert, useTheme, useMediaQuery
} from '@mui/material';
import {
    LineChart, Line, BarChart, Bar, XAxis, YAxis, CartesianGrid,
    Tooltip, Legend, ResponsiveContainer, ReferenceLine, Cell, ReferenceArea, ComposedChart
} from 'recharts';
import { useChartFullscreen } from '../../hooks/useChartFullscreen';
import { useSelectableSeries } from '../../hooks/useSelectableSeries';
import { ContractPriceTrendResponse } from '../../api/contractPriceTrend';

interface PriceTrendTabProps {
    data: ContractPriceTrendResponse | null;
    loading: boolean;
    error: string | null;
    spotBenchmark: 'day_ahead' | 'real_time';
}

// 趋势分析面板组件
const TrendSummaryPanel: React.FC<{
    stats: {
        slope: number;
        intercept: number;
        startPrice: number;
        endPrice: number;
        priceChange: number;
        priceChangePercent: number;
        avgSpread: number;
        positiveSpreadRatio: number;
        negativeSpreadRatio: number;
        maxSpread: number;
        minSpread: number;
    };
    spotBenchmark: 'day_ahead' | 'real_time';
}> = ({ stats, spotBenchmark }) => {
    const spotLabel = spotBenchmark === 'day_ahead' ? '日前' : '实时';

    // 趋势判断
    let trendText = "震荡";
    let trendColor = "text.secondary";
    if (stats.slope > 0.5) {
        trendText = "上涨趋势";
        trendColor = "error.main";
    } else if (stats.slope < -0.5) {
        trendText = "下跌趋势";
        trendColor = "success.main";
    }

    // 价差建议
    let spreadSuggestion = "";
    if (stats.avgSpread > 10) {
        spreadSuggestion = `中长期均价高于${spotLabel}，建议优化合同结构`;
    } else if (stats.avgSpread < -10) {
        spreadSuggestion = `中长期均价低于${spotLabel}，合同价格优势明显`;
    } else {
        spreadSuggestion = "中长期与现货价差较小";
    }

    return (
        <Paper
            variant="outlined"
            sx={{
                p: 2,
                mb: 2,
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                color: 'white',
                borderRadius: 2,
                boxShadow: '0 4px 20px rgba(102, 126, 234, 0.3)'
            }}
        >
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                {/* 趋势分析 */}
                <Typography variant="body2" sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, flexWrap: 'wrap' }}>
                    <Box component="span" sx={{ bgcolor: 'rgba(255,255,255,0.2)', px: 1, py: 0.5, borderRadius: 1, fontWeight: 'bold', flexShrink: 0 }}>
                        趋势分析
                    </Box>
                    <Box component="span">
                        中长期合同价格呈现
                        <Box component="span" sx={{ fontWeight: 'bold', mx: 0.5, color: '#fff' }}>{trendText}</Box>
                        (斜率: {stats.slope.toFixed(2)})，
                        区间涨跌幅 {stats.priceChange > 0 ? '+' : ''}{stats.priceChange.toFixed(2)} 元/MWh ({stats.priceChangePercent > 0 ? '+' : ''}{stats.priceChangePercent.toFixed(2)}%)
                    </Box>
                </Typography>

                {/* 价差分析 */}
                <Typography variant="body2" sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, flexWrap: 'wrap' }}>
                    <Box component="span" sx={{ bgcolor: 'rgba(255,255,255,0.2)', px: 1, py: 0.5, borderRadius: 1, fontWeight: 'bold', flexShrink: 0 }}>
                        价差分析
                    </Box>
                    <Box component="span">
                        平均价差 {stats.avgSpread.toFixed(2)} 元/MWh（中长期 - {spotLabel}），
                        正价差占比 {stats.positiveSpreadRatio.toFixed(1)}%，
                        负价差占比 {stats.negativeSpreadRatio.toFixed(1)}%。
                        最大价差 {stats.maxSpread.toFixed(2)}，最小价差 {stats.minSpread.toFixed(2)}。
                        <Box component="span" sx={{ fontWeight: 'bold', ml: 0.5, color: '#fff' }}>{spreadSuggestion}</Box>
                    </Box>
                </Typography>
            </Box>
        </Paper>
    );
};

// 辅助函数：渲染周末背景标记
const renderWeekendReferenceAreas = (data: any[]) => {
    if (!data || data.length === 0) return null;
    return data.map((entry, index) => {
        if (!entry.date) return null;
        const date = new Date(entry.date);
        const day = date.getDay();
        if (day === 0 || day === 6) {
            return (
                <ReferenceArea
                    key={`weekend-${index}`}
                    x1={entry.date}
                    x2={entry.date}
                    strokeOpacity={0}
                    fill="#e0e0e0"
                    fillOpacity={0.3}
                    ifOverflow="extendDomain"
                />
            );
        }
        return null;
    });
};

// 价差分布直方图组件
const PriceDistributionChart: React.FC<{ data: any[] }> = ({ data }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const chartRef = useRef<HTMLDivElement>(null);
    const { isFullscreen, FullscreenEnterButton, FullscreenExitButton, FullscreenTitle } = useChartFullscreen({
        chartRef,
        title: '价差分布直方图'
    });

    return (
        <Paper variant="outlined" sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>价差分布直方图</Typography>
            <Box ref={chartRef} sx={{
                height: { xs: 300, sm: 350 },
                position: 'relative',
                bgcolor: isFullscreen ? 'background.paper' : 'transparent',
                p: isFullscreen ? 2 : 0,
                ...(isFullscreen && { position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', zIndex: 1400 })
            }}>
                <FullscreenEnterButton />
                <FullscreenExitButton />
                <FullscreenTitle />
                <ResponsiveContainer>
                    <BarChart data={data}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis
                            dataKey="range"
                            tick={!isMobile ? { fontSize: 12 } : false}
                            interval={0}
                            angle={-45}
                            textAnchor="end"
                            height={isMobile ? 30 : 60}
                        />
                        <YAxis label={{ value: '天数', angle: -90, position: 'insideLeft' }} allowDecimals={false} />
                        <Tooltip />
                        <Bar dataKey="count" name="天数" fill="#8884d8">
                            {data.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={parseInt(entry.range) < 0 ? '#4caf50' : '#f44336'} />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </Box>
        </Paper>
    );
};

// 每日正负价差时段数图表组件
const DailySpreadCountChart: React.FC<{ data: any[] }> = ({ data }) => {
    const chartRef = useRef<HTMLDivElement>(null);
    const { isFullscreen, FullscreenEnterButton, FullscreenExitButton, FullscreenTitle } = useChartFullscreen({
        chartRef,
        title: '每日正负价差时段数'
    });

    return (
        <Paper variant="outlined" sx={{ p: 2, height: '100%' }}>
            <Typography variant="h6" gutterBottom>每日正负价差时段数</Typography>
            <Box ref={chartRef} sx={{
                height: { xs: 300, sm: 350 },
                position: 'relative',
                bgcolor: isFullscreen ? 'background.paper' : 'transparent',
                p: isFullscreen ? 2 : 0,
                ...(isFullscreen && { position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', zIndex: 1400 })
            }}>
                <FullscreenEnterButton />
                <FullscreenExitButton />
                <FullscreenTitle />
                <ResponsiveContainer>
                    <BarChart data={data} stackOffset="sign">
                        <CartesianGrid strokeDasharray="3 3" />
                        {renderWeekendReferenceAreas(data)}
                        <XAxis dataKey="date" />
                        <YAxis label={{ value: '时段数', angle: -90, position: 'insideLeft' }} />
                        <Tooltip
                            formatter={(value: number, name: string) => [Math.abs(value), name === 'positive_spread_count' ? '正价差时段数' : '负价差时段数']}
                        />
                        <Legend />
                        <ReferenceLine y={0} stroke="#000" />
                        <Bar dataKey="positive_spread_count" name="正价差时段数" fill="#d32f2f" stackId="stack" />
                        <Bar dataKey="negative_spread_count" name="负价差时段数" fill="#388e3c" stackId="stack">
                            {data.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill="#388e3c" />
                            ))}
                        </Bar>
                    </BarChart>
                </ResponsiveContainer>
            </Box>
        </Paper>
    );
};

export const PriceTrendTab: React.FC<PriceTrendTabProps> = ({ data, loading, error, spotBenchmark }) => {
    const theme = useTheme();
    const spotLabel = spotBenchmark === 'day_ahead' ? '日前' : '实时';

    // Derived values
    const chartHeight = { xs: 350, sm: 400 };

    // Refs for charts
    const priceChartRef = useRef<HTMLDivElement>(null);
    const spreadChartRef = useRef<HTMLDivElement>(null);

    // Fullscreen hooks
    const priceFullscreen = useChartFullscreen({ chartRef: priceChartRef, title: '日均价格趋势' });
    const spreadFullscreen = useChartFullscreen({ chartRef: spreadChartRef, title: '日均价差趋势' });

    // Series selection hooks
    const priceSeries = useSelectableSeries({ contract_vwap: true, spot_vwap: true, trend_line: true });

    // Calculate Trend Line and Stats
    const { chartData, stats, distributionData } = useMemo(() => {
        if (!data?.daily_trends) return { chartData: [], stats: null, distributionData: [] };
        const trends = [...data.daily_trends];

        // 1. Linear Regression on contract_vwap
        const points = trends
            .map((d: any, i: number) => ({ x: i, y: d.contract_vwap }))
            .filter(p => p.y !== null && p.y !== undefined);

        let slope = 0;
        let intercept = 0;

        if (points.length > 1) {
            const n = points.length;
            const sumX = points.reduce((acc, p) => acc + p.x, 0);
            const sumY = points.reduce((acc, p) => acc + p.y, 0);
            const sumXY = points.reduce((acc, p) => acc + p.x * p.y, 0);
            const sumXX = points.reduce((acc, p) => acc + p.x * p.x, 0);

            slope = (n * sumXY - sumX * sumY) / (n * sumXX - sumX * sumX);
            intercept = (sumY - slope * sumX) / n;

            // 给每个数据点添加趋势线值
            trends.forEach((d: any, i: number) => {
                d.trend_line = slope * i + intercept;
            });
        }

        // 2. Calculate Stats
        const startPrice = points.length > 0 ? (slope * 0 + intercept) : 0;
        const endPrice = points.length > 0 ? (slope * (points.length - 1) + intercept) : 0;
        const priceChange = endPrice - startPrice;
        const priceChangePercent = startPrice !== 0 ? (priceChange / startPrice) * 100 : 0;

        const statsObj = {
            slope, intercept, startPrice, endPrice, priceChange, priceChangePercent,
            avgSpread: data.spread_stats.avgSpread,
            positiveSpreadRatio: data.spread_stats.positiveSpreadRatio,
            negativeSpreadRatio: data.spread_stats.negativeSpreadRatio,
            maxSpread: data.spread_stats.maxSpread,
            minSpread: data.spread_stats.minSpread
        };

        // 3. Distribution Data
        const distributionData = data.spread_distribution || [];

        return {
            chartData: trends,
            stats: statsObj,
            distributionData
        };
    }, [data]);

    return (
        <Box>
            {/* Content Area */}
            {loading && !data ? (
                <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                    <CircularProgress />
                </Box>
            ) : error ? (
                <Alert severity="error">{error}</Alert>
            ) : data ? (
                <Box sx={{ position: 'relative' }}>
                    {/* Loading Overlay */}
                    {loading && (
                        <Box sx={{
                            position: 'absolute', top: 0, left: 0, right: 0, bottom: 0,
                            display: 'flex', alignItems: 'center', justifyContent: 'center',
                            backgroundColor: 'rgba(255, 255, 255, 0.7)', zIndex: 1000
                        }}>
                            <CircularProgress />
                        </Box>
                    )}

                    {/* Top: Trend Summary Panel */}
                    {stats && <TrendSummaryPanel stats={stats} spotBenchmark={spotBenchmark} />}

                    <Grid container spacing={{ xs: 1, sm: 2 }}>
                        {/* Row 1: Price Trend & Spread Trend */}
                        {/* Left: Price Trend */}
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Paper variant="outlined" sx={{ p: { xs: 1, sm: 2 } }}>
                                <Typography variant="h6" gutterBottom>日均价格趋势</Typography>
                                <Box ref={priceChartRef} sx={{
                                    height: chartHeight,
                                    position: 'relative',
                                    bgcolor: priceFullscreen.isFullscreen ? 'background.paper' : 'transparent',
                                    p: priceFullscreen.isFullscreen ? 2 : 0,
                                    ...(priceFullscreen.isFullscreen && { position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', zIndex: 1400 })
                                }}>
                                    <priceFullscreen.FullscreenEnterButton />
                                    <priceFullscreen.FullscreenExitButton />
                                    <priceFullscreen.FullscreenTitle />
                                    <ResponsiveContainer>
                                        <ComposedChart data={chartData}>
                                            <CartesianGrid strokeDasharray="3 3" />
                                            {renderWeekendReferenceAreas(chartData)}
                                            <XAxis dataKey="date" />
                                            <YAxis label={{ value: '元/MWh', angle: -90, position: 'insideLeft' }} />
                                            <Tooltip formatter={(value: number) => value?.toFixed(2)} />
                                            <Legend onClick={priceSeries.handleLegendClick} />
                                            <Line hide={!priceSeries.seriesVisibility.contract_vwap} type="monotone" dataKey="contract_vwap" name="中长期均价" stroke="#9c27b0" strokeWidth={2} dot={false} />
                                            <Line hide={!priceSeries.seriesVisibility.spot_vwap} type="monotone" dataKey="spot_vwap" name={`${spotLabel}均价`} stroke="#1976d2" strokeWidth={2} strokeDasharray="5 5" dot={false} />
                                            <Line hide={!priceSeries.seriesVisibility.trend_line} type="monotone" dataKey="trend_line" name="趋势线" stroke="#ff9800" strokeWidth={2} strokeDasharray="3 3" dot={false} />
                                        </ComposedChart>
                                    </ResponsiveContainer>
                                </Box>
                            </Paper>
                        </Grid>

                        {/* Right: Spread Trend */}
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Paper variant="outlined" sx={{ p: { xs: 1, sm: 2 }, height: '100%' }}>
                                <Typography variant="h6" gutterBottom>日均价差趋势（中长期 - {spotLabel}）</Typography>
                                <Box ref={spreadChartRef} sx={{
                                    height: { xs: 300, sm: 350 },
                                    position: 'relative',
                                    bgcolor: spreadFullscreen.isFullscreen ? 'background.paper' : 'transparent',
                                    p: spreadFullscreen.isFullscreen ? 2 : 0,
                                    ...(spreadFullscreen.isFullscreen && { position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', zIndex: 1400 })
                                }}>
                                    <spreadFullscreen.FullscreenEnterButton />
                                    <spreadFullscreen.FullscreenExitButton />
                                    <spreadFullscreen.FullscreenTitle />
                                    <ResponsiveContainer>
                                        <BarChart data={data.daily_trends}>
                                            <CartesianGrid strokeDasharray="3 3" />
                                            {renderWeekendReferenceAreas(data.daily_trends)}
                                            <XAxis dataKey="date" />
                                            <YAxis label={{ value: '元/MWh', angle: -90, position: 'insideLeft' }} />
                                            <Tooltip />
                                            <Legend />
                                            <ReferenceLine y={0} stroke="#000" />
                                            <Bar dataKey="vwap_spread" name="价差 (中长期-现货)">
                                                {data.daily_trends.map((entry: any, index: number) => (
                                                    <Cell key={`cell-${index}`} fill={entry.vwap_spread >= 0 ? '#d32f2f' : '#388e3c'} />
                                                ))}
                                            </Bar>
                                        </BarChart>
                                    </ResponsiveContainer>
                                </Box>
                            </Paper>
                        </Grid>

                        {/* Row 2: Daily Spread Count & Spread Distribution */}
                        {/* Left: Daily Spread Count */}
                        <Grid size={{ xs: 12, md: 6 }}>
                            <DailySpreadCountChart data={data.daily_trends.map((d: any) => ({
                                ...d,
                                negative_spread_count: -d.negative_spread_count // Convert to negative for display
                            }))} />
                        </Grid>

                        {/* Right: Spread Distribution */}
                        <Grid size={{ xs: 12, md: 6 }}>
                            <PriceDistributionChart data={distributionData} />
                        </Grid>
                    </Grid>
                </Box>
            ) : null}
        </Box>
    );
};
