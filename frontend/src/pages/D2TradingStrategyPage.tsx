import React, { useState } from 'react';
import {
    Box,
    Paper,
    Typography,
    Button,
    Grid,
    FormControl,
    FormLabel,
    FormControlLabel,
    Checkbox,
    Alert,
    Card,
    CardContent,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    useTheme,
    useMediaQuery,
    Chip
} from '@mui/material';
import {
    LocalizationProvider,
    DatePicker
} from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { zhCN } from 'date-fns/locale';
import { format, addDays } from 'date-fns';
import {
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    Area,
    AreaChart,
    ReferenceLine
} from 'recharts';
import apiClient from '../api/client';

// 类型定义
interface HourlyPrice {
    time: string;
    predicted_price: number;
    confidence_lower: number;
    confidence_upper: number;
}

interface D2Forecast {
    forecast_id: string;
    avg_price: number;
    price_range: [number, number];
    hourly_prices: HourlyPrice[];
    price_distribution: {
        min: number;
        max: number;
        mean: number;
        std: number;
    };
}

interface CurrentContract {
    total_amount: number;
    avg_price: number;
}

interface LoadForecast {
    total_load: number;
}

interface PeriodAdjustment {
    period: string;
    hours: string;
    predicted_avg_price: number;
    contract_price: number;
    price_spread: number;
    coverage: number;
    recommendation: string;
    amount: number;
    expected_savings: number;
    reasoning: string;
}

interface RiskAlert {
    type: string;
    severity: string;
    time_range: string;
    predicted_price?: number;
    std?: number;
    recommendation: string;
    potential_loss?: number;
}

interface StrategyData {
    strategy_id: string;
    customer_id: string;
    customer_name: string;
    target_date: string;
    d2_forecast: D2Forecast;
    current_contract: CurrentContract;
    load_forecast: LoadForecast;
    strategy_recommendations: {
        contract_coverage: {
            overall: number;
        };
        overall_recommendation: {
            action: string;
            amount: number;
            expected_cost_savings: number;
            reasoning: string;
        };
        period_adjustments: PeriodAdjustment[];
    };
    risk_alerts: RiskAlert[];
}

export const D2TradingStrategyPage: React.FC = () => {
    const theme = useTheme();
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    // 状态管理
    const [selectedCustomerId, setSelectedCustomerId] = useState<string>('CUST001');
    const [targetDate, setTargetDate] = useState<Date | null>(addDays(new Date(), 2));
    const [compareWithCurrent, setCompareWithCurrent] = useState<boolean>(true);
    const [compareWithSpot, setCompareWithSpot] = useState<boolean>(true);

    const [strategyData, setStrategyData] = useState<StrategyData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const customers = [
        { id: 'CUST001', name: '某某企业' },
        { id: 'CUST002', name: '某某集团' },
        { id: 'CUST003', name: '某某制造' }
    ];

    // 生成策略
    const generateStrategy = async () => {
        if (!targetDate) return;

        setLoading(true);
        setError(null);

        try {
            const compareWith = [
                compareWithCurrent ? 'current_contract' : null,
                compareWithSpot ? 'pure_spot' : null
            ].filter(Boolean).join(',');

            const response = await apiClient.post('/api/v1/trading/d2-strategy/generate', null, {
                params: {
                    customer_id: selectedCustomerId,
                    target_date: format(targetDate, 'yyyy-MM-dd'),
                    compare_with: compareWith
                }
            });

            setStrategyData(response.data);
        } catch (err: any) {
            console.error('Error generating D-2 strategy:', err);
            setError(err.response?.data?.detail || err.message || '生成策略失败');
            setStrategyData(null);
        } finally {
            setLoading(false);
        }
    };

    // 格式化金额
    const formatCurrency = (value: number): string => {
        if (value >= 10000) {
            return `${(value / 10000).toFixed(2)}万元`;
        }
        return `${value.toFixed(0)}元`;
    };

    // 获取建议对应的颜色
    const getRecommendationColor = (recommendation: string): string => {
        switch (recommendation) {
            case 'increase_contract':
                return theme.palette.success.main;
            case 'decrease_contract':
                return theme.palette.warning.main;
            case 'maintain':
            default:
                return theme.palette.info.main;
        }
    };

    // 获取风险等级对应的颜色
    const getSeverityColor = (severity: string): string => {
        switch (severity) {
            case 'high':
                return theme.palette.error.main;
            case 'medium':
                return theme.palette.warning.main;
            case 'low':
            default:
                return theme.palette.success.main;
        }
    };

    // 准备96点价格图表数据（降采样到每15分钟一个点，共96点）
    const preparePriceChartData = (d2Forecast: D2Forecast) => {
        return d2Forecast.hourly_prices.map(p => ({
            time: p.time,
            '预测价格': p.predicted_price,
            '置信区间下限': p.confidence_lower,
            '置信区间上限': p.confidence_upper
        }));
    };

    return (
        <Box sx={{ width: '100%' }}>
            {/* 移动端面包屑标题 */}
            {isTablet && (
                <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 'bold', color: 'text.primary' }}>
                    交易决策 / D-2 交易策略
                </Typography>
            )}

            <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={zhCN}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                    {/* 控制栏 */}
                    <Typography variant="h6" gutterBottom>策略配置</Typography>

                    <Grid container spacing={2} sx={{ mb: 2 }}>
                        <Grid size={{ xs: 12, md: 3 }}>
                            <FormControl fullWidth>
                                <Typography variant="body2" gutterBottom>客户</Typography>
                                <select
                                    value={selectedCustomerId}
                                    onChange={(e) => setSelectedCustomerId(e.target.value)}
                                    style={{ padding: '8px', width: '100%', borderRadius: '4px', border: '1px solid #ccc' }}
                                >
                                    {customers.map((c) => (
                                        <option key={c.id} value={c.id}>{c.name}</option>
                                    ))}
                                </select>
                            </FormControl>
                        </Grid>

                        <Grid size={{ xs: 12, md: 3 }}>
                            <DatePicker
                                label="目标日期"
                                value={targetDate}
                                onChange={(date) => setTargetDate(date)}
                                slotProps={{
                                    textField: {
                                        fullWidth: true
                                    }
                                }}
                            />
                        </Grid>

                        <Grid size={{ xs: 12, md: 6 }}>
                            <FormControl component="fieldset" sx={{ mt: 3 }}>
                                <FormLabel component="legend">对比基准</FormLabel>
                                <Box sx={{ display: 'flex', flexDirection: 'row' }}>
                                    <FormControlLabel
                                        control={
                                            <Checkbox
                                                checked={compareWithCurrent}
                                                onChange={(e) => setCompareWithCurrent(e.target.checked)}
                                            />
                                        }
                                        label="当前合同曲线"
                                    />
                                    <FormControlLabel
                                        control={
                                            <Checkbox
                                                checked={compareWithSpot}
                                                onChange={(e) => setCompareWithSpot(e.target.checked)}
                                            />
                                        }
                                        label="纯现货采购"
                                    />
                                </Box>
                            </FormControl>
                        </Grid>

                        <Grid size={{ xs: 12 }}>
                            <Button
                                variant="contained"
                                onClick={generateStrategy}
                                disabled={loading}
                                sx={{ px: 3, py: 1.5 }}
                            >
                                {loading ? '生成中...' : '生成 D-2 策略'}
                            </Button>
                        </Grid>
                    </Grid>

                    {error && (
                        <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
                    )}

                    {/* 策略概览 */}
                    {strategyData && (
                        <>
                            <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>策略概览</Typography>

                            <Grid container spacing={2}>
                                {/* D-2 预测价格 */}
                                <Grid size={{ xs: 12, md: 4 }}>
                                    <Card>
                                        <CardContent>
                                            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                                D-2 预测价格
                                            </Typography>
                                            <Typography variant="h5">
                                                {strategyData.d2_forecast.avg_price.toFixed(2)} 元/MWh
                                            </Typography>
                                            <Typography variant="body2" color="text.secondary">
                                                区间: [{strategyData.d2_forecast.price_range[0]}, {strategyData.d2_forecast.price_range[1]}]
                                            </Typography>
                                            <Typography variant="body2" sx={{ color: 'info.main', mt: 1 }}>
                                                趋势: {strategyData.d2_forecast.avg_price > strategyData.current_contract.avg_price ? '↑ 上涨' : '↓ 下跌'}
                                                {(((strategyData.d2_forecast.avg_price - strategyData.current_contract.avg_price) / strategyData.current_contract.avg_price) * 100).toFixed(1)}%
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>

                                {/* 合同覆盖分析 */}
                                <Grid size={{ xs: 12, md: 4 }}>
                                    <Card>
                                        <CardContent>
                                            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                                合同覆盖分析
                                            </Typography>
                                            <Typography variant="body2">
                                                当前合同: {strategyData.current_contract.total_amount.toFixed(0)} MWh
                                            </Typography>
                                            <Typography variant="body2">
                                                预测负荷: {strategyData.load_forecast.total_load.toFixed(0)} MWh
                                            </Typography>
                                            <Typography variant="body2">
                                                合同覆盖率: {(strategyData.strategy_recommendations.contract_coverage.overall * 100).toFixed(1)}%
                                            </Typography>
                                            <Typography variant="body2" sx={{ mt: 1 }}>
                                                缺口/盈余: {(strategyData.current_contract.total_amount - strategyData.load_forecast.total_load).toFixed(0)} MWh
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>

                                {/* 策略建议 */}
                                <Grid size={{ xs: 12, md: 4 }}>
                                    <Card>
                                        <CardContent>
                                            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                                策略建议
                                            </Typography>
                                            <Typography variant="body2" sx={{ color: getRecommendationColor(strategyData.strategy_recommendations.overall_recommendation.action), fontWeight: 'bold' }}>
                                                {strategyData.strategy_recommendations.overall_recommendation.action === 'increase_contract' ? '增加合同' :
                                                 strategyData.strategy_recommendations.overall_recommendation.action === 'decrease_contract' ? '减少合同' : '保持'}
                                                : {strategyData.strategy_recommendations.overall_recommendation.amount.toFixed(0)} MWh
                                            </Typography>
                                            <Typography variant="body2">
                                                预期成本差异: {strategyData.strategy_recommendations.overall_recommendation.expected_cost_savings >= 0 ? '+' : ''}{formatCurrency(strategyData.strategy_recommendations.overall_recommendation.expected_cost_savings)}
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                            </Grid>

                            {/* D-2 价格预测图表 */}
                            <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>D-2 价格预测</Typography>

                            <ResponsiveContainer width="100%" height={400}>
                                <AreaChart data={preparePriceChartData(strategyData.d2_forecast)}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis
                                        dataKey="time"
                                        interval={11}
                                        tick={{ fontSize: 12 }}
                                    />
                                    <YAxis />
                                    <Tooltip
                                        labelFormatter={(value) => `时间: ${value}`}
                                        formatter={(value: number, name: string) => [`${value.toFixed(2)} 元/MWh`, name]}
                                    />
                                    <Legend />
                                    <ReferenceLine
                                        y={strategyData.current_contract.avg_price}
                                        label={`合同价: ${strategyData.current_contract.avg_price.toFixed(0)}`}
                                        stroke="red"
                                        strokeDasharray="3 3"
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="置信区间下限"
                                        stackId="1"
                                        stroke="#8884d8"
                                        fill="#8884d8"
                                        fillOpacity={0.1}
                                        hide
                                    />
                                    <Area
                                        type="monotone"
                                        dataKey="置信区间上限"
                                        stackId="2"
                                        stroke="#8884d8"
                                        fill="#8884d8"
                                        fillOpacity={0.2}
                                        hide
                                    />
                                    <Line
                                        type="monotone"
                                        dataKey="预测价格"
                                        stroke="#1976d2"
                                        strokeWidth={2}
                                        dot={false}
                                    />
                                </AreaChart>
                            </ResponsiveContainer>

                            {/* 合同调整建议表 */}
                            <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>合同调整建议</Typography>

                            <TableContainer component={Paper} variant="outlined">
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>时段</TableCell>
                                            <TableCell>预测负荷</TableCell>
                                            <TableCell>合同覆盖率</TableCell>
                                            <TableCell>D-2 预测价</TableCell>
                                            <TableCell>合同价</TableCell>
                                            <TableCell>价差</TableCell>
                                            <TableCell>建议</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {strategyData.strategy_recommendations.period_adjustments.map((adj) => (
                                            <TableRow key={adj.period}>
                                                <TableCell>{adj.period} ({adj.hours})</TableCell>
                                                <TableCell>-</TableCell>
                                                <TableCell>{(adj.coverage * 100).toFixed(1)}%</TableCell>
                                                <TableCell>{adj.predicted_avg_price.toFixed(2)}</TableCell>
                                                <TableCell>{adj.contract_price.toFixed(2)}</TableCell>
                                                <TableCell>{adj.price_spread >= 0 ? '+' : ''}{adj.price_spread.toFixed(2)}</TableCell>
                                                <TableCell>
                                                    <Chip
                                                        label={adj.recommendation === 'increase_contract' ? '增加合同' :
                                                              adj.recommendation === 'decrease_contract' ? '减少合同' : '保持'}
                                                        size="small"
                                                        sx={{
                                                            backgroundColor: getRecommendationColor(adj.recommendation),
                                                            color: 'white'
                                                        }}
                                                    />
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>

                            {/* 调整优先级 */}
                            <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>调整优先级</Typography>

                            <Grid container spacing={2}>
                                {strategyData.strategy_recommendations.period_adjustments
                                    .filter(adj => adj.recommendation !== 'maintain')
                                    .sort((a, b) => b.expected_savings - a.expected_savings)
                                    .slice(0, 3)
                                    .map((adj, index) => (
                                        <Grid size={{ xs: 12, md: 4 }} key={adj.period}>
                                            <Card variant="outlined">
                                                <CardContent>
                                                    <Typography variant="subtitle2" color="text.secondary">
                                                        {index + 1}. {adj.period} ({adj.hours})
                                                    </Typography>
                                                    <Typography variant="body2" sx={{ color: getRecommendationColor(adj.recommendation), fontWeight: 'bold' }}>
                                                        {adj.recommendation === 'increase_contract' ? '增加' : '减少'} {adj.amount.toFixed(0)} MWh
                                                    </Typography>
                                                    <Typography variant="body2" sx={{ color: 'success.main' }}>
                                                        预期{adj.recommendation === 'increase_contract' ? '节省' : '收益'}: {formatCurrency(adj.expected_savings)}
                                                    </Typography>
                                                </CardContent>
                                            </Card>
                                        </Grid>
                                    ))}
                            </Grid>

                            {/* 风险预警 */}
                            {strategyData.risk_alerts.length > 0 && (
                                <>
                                    <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>风险预警</Typography>

                                    <Grid container spacing={2}>
                                        {strategyData.risk_alerts.map((alert, index) => (
                                            <Grid size={{ xs: 12 }} key={index}>
                                                <Alert
                                                    severity={alert.severity === 'high' ? 'error' : alert.severity === 'medium' ? 'warning' : 'success'}
                                                    sx={{ mb: 1 }}
                                                >
                                                    <Typography variant="subtitle2" gutterBottom>
                                                        {alert.type === 'negative_price' ? '负电价预警' :
                                                         alert.type === 'price_spike' ? '价格尖峰预警' :
                                                         alert.type === 'high_volatility' ? '高波动预警' : '风险预警'}
                                                    </Typography>
                                                    <Typography variant="body2">
                                                        时间: {alert.time_range}
                                                        {alert.predicted_price !== undefined && ` | 预测价: ${alert.predicted_price.toFixed(2)} 元/MWh`}
                                                        {alert.std !== undefined && ` | 标准差: ${alert.std.toFixed(2)} 元/MWh`}
                                                    </Typography>
                                                    <Typography variant="body2">
                                                        建议: {alert.recommendation}
                                                    </Typography>
                                                    {alert.potential_loss !== undefined && (
                                                        <Typography variant="body2">
                                                            潜在损失: {formatCurrency(alert.potential_loss)}
                                                        </Typography>
                                                    )}
                                                </Alert>
                                            </Grid>
                                        ))}
                                    </Grid>
                                </>
                            )}
                        </>
                    )}
                </Paper>
            </LocalizationProvider>
        </Box>
    );
};

export default D2TradingStrategyPage;
