import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import {
    Box, CircularProgress, Typography, Paper, Grid, Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    FormControl, FormLabel, RadioGroup, FormControlLabel, Radio
} from '@mui/material';
import { ComposedChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, Bar, ReferenceLine, Cell, LineChart } from 'recharts';
import apiClient from '../api/client';
import { format } from 'date-fns';
import { CustomTooltip } from './CustomTooltip';
import { useChartFullscreen } from '../hooks/useChartFullscreen';
import { useTouPeriodBackground } from '../hooks/useTouPeriodBackground';

// 偏差类型配置
const deviationTypeOptions = [
    { value: 'total_volume_deviation', label: '市场竞价空间偏差' },
    { value: 'system_load_deviation', label: '系统负荷偏差' },
    { value: 'renewable_deviation', label: '新能源偏差' },
    { value: 'nonmarket_unit_deviation', label: '非市场化机组偏差' },
    { value: 'tieline_deviation', label: '联络线偏差' }
];

// Custom Tooltip 内容组件
const CustomTooltipContent: React.FC<any> = ({ active, payload, label, unit }) => {
    if (active && payload && payload.length) {
        const periodType = payload[0].payload.period_type;
        return (
            <Paper sx={{ p: 1.5, backgroundColor: 'rgba(255, 255, 255, 0.95)', border: '1px solid #ccc', borderRadius: '4px' }}>
                <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
                    {periodType ? `时间: ${label} (${periodType})` : `时间: ${label}`}
                </Typography>
                {payload.map((pld: any) => (
                    <Typography key={pld.dataKey} variant="body2" sx={{ color: pld.color }}>
                        {`${pld.name}: ${Number(pld.value).toFixed(2)} ${unit}`}
                    </Typography>
                ))}
            </Paper>
        );
    }
    return null;
};

// 数据维度曲线图组件（支持多维度切换和鼠标同步）
const DataDimensionChart = React.memo<{
    data: any[];
    deviationType: string;
    dateStr: string;
    isFullscreen: boolean;
    FullscreenEnterButton: any;
    FullscreenExitButton: any;
    FullscreenTitle: any;
    chartRef: React.RefObject<HTMLDivElement | null>;
    syncedIndex: number | null;
    onMouseMove: (index: number | null) => void;
}>(({ data, deviationType, dateStr, isFullscreen, FullscreenEnterButton, FullscreenExitButton, FullscreenTitle, chartRef, syncedIndex, onMouseMove }) => {

    // 获取偏差类型的显示名称
    const deviationLabel = deviationTypeOptions.find(opt => opt.value === deviationType)?.label || '数据';

    // 使用 useMemo 缓存数据字段配置，避免每次渲染都创建新对象
    const dataKeys = useMemo(() => {
        switch (deviationType) {
            case 'total_volume_deviation':
                return { rtKey: 'volume_rt', daKey: 'volume_da', rtLabel: '实时竞价空间', daLabel: '日前竞价空间', unit: 'MW' };
            case 'system_load_deviation':
                return { rtKey: 'system_load_rt', daKey: 'system_load_da', rtLabel: '实时系统负荷', daLabel: '日前系统负荷', unit: 'MW' };
            case 'renewable_deviation':
                return { rtKey: 'renewable_rt', daKey: 'renewable_da', rtLabel: '实时新能源出力', daLabel: '日前新能源出力', unit: 'MW' };
            case 'nonmarket_unit_deviation':
                return { rtKey: 'nonmarket_unit_rt', daKey: 'nonmarket_unit_da', rtLabel: '实时非市场化机组', daLabel: '日前非市场化机组', unit: 'MW' };
            case 'tieline_deviation':
                return { rtKey: 'tieline_rt', daKey: 'tieline_da', rtLabel: '实时联络线', daLabel: '日前联络线', unit: 'MW' };
            default:
                return { rtKey: 'volume_rt', daKey: 'volume_da', rtLabel: '实时数据', daLabel: '日前数据', unit: 'MW' };
        }
    }, [deviationType]);

    const { rtKey, daKey, rtLabel, daLabel, unit } = dataKeys;

    // 使用 useMemo 缓存 Y 轴范围计算，只在 data 或 dataKeys 变化时重新计算
    const yAxisDomain = useMemo(() => {
        const values = data.flatMap(d => [d[rtKey], d[daKey]].filter(v => v !== null && v !== undefined));
        const minValue = values.length > 0 ? Math.min(...values) : 0;
        const maxValue = values.length > 0 ? Math.max(...values) : 0;
        return [Math.floor(minValue * 0.9), Math.ceil(maxValue * 1.1)];
    }, [data, rtKey, daKey]);

    const { TouPeriodAreas } = useTouPeriodBackground(data);

    // 使用 useCallback 缓存鼠标事件处理函数，避免每次渲染都创建新函数
    const handleMouseMove = useCallback((state: any) => {
        if (state && state.isTooltipActive && state.activeTooltipIndex !== undefined) {
            onMouseMove(state.activeTooltipIndex);
        }
    }, [onMouseMove]);

    const handleMouseLeave = useCallback(() => {
        onMouseMove(null);
    }, [onMouseMove]);

    return (
        <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
            <Typography variant="h6" gutterBottom>
                {deviationLabel}曲线对比
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

                {!data || data.length === 0 ? (
                    <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
                        <Typography>无数据</Typography>
                    </Box>
                ) : (
                    <ResponsiveContainer width="100%" height="100%">
                        <LineChart
                            data={data}
                            margin={{ top: 5, right: 30, left: 20, bottom: 5 }}
                            onMouseMove={handleMouseMove}
                            onMouseLeave={handleMouseLeave}
                        >
                            {TouPeriodAreas}
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis
                                dataKey="time_str"
                                tick={{ fontSize: 12 }}
                                interval={11}
                            />
                            <YAxis
                                domain={yAxisDomain}
                                label={{
                                    value: `${unit}`,
                                    angle: -90,
                                    position: 'insideLeft'
                                }}
                                tick={{ fontSize: 12 }}
                                tickFormatter={(value) => value.toFixed(0)}
                            />
                            <Tooltip content={<CustomTooltipContent unit={unit} />} />
                            <Legend />

                            {/* 同步的参考线 */}
                            {syncedIndex !== null && data[syncedIndex] && (
                                <ReferenceLine
                                    x={data[syncedIndex].time_str}
                                    stroke="rgba(0, 0, 0, 0.3)"
                                    strokeWidth={2}
                                    strokeDasharray="5 5"
                                />
                            )}

                            <Line
                                type="monotone"
                                dataKey={rtKey}
                                stroke="#ff9800"
                                strokeWidth={2}
                                name={rtLabel}
                                dot={false}
                            />
                            <Line
                                type="monotone"
                                dataKey={daKey}
                                stroke="#4caf50"
                                strokeWidth={2}
                                strokeDasharray="5 5"
                                name={daLabel}
                                dot={false}
                            />
                        </LineChart>
                    </ResponsiveContainer>
                )}
            </Box>
        </Paper>
    );
}, (prevProps, nextProps) => {
    // 自定义比较函数：只在关键 props 变化时才重新渲染
    // syncedIndex 变化时仍然需要重新渲染以更新参考线
    return (
        prevProps.data === nextProps.data &&
        prevProps.deviationType === nextProps.deviationType &&
        prevProps.dateStr === nextProps.dateStr &&
        prevProps.isFullscreen === nextProps.isFullscreen &&
        prevProps.syncedIndex === nextProps.syncedIndex
    );
});

interface SpreadAnalysisTabProps {
    selectedDate: Date | null;
}

export const SpreadAnalysisTab: React.FC<SpreadAnalysisTabProps> = ({ selectedDate }) => {
    const [selectedDeviationType, setSelectedDeviationType] = useState<string>('total_volume_deviation');
    const [loading, setLoading] = useState(false);
    const [analysisData, setAnalysisData] = useState<{ time_series: any[], systematic_bias: any[], price_distribution: any[] }>({
        time_series: [],
        systematic_bias: [],
        price_distribution: []
    });
    const [marketData, setMarketData] = useState<any[]>([]);

    // 同步鼠标悬停状态
    const [syncedIndex, setSyncedIndex] = useState<number | null>(null);

    // 数据缓存
    const [cachedDate, setCachedDate] = useState<string | null>(null);
    const [cachedData, setCachedData] = useState<{ time_series: any[], systematic_bias: any[], price_distribution: any[] } | null>(null);
    const [cachedMarketDate, setCachedMarketDate] = useState<string | null>(null);
    const [cachedMarketData, setCachedMarketData] = useState<any[] | null>(null);

    const [priceSpreadDomain, setPriceSpreadDomain] = useState<[number, number] | undefined>(undefined);
    const [deviationDomain, setDeviationDomain] = useState<[number, number] | undefined>(undefined);

    const chart3Ref = useRef<HTMLDivElement>(null);
    const chart4Ref = useRef<HTMLDivElement>(null);

    const dateStr = selectedDate ? format(selectedDate, 'yyyy-MM-dd') : '';

    const { isFullscreen: isFs3, FullscreenEnterButton: FSEnter3, FullscreenExitButton: FSExit3, FullscreenTitle: FSTitle3, NavigationButtons: FSNav3 } = useChartFullscreen({ chartRef: chart3Ref, title: `核心偏差归因 (${dateStr})` });
    const { isFullscreen: isFs4, FullscreenEnterButton: FSEnter4, FullscreenExitButton: FSExit4, FullscreenTitle: FSTitle4 } = useChartFullscreen({ chartRef: chart4Ref, title: `${deviationTypeOptions.find(opt => opt.value === selectedDeviationType)?.label} (${dateStr})` });

    useEffect(() => {
        if (!selectedDate) return;

        const formattedDate = format(selectedDate, 'yyyy-MM-dd');

        // 检查缓存
        if (cachedDate === formattedDate && cachedData) {
            console.log('使用缓存的价差归因数据:', formattedDate, '数据点数量:', cachedData.time_series?.length);
            setAnalysisData(cachedData);
            return;
        }

        console.log('加载价差归因数据:', formattedDate);
        setLoading(true);
        apiClient.get(`/api/v1/market-analysis/spread-attribution?date=${formattedDate}`)
            .then(response => {
                console.log('价差归因数据加载成功:', formattedDate, '数据点数量:', response.data.time_series?.length);
                setAnalysisData(response.data);
                // 更新缓存
                setCachedDate(formattedDate);
                setCachedData(response.data);
            })
            .catch(error => {
                console.error('Error fetching spread analysis data:', error);
                setAnalysisData({ time_series: [], systematic_bias: [], price_distribution: [] });
            })
            .finally(() => setLoading(false));
    }, [selectedDate]); // 移除 cachedDate 和 cachedData 依赖，避免无限循环

    // 获取市场数据
    useEffect(() => {
        if (!selectedDate) return;

        const fetchMarketData = async () => {
            const formattedDate = format(selectedDate, 'yyyy-MM-dd');

            // 检查缓存
            if (cachedMarketDate === formattedDate && cachedMarketData) {
                console.log('使用缓存的市场数据:', formattedDate, '数据点数量:', cachedMarketData?.length);
                setMarketData(cachedMarketData);
                return;
            }

            console.log('加载市场数据:', formattedDate);
            try {
                const response = await apiClient.get('/api/v1/market-analysis/dashboard', {
                    params: { date_str: formattedDate }
                });
                console.log('市场数据加载成功:', formattedDate, '数据点数量:', response.data.time_series?.length);
                setMarketData(response.data.time_series || []);
                // 更新缓存
                setCachedMarketDate(formattedDate);
                setCachedMarketData(response.data.time_series || []);
            } catch (err) {
                console.error('Error fetching market data:', err);
                setMarketData([]);
            }
        };

        fetchMarketData();
    }, [selectedDate]); // 移除 cachedMarketDate 和 cachedMarketData 依赖，避免无限循环

    useEffect(() => {
        if (analysisData.time_series.length > 0) {
            let maxPriceSpreadAbs = 0;
            let maxDeviationAbs = 0;

            analysisData.time_series.forEach(entry => {
                if (entry.price_spread !== null && entry.price_spread !== undefined) {
                    maxPriceSpreadAbs = Math.max(maxPriceSpreadAbs, Math.abs(entry.price_spread));
                }
                // 根据选中的偏差类型计算最大值
                const deviationValue = entry[selectedDeviationType as keyof typeof entry];
                if (deviationValue !== null && deviationValue !== undefined && typeof deviationValue === 'number') {
                    maxDeviationAbs = Math.max(maxDeviationAbs, Math.abs(deviationValue));
                }
            });

            // Set a minimum domain extent to avoid axis collapsing if all values are zero
            const priceSpreadExtent = Math.max(maxPriceSpreadAbs * 1.1, 10); // Ensure at least +/-10
            setPriceSpreadDomain([-priceSpreadExtent, priceSpreadExtent]);

            const deviationExtent = Math.max(maxDeviationAbs * 1.1, 10); // Ensure at least +/-10
            setDeviationDomain([-deviationExtent, deviationExtent]);

        } else {
            setPriceSpreadDomain(undefined);
            setDeviationDomain(undefined);
        }
    }, [analysisData.time_series, selectedDeviationType]);

    const renderTableCell = (value: number | null) => {
        if (value === null || value === undefined) return <TableCell align="right">N/A</TableCell>;
        const color = value > 0 ? 'error.main' : value < 0 ? 'success.main' : 'text.primary';
        return <TableCell align="right" sx={{ color, fontWeight: 'bold' }}>{value.toFixed(2)}</TableCell>;
    };

    return (
        <Box>
            <Paper variant="outlined" sx={{ p: 2, mb: 2, background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)', color: 'white', borderRadius: 2, boxShadow: '0 4px 20px rgba(102, 126, 234, 0.3)' }}>
                <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1.5 }}>
                    <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box component="span" sx={{ bgcolor: 'rgba(255,255,255,0.2)', px: 1, py: 0.5, borderRadius: 1, fontWeight: 'bold' }}>价差含义</Box>
                        绿色表示日前价格高于实时价格(负价差)
                    </Typography>
                    <Typography variant="body2" sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                        <Box component="span" sx={{ bgcolor: 'rgba(255,255,255,0.2)', px: 1, py: 0.5, borderRadius: 1, fontWeight: 'bold' }}>售电侧策略</Box>
                        负价差意味着实时市场价格偏低,建议少报日前,赚取价差收益
                    </Typography>
                </Box>
            </Paper>

            {/* 核心偏差归因图表 */}
            <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
                <Typography variant="h6" gutterBottom>核心偏差归因</Typography>

                {/* 偏差类型选择器 */}
                <Box sx={{ mb: 2 }}>
                    <FormControl component="fieldset">
                        <FormLabel component="legend">选择偏差维度</FormLabel>
                        <RadioGroup
                            row
                            value={selectedDeviationType}
                            onChange={(e) => setSelectedDeviationType(e.target.value)}
                            sx={{ flexWrap: { xs: 'wrap', sm: 'nowrap' } }}
                        >
                            {deviationTypeOptions.map(option => (
                                <FormControlLabel
                                    key={option.value}
                                    value={option.value}
                                    control={<Radio />}
                                    label={option.label}
                                    sx={{ mr: { xs: 1, sm: 2 } }}
                                />
                            ))}
                        </RadioGroup>
                    </FormControl>
                </Box>

                {/* 图表容器 */}
                <Box
                    ref={chart3Ref}
                    sx={{
                        height: { xs: 350, sm: 400 },
                        position: 'relative',
                        backgroundColor: isFs3 ? 'background.paper' : 'transparent',
                        p: isFs3 ? 2 : 0,
                        ...(isFs3 && { position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', zIndex: 1400 })
                    }}
                >
                    {FSEnter3()}{FSExit3()}{FSTitle3()}{FSNav3()}
                    {loading ? (
                        <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}><CircularProgress /></Box>
                    ) : !analysisData.time_series || analysisData.time_series.length === 0 ? (
                        <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}><Typography>无数据</Typography></Box>
                    ) : (
                        <ResponsiveContainer width="100%" height="100%">
                            <ComposedChart
                                data={analysisData.time_series}
                                onMouseMove={(state: any) => {
                                    if (state && state.isTooltipActive && state.activeTooltipIndex !== undefined) {
                                        setSyncedIndex(state.activeTooltipIndex);
                                    }
                                }}
                                onMouseLeave={() => setSyncedIndex(null)}
                            >
                                <CartesianGrid strokeDasharray="3 3" />
                                <XAxis dataKey="time_str" interval={11} tick={{ fontSize: 12 }} />
                                <YAxis
                                    yAxisId="left"
                                    label={{ value: '价差(元/MWh)', angle: -90, position: 'insideLeft' }}
                                    tick={{ fontSize: 12 }}
                                    domain={priceSpreadDomain}
                                    tickFormatter={(value) => value.toFixed(1)}
                                />
                                <YAxis
                                    yAxisId="right"
                                    orientation="right"
                                    label={{ value: '偏差(MW)', angle: -90, position: 'insideRight' }}
                                    tick={{ fontSize: 12 }}
                                    domain={deviationDomain}
                                    tickFormatter={(value) => value.toFixed(0)}
                                />
                                <Tooltip content={<CustomTooltip unitMap={{ price_spread: '元/MWh' }} unit="MW" />} />
                                <Legend />
                                <ReferenceLine y={0} stroke="#000" yAxisId="left" />
                                <ReferenceLine y={0} stroke="#000" yAxisId="right" />

                                {/* 同步的参考线 */}
                                {syncedIndex !== null && analysisData.time_series[syncedIndex] && (
                                    <ReferenceLine
                                        x={analysisData.time_series[syncedIndex].time_str}
                                        stroke="rgba(0, 0, 0, 0.3)"
                                        strokeWidth={2}
                                        strokeDasharray="5 5"
                                    />
                                )}

                                <Bar yAxisId="left" dataKey="price_spread" name="价格偏差" barSize={20}>
                                    {(analysisData.time_series || []).map((entry, index) => (
                                        <Cell key={`cell-${index}`} fill={entry.price_spread > 0 ? 'rgba(244, 67, 54, 0.5)' : 'rgba(76, 175, 80, 0.5)'} />
                                    ))}
                                </Bar>
                                <Line
                                    yAxisId="right"
                                    type="monotone"
                                    dataKey={selectedDeviationType}
                                    name={deviationTypeOptions.find(opt => opt.value === selectedDeviationType)?.label}
                                    stroke="#FF8042"
                                    dot={false}
                                />
                            </ComposedChart>
                        </ResponsiveContainer>
                    )}
                </Box>
            </Paper>

            {/* 数据维度曲线对比图表（联动显示） */}
            <DataDimensionChart
                data={selectedDeviationType === 'total_volume_deviation' ? marketData : analysisData.time_series}
                deviationType={selectedDeviationType}
                dateStr={dateStr}
                isFullscreen={isFs4}
                FullscreenEnterButton={FSEnter4}
                FullscreenExitButton={FSExit4}
                FullscreenTitle={FSTitle4}
                chartRef={chart4Ref}
                syncedIndex={syncedIndex}
                onMouseMove={setSyncedIndex}
            />

            <Paper variant="outlined" sx={{ p: { xs: 1, sm: 2 }, mt: 2 }}>
                <Typography variant="h6" gutterBottom>系统性偏差分析</Typography>
                <TableContainer sx={{ overflowX: 'auto' }}>
                    <Table
                        size="small"
                        sx={{
                            '& .MuiTableCell-root': {
                                fontSize: { xs: '0.75rem', sm: '0.875rem' },
                                px: { xs: 0.5, sm: 2 },
                            }
                        }}
                    >
                        <TableHead>
                            <TableRow>
                                <TableCell>时段</TableCell>
                                <TableCell align="right">平均价差</TableCell>
                                <TableCell align="right">平均竞价空间偏差</TableCell>
                                <TableCell align="right">平均系统负荷偏差</TableCell>
                                <TableCell align="right">平均新能源偏差</TableCell>
                                <TableCell align="right">平均非市场化机组偏差</TableCell>
                                <TableCell align="right">平均联络线偏差</TableCell>
                            </TableRow>
                        </TableHead>
                        <TableBody>
                            {analysisData.systematic_bias.map((row) => (
                                <TableRow key={row.period_name}>
                                    <TableCell component="th" scope="row">{row.period_name}</TableCell>
                                    {renderTableCell(row.avg_price_spread)}
                                    {renderTableCell(row.avg_total_volume_deviation)}
                                    {renderTableCell(row.avg_system_load_deviation)}
                                    {renderTableCell(row.avg_renewable_deviation)}
                                    {renderTableCell(row.avg_nonmarket_unit_deviation)}
                                    {renderTableCell(row.avg_tieline_deviation)}
                                </TableRow>
                            ))}
                        </TableBody>
                    </Table>
                </TableContainer>
            </Paper>
        </Box>
    );
};