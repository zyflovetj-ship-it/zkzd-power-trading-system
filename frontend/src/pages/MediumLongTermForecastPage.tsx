/**
 * 中长期负荷预测页面
 *
 * 展示未来6个月的系统级中长期负荷预测数据，包括预测值、上限和下限。
 */

import React, { useState, useEffect, useRef } from 'react';
import {
  Box,
  Paper,
  Typography,
  CircularProgress,
  Alert,
  useTheme,
  useMediaQuery,
} from '@mui/material';
import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
} from 'recharts';
import apiClient from '../api/client';
import { useChartFullscreen } from '../hooks/useChartFullscreen';

interface MonthlyForecastPoint {
  month: string;
  forecast_value: number;
  upper_bound: number;
  lower_bound: number;
  timestamp: string;
}

interface ForecastResponse {
  forecast_date: string;
  forecast_horizon_months: number;
  data: MonthlyForecastPoint[];
  total_months: number;
}

export const MediumLongTermForecastPage: React.FC = () => {
  const theme = useTheme();
  const isTablet = useMediaQuery(theme.breakpoints.down('md'));

  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [forecastData, setForecastData] = useState<ForecastResponse | null>(null);

  const chartRef = useRef<HTMLDivElement>(null);

  // 全屏 Hook
  const {
    isFullscreen,
    FullscreenEnterButton,
    FullscreenExitButton,
    FullscreenTitle,
  } = useChartFullscreen({
    chartRef,
    title: '中长期负荷预测（未来6个月）',
  });

  // 加载预测数据
  const fetchForecastData = () => {
    setLoading(true);
    setError(null);

    apiClient
      .get<ForecastResponse>('/api/v1/medium-long-term-load-forecast/latest')
      .then((response) => {
        setForecastData(response.data);
      })
      .catch((err) => {
        console.error('加载预测数据失败:', err);
        setError(
          err.response?.data?.detail || err.message || '加载预测数据失败',
        );
        setForecastData(null);
      })
      .finally(() => {
        setLoading(false);
      });
  };

  // 初始加载
  useEffect(() => {
    fetchForecastData();
  }, []);

  return (
    <Box sx={{ width: '100%' }}>
      {/* 移动端面包屑标题 */}
      {isTablet && (
        <Typography
          variant="subtitle1"
          sx={{
            mb: 2,
            fontWeight: 'bold',
            color: 'text.primary',
          }}
        >
          负荷分析 / 中长期负荷预测
        </Typography>
      )}

      {/* 主内容区域 */}
      <Paper variant="outlined" sx={{ p: { xs: 1, sm: 2 } }}>
        {/* 预测信息 */}
        <Box sx={{ mb: 2 }}>
          <Typography variant="h6" gutterBottom>
            中长期负荷预测
          </Typography>
          {forecastData && (
            <Typography variant="body2" color="text.secondary">
              预测发布日期: {forecastData.forecast_date} | 预测时间范围:{' '}
              {forecastData.forecast_horizon_months} 个月
            </Typography>
          )}
        </Box>

        {/* 首次加载显示完整的 loading */}
        {loading && !forecastData ? (
          <Box
            display="flex"
            justifyContent="center"
            alignItems="center"
            minHeight="400px"
          >
            <CircularProgress />
          </Box>
        ) : error ? (
          <Alert severity="error" sx={{ mt: 2 }}>
            {error}
          </Alert>
        ) : forecastData ? (
          <Box sx={{ position: 'relative' }}>
            {/* 数据加载时的覆盖层（不卸载组件） */}
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
                  zIndex: 1000,
                }}
              >
                <CircularProgress />
              </Box>
            )}

            {/* 图表容器 */}
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
                  zIndex: 1400,
                }),
              }}
            >
              <FullscreenEnterButton />
              <FullscreenExitButton />
              <FullscreenTitle />

              {!forecastData.data || forecastData.data.length === 0 ? (
                <Box
                  sx={{
                    display: 'flex',
                    height: '100%',
                    alignItems: 'center',
                    justifyContent: 'center',
                  }}
                >
                  <Typography>无数据</Typography>
                </Box>
              ) : (
                <ResponsiveContainer width="100%" height="100%">
                  <LineChart
                    data={forecastData.data}
                    margin={{
                      top: 20,
                      right: 30,
                      left: 20,
                      bottom: 5,
                    }}
                  >
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis
                      dataKey="month"
                      label={{ value: '月份', position: 'insideBottom', offset: -5 }}
                    />
                    <YAxis
                      label={{ value: '负荷 (MW)', angle: -90, position: 'insideLeft' }}
                    />
                    <Tooltip
                      formatter={(value: number, name: string) => {
                        const nameMap: Record<string, string> = {
                          forecast_value: '预测值',
                          upper_bound: '上限',
                          lower_bound: '下限',
                        };
                        return [`${value.toFixed(2)} MW`, nameMap[name] || name];
                      }}
                    />
                    <Legend />
                    <Line
                      type="monotone"
                      dataKey="upper_bound"
                      stroke="#ffc658"
                      strokeDasharray="5 5"
                      name="上限"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="forecast_value"
                      stroke="#8884d8"
                      name="预测值"
                      strokeWidth={3}
                      dot={{ r: 6 }}
                    />
                    <Line
                      type="monotone"
                      dataKey="lower_bound"
                      stroke="#82ca9d"
                      strokeDasharray="5 5"
                      name="下限"
                      strokeWidth={2}
                      dot={{ r: 4 }}
                    />
                  </LineChart>
                </ResponsiveContainer>
              )}
            </Box>
          </Box>
        ) : null}
      </Paper>
    </Box>
  );
};
