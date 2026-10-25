import React, { useState } from 'react';
import {
    Box, Paper, Typography, Button, Grid, Card, CardContent,
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow,
    Alert, useTheme, useMediaQuery, Chip
} from '@mui/material';
import { LocalizationProvider, DatePicker } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { zhCN } from 'date-fns/locale';
import { format, addDays } from 'date-fns';
import {
    AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, Legend,
    ResponsiveContainer, ReferenceLine, BarChart, Bar
} from 'recharts';
import apiClient from '../api/client';

// 类型定义
interface HourlyPlan {
    time: string;
    predicted_load: number;
    contract_amount: number;
    day_ahead_amount: number;
    day_ahead_predicted_price: number;
    total_cost: number;
}

interface PlanData {
    plan_id: string;
    customer_id: string;
    customer_name: string;
    target_date: string;
    d1_forecast: {
        avg_price: number;
        hourly_prices: Array<{ time: string; predicted_price: number }>;
    };
    load_forecast: { total_load: number };
    hourly_trading_plan: HourlyPlan[];
    priority_recommendations: Array<{
        time_slot: string;
        priority: number;
        predicted_price: number;
        day_ahead_amount: number;
        expected_savings: number;
        reasoning: string;
    }>;
    risk_alerts: Array<{
        type: string;
        severity: string;
        time_slot: string;
        recommendation: string;
    }>;
}

export const DayAheadTradingStrategyPage: React.FC = () => {
    const theme = useTheme();
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    const [selectedCustomerId, setSelectedCustomerId] = useState<string>('CUST001');
    const [targetDate, setTargetDate] = useState<Date | null>(addDays(new Date(), 1));
    const [strategyType, setStrategyType] = useState<'conservative' | 'balanced' | 'aggressive'>('balanced');

    const [planData, setPlanData] = useState<PlanData | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const customers = [
        { id: 'CUST001', name: '某某企业' },
        { id: 'CUST002', name: '某某集团' },
        { id: 'CUST003', name: '某某制造' }
    ];

    const generatePlan = async () => {
        if (!targetDate) return;
        setLoading(true);
        setError(null);
        try {
            const response = await apiClient.post('/api/v1/trading/day-ahead-strategy/generate', null, {
                params: {
                    customer_id: selectedCustomerId,
                    target_date: format(targetDate, 'yyyy-MM-dd'),
                    strategy_type: strategyType
                }
            });
            setPlanData(response.data);
        } catch (err: any) {
            console.error('Error:', err);
            setError(err.response?.data?.detail || err.message || '生成方案失败');
            setPlanData(null);
        } finally {
            setLoading(false);
        }
    };

    const formatCurrency = (value: number): string => {
        if (value >= 10000) return `${(value / 10000).toFixed(2)}万元`;
        return `${value.toFixed(0)}元`;
    };

    const prepareChartData = (plan: PlanData) => {
        return plan.hourly_trading_plan.slice(0, 96).map(p => ({
            time: p.time,
            '预测负荷': p.predicted_load,
            '合同电量': p.contract_amount,
            '日前采购': p.day_ahead_amount,
            '预测价格': p.day_ahead_predicted_price
        }));
    };

    return (
        <Box sx={{ width: '100%' }}>
            {isTablet && (
                <Typography variant="subtitle1" sx={{ mb: 2, fontWeight: 'bold', color: 'text.primary' }}>
                    交易决策 / 日前交易策略
                </Typography>
            )}

            <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={zhCN}>
                <Paper variant="outlined" sx={{ p: 2 }}>
                    <Typography variant="h6" gutterBottom>策略配置</Typography>

                    <Grid container spacing={2} sx={{ mb: 2 }}>
                        <Grid size={{ xs: 12, md: 3 }}>
                            <Typography variant="body2" gutterBottom>客户</Typography>
                            <select
                                value={selectedCustomerId}
                                onChange={(e) => setSelectedCustomerId(e.target.value)}
                                style={{ padding: '8px', width: '100%', borderRadius: '4px', border: '1px solid #ccc' }}
                            >
                                {customers.map(c => <option key={c.id} value={c.id}>{c.name}</option>)}
                            </select>
                        </Grid>

                        <Grid size={{ xs: 12, md: 3 }}>
                            <DatePicker
                                label="目标日期"
                                value={targetDate}
                                onChange={(date) => setTargetDate(date)}
                                slotProps={{ textField: { fullWidth: true } }}
                            />
                        </Grid>

                        <Grid size={{ xs: 12, md: 3 }}>
                            <Typography variant="body2" gutterBottom>策略类型</Typography>
                            <select
                                value={strategyType}
                                onChange={(e) => setStrategyType(e.target.value as any)}
                                style={{ padding: '8px', width: '100%', borderRadius: '4px', border: '1px solid #ccc' }}
                            >
                                <option value="conservative">保守策略</option>
                                <option value="balanced">平衡策略</option>
                                <option value="aggressive">激进策略</option>
                            </select>
                        </Grid>

                        <Grid size={{ xs: 12 }}>
                            <Button variant="contained" onClick={generatePlan} disabled={loading}>
                                {loading ? '生成中...' : '生成日前方案'}
                            </Button>
                        </Grid>
                    </Grid>

                    {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

                    {planData && (
                        <>
                            <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>方案概览</Typography>

                            <Grid container spacing={2}>
                                <Grid size={{ xs: 12, md: 4 }}>
                                    <Card>
                                        <CardContent>
                                            <Typography variant="subtitle2" color="text.secondary">D-1 预测价格</Typography>
                                            <Typography variant="h5">{planData.d1_forecast.avg_price.toFixed(2)} 元/MWh</Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                                <Grid size={{ xs: 12, md: 4 }}>
                                    <Card>
                                        <CardContent>
                                            <Typography variant="subtitle2" color="text.secondary">预测负荷</Typography>
                                            <Typography variant="h5">{planData.load_forecast.total_load.toFixed(0)} MWh</Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                                <Grid size={{ xs: 12, md: 4 }}>
                                    <Card>
                                        <CardContent>
                                            <Typography variant="subtitle2" color="text.secondary">策略类型</Typography>
                                            <Typography variant="h5">
                                                {strategyType === 'conservative' ? '保守' : strategyType === 'balanced' ? '平衡' : '激进'}
                                            </Typography>
                                        </CardContent>
                                    </Card>
                                </Grid>
                            </Grid>

                            <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>96点交易方案</Typography>

                            <ResponsiveContainer width="100%" height={400}>
                                <AreaChart data={prepareChartData(planData)}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="time" interval={11} tick={{ fontSize: 12 }} />
                                    <YAxis yAxisId="left" orientation="left" />
                                    <YAxis yAxisId="right" orientation="right" />
                                    <Tooltip />
                                    <Legend />
                                    <Area yAxisId="left" type="monotone" dataKey="合同电量" stackId="1" stroke="#1976d2" fill="#1976d2" fillOpacity={0.6} />
                                    <Area yAxisId="left" type="monotone" dataKey="日前采购" stackId="1" stroke="#2e7d32" fill="#2e7d32" fillOpacity={0.6} />
                                </AreaChart>
                            </ResponsiveContainer>

                            {planData.priority_recommendations.length > 0 && (
                                <>
                                    <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>高优先级交易建议</Typography>

                                    {planData.priority_recommendations.map((rec, index) => (
                                        <Alert key={index} severity="info" sx={{ mb: 1 }}>
                                            <Typography variant="subtitle2">
                                                {index + 1}. {rec.time_slot} - 预期节省: {formatCurrency(rec.expected_savings)}
                                            </Typography>
                                            <Typography variant="body2">{rec.reasoning}</Typography>
                                        </Alert>
                                    ))}
                                </>
                            )}

                            {planData.risk_alerts.length > 0 && (
                                <>
                                    <Typography variant="h6" sx={{ mt: 4, mb: 2 }}>风险预警</Typography>

                                    {planData.risk_alerts.map((alert, index) => (
                                        <Alert
                                            key={index}
                                            severity={alert.severity === 'high' ? 'error' : 'warning'}
                                            sx={{ mb: 1 }}
                                        >
                                            <Typography variant="subtitle2">
                                                {alert.type === 'negative_price' ? '负电价预警' : '价格尖峰预警'}
                                            </Typography>
                                            <Typography variant="body2">{alert.recommendation}</Typography>
                                        </Alert>
                                    ))}
                                </>
                            )}
                        </>
                    )}
                </Paper>
            </LocalizationProvider>
        </Box>
    );
};

export default DayAheadTradingStrategyPage;
