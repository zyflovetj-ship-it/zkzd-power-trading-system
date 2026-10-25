import React, { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    Button,
    Grid,
    Slider,
    FormControlLabel,
    Radio,
    RadioGroup,
    FormControl,
    FormLabel,
    CircularProgress,
    Alert,
    Card,
    CardContent,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Tabs,
    Tab,
    useTheme,
    useMediaQuery
} from '@mui/material';
import {
    LocalizationProvider,
    DatePicker
} from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { zhCN } from 'date-fns/locale';
import { format } from 'date-fns';
import {
    PieChart,
    Pie,
    Cell,
    BarChart,
    Bar,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    Area,
    AreaChart
} from 'recharts';
import apiClient from '../api/client';

// 类型定义
type OptimizationObjective = 'cost' | 'risk' | 'balanced';

interface StrategyConfig {
    annual_contract_ratio: number;
    monthly_bid_ratio: number;
    spot_ratio: number;
    optimization_objective: OptimizationObjective;
}

interface TradingMix {
    annual_contract: {
        amount: number;
        ratio: number;
        avg_price: number;
        total_cost: number;
    };
    monthly_bid: {
        amount: number;
        ratio: number;
        avg_price: number;
        total_cost: number;
    };
    spot: {
        amount: number;
        ratio: number;
        avg_price: number;
        total_cost: number;
    };
}

interface OptimizationResults {
    trading_mix: TradingMix;
    total_demand: number;
    blended_cost: number;
    total_cost: number;
    vs_pure_spot: {
        cost_savings: number;
        savings_percentage: number;
    };
    vs_full_contract: {
        cost_increase: number;
        risk_reduction: number;
    };
    risk_metrics: {
        cost_variance: number;
        value_at_risk_95: number;
        sharpe_ratio: number;
        flexibility_score: number;
    };
}

interface TimingRecommendation {
    date: string;
    type: string;
    recommended_amount: number;
    recommended_price_range: number[];
    reasoning: string;
}

interface ScenarioAnalysis {
    base_case: { total_cost: number; var_95: number };
    high_price: { price_deviation: number; total_cost: number; cost_increase: number };
    low_price: { price_deviation: number; total_cost: number; cost_decrease: number };
    high_load: { load_deviation: number; total_cost: number; cost_increase: number };
    low_load: { load_deviation: number; total_cost: number; cost_decrease: number };
}

interface PriceTrendData {
    target_month: { year: number; month: number };
    daily_prices: Array<{
        date: string;
        predicted_price: number;
        confidence_lower: number;
        confidence_upper: number;
    }>;
    price_distribution: {
        min: number;
        max: number;
        mean: number;
        std: number;
        percentiles: {
            p10: number;
            p25: number;
            p50: number;
            p75: number;
            p90: number;
        };
    };
}

interface StrategyData {
    strategy_id: string;
    customer_id: string;
    customer_name: string;
    target_month: { year: number; month: number };
    strategy_config: StrategyConfig;
    optimization_results: OptimizationResults;
    timing_recommendations: TimingRecommendation[];
    scenario_analysis: ScenarioAnalysis;
}

// 颜色配置
const COLORS = {
    annual: '#1976d2',  // primary.main
    monthly: '#2e7d32',  // success.main
    spot: '#ed6c02'      // warning.main
};

export const MonthlyTradingStrategyPage: React.FC = () => {
    const theme = useTheme();
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    // 状态管理
    const [selectedCustomerId, setSelectedCustomerId] = useState<string>('CUST001');
    const [selectedMonth, setSelectedMonth] = useState<Date | null>(new Date());
    const [annualRatio, setAnnualRatio] = useState<number>(70);
    const [monthlyRatio, setMonthlyRatio] = useState<number>(20);
    const [spotRatio, setSpotRatio] = useState<number>(10);
    const [objective, setObjective] = useState<OptimizationObjective>('balanced');

    const [strategyData, setStrategyData] = useState<StrategyData | null>(null);
    const [priceTrendData, setPriceTrendData] = useState<PriceTrendData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [scenarioTab, setScenarioTab] = useState<number>(0);

    const customers = [
        { id: 'CUST001', name: '某某企业' },
        { id: 'CUST002', name: '某某集团' },
        { id: 'CUST003', name: '某某制造' }
    ];

    // 生成策略
    const generateStrategy = async () => {
        if (!selectedMonth) return;

        setLoading(true);
        setError(null);

        try {
            const targetYear = selectedMonth.getFullYear();
            const targetMonthValue = selectedMonth.getMonth() + 1;

            const response = await apiClient.post('/api/v1/trading/monthly-strategy/generate', null, {
                params: {
                    customer_id: selectedCustomerId,
                    target_year: targetYear,
                    target_month: targetMonthValue,
                    annual_contract_ratio: annualRatio / 100,
                    monthly_bid_ratio: monthlyRatio / 100,
                    spot_ratio: spotRatio / 100,
                    optimization_objective: objective
                }
            });

            setStrategyData(response.data);

            // 获取价格走势
            fetchPriceTrend(targetYear, targetMonthValue);
        } catch (err: any) {
            console.error('Error generating strategy:', err);
            setError(err.response?.data?.detail || err.message || '生成策略失败');
            setStrategyData(null);
        } finally {
            setLoading(false);
        }
    };

    // 获取价格走势
    const fetchPriceTrend = async (year: number, month: number) => {
        try {
            const response = await apiClient.get('/api/v1/trading/monthly-strategy/price-trend', {
                params: {
                    target_year: year,
                    target_month: month
                }
            });
            setPriceTrendData(response.data);
        } catch (err: any) {
            console.error('Error fetching price trend:', err);
        }
    };

    // 格式化金额
    const formatCurrency = (value: number): string => {
        if (value >= 10000) {
            return `${(value / 10000).toFixed(1)}万元`;
        }
        return `${value.toFixed(0)}元`;
    };

    // 准备交易组合饼图数据
    const preparePieData = (results: OptimizationResults) => [
        { name: '年度双边', value: results.trading_mix.annual_contract.amount, color: COLORS.annual },
        { name: '月度竞价', value: results.trading_mix.monthly_bid.amount, color: COLORS.monthly },
        { name: '现货采购', value: results.trading_mix.spot.amount, color: COLORS.spot }
    ];

    // 准备情景对比表数据
    const prepareScenarioTableData = (scenario: ScenarioAnalysis) => [
        {
            scenario: '基准情景',
            assumption: '价格预测准确',
            total_cost: formatCurrency(scenario.base_case.total_cost),
            diff: '-',
            var: formatCurrency(scenario.base_case.var_95)
        },
        {
            scenario: '高价情景',
            assumption: `价格+${(scenario.high_price.price_deviation * 100).toFixed(0)}%`,
            total_cost: formatCurrency(scenario.high_price.total_cost),
            diff: `+${formatCurrency(scenario.high_price.cost_increase)}`,
            var: `${formatCurrency(scenario.high_price.cost_increase * 0.4)}`
        },
        {
            scenario: '低价情景',
            assumption: `价格-${(scenario.low_price.price_deviation * -100).toFixed(0)}%`,
            total_cost: formatCurrency(scenario.low_price.total_cost),
            diff: formatCurrency(scenario.low_price.cost_decrease),
            var: `${formatCurrency(scenario.low_price.cost_decrease * 0.15)}`
        },
        {
            scenario: '高负荷情景',
            assumption: `负荷+${(scenario.high_load.load_deviation * 100).toFixed(0)}%`,
            total_cost: formatCurrency(scenario.high_load.total_cost),
            diff: `+${formatCurrency(scenario.high_load.cost_increase)}`,
            var: `${formatCurrency(scenario.high_load.cost_increase * 0.5)}`
        },
        {
            scenario: '低负荷情景',
            assumption: `负荷-${(scenario.low_load.load_deviation * -100).toFixed(0)}%`,
            total_cost: formatCurrency(scenario.low_load.total_cost),
            diff: formatCurrency(scenario.low_load.cost_decrease),
            var: `${formatCurrency(scenario.low_load.cost_decrease * 0.2)}`
        }
    ];

    return (
        <Box sx={{ width: '100%' }}>
            {/* 移动端面包屑标题 */}
            {isTablet && (
                <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 'bold', color: 'text.primary' }}>
                    交易决策 / 月度交易策略
                </Typography>
            )}

            <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={zhCN}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                    {/* 策略配置区 */}
                    <Typography variant="h6" gutterBottom>策略配置</Typography>

                    <Grid container spacing={2} sx={{ mb: 2 }}>
                        <Grid size={{ xs: 12, md: 4 }}>
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

                        <Grid size={{ xs: 12, md: 4 }}>
                            <DatePicker
                                label="目标月份"
                                value={selectedMonth}
                                onChange={(date) => setSelectedMonth(date)}
                                slotProps={{
                                    textField: {
                                        fullWidth: true
                                    }
                                }}
                                views={['year', 'month']}
                                openTo="month"
                            />
                        </Grid>

                        <Grid size={{ xs: 12, md: 4 }}>
                            <FormControl component="fieldset">
                                <FormLabel component="legend">优化目标</FormLabel>
                                <RadioGroup
                                    row
                                    value={objective}
                                    onChange={(e) => setObjective(e.target.value as OptimizationObjective)}
                                >
                                    <FormControlLabel value="cost" control={<Radio />} label="成本优先" />
                                    <FormControlLabel value="risk" control={<Radio />} label="风险优先" />
                                    <FormControlLabel value="balanced" control={<Radio />} label="平衡策略" />
                                </RadioGroup>
                            </FormControl>
                        </Grid>

                        <Grid size={{ xs: 12 }}>
                            <Typography variant="body2" gutterBottom>
                                年度双边比例: {annualRatio}% |
                                月度竞价比例: {monthlyRatio}% |
                                现货采购比例: {spotRatio}%
                            </Typography>
                            <Slider
                                value={annualRatio}
                                onChange={(_, value) => {
                                    setAnnualRatio(value as number);
                                    setMonthlyRatio(100 - (value as number) - spotRatio);
                                }}
                                valueLabelDisplay="auto"
                                valueLabelFormat={(value) => `${value}%`}
                                sx={{ color: COLORS.annual }}
                            />
                            <Slider
                                value={monthlyRatio}
                                onChange={(_, value) => {
                                    setMonthlyRatio(value as number);
                                    setAnnualRatio(100 - spotRatio - (value as number));
                                }}
                                valueLabelDisplay="auto"
                                valueLabelFormat={(value) => `${value}%`}
                                sx={{ color: COLORS.monthly, mt: 1 }}
                            />
                            <Slider
                                value={spotRatio}
                                onChange={(_, value) => {
                                    setSpotRatio(value as number);
                                    setAnnualRatio(100 - monthlyRatio - (value as number));
                                }}
                                valueLabelDisplay="auto"
                                valueLabelFormat={(value) => `${value}%`}
                                sx={{ color: COLORS.spot, mt: 1 }}
                            />
                        </Grid>

                        <Grid size={{ xs: 12 }}>
                            <Button
                                variant="contained"
                                onClick={generateStrategy}
                                disabled={loading}
                                sx={{ px: 3, py: 1.5 }}
                            >
                                {loading ? '生成中...' : '生成交易策略'}
                            </Button>
                        </Grid>
                    </Grid>

                    {error && (
                        <Alert severity="error" sx={{ mt: 2 }}>{error}</Alert>
                    )}

                    {/* 优化建议概览 */}
                    {strategyData && (
                        <>
                            <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>优化建议概览</Typography>

                            <Grid container spacing={2}>
                                {/* 推荐交易组合 */}
                                <Grid size={{ xs: 12, md: 4 }}>
                                    <Card>
                                        <CardContent>
                                            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                                推荐交易组合
                                            </Typography>
                                            <Typography variant="body2" sx={{ color: COLORS.annual }}>
                                                年度双边: {strategyData.optimization_results.trading_mix.annual_contract.amount.toFixed(0)} MWh
                                                ({(strategyData.optimization_results.trading_mix.annual_contract.ratio * 100).toFixed(0)}%)
                                            </Typography>
                                            <Typography variant="body2" sx={{ color: COLORS.monthly }}>
                                                月度竞价: {strategyData.optimization_results.trading_mix.monthly_bid.amount.toFixed(0)} MWh
                                                ({(strategyData.optimization_results.trading_mix.monthly_bid.ratio * 100).toFixed(0)}%)
                                            </Typography>
                                            <Typography variant="body2" sx={{ color: COLORS.spot }}>
                                                现货采购: {strategyData.optimization_results.trading_mix.spot.amount.toFixed(0)} MWh
                                                ({(strategyData.optimization_results.trading_mix.spot.ratio * 100).toFixed(0)}%)
                                            </Typography>
                                            <Typography variant="body2" sx={{ mt: 1, fontWeight: 'bold' }}>
                                                总计: {strategyData.optimization_results.total_demand.toFixed(0)} MWh
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>

                                {/* 预期成本 */}
                                <Grid size={{ xs: 12, md: 4 }}>
                                    <Card>
                                        <CardContent>
                                            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                                预期成本
                                            </Typography>
                                            <Typography variant="body2">
                                                综合成本: {strategyData.optimization_results.blended_cost.toFixed(2)} 元/MWh
                                            </Typography>
                                            <Typography variant="body2" sx={{ color: COLORS.annual }}>
                                                年度双边: {strategyData.optimization_results.trading_mix.annual_contract.avg_price.toFixed(2)} 元/MWh
                                            </Typography>
                                            <Typography variant="body2" sx={{ color: COLORS.monthly }}>
                                                月度竞价: {strategyData.optimization_results.trading_mix.monthly_bid.avg_price.toFixed(2)} 元/MWh
                                            </Typography>
                                            <Typography variant="body2" sx={{ color: COLORS.spot }}>
                                                现货: {strategyData.optimization_results.trading_mix.spot.avg_price.toFixed(2)} 元/MWh
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>

                                {/* 收益指标 */}
                                <Grid size={{ xs: 12, md: 4 }}>
                                    <Card>
                                        <CardContent>
                                            <Typography variant="subtitle2" color="text.secondary" gutterBottom>
                                                收益指标
                                            </Typography>
                                            <Typography variant="body2" sx={{ color: 'success.main' }}>
                                                vs纯现货: 节省 {formatCurrency(strategyData.optimization_results.vs_pure_spot.cost_savings)}
                                                ({strategyData.optimization_results.vs_pure_spot.savings_percentage.toFixed(1)}%)
                                            </Typography>
                                            <Typography variant="body2" sx={{ color: 'info.main' }}>
                                                风险降低: {strategyData.optimization_results.vs_full_contract.risk_reduction.toFixed(1)}%
                                            </Typography>
                                            <Typography variant="body2">
                                                Sharpe比率: {strategyData.optimization_results.risk_metrics.sharpe_ratio.toFixed(2)}
                                            </Typography>
                                            <Typography variant="body2">
                                                灵活性评分: {strategyData.optimization_results.risk_metrics.flexibility_score.toFixed(2)}
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                            </Grid>

                            {/* 交易组合图表 */}
                            <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>交易组合分析</Typography>

                            <Grid container spacing={2}>
                                <Grid size={{ xs: 12, md: 6 }}>
                                    <Typography variant="subtitle2" gutterBottom>组合比例</Typography>
                                    <ResponsiveContainer width="100%" height={300}>
                                        <PieChart>
                                            <Pie
                                                data={preparePieData(strategyData.optimization_results)}
                                                cx="50%"
                                                cy="50%"
                                                labelLine={false}
                                                label={({ name, percent }: any) => `${name} ${(percent * 100).toFixed(0)}%`}
                                                outerRadius={80}
                                                fill="#8884d8"
                                                dataKey="value"
                                            >
                                                {preparePieData(strategyData.optimization_results).map((entry, index) => (
                                                    <Cell key={`cell-${index}`} fill={entry.color} />
                                                ))}
                                            </Pie>
                                            <Tooltip formatter={(value: number) => `${value.toFixed(0)} MWh`} />
                                        </PieChart>
                                    </ResponsiveContainer>
                                </Grid>

                                <Grid size={{ xs: 12, md: 6 }}>
                                    <Typography variant="subtitle2" gutterBottom>情景对比表</Typography>
                                    <TableContainer component={Paper} variant="outlined">
                                        <Table size="small">
                                            <TableHead>
                                                <TableRow>
                                                    <TableCell>情景</TableCell>
                                                    <TableCell>综合成本</TableCell>
                                                    <TableCell>对基准差异</TableCell>
                                                </TableRow>
                                            </TableHead>
                                            <TableBody>
                                                {prepareScenarioTableData(strategyData.scenario_analysis).map((row) => (
                                                    <TableRow key={row.scenario}>
                                                        <TableCell>{row.scenario}</TableCell>
                                                        <TableCell>{row.total_cost}</TableCell>
                                                        <TableCell>{row.diff}</TableCell>
                                                    </TableRow>
                                                ))}
                                            </TableBody>
                                        </Table>
                                    </TableContainer>
                                </Grid>
                            </Grid>

                            {/* 价格走势分析 */}
                            {priceTrendData && (
                                <>
                                    <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>价格走势分析</Typography>
                                    <ResponsiveContainer width="100%" height={350}>
                                        <AreaChart data={priceTrendData.daily_prices}>
                                            <CartesianGrid strokeDasharray="3 3" />
                                            <XAxis
                                                dataKey="date"
                                                tickFormatter={(value) => value.substring(5)}
                                                interval={4}
                                            />
                                            <YAxis />
                                            <Tooltip
                                                labelFormatter={(value) => `日期: ${value}`}
                                                formatter={(value: number) => [`${value.toFixed(2)} 元/MWh`, '预测价格']}
                                            />
                                            <Legend />
                                            <Area
                                                type="monotone"
                                                dataKey="predicted_price"
                                                stroke="#1976d2"
                                                fill="#1976d2"
                                                fillOpacity={0.3}
                                                name="预测价格"
                                            />
                                        </AreaChart>
                                    </ResponsiveContainer>
                                </>
                            )}

                            {/* 交易执行计划 */}
                            <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>交易执行计划</Typography>

                            <Grid container spacing={2}>
                                <Grid size={{ xs: 12 }}>
                                    <Paper variant="outlined" sx={{ p: 2 }}>
                                        <Typography variant="subtitle2" gutterBottom>交易时间表</Typography>
                                        {strategyData.timing_recommendations.map((rec, index) => (
                                            <Typography key={index} variant="body2" sx={{ mb: 1 }}>
                                                <strong>{rec.date}</strong> ({rec.type}): {rec.recommended_amount.toFixed(0)} MWh,
                                                价格区间: [{rec.recommended_price_range[0]}, {rec.recommended_price_range[1]}] 元/MWh
                                                <br />
                                                <span style={{ color: 'text.secondary', fontSize: '0.875rem' }}>
                                                    {rec.reasoning}
                                                </span>
                                            </Typography>
                                        ))}
                                    </Paper>
                                </Grid>

                                <Grid size={{ xs: 12 }}>
                                    <Paper variant="outlined" sx={{ p: 2 }}>
                                        <Typography variant="subtitle2" gutterBottom>价格预警</Typography>
                                        <Typography variant="body2">
                                            目标价格区间: [350, 400] 元/MWh
                                        </Typography>
                                        <Typography variant="body2" sx={{ color: 'warning.main' }}>
                                            超过预警阈值: 450 元/MWh (建议观望)
                                        </Typography>
                                        <Typography variant="body2" sx={{ color: 'success.main' }}>
                                            低于抄底价格: 300 元/MWh (建议加大采购)
                                        </Typography>
                                    </Paper>
                                </Grid>
                            </Grid>
                        </>
                    )}
                </Paper>
            </LocalizationProvider>
        </Box>
    );
};

export default MonthlyTradingStrategyPage;
