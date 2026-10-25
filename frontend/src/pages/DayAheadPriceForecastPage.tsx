import React, { useState, useEffect } from 'react';
import {
    Box,
    Paper,
    Typography,
    useMediaQuery,
    useTheme,
} from '@mui/material';
import { subDays } from 'date-fns';

import { DayAheadForecastControlBar } from '../components/DayAheadForecastControlBar';
import { DayAheadForecastChart } from '../components/DayAheadForecastChart';
import { DayAheadForecastAccuracy } from '../components/DayAheadForecastAccuracy';
import apiClient from '../api/client';

interface ForecastVersion {
    forecast_id: string;
    forecast_type: string;
    model_type: string;
    model_version: string;
    created_at: string;
    target_date: string;
}

interface ChartData {
    forecast_id: string;
    target_date: string;
    data: Array<{
        datetime: string;
        time: string;
        predicted: number;
        actual: number | null;
        error?: number;
        confidence_80_lower?: number;
        confidence_80_upper?: number;
        confidence_90_lower?: number;
        confidence_90_upper?: number;
    }>;
    has_actual: boolean;
}

interface AccuracyData {
    forecast_id: string;
    target_date: string;
    wmape_accuracy: number;
    mae: number;
    rmse: number;
    mape: number;
    direction_accuracy: number;
    period_accuracy: Record<string, number>;
    stats: {
        max_value?: number;
        min_value?: number;
        mean_value?: number;
        has_negative?: boolean;
    };
    rate_90_pass?: boolean;
    rate_85_pass?: boolean;
    r2_score?: number;
}

export const DayAheadPriceForecastPage: React.FC = () => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('md'));

    // 状态管理
    const [selectedDate, setSelectedDate] = useState<Date | null>(subDays(new Date(), 1));
    const [forecastType, setForecastType] = useState<'d1_price' | 'd2_price'>('d1_price');
    const [selectedVersion, setSelectedVersion] = useState<ForecastVersion | null>(null);
    const [versions, setVersions] = useState<ForecastVersion[]>([]);
    const [chartData, setChartData] = useState<ChartData | null>(null);
    const [accuracyData, setAccuracyData] = useState<AccuracyData | null>(null);

    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    // 加载预测版本列表
    useEffect(() => {
        if (selectedDate) {
            fetchVersions();
        }
    }, [selectedDate, forecastType]);

    // 当选中版本变化时，加载图表数据和准确度数据
    useEffect(() => {
        if (selectedVersion) {
            fetchChartData();
            fetchAccuracyData();
        }
    }, [selectedVersion]);

    const fetchVersions = async () => {
        if (!selectedDate) return;

        setLoading(true);
        setError(null);

        const dateStr = selectedDate.toISOString().split('T')[0];

        try {
            const response = await apiClient.get('/api/v1/day-ahead-forecast/versions', {
                params: {
                    target_date: dateStr,
                    forecast_type: forecastType
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
        if (!selectedVersion || !selectedDate) return;

        setLoading(true);
        const dateStr = selectedDate.toISOString().split('T')[0];

        try {
            const response = await apiClient.get('/api/v1/day-ahead-forecast/data', {
                params: {
                    forecast_id: selectedVersion.forecast_id,
                    target_date: dateStr
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
            const response = await apiClient.get('/api/v1/day-ahead-forecast/accuracy', {
                params: {
                    forecast_id: selectedVersion.forecast_id
                }
            });

            setAccuracyData(response.data);
        } catch (err: any) {
            // 准确度数据可能不存在（例如未来日期）
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
                    价格预测 / 日前价格预测
                </Typography>
            )}

            {/* 控制栏 */}
            <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                <DayAheadForecastControlBar
                    selectedDate={selectedDate}
                    onDateChange={setSelectedDate}
                    forecastType={forecastType}
                    onForecastTypeChange={setForecastType}
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
                <DayAheadForecastChart
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
                    <DayAheadForecastAccuracy data={accuracyData} />
                </Paper>
            )}

            {/* 等待实际价格的提示 */}
            {selectedVersion && !accuracyData && !loading && (
                <Paper variant="outlined" sx={{ p: 2, textAlign: 'center', bgcolor: 'grey.50' }}>
                    <Typography variant="body2" color="text.secondary">
                        等待实际价格出清后生成评估报告
                    </Typography>
                </Paper>
            )}
        </Box>
    );
};
