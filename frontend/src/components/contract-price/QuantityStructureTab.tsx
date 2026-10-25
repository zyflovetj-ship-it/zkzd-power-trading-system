/**
 * 中长期日内分析 - Tab3: 电量结构
 * 
 * 功能：
 * 1. 蓝色渐变消息提示框（电量汇总）
 * 2. 堆叠柱状图（可切换按周期/按类型分色）
 * 3. 电量占比双饼图（左:按周期，右:按类型）
 */
import React, { useState, useRef, useMemo } from 'react';
import {
    Box,
    Paper,
    Typography,
    CircularProgress,
    Alert,
    Grid,
    Chip
} from '@mui/material';
import {
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    PieChart,
    Pie,
    Cell
} from 'recharts';
import { useChartFullscreen } from '../../hooks/useChartFullscreen';
import { DailySummaryResponse, CurvePoint } from '../../api/contractPrice';

// Props 接口
interface QuantityStructureTabProps {
    data: DailySummaryResponse | null;
    loading: boolean;
    error: string | null;
    dateStr: string;
}

// 颜色配置
const PERIOD_COLORS: { [key: string]: string } = {
    '年度': '#1976d2',
    '月度': '#43a047',
    '月内': '#ff9800'
};

const TYPE_COLORS: { [key: string]: string } = {
    '市场化': '#1976d2',
    '绿电': '#43a047',
    '代购电': '#ff9800'
};

// 分色模式
type ColorMode = 'period' | 'type';

// 蓝色渐变消息提示框
const SummaryPanel: React.FC<{
    totalQuantity: number;
    periodRatios: { name: string; ratio: number }[];
}> = ({ totalQuantity, periodRatios }) => {
    return (
        <Paper
            variant="outlined"
            sx={{
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                color: 'white',
                p: 2,
                borderRadius: 2,
                boxShadow: '0 4px 20px rgba(102, 126, 234, 0.3)',
                border: 'none'
            }}
        >
            <Typography variant="body1" sx={{ fontWeight: 500 }}>
                <Box component="span" sx={{ fontWeight: 'bold', mr: 1 }}>[电量结构]</Box>
                当日总电量 {totalQuantity.toLocaleString()} MWh
                {periodRatios.length > 0 && (
                    <>
                        ，{periodRatios.map((p, i) => (
                            <span key={p.name}>
                                {p.name}占比 {p.ratio.toFixed(1)}%{i < periodRatios.length - 1 ? '、' : ''}
                            </span>
                        ))}
                    </>
                )}
            </Typography>
        </Paper>
    );
};

// 堆叠柱状图
const StackedBarChart: React.FC<{
    curvesByPeriod: { [key: string]: CurvePoint[] };
    typeSummary: { contract_type: string; contract_period: string; daily_total_quantity: number }[];
    colorMode: ColorMode;
    dateStr: string;
}> = ({ curvesByPeriod, typeSummary, colorMode, dateStr }) => {
    const chartRef = useRef<HTMLDivElement>(null);

    const { isFullscreen, FullscreenEnterButton, FullscreenExitButton, FullscreenTitle } =
        useChartFullscreen({
            chartRef,
            title: `电量结构 (${dateStr})`
        });

    // 构建堆叠图表数据
    const chartData = useMemo(() => {
        // 收集所有时段
        const periods = new Set<number>();
        Object.values(curvesByPeriod).forEach(curves => {
            curves.forEach(p => periods.add(p.period));
        });

        // 对于"按周期"分色：从整体合同类型下获取年度/月度/月内数据
        // 对于"按类型"分色：从各合同类型-整体下获取数据
        if (colorMode === 'period') {
            // 按周期分色：使用 市场化-年度/月度/月内 的电量
            const periodKeys = ['市场化-年度', '市场化-月度', '市场化-月内'];
            return Array.from(periods).sort((a, b) => a - b).map(period => {
                const dataPoint: any = { period };

                // 找到时间字符串
                for (const key of Object.keys(curvesByPeriod)) {
                    const point = curvesByPeriod[key]?.find(p => p.period === period);
                    if (point?.time_str) {
                        dataPoint.time_str = point.time_str;
                        break;
                    }
                }

                // 尝试从各周期曲线获取电量
                periodKeys.forEach(key => {
                    const point = curvesByPeriod[key]?.find(p => p.period === period);
                    const periodName = key.split('-')[1]; // 年度/月度/月内
                    dataPoint[periodName] = point?.quantity ?? 0;
                });

                return dataPoint;
            });
        } else {
            // 按类型分色
            const typeKeys = ['市场化-整体', '绿电-整体', '代理购电-整体'];
            return Array.from(periods).sort((a, b) => a - b).map(period => {
                const dataPoint: any = { period };

                for (const key of Object.keys(curvesByPeriod)) {
                    const point = curvesByPeriod[key]?.find(p => p.period === period);
                    if (point?.time_str) {
                        dataPoint.time_str = point.time_str;
                        break;
                    }
                }

                typeKeys.forEach(key => {
                    const point = curvesByPeriod[key]?.find(p => p.period === period);
                    const typeName = key.split('-')[0]; // 市场化/绿电/代理购电
                    const displayName = typeName === '代理购电' ? '代购电' : typeName;
                    dataPoint[displayName] = point?.quantity ?? 0;
                });

                return dataPoint;
            });
        }
    }, [curvesByPeriod, colorMode]);

    const hasData = chartData.length > 0;
    const colors = colorMode === 'period' ? PERIOD_COLORS : TYPE_COLORS;
    const stackKeys = colorMode === 'period'
        ? ['年度', '月度', '月内']
        : ['市场化', '绿电', '代购电'];

    return (
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

            {!hasData ? (
                <Box sx={{ display: 'flex', height: '100%', alignItems: 'center', justifyContent: 'center' }}>
                    <Typography color="text.secondary">暂无电量数据</Typography>
                </Box>
            ) : (
                <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={chartData} margin={{ top: 20, right: 30, left: 20, bottom: 5 }}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="time_str" tick={{ fontSize: 10 }} interval={5} />
                        <YAxis
                            label={{ value: '电量 (MWh)', angle: -90, position: 'insideLeft' }}
                            tick={{ fontSize: 12 }}
                        />
                        <Tooltip
                            content={({ active, payload, label }) => {
                                if (active && payload && payload.length) {
                                    const total = payload.reduce((sum: number, p: any) => sum + (p.value || 0), 0);
                                    return (
                                        <Paper sx={{ p: 1.5, backgroundColor: 'rgba(255, 255, 255, 0.95)' }}>
                                            <Typography variant="body2" sx={{ fontWeight: 'bold', mb: 1 }}>
                                                时间: {label}
                                            </Typography>
                                            {payload.map((pld: any) => (
                                                <Typography key={pld.dataKey} variant="body2" sx={{ color: pld.fill }}>
                                                    {pld.name}: {pld.value?.toFixed(2)} MWh
                                                </Typography>
                                            ))}
                                            <Typography variant="body2" sx={{ fontWeight: 'bold', mt: 1, borderTop: '1px solid #ccc', pt: 1 }}>
                                                合计: {total.toFixed(2)} MWh
                                            </Typography>
                                        </Paper>
                                    );
                                }
                                return null;
                            }}
                        />
                        <Legend />

                        {stackKeys.map(key => (
                            <Bar
                                key={key}
                                dataKey={key}
                                stackId="a"
                                fill={colors[key]}
                                name={key}
                            />
                        ))}
                    </BarChart>
                </ResponsiveContainer>
            )}
        </Box>
    );
};

// 饼图组件
const QuantityPieChart: React.FC<{
    data: { name: string; value: number; color: string }[];
    title: string;
}> = ({ data, title }) => {
    const total = data.reduce((sum, d) => sum + d.value, 0);

    return (
        <Paper variant="outlined" sx={{ p: 2 }}>
            <Typography variant="subtitle1" sx={{ fontWeight: 'bold', textAlign: 'center', mb: 1 }}>
                {title}
            </Typography>
            <Box sx={{ height: 200 }}>
                <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                        <Pie
                            data={data}
                            cx="50%"
                            cy="50%"
                            labelLine={false}
                            label={({ name, percent }: any) => `${name} ${((percent || 0) * 100).toFixed(1)}%`}
                            outerRadius={70}
                            dataKey="value"
                        >
                            {data.map((entry, index) => (
                                <Cell key={`cell-${index}`} fill={entry.color} />
                            ))}
                        </Pie>
                        <Tooltip
                            formatter={(value: number) => [`${value.toFixed(2)} MWh`, '电量']}
                        />
                    </PieChart>
                </ResponsiveContainer>
            </Box>
            {/* 图例 */}
            <Box sx={{ display: 'flex', justifyContent: 'center', gap: 2, flexWrap: 'wrap', mt: 1 }}>
                {data.map(d => (
                    <Box key={d.name} sx={{ display: 'flex', alignItems: 'center', gap: 0.5 }}>
                        <Box sx={{ width: 12, height: 12, backgroundColor: d.color, borderRadius: '50%' }} />
                        <Typography variant="caption">
                            {d.name}: {total > 0 ? ((d.value / total) * 100).toFixed(1) : 0}%
                        </Typography>
                    </Box>
                ))}
            </Box>
        </Paper>
    );
};

// 主组件
export const QuantityStructureTab: React.FC<QuantityStructureTabProps> = ({
    data,
    loading,
    error,
    dateStr
}) => {
    const [colorMode, setColorMode] = useState<ColorMode>('period');

    // 计算周期占比数据 - 从curves_by_period中累加各周期的总电量
    const periodData = useMemo(() => {
        if (!data?.curves_by_period) return [];

        const periodTotals: { [key: string]: number } = { '年度': 0, '月度': 0, '月内': 0 };

        // 遍历所有曲线，按周期累加电量
        Object.entries(data.curves_by_period).forEach(([key, curves]) => {
            // key格式: "市场化-年度", "绿电-月内" 等
            const period = key.split('-')[1]; // 提取周期部分
            if (period && period in periodTotals && curves) {
                // 累加该曲线所有时段的电量
                const curveTotal = curves.reduce((sum, p) => sum + (p.quantity || 0), 0);
                periodTotals[period] += curveTotal;
            }
        });

        return Object.entries(periodTotals)
            .filter(([_, value]) => value > 0)
            .map(([name, value]) => ({
                name,
                value,
                color: PERIOD_COLORS[name]
            }));
    }, [data]);

    // 计算类型占比数据 - 从curves_by_period中累加各类型的总电量
    const typeData = useMemo(() => {
        if (!data?.curves_by_period) return [];

        const typeTotals: { [key: string]: number } = { '市场化': 0, '绿电': 0, '代购电': 0 };
        const typeMapping: { [key: string]: string } = { '代理购电': '代购电' };

        // 遍历所有曲线，按类型累加电量
        Object.entries(data.curves_by_period).forEach(([key, curves]) => {
            // key格式: "市场化-年度", "绿电-月内" 等
            let type = key.split('-')[0]; // 提取类型部分
            type = typeMapping[type] || type; // 映射名称
            if (type && type in typeTotals && curves) {
                // 累加该曲线所有时段的电量
                const curveTotal = curves.reduce((sum, p) => sum + (p.quantity || 0), 0);
                typeTotals[type] += curveTotal;
            }
        });

        return Object.entries(typeTotals)
            .filter(([_, value]) => value > 0)
            .map(([name, value]) => ({
                name,
                value,
                color: TYPE_COLORS[name]
            }));
    }, [data]);

    // 总电量和周期占比
    const totalQuantity = data?.kpis?.total_quantity || 0;
    const periodRatios = [
        { name: '年度', ratio: data?.kpis?.yearly_ratio || 0 },
        { name: '月度', ratio: data?.kpis?.monthly_ratio || 0 },
        { name: '月内', ratio: data?.kpis?.within_month_ratio || 0 }
    ].filter(p => p.ratio > 0);

    // 首次加载
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
            {/* Loading覆盖层 */}
            {loading && (
                <Box
                    sx={{
                        position: 'absolute',
                        top: 0, left: 0, right: 0, bottom: 0,
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
            <SummaryPanel totalQuantity={totalQuantity} periodRatios={periodRatios} />

            {/* 第二部分：堆叠柱状图 */}
            <Paper variant="outlined" sx={{ p: 2, mt: 2 }}>
                {/* 分色切换按钮 */}
                <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 2 }}>
                    <Typography variant="body2" sx={{ fontWeight: 'bold' }}>分色维度:</Typography>
                    <Chip
                        label="按周期"
                        size="small"
                        onClick={() => setColorMode('period')}
                        sx={{
                            backgroundColor: colorMode === 'period' ? '#1976d2' : 'transparent',
                            color: colorMode === 'period' ? 'white' : 'text.primary',
                            border: `1px solid ${colorMode === 'period' ? '#1976d2' : '#ccc'}`,
                            fontWeight: colorMode === 'period' ? 'bold' : 'normal',
                            cursor: 'pointer'
                        }}
                    />
                    <Chip
                        label="按类型"
                        size="small"
                        onClick={() => setColorMode('type')}
                        sx={{
                            backgroundColor: colorMode === 'type' ? '#1976d2' : 'transparent',
                            color: colorMode === 'type' ? 'white' : 'text.primary',
                            border: `1px solid ${colorMode === 'type' ? '#1976d2' : '#ccc'}`,
                            fontWeight: colorMode === 'type' ? 'bold' : 'normal',
                            cursor: 'pointer'
                        }}
                    />
                </Box>

                <StackedBarChart
                    curvesByPeriod={data.curves_by_period || {}}
                    typeSummary={data.type_summary || []}
                    colorMode={colorMode}
                    dateStr={dateStr}
                />
            </Paper>

            {/* 第三部分：双饼图 */}
            <Grid container spacing={2} sx={{ mt: 1 }}>
                <Grid size={{ xs: 12, md: 6 }}>
                    <QuantityPieChart data={periodData} title="按交易周期" />
                </Grid>
                <Grid size={{ xs: 12, md: 6 }}>
                    <QuantityPieChart data={typeData} title="按合同类型" />
                </Grid>
            </Grid>
        </Box>
    );
};
