/**
 * 中长期日内分析 - Tab1: 价格总览
 * 
 * 布局：
 * 1. 蓝色渐变消息提示框（汇总指标文字表达）
 * 2. 主图表（中长期整体曲线 + 日前现货对标）
 * 3. 明细表格
 */
import React, { useRef } from 'react';
import {
    Box,
    Paper,
    Typography,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    CircularProgress,
    Alert,
    useMediaQuery,
    useTheme
} from '@mui/material';
import {
    ComposedChart,
    LineChart,
    Line,
    Area,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    ReferenceDot,
    ReferenceLine
} from 'recharts';

import { useChartFullscreen } from '../../hooks/useChartFullscreen';
import { DailySummaryResponse, CurvePoint, ContractTypeSummary } from '../../api/contractPrice';

// Props 接口
interface DailySummaryTabProps {
    data: DailySummaryResponse | null;
    loading: boolean;
    error: string | null;
    dateStr: string;
    selectedBenchmark: 'day_ahead' | 'real_time';
}

// 蓝色渐变消息提示框组件
const SummaryPanel: React.FC<{ data: DailySummaryResponse }> = ({ data }) => {
    const { kpis } = data;

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
                {/* 第一行：合同概况 */}
                <Typography variant="body2" sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, flexWrap: 'wrap' }}>
                    <Box component="span" sx={{ bgcolor: 'rgba(255,255,255,0.2)', px: 1, py: 0.5, borderRadius: 1, fontWeight: 'bold', flexShrink: 0 }}>
                        合同概况
                    </Box>
                    <Box component="span">
                        当日中长期合同电量 {kpis.total_quantity.toFixed(0)} MWh，
                        整体加权均价 {kpis.overall_avg_price.toFixed(2)} 元/MWh，
                        价格区间 {kpis.price_range_min.toFixed(0)}~{kpis.price_range_max.toFixed(0)} 元/MWh
                    </Box>
                </Typography>

                {/* 第二行：结构分布 */}
                <Typography variant="body2" sx={{ display: 'flex', alignItems: 'flex-start', gap: 1, flexWrap: 'wrap' }}>
                    <Box component="span" sx={{ bgcolor: 'rgba(255,255,255,0.2)', px: 1, py: 0.5, borderRadius: 1, fontWeight: 'bold', flexShrink: 0 }}>
                        结构分布
                    </Box>
                    <Box component="span">
                        年度占比 {kpis.yearly_ratio.toFixed(1)}%
                        {kpis.yearly_avg_price !== null && `（均价 ${kpis.yearly_avg_price.toFixed(0)}元）`}，
                        月度占比 {kpis.monthly_ratio.toFixed(1)}%
                        {kpis.monthly_avg_price !== null && `（均价 ${kpis.monthly_avg_price.toFixed(0)}元）`}，
                        月内占比 {kpis.within_month_ratio.toFixed(1)}%
                        {kpis.within_month_avg_price !== null && `（均价 ${kpis.within_month_avg_price.toFixed(0)}元）`}
                    </Box>
                </Typography>
            </Box>
        </Paper>
    );
};

// 价格曲线图组件
const PriceChart: React.FC<{
    contractCurves: CurvePoint[];
    spotCurves: CurvePoint[];
    curvesByType: { [key: string]: CurvePoint[] };
    dateStr: string;
    selectedBenchmark: 'day_ahead' | 'real_time';
}> = ({ contractCurves, spotCurves, curvesByType, dateStr, selectedBenchmark }) => {
    const chartRef = useRef<HTMLDivElement>(null);
    const [selectedType, setSelectedType] = React.useState<string>('整体');
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // 合同类型选项（移动端简写）
    const typeOptions = [
        { value: '整体', label: '整体', mobileLabel: '整体' },
        { value: '市场化', label: '市场化', mobileLabel: '市场化' },
        { value: '绿电', label: '绿电', mobileLabel: '绿电' },
        { value: '代理购电', label: '代理购电', mobileLabel: '代购电' }
    ];

    // 根据选择获取当前显示的曲线数据
    const currentCurves = selectedType === '整体'
        ? contractCurves
        : (curvesByType[selectedType] || []);

    // 合并数据用于图表
    const chartData = currentCurves.map(cp => {
        const spotPoint = spotCurves.find(sp => sp.period === cp.period);
        const contractQty = cp.quantity ?? 0;
        const spotQty = spotPoint?.quantity ?? 0;

        return {
            period: cp.period,
            time_str: cp.time_str,
            contract_price: cp.price,
            spot_price: spotPoint?.price ?? null,
            contract_quantity: contractQty,  // 合同电量
            spot_quantity: spotQty  // 出清电量
        };
    });


    // 计算Y轴范围
    const allPrices = [
        ...currentCurves.map(p => p.price),
        ...spotCurves.map(p => p.price)
    ].filter(p => p !== null && p !== undefined);
    const minPrice = allPrices.length > 0 ? Math.min(...allPrices) : 0;
    const maxPrice = allPrices.length > 0 ? Math.max(...allPrices) : 500;

    // 找到极值点
    const maxContractPoint = currentCurves.length > 0
        ? currentCurves.reduce((prev, curr) => curr.price > prev.price ? curr : prev)
        : null;
    const minContractPoint = currentCurves.length > 0
        ? currentCurves.reduce((prev, curr) => curr.price < prev.price ? curr : prev)
        : null;

    // 全屏功能
    const { isFullscreen, FullscreenEnterButton, FullscreenExitButton, FullscreenTitle } = useChartFullscreen({
        chartRef,
        title: `${dateStr} ${selectedType}合同价格曲线`
    });

    // 获取曲线颜色
    const getCurveColor = (type: string) => {
        const colors: { [key: string]: string } = {
            '整体': '#2196f3',
            '市场化': '#4caf50',
            '绿电': '#8bc34a',
            '代理购电': '#ff9800'
        };
        return colors[type] || '#2196f3';
    };

    return (
        <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
            {/* 标题栏：左侧标题+合同类型 */}
            <Box sx={{ display: 'flex', alignItems: 'center', gap: 2, flexWrap: 'wrap', mb: 1 }}>
                <Typography variant="h6">价格曲线</Typography>
                <Box sx={{ display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                    {typeOptions.map(option => (
                        <Box
                            key={option.value}
                            onClick={() => setSelectedType(option.value)}
                            sx={{
                                px: 1.5,
                                py: 0.5,
                                borderRadius: 1,
                                fontSize: '0.875rem',
                                cursor: 'pointer',
                                border: '1px solid',
                                borderColor: selectedType === option.value ? getCurveColor(option.value) : 'divider',
                                backgroundColor: selectedType === option.value ? getCurveColor(option.value) : 'transparent',
                                color: selectedType === option.value ? 'white' : 'text.primary',
                                fontWeight: selectedType === option.value ? 'bold' : 'normal',
                                transition: 'all 0.2s',
                                '&:hover': {
                                    borderColor: getCurveColor(option.value),
                                    opacity: 0.8
                                }
                            }}
                        >
                            {isMobile ? option.mobileLabel : option.label}
                        </Box>
                    ))}
                </Box>
            </Box>


            <Box
                ref={chartRef}
                sx={{
                    height: { xs: 450, sm: 520 },  // 增加高度容纳两个图表
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

                {chartData.length === 0 ? (
                    <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
                        <Typography color="text.secondary">无曲线数据（{selectedType}）</Typography>
                    </Box>
                ) : (
                    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
                        {/* 上方：价格曲线图 (70%) */}
                        <Box sx={{ flex: '0 0 70%', width: '100%' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <LineChart data={chartData} syncId="priceChart" margin={{ top: 5, right: 30, left: 20, bottom: 0 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="time_str" tick={false} axisLine={false} />
                                    <YAxis
                                        domain={[Math.floor(minPrice * 0.9), Math.ceil(maxPrice * 1.1)]}
                                        label={{
                                            value: '价格 (元/MWh)',
                                            angle: -90,
                                            position: 'insideLeft'
                                        }}
                                        tick={{ fontSize: 12 }}
                                    />
                                    <Tooltip
                                        content={({ active, payload, label }) => {
                                            if (active && payload && payload.length) {
                                                // 从chartData中找到对应的完整数据
                                                const dataPoint = chartData.find(d => d.time_str === label);
                                                const spotLabel = selectedBenchmark === 'day_ahead' ? '日前' : '实时';
                                                return (
                                                    <Paper sx={{ p: 1.5, backgroundColor: 'rgba(255, 255, 255, 0.95)', border: '1px solid #ccc', borderRadius: '4px' }}>
                                                        <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
                                                            时间: {label}
                                                        </Typography>
                                                        {/* 价格 */}
                                                        {payload.map((pld: any) => (
                                                            <Typography key={pld.dataKey} variant="body2" sx={{ color: pld.color }}>
                                                                {pld.name}: {pld.value !== null ? `${Number(pld.value).toFixed(2)} 元/MWh` : 'N/A'}
                                                            </Typography>
                                                        ))}
                                                        {/* 电量 */}
                                                        {dataPoint && (
                                                            <>
                                                                <Typography variant="body2" sx={{ color: getCurveColor(selectedType), mt: 0.5 }}>
                                                                    {selectedType}电量: {dataPoint.contract_quantity.toFixed(1)} MWh
                                                                </Typography>
                                                                <Typography variant="body2" sx={{ color: '#f44336' }}>
                                                                    {spotLabel}出清: {dataPoint.spot_quantity.toFixed(1)} MWh
                                                                </Typography>
                                                            </>
                                                        )}
                                                    </Paper>
                                                );

                                            }
                                            return null;
                                        }}
                                    />
                                    {/* 图例不在这里显示 */}
                                    <Line
                                        type="monotone"
                                        dataKey="contract_price"
                                        stroke={getCurveColor(selectedType)}
                                        strokeWidth={2}
                                        name={`${selectedType}均价`}
                                        dot={false}
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="spot_price"
                                        stroke="#f44336"
                                        strokeWidth={2}
                                        strokeDasharray="5 5"
                                        name={selectedBenchmark === 'day_ahead' ? '日前现货' : '实时现货'}
                                        dot={false}
                                    />

                                    {/* 最高价标注 */}
                                    {maxContractPoint && (
                                        <ReferenceDot
                                            x={maxContractPoint.time_str}
                                            y={maxContractPoint.price}
                                            r={6}
                                            fill={getCurveColor(selectedType)}
                                            stroke="#fff"
                                            strokeWidth={2}
                                            label={{
                                                value: maxContractPoint.price.toFixed(0),
                                                position: 'top',
                                                fill: getCurveColor(selectedType),
                                                fontSize: 12,
                                                fontWeight: 'bold'
                                            }}
                                        />
                                    )}

                                    {/* 最低价标注 */}
                                    {minContractPoint && (
                                        <ReferenceDot
                                            x={minContractPoint.time_str}
                                            y={minContractPoint.price}
                                            r={6}
                                            fill={getCurveColor(selectedType)}
                                            stroke="#fff"
                                            strokeWidth={2}
                                            label={{
                                                value: minContractPoint.price.toFixed(0),
                                                position: 'bottom',
                                                fill: getCurveColor(selectedType),
                                                fontSize: 12,
                                                fontWeight: 'bold'
                                            }}
                                        />
                                    )}
                                </LineChart>
                            </ResponsiveContainer>
                        </Box>

                        {/* 下方：仓位占比面积图 (30%) */}
                        <Box sx={{ flex: '0 0 30%', width: '100%' }}>
                            <ResponsiveContainer width="100%" height="100%">
                                <ComposedChart data={chartData} syncId="priceChart" margin={{ top: 0, right: 30, left: 20, bottom: 5 }}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis
                                        dataKey="time_str"
                                        tick={{ fontSize: 12 }}
                                        interval={5}
                                    />
                                    {/* Y轴：电量 */}
                                    <YAxis
                                        yAxisId="quantity"
                                        label={{
                                            value: '电量 (MWh)',
                                            angle: -90,
                                            position: 'insideLeft'
                                        }}
                                        tick={{ fontSize: 12 }}
                                    />

                                    {/* 共用上方Tooltip，此处隐藏 */}
                                    <Tooltip content={() => null} />
                                    {/* 柱状图：合同电量 */}
                                    <Bar
                                        yAxisId="quantity"
                                        dataKey="contract_quantity"
                                        fill={getCurveColor(selectedType)}
                                        fillOpacity={0.4}
                                        name={`${selectedType}电量`}
                                    />
                                    {/* 面积图：出清电量 */}
                                    <Area
                                        yAxisId="quantity"
                                        type="monotone"
                                        dataKey="spot_quantity"
                                        stroke="#f44336"
                                        fill="#f44336"
                                        fillOpacity={0.2}
                                        name={selectedBenchmark === 'day_ahead' ? '日前出清' : '实时出清'}
                                        dot={false}
                                    />
                                </ComposedChart>



                            </ResponsiveContainer>
                        </Box>

                        {/* 底部统一图例 */}
                        <Box sx={{ display: 'flex', justifyContent: 'center', gap: 3, flexWrap: 'wrap', pt: 1 }}>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <Box sx={{ width: 20, height: 2, backgroundColor: getCurveColor(selectedType) }} />
                                <Typography variant="caption">{selectedType}均价</Typography>
                            </Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <Box sx={{ width: 20, height: 0, borderTop: '2px dashed #f44336' }} />
                                <Typography variant="caption">{selectedBenchmark === 'day_ahead' ? '日前现货' : '实时现货'}</Typography>
                            </Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <Box sx={{ width: 12, height: 12, backgroundColor: getCurveColor(selectedType), opacity: 0.4 }} />
                                <Typography variant="caption">{selectedType}电量</Typography>
                            </Box>
                            <Box sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                                <Box sx={{ width: 12, height: 12, backgroundColor: '#f44336', opacity: 0.2 }} />
                                <Typography variant="caption">{selectedBenchmark === 'day_ahead' ? '日前出清' : '实时出清'}</Typography>
                            </Box>
                        </Box>

                    </Box>
                )}

            </Box>
        </Paper >
    );
};


// 明细表格组件
const DetailTable: React.FC<{ typeSummary: ContractTypeSummary[] }> = ({ typeSummary }) => {
    return (
        <Paper variant="outlined" sx={{ mt: 2 }}>
            <Typography variant="h6" sx={{ p: 2, pb: 1 }}>合同明细</Typography>
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
                            <TableCell sx={{ fontWeight: 'bold' }}>合同类型</TableCell>
                            <TableCell sx={{ fontWeight: 'bold' }}>交易周期</TableCell>
                            <TableCell align="right" sx={{ fontWeight: 'bold' }}>日电量<br />(MWh)</TableCell>
                            <TableCell align="right" sx={{ fontWeight: 'bold' }}>均价<br />(元/MWh)</TableCell>
                            <TableCell align="right" sx={{ fontWeight: 'bold' }}>最高价</TableCell>
                            <TableCell align="right" sx={{ fontWeight: 'bold' }}>最低价</TableCell>
                            <TableCell align="right" sx={{ fontWeight: 'bold' }}>峰谷差</TableCell>
                        </TableRow>
                    </TableHead>
                    <TableBody>
                        {typeSummary.length === 0 ? (
                            <TableRow>
                                <TableCell colSpan={7} align="center">
                                    <Typography color="text.secondary">暂无数据</Typography>
                                </TableCell>
                            </TableRow>
                        ) : (
                            typeSummary.map((row, index) => (
                                <TableRow key={index} hover>
                                    <TableCell>{row.contract_type}</TableCell>
                                    <TableCell>{row.contract_period}</TableCell>
                                    <TableCell align="right">{row.daily_total_quantity.toFixed(0)}</TableCell>
                                    <TableCell align="right">{row.daily_avg_price.toFixed(2)}</TableCell>
                                    <TableCell align="right">{row.max_price?.toFixed(0) ?? 'N/A'}</TableCell>
                                    <TableCell align="right">{row.min_price?.toFixed(0) ?? 'N/A'}</TableCell>
                                    <TableCell align="right">{row.peak_valley_spread?.toFixed(0) ?? 'N/A'}</TableCell>
                                </TableRow>
                            ))
                        )}
                    </TableBody>
                </Table>
            </TableContainer>
        </Paper>
    );
};

// 主组件
export const DailySummaryTab: React.FC<DailySummaryTabProps> = ({
    data,
    loading,
    error,
    dateStr,
    selectedBenchmark
}) => {
    // 首次加载显示完整loading

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

    if (!data) {
        return <Alert severity="info" sx={{ mt: 2 }}>请选择日期查看数据</Alert>;
    }

    return (
        <Box sx={{ position: 'relative' }}>
            {/* 数据刷新时的覆盖层 */}
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

            {/* 第一部分：蓝色渐变消息提示框 */}
            <SummaryPanel data={data} />

            {/* 第二部分：主图表 */}
            <PriceChart
                contractCurves={data.contract_curves}
                spotCurves={data.spot_curves}
                curvesByType={data.curves_by_type || {}}
                dateStr={dateStr}
                selectedBenchmark={selectedBenchmark}
            />


            {/* 第三部分：明细表格 */}
            <DetailTable typeSummary={data.type_summary} />
        </Box>
    );
};
