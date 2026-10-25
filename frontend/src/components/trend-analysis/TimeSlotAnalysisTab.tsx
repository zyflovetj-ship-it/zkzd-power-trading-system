import React, { useState, useEffect, useRef, useMemo } from 'react';
import {
    Box, Paper, Typography, Grid,
    CircularProgress, Alert, Table, TableBody, TableCell, TableContainer,
    TableHead, TableRow, TablePagination, TableSortLabel, Chip,
    LinearProgress, Button, Card, Stack, Select, MenuItem, FormControl,
    InputLabel, IconButton, useTheme, useMediaQuery
} from '@mui/material';
import {
    ComposedChart, Bar, XAxis, YAxis, CartesianGrid,
    Tooltip, Legend, ResponsiveContainer, ReferenceLine, ErrorBar, Line, Scatter, Customized, ReferenceArea
} from 'recharts';
import { useChartFullscreen } from '../../hooks/useChartFullscreen';
import DownloadIcon from '@mui/icons-material/Download';
import ArrowUpwardIcon from '@mui/icons-material/ArrowUpward';
import ArrowDownwardIcon from '@mui/icons-material/ArrowDownward';

interface TimeSlotAnalysisTabProps {
    data: TimeSlotAnalysisData | null;
    loading: boolean;
    error: string | null;
}

interface TimeSlotStats {
    timeslot: number;
    time_label: string;
    avg_price_rt: number;
    avg_price_da: number;
    std_price_rt: number;
    max_price_rt: number;
    min_price_rt: number;
    avg_spread: number;
    std_spread: number;
    positive_spread_ratio: number;
    negative_spread_ratio: number;
    max_spread: number;
    min_spread: number;
    consistency_score: number;
    recommended_strategy: string;
    confidence: string;
    risk_level: string;
    sample_size: number;
    recommendation_index: number;
    signal_strength: number;
}

interface BoxPlotDataPoint {
    timeslot: number;
    time_label: string;
    min: number;
    q1: number;
    median: number;
    q3: number;
    max: number;
    outliers: number[];
}

interface TimeSlotKPIs {
    high_consistency_count: number;
    avg_consistency: number;
    recommended_count: number;
    high_risk_count: number;
    top_consistency_timeslots: string[];
    top_risk_timeslots: string[];
}

interface TimeSlotAnalysisData {
    kpis: TimeSlotKPIs;
    timeslot_stats: TimeSlotStats[];
    box_plot_data: BoxPlotDataPoint[];
}

// 排序选项配置
const SORT_OPTIONS: { value: keyof TimeSlotStats; label: string }[] = [
    { value: 'timeslot', label: '时段顺序' },
    { value: 'recommendation_index', label: '推荐指数' },
    { value: 'avg_spread', label: '平均价差' },
    { value: 'consistency_score', label: '一致性评分' },
    { value: 'std_price_rt', label: '波动性' },
];

// 移动端卡片组件
interface TimeSlotCardProps {
    row: TimeSlotStats;
    getStrategyColor: (strategy: string) => "success" | "error" | "default";
    getRiskColor: (risk: string) => "success" | "warning" | "error";
}

const TimeSlotCard: React.FC<TimeSlotCardProps> = ({ row, getStrategyColor, getRiskColor }) => {
    const borderColor = row.avg_spread >= 0 ? '#f44336' : '#4caf50';

    return (
        <Card
            variant="outlined"
            sx={{
                p: 1.5,
                borderLeft: `4px solid ${borderColor}`,
                mb: 1.5
            }}
        >
            {/* 标题行 */}
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 1 }}>
                <Box sx={{ display: 'flex', alignItems: 'baseline', gap: 1 }}>
                    <Typography variant="body1" fontWeight="bold">
                        {row.time_label}
                    </Typography>
                    <Typography variant="caption" color="text.secondary">
                        #{row.timeslot}
                    </Typography>
                </Box>
                <Chip
                    label={row.recommended_strategy}
                    size="small"
                    color={getStrategyColor(row.recommended_strategy)}
                    sx={{ fontSize: '0.7rem' }}
                />
            </Box>

            {/* 核心指标区 (2x2 网格) */}
            <Grid container spacing={1}>
                {/* 左上: 平均价差 */}
                <Grid size={{ xs: 6 }}>
                    <Box sx={{ textAlign: 'center', py: 0.5 }}>
                        <Typography variant="caption" color="text.secondary" display="block">
                            平均价差
                        </Typography>
                        <Typography
                            variant="body2"
                            fontWeight="bold"
                            color={row.avg_spread >= 0 ? 'error.main' : 'success.main'}
                        >
                            {row.avg_spread >= 0 ? '+' : ''}{row.avg_spread.toFixed(2)}
                        </Typography>
                    </Box>
                </Grid>

                {/* 右上: 一致性评分 */}
                <Grid size={{ xs: 6 }}>
                    <Box sx={{ textAlign: 'center', py: 0.5 }}>
                        <Typography variant="caption" color="text.secondary" display="block">
                            一致性
                        </Typography>
                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 0.5 }}>
                            <LinearProgress
                                variant="determinate"
                                value={row.consistency_score * 100}
                                sx={{
                                    width: 40,
                                    height: 4,
                                    borderRadius: 2,
                                    bgcolor: 'grey.200',
                                    '& .MuiLinearProgress-bar': {
                                        bgcolor: row.consistency_score >= 0.7 ? 'success.main' : 'warning.main'
                                    }
                                }}
                            />
                            <Typography variant="body2" fontWeight="bold">
                                {(row.consistency_score * 100).toFixed(0)}%
                            </Typography>
                        </Box>
                    </Box>
                </Grid>

                {/* 左下: 风险等级 */}
                <Grid size={{ xs: 6 }}>
                    <Box sx={{ textAlign: 'center', py: 0.5 }}>
                        <Typography variant="caption" color="text.secondary" display="block">
                            风险等级
                        </Typography>
                        <Chip
                            label={row.risk_level}
                            size="small"
                            color={getRiskColor(row.risk_level)}
                            variant="outlined"
                            sx={{ fontSize: '0.65rem', height: 20 }}
                        />
                    </Box>
                </Grid>

                {/* 右下: 推荐指数 */}
                <Grid size={{ xs: 6 }}>
                    <Box sx={{ textAlign: 'center', py: 0.5 }}>
                        <Typography variant="caption" color="text.secondary" display="block">
                            推荐指数
                        </Typography>
                        <Box sx={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'center', gap: 0.5 }}>
                            {[1, 2, 3, 4, 5].map((i) => (
                                <Box
                                    key={i}
                                    sx={{
                                        width: 4,
                                        height: 6 + (i * 2),
                                        bgcolor: i <= row.signal_strength ? 'primary.main' : 'grey.300',
                                        borderRadius: 0.5
                                    }}
                                />
                            ))}
                            <Typography variant="body2" fontWeight="bold" sx={{ ml: 0.5 }}>
                                {row.recommendation_index.toFixed(1)}
                            </Typography>
                        </Box>
                    </Box>
                </Grid>
            </Grid>
        </Card>
    );
};

export const TimeSlotAnalysisTab: React.FC<TimeSlotAnalysisTabProps> = ({ data, loading, error }) => {
    // 响应式断点检测
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // 表格状态（桌面端）
    const [page, setPage] = useState(0);
    const [rowsPerPage, setRowsPerPage] = useState(25);
    const [orderBy, setOrderBy] = useState<keyof TimeSlotStats>('recommendation_index');
    const [order, setOrder] = useState<'asc' | 'desc'>('desc');

    // 移动端卡片列表状态
    const [visibleCount, setVisibleCount] = useState(10);

    // 动画控制状态
    const [chartData, setChartData] = useState<BoxPlotDataPoint[]>([]);

    // 监听 data 变化，强制触发重绘动画
    useEffect(() => {
        if (data?.box_plot_data) {
            // 先置空，利用 setTimeout 触发 Recharts 的 update 动画
            setChartData([]);
            const timer = setTimeout(() => {
                setChartData(data.box_plot_data);
            }, 50);
            return () => clearTimeout(timer);
        } else {
            setChartData([]);
        }
    }, [data]);

    // Ref for chart
    const chartRef = useRef<HTMLDivElement>(null);
    const { isFullscreen, FullscreenEnterButton, FullscreenExitButton, FullscreenTitle } = useChartFullscreen({
        chartRef,
        title: '时段价差分布'
    });

    // 表格排序
    const handleSort = (property: keyof TimeSlotStats) => {
        const isAsc = orderBy === property && order === 'asc';
        setOrder(isAsc ? 'desc' : 'asc');
        setOrderBy(property);
        // 移动端重置显示数量
        if (isMobile) {
            setVisibleCount(10);
        }
    };

    const sortedData = useMemo(() => {
        if (!data) return [];
        return [...data.timeslot_stats].sort((a, b) => {
            const aVal = a[orderBy];
            const bVal = b[orderBy];
            if (order === 'asc') {
                return aVal < bVal ? -1 : 1;
            } else {
                return aVal > bVal ? -1 : 1;
            }
        });
    }, [data, order, orderBy]);

    // 分页（桌面端）
    const paginatedData = useMemo(() => {
        return sortedData.slice(page * rowsPerPage, page * rowsPerPage + rowsPerPage);
    }, [sortedData, page, rowsPerPage]);

    // 移动端可见数据
    const visibleData = useMemo(() => {
        return sortedData.slice(0, visibleCount);
    }, [sortedData, visibleCount]);

    const handleChangePage = (event: unknown, newPage: number) => {
        setPage(newPage);
    };

    const handleChangeRowsPerPage = (event: React.ChangeEvent<HTMLInputElement>) => {
        setRowsPerPage(parseInt(event.target.value, 10));
        setPage(0);
    };

    // 加载更多
    const handleLoadMore = () => {
        setVisibleCount(prev => Math.min(prev + 10, sortedData.length));
    };

    // 策略颜色映射
    const getStrategyColor = (strategy: string): "success" | "error" | "default" => {
        if (strategy === '做多日前') return 'success';
        if (strategy === '做空日前') return 'error';
        return 'default';
    };

    const getConfidenceColor = (confidence: string): "success" | "warning" | "default" => {
        if (confidence === '高') return 'success';
        if (confidence === '中') return 'warning';
        return 'default';
    };

    const getRiskColor = (risk: string): "success" | "warning" | "error" => {
        if (risk === '低风险') return 'success';
        if (risk === '中风险') return 'warning';
        return 'error';
    };

    // X轴标签格式化（移动端竖屏非全屏每隔6个显示）
    const xAxisTickFormatter = (value: number) => {
        if (isMobile && !isFullscreen) {
            // 移动端：每隔6个时段显示一个标签（0, 6, 12, 18, 24, 30, 36, 42, 48）
            return value % 6 === 0 ? String(value) : '';
        }
        return String(value);
    };

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

                    {/* Summary Panel */}
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
                            {/* Row 1: Metrics Overview */}
                            <Typography variant="body2" sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, flexWrap: 'wrap' }}>
                                <Box component="span" sx={{ bgcolor: 'rgba(255,255,255,0.2)', px: 1, py: 0.5, borderRadius: 1, fontWeight: 'bold', flexShrink: 0 }}>
                                    指标速览
                                </Box>
                                <Box component="span" sx={{ lineHeight: 2 }}>
                                    本周期共发现 <Box component="span" sx={{ fontWeight: 'bold', fontSize: '1.1em', mx: 0.5 }}>{data.kpis.high_consistency_count}</Box> 个高确定性时段，
                                    其中前三时段分别是 <Box component="span" sx={{ fontWeight: 'bold', mx: 0.5 }}>{data.kpis.top_consistency_timeslots.join(', ') || '无'}</Box>，
                                    另外⚠️注意：检测到 <Box component="span" sx={{ fontWeight: 'bold', fontSize: '1.1em', mx: 0.5, color: '#ffeb3b' }}>{data.kpis.high_risk_count}</Box> 个高风险时段，建议谨慎操作。
                                </Box>
                            </Typography>

                            {/* Row 2: Definitions */}
                            <Typography variant="body2" sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, flexWrap: 'wrap' }}>
                                <Box component="span" sx={{ bgcolor: 'rgba(255,255,255,0.2)', px: 1, py: 0.5, borderRadius: 1, fontWeight: 'bold', flexShrink: 0 }}>
                                    指标定义
                                </Box>
                                <Box component="span" sx={{ opacity: 0.9, lineHeight: 2 }}>
                                    高确定性：一致性评分 ≥ 70% 且 平均价差绝对值 &gt; 10元；
                                    一致性评分 = max(正价差占比, 负价差占比)；
                                    高风险：价差标准差 ≥ 动态阈值 (Top 20%)。
                                </Box>
                            </Typography>
                        </Box>
                    </Paper>

                    {/* Box Plot Chart */}
                    <Paper variant="outlined" sx={{ p: { xs: 1, sm: 2 }, mb: 2 }}>
                        <Typography variant="h6" gutterBottom>时段价差分布</Typography>
                        <Box ref={chartRef} sx={{
                            height: { xs: 350, sm: 400 },
                            position: 'relative',
                            bgcolor: isFullscreen ? 'background.paper' : 'transparent',
                            p: isFullscreen ? 2 : 0,
                            ...(isFullscreen && { position: 'fixed', top: 0, left: 0, width: '100vw', height: '100vh', zIndex: 1400 })
                        }}>
                            <FullscreenEnterButton />
                            <FullscreenExitButton />
                            <FullscreenTitle />
                            <ResponsiveContainer>
                                <ComposedChart data={chartData} margin={{ top: 20, right: 20, bottom: 20, left: 20 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis
                                        dataKey="timeslot"
                                        label={{ value: '时段编号', position: 'insideBottom', offset: -5 }}
                                        type="number"
                                        domain={[0, 49]}
                                        tickFormatter={xAxisTickFormatter}
                                    />
                                    <YAxis
                                        label={{ value: '价差 (元/MWh)', angle: -90, position: 'insideLeft' }}
                                        domain={[
                                            (dataMin: number) => {
                                                const hasData = chartData.length > 0;
                                                const minVal = hasData ? Math.min(...chartData.map(d => d.min)) : 0;
                                                return Math.floor(Math.min(dataMin, minVal) * 1.1);
                                            },
                                            (dataMax: number) => {
                                                const hasData = chartData.length > 0;
                                                const maxVal = hasData ? Math.max(...chartData.map(d => d.max)) : 0;
                                                return Math.ceil(Math.max(dataMax, maxVal) * 1.1);
                                            }
                                        ]}
                                    />
                                    <Tooltip content={({ active, payload }) => {
                                        if (active && payload && payload.length > 0) {
                                            const d = payload[0].payload as BoxPlotDataPoint;
                                            return (
                                                <Paper sx={{ p: 1 }}>
                                                    <Typography variant="caption" fontWeight="bold">时段 {d.timeslot}</Typography>
                                                    <Typography variant="body2">{d.time_label}</Typography>
                                                    <Typography variant="caption">最大: {d.max.toFixed(2)}</Typography><br />
                                                    <Typography variant="caption">Q3: {d.q3.toFixed(2)}</Typography><br />
                                                    <Typography variant="caption" fontWeight="bold" color="primary">中位数: {d.median.toFixed(2)}</Typography><br />
                                                    <Typography variant="caption">Q1: {d.q1.toFixed(2)}</Typography><br />
                                                    <Typography variant="caption">最小: {d.min.toFixed(2)}</Typography>
                                                </Paper>
                                            );
                                        }
                                        return null;
                                    }} />
                                    <ReferenceLine y={0} stroke="#000" strokeWidth={1.5} />

                                    {/* 隐藏的Bar,用于强制触发图表渲染和坐标轴计算 */}
                                    <Bar dataKey="median" fill="rgba(0,0,0,0)" legendType="none" tooltipType="none" animationDuration={1000} />

                                    {/* 使用 ReferenceArea 和 ReferenceLine 绘制箱线图 */}
                                    {chartData.map((entry, index) => {
                                        const { timeslot, min, q1, median, q3, max } = entry;
                                        const color = median >= 0 ? '#f44336' : '#4caf50';
                                        const width = 0.3; // 箱体宽度 (X轴单位)

                                        return (
                                            <React.Fragment key={`boxplot-${index}`}>
                                                {/* 须线 (Min 到 Max) */}
                                                <ReferenceLine
                                                    segment={[{ x: timeslot, y: min }, { x: timeslot, y: max }]}
                                                    stroke="#666"
                                                    strokeWidth={1.5}
                                                />
                                                {/* 须线端点 (Min) */}
                                                <ReferenceLine
                                                    segment={[{ x: timeslot - width / 2, y: min }, { x: timeslot + width / 2, y: min }]}
                                                    stroke="#666"
                                                    strokeWidth={1.5}
                                                />
                                                {/* 须线端点 (Max) */}
                                                <ReferenceLine
                                                    segment={[{ x: timeslot - width / 2, y: max }, { x: timeslot + width / 2, y: max }]}
                                                    stroke="#666"
                                                    strokeWidth={1.5}
                                                />

                                                {/* 箱体 (Q1 到 Q3) */}
                                                <ReferenceArea
                                                    x1={timeslot - width}
                                                    x2={timeslot + width}
                                                    y1={Math.min(q1, q3)}
                                                    y2={Math.max(q1, q3)}
                                                    fill={color}
                                                    fillOpacity={0.6}
                                                    stroke={color}
                                                    strokeWidth={1.5}
                                                />

                                                {/* 中位数线 */}
                                                <ReferenceLine
                                                    segment={[
                                                        { x: timeslot - width, y: median },
                                                        { x: timeslot + width, y: median }
                                                    ]}
                                                    stroke="#000"
                                                    strokeWidth={2}
                                                />
                                            </React.Fragment>
                                        );
                                    })}
                                </ComposedChart>
                            </ResponsiveContainer>
                        </Box>
                        <Typography variant="caption" color="text.secondary" sx={{ mt: 1, display: 'block' }}>
                            ℹ️ 箱体=25%-75%分位数(红色为正价差,绿色为负价差), 粗黑线=中位数, 须线=最小/最大值
                        </Typography>
                    </Paper>

                    {/* Data Section - 响应式布局 */}
                    <Paper variant="outlined" sx={{ p: { xs: 1, sm: 2 } }}>
                        <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', mb: 2, flexWrap: 'wrap', gap: 1 }}>
                            <Typography variant="h6">时段统计分析</Typography>
                            {!isMobile && (
                                <Button variant="outlined" size="small" startIcon={<DownloadIcon />}>
                                    导出Excel
                                </Button>
                            )}
                        </Box>

                        {/* 移动端：排序工具栏 + 卡片列表 */}
                        {isMobile ? (
                            <>
                                {/* 排序工具栏 */}
                                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                                    <FormControl size="small" sx={{ minWidth: 120, flex: 1 }}>
                                        <InputLabel>排序依据</InputLabel>
                                        <Select
                                            value={orderBy}
                                            label="排序依据"
                                            onChange={(e) => {
                                                setOrderBy(e.target.value as keyof TimeSlotStats);
                                                setVisibleCount(10); // 重置显示数量
                                            }}
                                        >
                                            {SORT_OPTIONS.map((option) => (
                                                <MenuItem key={option.value} value={option.value}>
                                                    {option.label}
                                                </MenuItem>
                                            ))}
                                        </Select>
                                    </FormControl>
                                    <IconButton
                                        onClick={() => setOrder(prev => prev === 'asc' ? 'desc' : 'asc')}
                                        size="small"
                                        sx={{ border: 1, borderColor: 'divider' }}
                                    >
                                        {order === 'asc' ? <ArrowUpwardIcon /> : <ArrowDownwardIcon />}
                                    </IconButton>
                                </Box>

                                {/* 卡片列表 */}
                                <Stack spacing={0}>
                                    {visibleData.map((row) => (
                                        <TimeSlotCard
                                            key={row.timeslot}
                                            row={row}
                                            getStrategyColor={getStrategyColor}
                                            getRiskColor={getRiskColor}
                                        />
                                    ))}
                                </Stack>

                                {/* 加载更多按钮 */}
                                {visibleCount < sortedData.length && (
                                    <Box sx={{ textAlign: 'center', mt: 2 }}>
                                        <Button
                                            variant="outlined"
                                            onClick={handleLoadMore}
                                            fullWidth
                                        >
                                            加载更多 ({visibleCount}/{sortedData.length})
                                        </Button>
                                    </Box>
                                )}

                                {/* 已全部加载提示 */}
                                {visibleCount >= sortedData.length && sortedData.length > 0 && (
                                    <Typography variant="caption" color="text.secondary" sx={{ display: 'block', textAlign: 'center', mt: 2 }}>
                                        已显示全部 {sortedData.length} 条数据
                                    </Typography>
                                )}
                            </>
                        ) : (
                            /* 桌面端：原有表格 */
                            <>
                                <TableContainer sx={{ maxHeight: 600 }}>
                                    <Table stickyHeader size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>
                                                    <TableSortLabel
                                                        active={orderBy === 'timeslot'}
                                                        direction={order}
                                                        onClick={() => handleSort('timeslot')}
                                                    >
                                                        时段
                                                    </TableSortLabel>
                                                </TableCell>
                                                <TableCell align="right">
                                                    <TableSortLabel
                                                        active={orderBy === 'recommendation_index'}
                                                        direction={order}
                                                        onClick={() => handleSort('recommendation_index')}
                                                    >
                                                        推荐指数
                                                    </TableSortLabel>
                                                </TableCell>
                                                <TableCell align="right">
                                                    <TableSortLabel
                                                        active={orderBy === 'avg_price_rt'}
                                                        direction={order}
                                                        onClick={() => handleSort('avg_price_rt')}
                                                    >
                                                        平均价格_RT
                                                    </TableSortLabel>
                                                </TableCell>
                                                <TableCell align="right">
                                                    <TableSortLabel
                                                        active={orderBy === 'std_price_rt'}
                                                        direction={order}
                                                        onClick={() => handleSort('std_price_rt')}
                                                    >
                                                        波动性(σ)
                                                    </TableSortLabel>
                                                </TableCell>
                                                <TableCell align="right">
                                                    <TableSortLabel
                                                        active={orderBy === 'avg_spread'}
                                                        direction={order}
                                                        onClick={() => handleSort('avg_spread')}
                                                    >
                                                        平均价差
                                                    </TableSortLabel>
                                                </TableCell>
                                                <TableCell align="right">
                                                    <TableSortLabel
                                                        active={orderBy === 'consistency_score'}
                                                        direction={order}
                                                        onClick={() => handleSort('consistency_score')}
                                                    >
                                                        一致性
                                                    </TableSortLabel>
                                                </TableCell>
                                                <TableCell align="center">正价差占比</TableCell>
                                                <TableCell align="center">负价差占比</TableCell>
                                                <TableCell align="center">推荐策略</TableCell>
                                                <TableCell align="center">置信度</TableCell>
                                                <TableCell align="center">风险等级</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {paginatedData.map((row) => (
                                                <TableRow key={row.timeslot} hover>
                                                    <TableCell>
                                                        <Typography variant="body2" fontWeight="bold">
                                                            #{row.timeslot}
                                                        </Typography>
                                                        <Typography variant="caption" color="text.secondary">
                                                            {row.time_label}
                                                        </Typography>
                                                    </TableCell>
                                                    <TableCell align="right">
                                                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'flex-end', gap: 1 }}>
                                                            <Box display="flex" gap={0.5} alignItems="flex-end">
                                                                {[1, 2, 3, 4, 5].map((i) => (
                                                                    <Box
                                                                        key={i}
                                                                        sx={{
                                                                            width: 4,
                                                                            height: 8 + (i * 2),
                                                                            bgcolor: i <= row.signal_strength ? 'primary.main' : 'grey.300',
                                                                            borderRadius: 0.5
                                                                        }}
                                                                    />
                                                                ))}
                                                            </Box>
                                                            <Typography variant="body2" fontWeight="bold">
                                                                {row.recommendation_index.toFixed(1)}
                                                            </Typography>
                                                        </Box>
                                                    </TableCell>
                                                    <TableCell align="right">{row.avg_price_rt.toFixed(2)}</TableCell>
                                                    <TableCell align="right">
                                                        <Typography
                                                            variant="body2"
                                                            color={row.std_price_rt >= 30 ? 'error.main' : 'text.primary'}
                                                        >
                                                            {row.std_price_rt.toFixed(2)}
                                                        </Typography>
                                                    </TableCell>
                                                    <TableCell align="right">
                                                        <Typography
                                                            variant="body2"
                                                            color={row.avg_spread >= 0 ? 'error.main' : 'success.main'}
                                                            fontWeight="bold"
                                                        >
                                                            {row.avg_spread >= 0 ? '+' : ''}{row.avg_spread.toFixed(2)}
                                                        </Typography>
                                                    </TableCell>
                                                    <TableCell align="right">
                                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1 }}>
                                                            <LinearProgress
                                                                variant="determinate"
                                                                value={row.consistency_score * 100}
                                                                sx={{
                                                                    flexGrow: 1,
                                                                    height: 6,
                                                                    borderRadius: 3,
                                                                    bgcolor: 'grey.200',
                                                                    '& .MuiLinearProgress-bar': {
                                                                        bgcolor: row.consistency_score >= 0.7 ? 'success.main' : 'warning.main'
                                                                    }
                                                                }}
                                                            />
                                                            <Typography variant="caption">
                                                                {(row.consistency_score * 100).toFixed(0)}%
                                                            </Typography>
                                                        </Box>
                                                    </TableCell>
                                                    <TableCell align="center">
                                                        <Typography variant="body2" color="error.main">
                                                            {(row.positive_spread_ratio * 100).toFixed(0)}%
                                                        </Typography>
                                                    </TableCell>
                                                    <TableCell align="center">
                                                        <Typography variant="body2" color="success.main">
                                                            {(row.negative_spread_ratio * 100).toFixed(0)}%
                                                        </Typography>
                                                    </TableCell>
                                                    <TableCell align="center">
                                                        <Chip
                                                            label={row.recommended_strategy}
                                                            size="small"
                                                            color={getStrategyColor(row.recommended_strategy)}
                                                            sx={{ fontSize: '0.7rem' }}
                                                        />
                                                    </TableCell>
                                                    <TableCell align="center">
                                                        <Chip
                                                            label={row.confidence}
                                                            size="small"
                                                            color={getConfidenceColor(row.confidence)}
                                                            variant="outlined"
                                                            sx={{ fontSize: '0.7rem' }}
                                                        />
                                                    </TableCell>
                                                    <TableCell align="center">
                                                        <Chip
                                                            label={row.risk_level}
                                                            size="small"
                                                            color={getRiskColor(row.risk_level)}
                                                            variant="outlined"
                                                            sx={{ fontSize: '0.7rem' }}
                                                        />
                                                    </TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                                <TablePagination
                                    component="div"
                                    count={sortedData.length}
                                    page={page}
                                    onPageChange={handleChangePage}
                                    rowsPerPage={rowsPerPage}
                                    onRowsPerPageChange={handleChangeRowsPerPage}
                                    rowsPerPageOptions={[10, 25, 50]}
                                    labelRowsPerPage="每页行数:"
                                />
                            </>
                        )}
                    </Paper>
                </Box >
            ) : null}
        </Box >
    );
};
