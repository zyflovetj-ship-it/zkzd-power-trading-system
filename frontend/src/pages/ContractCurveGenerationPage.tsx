import React, { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    useMediaQuery,
    useTheme,
    Tab,
    Tabs,
    CircularProgress,
    Alert,
    Button,
    Grid,
    Card,
    CardContent,
} from '@mui/material';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { zhCN } from 'date-fns/locale';
import {
    LineChart,
    Line,
    AreaChart,
    Area,
    BarChart,
    Bar,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer,
    ComposedChart,
} from 'recharts';

import apiClient from '../api/client';

interface ContractCurveData {
    curve_id: string;
    customer_id: string;
    customer_name: string;
    contract_month: {
        year: number;
        month: number;
    };
    optimization_params: {
        objective: string;
        contract_coverage: number;
        risk_aversion: number;
    };
    daily_contracts: Array<{
        date: string;
        predicted_load: number;
        contract_amount: number;
        spot_amount: number;
        contract_price: number;
        predicted_spot_price: number;
        contract_cost: number;
        predicted_spot_cost: number;
        total_cost: number;
    }>;
    summary: {
        total_contract_amount: number;
        total_spot_amount: number;
        total_demand: number;
        contract_coverage: number;
        avg_contract_price: number;
        total_cost: number;
        contract_cost: number;
        spot_cost: number;
        blended_cost: number;
        price_variance: number;
        value_at_risk_95: number;
        sharpe_ratio: number;
        vs_pure_spot: {
            cost_difference: number;
            cost_percentage: number;
        };
        vs_equal_contract: {
            cost_difference: number;
            cost_percentage: number;
        };
    };
    created_at: string;
    status: string;
}

interface ScenarioData {
    scenario_type: string;
    data: Array<{
        price_deviation?: number;
        load_deviation?: number;
        scenario_name?: string;
        total_cost: number;
        cost_change: number;
    }>;
}

type OptimizationObjective = 'cost_min' | 'risk_min' | 'balanced';

export const ContractCurveGenerationPage: React.FC = () => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('md'));

    // 状态管理
    const [selectedCustomerId, setSelectedCustomerId] = useState<string>('CUST001');
    const [selectedMonth, setSelectedMonth] = useState<Date>(new Date());
    const [objective, setObjective] = useState<OptimizationObjective>('balanced');
    const [contractCoverage, setContractCoverage] = useState<number>(0.85);

    const [curveData, setCurveData] = useState<ContractCurveData | null>(null);
    const [priceScenarios, setPriceScenarios] = useState<ScenarioData | null>(null);
    const [loadScenarios, setLoadScenarios] = useState<ScenarioData | null>(null);
    const [scenarioTab, setScenarioTab] = useState<number>(0);

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // 生成合同曲线
    const generateCurve = async () => {
        if (!selectedMonth) return;

        setLoading(true);
        setError(null);

        const targetYear = selectedMonth.getFullYear();
        const targetMonthValue = selectedMonth.getMonth() + 1;

        try {
            const response = await apiClient.post('/api/v1/trading/contract-curve/generate', null, {
                params: {
                    customer_id: selectedCustomerId,
                    target_year: targetYear,
                    target_month: targetMonthValue,
                    objective,
                    contract_coverage: contractCoverage
                }
            });

            setCurveData(response.data);

            // 获取情景分析
            fetchPriceScenarios();
            fetchLoadScenarios();
        } catch (err: any) {
            console.error('生成合同曲线失败:', err);
            setError(err.response?.data?.detail || err.message || '生成合同曲线失败');
            setCurveData(null);
        } finally {
            setLoading(false);
        }
    };

    // 获取价格敏感度分析
    const fetchPriceScenarios = async () => {
        if (!curveData) return;
        try {
            const response = await apiClient.get('/api/v1/trading/contract-curve/scenarios', {
                params: {
                    curve_id: curveData.curve_id,
                    scenario_type: 'price_sensitivity'
                }
            });
            setPriceScenarios(response.data);
        } catch (err: any) {
            console.warn('获取价格敏感度失败:', err);
        }
    };

    // 获取负荷敏感度分析
    const fetchLoadScenarios = async () => {
        if (!curveData) return;
        try {
            const response = await apiClient.get('/api/v1/trading/contract-curve/scenarios', {
                params: {
                    curve_id: curveData.curve_id,
                    scenario_type: 'load_sensitivity'
                }
            });
            setLoadScenarios(response.data);
        } catch (err: any) {
            console.warn('获取负荷敏感度失败:', err);
        }
    };

    // 格式化货币
    const formatCurrency = (value: number): string => {
        return new Intl.NumberFormat('zh-CN', {
            style: 'currency',
            currency: 'CNY',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(value);
    };

    return (
        <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={zhCN}>
            <Box sx={{ width: '100%' }}>
                {/* 移动端面包屑标题 */}
                {isMobile && (
                    <Typography
                        variant="subtitle1"
                        sx={{
                            mb: 2,
                            fontWeight: 'bold',
                            color: 'text.primary'
                        }}
                    >
                        交易决策 / 合同曲线生成
                    </Typography>
                )}

                {/* 控制栏 */}
                <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                    <Typography variant="h6" gutterBottom>
                        优化参数配置
                    </Typography>

                    <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                        {/* 客户和月份选择 */}
                        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                            <Box sx={{ minWidth: 200 }}>
                                <Typography variant="body2" gutterBottom>
                                    选择客户
                                </Typography>
                                <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                                    某某制造企业
                                </Typography>
                            </Box>

                            <Box sx={{ minWidth: 200 }}>
                                <Typography variant="body2" gutterBottom>
                                    目标月份
                                </Typography>
                                <Typography variant="body1" sx={{ fontWeight: 'bold' }}>
                                    {selectedMonth.getFullYear()}年{selectedMonth.getMonth() + 1}月
                                </Typography>
                            </Box>
                        </Box>

                        {/* 优化目标选择 */}
                        <Box>
                            <Typography variant="body2" gutterBottom>
                                优化目标
                            </Typography>
                            <Box sx={{ display: 'flex', gap: 2 }}>
                                <Typography
                                    variant="body2"
                                    onClick={() => setObjective('cost_min')}
                                    sx={{
                                        cursor: 'pointer',
                                        px: 2,
                                        py: 1,
                                        border: 1,
                                        borderColor: objective === 'cost_min' ? 'primary.main' : 'divider',
                                        borderRadius: 1,
                                        bgcolor: objective === 'cost_min' ? 'primary.50' : 'transparent'
                                    }}
                                >
                                    成本最小化
                                </Typography>
                                <Typography
                                    variant="body2"
                                    onClick={() => setObjective('balanced')}
                                    sx={{
                                        cursor: 'pointer',
                                        px: 2,
                                        py: 1,
                                        border: 1,
                                        borderColor: objective === 'balanced' ? 'primary.main' : 'divider',
                                        borderRadius: 1,
                                        bgcolor: objective === 'balanced' ? 'primary.50' : 'transparent'
                                    }}
                                >
                                    平衡策略
                                </Typography>
                                <Typography
                                    variant="body2"
                                    onClick={() => setObjective('risk_min')}
                                    sx={{
                                        cursor: 'pointer',
                                        px: 2,
                                        py: 1,
                                        border: 1,
                                        borderColor: objective === 'risk_min' ? 'primary.main' : 'divider',
                                        borderRadius: 1,
                                        bgcolor: objective === 'risk_min' ? 'primary.50' : 'transparent'
                                    }}
                                >
                                    风险最小化
                                </Typography>
                            </Box>
                        </Box>

                        {/* 合同覆盖率滑块 */}
                        <Box>
                            <Typography variant="body2" gutterBottom>
                                合同覆盖率: {(contractCoverage * 100).toFixed(0)}%
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                调整滑块以设置合同电量覆盖预测负荷的比例
                            </Typography>
                        </Box>

                        {/* 生成按钮 */}
                        <Box>
                            <Button
                                variant="contained"
                                onClick={generateCurve}
                                disabled={loading}
                                sx={{ px: 3, py: 1.5 }}
                            >
                                {loading ? '生成中...' : '生成合同曲线'}
                            </Button>
                        </Box>
                    </Box>
                </Paper>

                {/* 错误提示 */}
                {error && (
                    <Paper variant="outlined" sx={{ p: 2, mb: 2, borderColor: 'error.main', bgcolor: 'error.50' }}>
                        <Typography color="error">{error}</Typography>
                    </Paper>
                )}

                {/* 优化结果概览 */}
                {curveData && !loading && (
                    <>
                        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                            <Typography variant="h6" gutterBottom>
                                优化结果概览
                            </Typography>

                            {/* 核心指标卡片 */}
                            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', mb: 2 }}>
                                <Box sx={{ flex: '1 1 200px', p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                                    <Typography variant="caption" color="text.secondary">
                                        总合同电量
                                    </Typography>
                                    <Typography variant="h5">
                                        {curveData.summary.total_contract_amount.toFixed(0)} MWh
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        覆盖率: {(curveData.summary.contract_coverage * 100).toFixed(1)}%
                                    </Typography>
                                </Box>

                                <Box sx={{ flex: '1 1 200px', p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                                    <Typography variant="caption" color="text.secondary">
                                        月度合同均价
                                    </Typography>
                                    <Typography variant="h5">
                                        {curveData.summary.avg_contract_price.toFixed(0)} 元/MWh
                                    </Typography>
                                </Box>

                                <Box sx={{ flex: '1 1 200px', p: 2, border: 1, borderColor: 'divider', borderRadius: 1 }}>
                                    <Typography variant="caption" color="text.secondary">
                                        预计总成本
                                    </Typography>
                                    <Typography variant="h5">
                                        {formatCurrency(curveData.summary.total_cost)}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        均价: {curveData.summary.blended_cost.toFixed(0)} 元/MWh
                                    </Typography>
                                </Box>

                                <Box sx={{ flex: '1 1 200px', p: 2, border: 1, borderColor: 'success.main', borderRadius: 1, bgcolor: 'success.50' }}>
                                    <Typography variant="caption" color="text.secondary">
                                        vs纯现货节省
                                    </Typography>
                                    <Typography variant="h5" color="success.main">
                                        {formatCurrency(curveData.summary.vs_pure_spot.cost_difference)}
                                    </Typography>
                                    <Typography variant="caption" color="text.secondary">
                                        {curveData.summary.vs_pure_spot.cost_percentage.toFixed(2)}%
                                    </Typography>
                                </Box>
                            </Box>

                            {/* 风险指标 */}
                            <Box sx={{ mt: 2 }}>
                                <Typography variant="subtitle2" gutterBottom>
                                    风险指标
                                </Typography>
                                <Box sx={{ display: 'flex', gap: 3, flexWrap: 'wrap' }}>
                                    <Box>
                                        <Typography variant="body2" color="text.secondary">
                                            价格风险敞口: {formatCurrency(curveData.summary.spot_cost)}
                                        </Typography>
                                    </Box>
                                    <Box>
                                        <Typography variant="body2" color="text.secondary">
                                            VaR 95%: {formatCurrency(curveData.summary.value_at_risk_95)}
                                        </Typography>
                                    </Box>
                                    <Box>
                                        <Typography variant="body2" color="text.secondary">
                                            夏普比率: {curveData.summary.sharpe_ratio.toFixed(2)}
                                        </Typography>
                                    </Box>
                                </Box>
                            </Box>
                        </Paper>

                        {/* 合同曲线图表 */}
                        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                            <Typography variant="h6" gutterBottom>
                                日度合同曲线
                            </Typography>

                            <ResponsiveContainer width="100%" height={400}>
                                <ComposedChart data={curveData.daily_contracts}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis
                                        dataKey="date"
                                        tick={{ fontSize: 12 }}
                                        interval={Math.ceil(curveData.daily_contracts.length / 10)}
                                    />
                                    <YAxis yAxisId="left" label={{ value: '电量 (MWh)', position: 'insideLeft', angle: -90 }} />
                                    <YAxis yAxisId="right" orientation="right" label={{ value: '成本 (元)', position: 'insideRight', angle: 90 }} />
                                    <Tooltip
                                        labelFormatter={(value) => `日期: ${value}`}
                                        formatter={(value: number, name: string) => {
                                            if (name === '预测负荷' || name === '合同电量' || name === '现货采购') {
                                                return [`${value.toFixed(0)} MWh`, name];
                                            }
                                            return [`${value.toFixed(0)} 元`, name];
                                        }}
                                    />
                                    <Legend />
                                    <Area
                                        yAxisId="left"
                                        type="monotone"
                                        dataKey="predicted_load"
                                        name="预测负荷"
                                        stroke="#999999"
                                        fill="#999999"
                                        fillOpacity={0.1}
                                        strokeDasharray="5 5"
                                    />
                                    <Area
                                        yAxisId="left"
                                        type="monotone"
                                        dataKey="contract_amount"
                                        name="合同电量"
                                        stroke="#1976d2"
                                        fill="#1976d2"
                                        fillOpacity={0.3}
                                    />
                                    <Area
                                        yAxisId="left"
                                        type="monotone"
                                        dataKey="spot_amount"
                                        name="现货采购"
                                        stroke="#ed6c02"
                                        fill="#ed6c02"
                                        fillOpacity={0.3}
                                    />
                                </ComposedChart>
                            </ResponsiveContainer>
                        </Paper>

                        {/* 成本构成图表 */}
                        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                            <Typography variant="h6" gutterBottom>
                                日度成本构成
                            </Typography>

                            <ResponsiveContainer width="100%" height={350}>
                                <BarChart data={curveData.daily_contracts}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis
                                        dataKey="date"
                                        tick={{ fontSize: 12 }}
                                        interval={Math.ceil(curveData.daily_contracts.length / 10)}
                                    />
                                    <YAxis label={{ value: '成本 (元)', position: 'insideLeft', angle: -90 }} />
                                    <Tooltip
                                        labelFormatter={(value) => `日期: ${value}`}
                                        formatter={(value: number) => [`${value.toFixed(0)} 元`, '']}
                                    />
                                    <Legend />
                                    <Bar dataKey="contract_cost" name="合同成本" stackId="cost" fill="#1976d2" />
                                    <Bar dataKey="predicted_spot_cost" name="现货成本" stackId="cost" fill="#ed6c02" />
                                </BarChart>
                            </ResponsiveContainer>
                        </Paper>

                        {/* 情景分析 */}
                        <Paper variant="outlined" sx={{ p: 2 }}>
                            <Typography variant="h6" gutterBottom>
                                情景分析
                            </Typography>

                            <Box sx={{ borderBottom: 1, borderColor: 'divider', mb: 2 }}>
                                <Tabs value={scenarioTab} onChange={(_, newValue) => setScenarioTab(newValue)}>
                                    <Tab label="价格敏感度" />
                                    <Tab label="负荷敏感度" />
                                </Tabs>
                            </Box>

                            {/* 价格敏感度面板 */}
                            {scenarioTab === 0 && priceScenarios && (
                                <Box>
                                    <Typography variant="body2" gutterBottom sx={{ fontWeight: 'bold', mb: 2 }}>
                                        价格偏离度对总成本的影响
                                    </Typography>

                                    {/* 价格敏感度图表 */}
                                    <ResponsiveContainer width="100%" height={300}>
                                        <AreaChart data={priceScenarios.data}>
                                            <CartesianGrid strokeDasharray="3 3" />
                                            <XAxis
                                                dataKey="price_deviation"
                                                tickFormatter={(value) => `${(value * 100).toFixed(0)}%`}
                                            />
                                            <YAxis label={{ value: '总成本 (元)', position: 'insideLeft', angle: -90 }} />
                                            <Tooltip
                                                labelFormatter={(value) => `价格偏离: ${(value * 100).toFixed(0)}%`}
                                                formatter={(value: number) => formatCurrency(value)}
                                            />
                                            <Area
                                                type="monotone"
                                                dataKey="total_cost"
                                                stroke="#1976d2"
                                                fill="#1976d2"
                                                fillOpacity={0.3}
                                                name="总成本"
                                            />
                                        </AreaChart>
                                    </ResponsiveContainer>

                                    {/* 数据表格 */}
                                    <Box sx={{ mt: 2 }}>
                                        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                                            {priceScenarios.data.map((item, index) => (
                                                <Box
                                                    key={index}
                                                    sx={{
                                                        p: 2,
                                                        border: 1,
                                                        borderColor: 'divider',
                                                        borderRadius: 1,
                                                        bgcolor: item.price_deviation === 0 ? 'primary.50' : 'transparent'
                                                    }}
                                                >
                                                    <Typography variant="caption" color="text.secondary" display="block">
                                                        价格偏离
                                                    </Typography>
                                                    <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                                                        {item.price_deviation! > 0 ? '+' : ''}{(item.price_deviation! * 100).toFixed(0)}%
                                                    </Typography>
                                                    <Typography variant="body2" color="text.secondary">
                                                        总成本: {formatCurrency(item.total_cost)}
                                                    </Typography>
                                                    <Typography
                                                        variant="body2"
                                                        color={item.cost_change > 0 ? 'error.main' : 'success.main'}
                                                    >
                                                        变化: {item.cost_change > 0 ? '+' : ''}{formatCurrency(item.cost_change)}
                                                    </Typography>
                                                </Box>
                                            ))}
                                        </Box>
                                    </Box>
                                </Box>
                            )}

                            {scenarioTab === 0 && !priceScenarios && (
                                <Box sx={{ py: 4, textAlign: 'center', color: 'text.secondary' }}>
                                    <Typography>暂无价格敏感度数据</Typography>
                                </Box>
                            )}

                            {/* 负荷敏感度面板 */}
                            {scenarioTab === 1 && loadScenarios && (
                                <Box>
                                    <Typography variant="body2" gutterBottom sx={{ fontWeight: 'bold', mb: 2 }}>
                                        负荷变化对总成本的影响
                                    </Typography>

                                    {/* 负荷敏感度图表 */}
                                    <ResponsiveContainer width="100%" height={300}>
                                        <BarChart data={loadScenarios.data}>
                                            <CartesianGrid strokeDasharray="3 3" />
                                            <XAxis dataKey="scenario_name" />
                                            <YAxis label={{ value: '总成本 (元)', position: 'insideLeft', angle: -90 }} />
                                            <Tooltip formatter={(value: number) => formatCurrency(value)} />
                                            <Legend />
                                            <Bar dataKey="total_cost" name="总成本" fill="#2e7d32" />
                                        </BarChart>
                                    </ResponsiveContainer>

                                    {/* 数据表格 */}
                                    <Box sx={{ mt: 2 }}>
                                        <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap' }}>
                                            {loadScenarios.data.map((item, index) => (
                                                <Box
                                                    key={index}
                                                    sx={{
                                                        p: 2,
                                                        border: 1,
                                                        borderColor: 'divider',
                                                        borderRadius: 1,
                                                        bgcolor: item.load_deviation === 0 ? 'primary.50' : 'transparent'
                                                    }}
                                                >
                                                    <Typography variant="caption" color="text.secondary" display="block">
                                                        {item.scenario_name}
                                                    </Typography>
                                                    <Typography variant="h6" sx={{ fontWeight: 'bold' }}>
                                                        {item.load_deviation! > 0 ? '+' : ''}{(item.load_deviation! * 100).toFixed(0)}%
                                                    </Typography>
                                                    <Typography variant="body2" color="text.secondary">
                                                        总成本: {formatCurrency(item.total_cost)}
                                                    </Typography>
                                                    <Typography
                                                        variant="body2"
                                                        color={item.cost_change > 0 ? 'error.main' : 'success.main'}
                                                    >
                                                        变化: {item.cost_change > 0 ? '+' : ''}{formatCurrency(item.cost_change)}
                                                    </Typography>
                                                </Box>
                                            ))}
                                        </Box>
                                    </Box>
                                </Box>
                            )}

                            {scenarioTab === 1 && !loadScenarios && (
                                <Box sx={{ py: 4, textAlign: 'center', color: 'text.secondary' }}>
                                    <Typography>暂无负荷敏感度数据</Typography>
                                </Box>
                            )}
                        </Paper>
                    </>
                )}

                {/* 首次加载提示 */}
                {!curveData && !loading && !error && (
                    <Paper variant="outlined" sx={{ p: 4, textAlign: 'center', bgcolor: 'grey.50' }}>
                        <Typography variant="body1" color="text.secondary">
                            请配置优化参数并点击"生成合同曲线"按钮
                        </Typography>
                    </Paper>
                )}
            </Box>
        </LocalizationProvider>
    );
};
