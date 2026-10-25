import React, { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    useMediaQuery,
    useTheme,
} from '@mui/material';

import { MonthlyForecastControlBar } from '../components/MonthlyForecastControlBar';
import { MonthlyForecastChart } from '../components/MonthlyForecastChart';
import { MonthlyForecastAccuracy } from '../components/MonthlyForecastAccuracy';
import apiClient from '../api/client';

interface ForecastVersion {
    forecast_id: string;
    forecast_type: string;
    model_type: string;
    model_version: string;
    created_at: string;
    status: string;
}

interface ChartData {
    forecast_id: string;
    target_month: {
        year: number;
        month: number;
    };
    chart_type: string;
    data: Array<{
        date: string;
        day: number;
        price_max: number;
        price_min: number;
        price_mean: number;
        price_peak: number;
        price_valley: number;
        price_spread: number;
        confidence_80_lower?: number;
        confidence_80_upper?: number;
        confidence_90_lower?: number;
        confidence_90_upper?: number;
        actual_mean?: number;
        actual_max?: number;
        actual_min?: number;
        actual_spread?: number;
    }>;
    has_actual: boolean;
    last_month_avg?: number;
}

interface AccuracyData {
    forecast_id: string;
    target_month: {
        year: number;
        month: number;
    };
    mape: number;
    wmape_accuracy: number;
    mae: number;
    rmse: number;
    direction_accuracy: number;
    period_accuracy: Record<string, number>;
    stats: {
        max_value?: number;
        min_value?: number;
        mean_value?: number;
        has_negative?: boolean;
        volatility?: number;
    };
    rate_90_pass?: boolean;
    rate_85_pass?: boolean;
    r2_score?: number;
    daily_errors?: Array<{
        date: string;
        mape: number;
    }>;
}

type ChartType = 'mean_trend' | 'price_spread' | 'peak_valley';

export const MonthlyPriceForecastPage: React.FC = () => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('md'));

    // 状态管理
    const [selectedMonth, setSelectedMonth] = useState<Date>(new Date());
    const [chartType, setChartType] = useState<ChartType>('mean_trend');
    const [selectedVersion, setSelectedVersion] = useState<ForecastVersion | null>(null);
    const [versions, setVersions] = useState<ForecastVersion[]>([]);
    const [chartData, setChartData] = useState<ChartData | null>(null);
    const [accuracyData, setAccuracyData] = useState<AccuracyData | null>(null);

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // 加载预测版本列表
    useEffect(() => {
        if (selectedMonth) {
            fetchVersions();
        }
    }, [selectedMonth]);

    // 当选中版本或图表类型变化时，加载图表数据
    useEffect(() => {
        if (selectedVersion) {
            fetchChartData();
        }
    }, [selectedVersion, chartType]);

    // 当选中版本变化时，加载准确度数据
    useEffect(() => {
        if (selectedVersion) {
            fetchAccuracyData();
        }
    }, [selectedVersion]);

    const fetchVersions = async () => {
        setLoading(true);
        setError(null);

        const year = selectedMonth.getFullYear();
        const month = selectedMonth.getMonth() + 1;

        try {
            const response = await apiClient.get('/api/v1/monthly-forecast/versions', {
                params: {
                    target_year: year,
                    target_month: month
                }
            });

            const versionList = response.data;
            setVersions(versionList);

            // 默认选中最新版本
            if (versionList.length > 0) {
                setSelectedVersion(versionList[0]);
            } else {
                setSelectedVersion(null);
                setChartData(null);
                setAccuracyData(null);
            }
        } catch (err: any) {
            console.error('加载预测版本失败:', err);
            setError(err.response?.data?.detail || err.message || '加载预测版本失败');
        } finally {
            setLoading(false);
        }
    };

    const fetchChartData = async () => {
        if (!selectedVersion) return;

        setLoading(true);

        try {
            const response = await apiClient.get('/api/v1/monthly-forecast/data', {
                params: {
                    forecast_id: selectedVersion.forecast_id,
                    chart_type: chartType
                }
            });

            setChartData(response.data);
        } catch (err: any) {
            console.error('加载图表数据失败:', err);
            setError(err.response?.data?.detail || err.message || '加载图表数据失败');
        } finally {
            setLoading(false);
        }
    };

    const fetchAccuracyData = async () => {
        if (!selectedVersion) return;

        try {
            const response = await apiClient.get('/api/v1/monthly-forecast/accuracy', {
                params: {
                    forecast_id: selectedVersion.forecast_id
                }
            });

            setAccuracyData(response.data);
        } catch (err: any) {
            // 准确度数据可能不存在（例如未来月份）
            console.warn('准确度数据不存在:', err);
            setAccuracyData(null);
        }
    };

    return (
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
                    价格预测 / 月度价格预测
                </Typography>
            )}

            {/* 控制栏 */}
            <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                <MonthlyForecastControlBar
                    selectedMonth={selectedMonth}
                    onMonthChange={setSelectedMonth}
                    chartType={chartType}
                    onChartTypeChange={setChartType}
                    versions={versions}
                    selectedVersion={selectedVersion}
                    onVersionChange={setSelectedVersion}
                    loading={loading}
                />
            </Paper>

            {/* 错误提示 */}
            {error && (
                <Paper variant="outlined" sx={{ p: 2, mb: 2, borderColor: 'error.main', bgcolor: 'error.50' }}>
                    <Typography color="error">{error}</Typography>
                </Paper>
            )}

            {/* 图表区域 */}
            <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                <MonthlyForecastChart
                    data={chartData}
                    loading={loading}
                />
            </Paper>

            {/* 准确度评估区域 - 仅当有数据时显示 */}
            {accuracyData && chartData?.has_actual && (
                <Paper variant="outlined" sx={{ p: 2 }}>
                    <Typography variant="h6" gutterBottom>
                        准确度评估详情
                    </Typography>
                    <MonthlyForecastAccuracy data={accuracyData} />
                </Paper>
            )}

            {/* 等待实际价格的提示 */}
            {selectedVersion && !accuracyData && !loading && (
                <Paper variant="outlined" sx={{ p: 2, textAlign: 'center', bgcolor: 'grey.50' }}>
                    <Typography variant="body2" color="text.secondary">
                        等待实际价格数据生成评估报告
                    </Typography>
                </Paper>
            )}
        </Box>
    );
};
