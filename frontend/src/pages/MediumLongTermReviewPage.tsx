import React, { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    Grid,
    Card,
    CardContent,
    Table,
    TableBody,
    TableCell,
    TableContainer,
    TableHead,
    TableRow,
    Alert,
    CircularProgress
} from '@mui/material';
import { LocalizationProvider, DatePicker } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { zhCN } from 'date-fns/locale';
import { format, subMonths } from 'date-fns';
import {
    AreaChart,
    Area,
    BarChart,
    Bar,
    LineChart,
    Line,
    XAxis,
    YAxis,
    CartesianGrid,
    Tooltip,
    Legend,
    ResponsiveContainer
} from 'recharts';
import apiClient from '../api/client';

interface ExecutionMetrics {
    planned_contract_coverage: number;
    actual_contract_coverage: number;
    execution_rate: number;
    avg_deviation: number;
    max_deviation_amount: number;
}

interface CostMetrics {
    contract_cost: number;
    spot_cost: number;
    total_cost: number;
    blended_price: number;
    market_cost: number;
    cost_savings: number;
    savings_percentage: number;
}

interface TimingAnalysis {
    avg_days_before_effective: number;
    avg_price_advantage_at_signing: number;
    timing_accuracy: number;
}

interface Strategy {
    strategy: string;
    contract_coverage: number;
    total_cost: number;
    risk_score: string;
}

interface Anomaly {
    date: string;
    type: string;
    description: string;
    deviation: number;
    impact_cost: number;
    recommendation: string;
}

interface ReviewSummary {
    highlights: string[];
    issues: string[];
    recommendations: Array<{
        priority: number;
        action: string;
        reason: string;
        suggestion: string;
        expected_benefit: string;
    }>;
}

interface ReviewData {
    review_id: string;
    customer_id: string;
    customer_name: string;
    review_period: {
        start_date: string;
        end_date: string;
        type: string;
    };
    execution_metrics: ExecutionMetrics;
    cost_metrics: CostMetrics;
    timing_analysis: TimingAnalysis;
    strategy_comparison: Strategy[];
    anomalies: Anomaly[];
    summary: ReviewSummary;
    generated_at: string;
}

export const MediumLongTermReviewPage: React.FC = () => {
    const [selectedCustomerId, setSelectedCustomerId] = useState<string>('CUST001');
    const [startDate, setStartDate] = useState<Date>(subMonths(new Date(), 2));
    const [endDate, setEndDate] = useState<Date>(new Date());
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const [reviewData, setReviewData] = useState<ReviewData | null>(null);

    const customers = [
        { id: 'CUST001', name: '某某制造' },
        { id: 'CUST002', name: '某某集团' },
        { id: 'CUST003', name: '某某企业' }
    ];

    // 加载复盘数据
    const fetchReviewData = () => {
        if (!startDate || !endDate) return;

        setLoading(true);
        setError(null);

        const startStr = format(startDate, 'yyyy-MM-dd');
        const endStr = format(endDate, 'yyyy-MM-dd');

        apiClient.post('/api/v1/review/medium-long-term/generate', {
            customer_id: selectedCustomerId,
            start_date: startStr,
            end_date: endStr,
            compare_baselines: ['pure_spot', 'fixed_price', 'market_avg']
        })
            .then(response => {
                setReviewData(response.data);
            })
            .catch(err => {
                console.error('Error:', err);
                setError(err.response?.data?.detail || err.message || '加载复盘数据失败');
                setReviewData(null);
            })
            .finally(() => setLoading(false));
    };

    useEffect(() => {
        fetchReviewData();
    }, [selectedCustomerId, startDate, endDate]);

    // 准备策略对比图表数据
    const prepareStrategyChartData = () => {
        if (!reviewData) return [];
        return reviewData.strategy_comparison.map(s => ({
            strategy: getStrategyName(s.strategy),
            '总成本': s.total_cost / 10000, // 转换为万元
            '合同覆盖率': s.contract_coverage * 100
        }));
    };

    const getStrategyName = (strategy: string): string => {
        const names: Record<string, string> = {
            'actual': '实际执行',
            'pure_spot': '纯现货',
            'full_contract': '全合同',
            'conservative': '保守策略',
            'aggressive': '激进策略'
        };
        return names[strategy] || strategy;
    };

    const getRiskScoreColor = (score: string): string => {
        if (score === 'low') return '#4caf50';
        if (score === 'medium') return '#ff9800';
        return '#f44336';
    };

    const getRiskScoreLabel = (score: string): string => {
        const labels: Record<string, string> = {
            'low': '低',
            'medium': '中',
            'high': '高'
        };
        return labels[score] || score;
    };

    return (
        <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={zhCN}>
            <Box sx={{ width: '100%' }}>
                {/* 控制栏 */}
                <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                    <Grid container spacing={2} alignItems="center">
                        <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                            <Typography variant="subtitle2" gutterBottom>
                                客户选择
                            </Typography>
                            <select
                                value={selectedCustomerId}
                                onChange={(e) => setSelectedCustomerId(e.target.value)}
                                disabled={loading}
                                style={{
                                    width: '100%',
                                    padding: '8px',
                                    borderRadius: '4px',
                                    border: '1px solid #ccc'
                                }}
                            >
                                {customers.map(c => (
                                    <option key={c.id} value={c.id}>{c.name}</option>
                                ))}
                            </select>
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                            <Typography variant="subtitle2" gutterBottom>
                                开始日期
                            </Typography>
                            <DatePicker
                                value={startDate}
                                onChange={(date) => date && setStartDate(date)}
                                disabled={loading}
                                slotProps={{
                                    textField: {
                                        sx: { width: '100%' }
                                    }
                                }}
                            />
                        </Grid>
                        <Grid size={{ xs: 12, sm: 6, md: 4 }}>
                            <Typography variant="subtitle2" gutterBottom>
                                结束日期
                            </Typography>
                            <DatePicker
                                value={endDate}
                                onChange={(date) => date && setEndDate(date)}
                                disabled={loading}
                                slotProps={{
                                    textField: {
                                        sx: { width: '100%' }
                                    }
                                }}
                            />
                        </Grid>
                    </Grid>
                </Paper>

                {/* 首次加载 */}
                {loading && !reviewData && (
                    <Box display="flex" justifyContent="center" alignItems="center" minHeight="400px">
                        <CircularProgress />
                    </Box>
                )}

                {/* 错误提示 */}
                {error && (
                    <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>
                )}

                {/* 复盘内容 */}
                {reviewData && !loading && (
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

                        {/* 复盘概览 */}
                        <Typography variant="h6" gutterBottom sx={{ mt: 2 }}>
                            复盘概览
                        </Typography>
                        <Grid container spacing={2} sx={{ mb: 3 }}>
                            {/* 合同覆盖率卡片 */}
                            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                <Card>
                                    <CardContent>
                                        <Typography variant="subtitle2" color="textSecondary">
                                            合同覆盖率
                                        </Typography>
                                        <Typography variant="h5" sx={{ mt: 1 }}>
                                            {(reviewData.execution_metrics.actual_contract_coverage * 100).toFixed(1)}%
                                        </Typography>
                                        <Typography variant="body2" color="textSecondary">
                                            计划: {(reviewData.execution_metrics.planned_contract_coverage * 100).toFixed(1)}%
                                        </Typography>
                                        <Typography variant="body2" color={reviewData.execution_metrics.execution_rate >= 0.95 ? 'success.main' : 'warning.main'}>
                                            执行率: {(reviewData.execution_metrics.execution_rate * 100).toFixed(1)}%
                                        </Typography>
                                    </CardContent>
                                </Card>
                            </Grid>

                            {/* 成本对比卡片 */}
                            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                <Card>
                                    <CardContent>
                                        <Typography variant="subtitle2" color="textSecondary">
                                            成本对比
                                        </Typography>
                                        <Typography variant="h5" sx={{ mt: 1 }}>
                                            {(reviewData.cost_metrics.total_cost / 10000).toFixed(0)}万元
                                        </Typography>
                                        <Typography variant="body2" color="textSecondary">
                                            市场: {(reviewData.cost_metrics.market_cost / 10000).toFixed(0)}万元
                                        </Typography>
                                        <Typography variant="body2" color={reviewData.cost_metrics.cost_savings > 0 ? 'success.main' : 'error.main'}>
                                            {reviewData.cost_metrics.cost_savings > 0 ? '节省' : '超支'}: {Math.abs(reviewData.cost_metrics.cost_savings / 10000).toFixed(1)}万元
                                        </Typography>
                                    </CardContent>
                                </Card>
                            </Grid>

                            {/* 均价对比卡片 */}
                            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                <Card>
                                    <CardContent>
                                        <Typography variant="subtitle2" color="textSecondary">
                                            综合均价
                                        </Typography>
                                        <Typography variant="h5" sx={{ mt: 1 }}>
                                            {reviewData.cost_metrics.blended_price.toFixed(0)}元
                                        </Typography>
                                        <Typography variant="body2" color="textSecondary">
                                            节省率: {(reviewData.cost_metrics.savings_percentage * 100).toFixed(2)}%
                                        </Typography>
                                    </CardContent>
                                </Card>
                            </Grid>

                            {/* 时机分析卡片 */}
                            <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                                <Card>
                                    <CardContent>
                                        <Typography variant="subtitle2" color="textSecondary">
                                            签订时机
                                        </Typography>
                                        <Typography variant="h5" sx={{ mt: 1 }}>
                                            {reviewData.timing_analysis.avg_price_advantage_at_signing.toFixed(0)}元
                                        </Typography>
                                        <Typography variant="body2" color="textSecondary">
                                            平均提前: {reviewData.timing_analysis.avg_days_before_effective}天
                                        </Typography>
                                        <Typography variant="body2" color="textSecondary">
                                            准确率: {(reviewData.timing_analysis.timing_accuracy * 100).toFixed(0)}%
                                        </Typography>
                                    </CardContent>
                                </Card>
                            </Grid>
                        </Grid>

                        {/* 策略对比 */}
                        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                            <Typography variant="h6" gutterBottom>
                                策略对比
                            </Typography>
                            <ResponsiveContainer width="100%" height={300}>
                                <BarChart data={prepareStrategyChartData()}>
                                    <CartesianGrid strokeDasharray="3 3" />
                                    <XAxis dataKey="strategy" />
                                    <YAxis yAxisId="left" label={{ value: '总成本 (万元)', position: 'insideLeft', angle: -90 }} />
                                    <YAxis yAxisId="right" orientation="right" label={{ value: '合同覆盖率 (%)', position: 'insideRight', angle: 90 }} />
                                    <Tooltip formatter={(value: number, name: string) => {
                                        if (name === '总成本') {
                                            return [`${value.toFixed(0)} 万元`, name];
                                        }
                                        return [`${value.toFixed(1)}%`, name];
                                    }} />
                                    <Legend />
                                    <Bar yAxisId="left" dataKey="总成本" fill="#1976d2" />
                                    <Bar yAxisId="right" dataKey="合同覆盖率" fill="#4caf50" />
                                </BarChart>
                            </ResponsiveContainer>
                        </Paper>

                        {/* 策略对比表格 */}
                        <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                            <Typography variant="h6" gutterBottom>
                                策略详细对比
                            </Typography>
                            <TableContainer>
                                <Table size="small">
                                    <TableHead>
                                        <TableRow>
                                            <TableCell>策略类型</TableCell>
                                            <TableCell align="right">合同覆盖率</TableCell>
                                            <TableCell align="right">总成本 (万元)</TableCell>
                                            <TableCell align="center">风险评分</TableCell>
                                        </TableRow>
                                    </TableHead>
                                    <TableBody>
                                        {reviewData.strategy_comparison.map((s, idx) => (
                                            <TableRow key={idx}>
                                                <TableCell>{getStrategyName(s.strategy)}</TableCell>
                                                <TableCell align="right">{(s.contract_coverage * 100).toFixed(0)}%</TableCell>
                                                <TableCell align="right">{(s.total_cost / 10000).toFixed(0)}</TableCell>
                                                <TableCell align="center">
                                                    <Box
                                                        sx={{
                                                            display: 'inline-block',
                                                            px: 1,
                                                            py: 0.5,
                                                            borderRadius: 1,
                                                            backgroundColor: getRiskScoreColor(s.risk_score),
                                                            color: 'white',
                                                            fontSize: '0.75rem'
                                                        }}
                                                    >
                                                        {getRiskScoreLabel(s.risk_score)}
                                                    </Box>
                                                </TableCell>
                                            </TableRow>
                                        ))}
                                    </TableBody>
                                </Table>
                            </TableContainer>
                        </Paper>

                        {/* 异常交易分析 */}
                        {reviewData.anomalies.length > 0 && (
                            <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                                <Typography variant="h6" gutterBottom>
                                    异常交易分析
                                </Typography>
                                <TableContainer>
                                    <Table size="small">
                                        <TableHead>
                                            <TableRow>
                                                <TableCell>日期</TableCell>
                                                <TableCell>异常类型</TableCell>
                                                <TableCell>描述</TableCell>
                                                <TableCell align="right">影响金额 (元)</TableCell>
                                                <TableCell>改进建议</TableCell>
                                            </TableRow>
                                        </TableHead>
                                        <TableBody>
                                            {reviewData.anomalies.map((a, idx) => (
                                                <TableRow key={idx}>
                                                    <TableCell>{format(new Date(a.date), 'yyyy-MM-dd')}</TableCell>
                                                    <TableCell>{a.type}</TableCell>
                                                    <TableCell>{a.description}</TableCell>
                                                    <TableCell align="right" sx={{ color: a.impact_cost > 0 ? 'error.main' : 'success.main' }}>
                                                        {a.impact_cost > 0 ? '+' : ''}{a.impact_cost.toFixed(0)}
                                                    </TableCell>
                                                    <TableCell>{a.recommendation}</TableCell>
                                                </TableRow>
                                            ))}
                                        </TableBody>
                                    </Table>
                                </TableContainer>
                            </Paper>
                        )}

                        {/* 复盘总结 */}
                        <Paper variant="outlined" sx={{ p: 2 }}>
                            <Typography variant="h6" gutterBottom>
                                复盘总结
                            </Typography>

                            {/* 亮点 */}
                            <Box sx={{ mb: 2 }}>
                                <Typography variant="subtitle1" fontWeight="bold" sx={{ mb: 1 }}>
                                    亮点
                                </Typography>
                                {reviewData.summary.highlights.map((h, idx) => (
                                    <Typography key={idx} variant="body2" sx={{ ml: 2, mb: 0.5 }}>
                                        • {h}
                                    </Typography>
                                ))}
                            </Box>

                            {/* 问题 */}
                            {reviewData.summary.issues.length > 0 && (
                                <Box sx={{ mb: 2 }}>
                                    <Typography variant="subtitle1" fontWeight="bold" sx={{ mb: 1 }}>
                                        问题
                                    </Typography>
                                    {reviewData.summary.issues.map((i, idx) => (
                                        <Typography key={idx} variant="body2" sx={{ ml: 2, mb: 0.5 }} color="error.main">
                                            • {i}
                                        </Typography>
                                    ))}
                                </Box>
                            )}

                            {/* 建议 */}
                            <Box>
                                <Typography variant="subtitle1" fontWeight="bold" sx={{ mb: 1 }}>
                                    优化建议
                                </Typography>
                                {reviewData.summary.recommendations.map((r, idx) => (
                                    <Box key={idx} sx={{ ml: 2, mb: 1, p: 1, backgroundColor: 'action.hover', borderRadius: 1 }}>
                                        <Typography variant="subtitle2" fontWeight="bold">
                                            优先级 {r.priority}: {r.action}
                                        </Typography>
                                        <Typography variant="body2" sx={{ mt: 0.5 }}>
                                            理由: {r.reason}
                                        </Typography>
                                        <Typography variant="body2">
                                            建议: {r.suggestion}
                                        </Typography>
                                        <Typography variant="body2" color="success.main">
                                            预期收益: {r.expected_benefit}
                                        </Typography>
                                    </Box>
                                ))}
                            </Box>
                        </Paper>
                    </Box>
                )}
            </Box>
        </LocalizationProvider>
    );
};
