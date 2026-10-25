import React from 'react';
import {
    Box,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    CircularProgress,
    Typography,
    Tab,
    Tabs,
    useTheme,
    useMediaQuery,
} from '@mui/material';
import { DatePicker } from '@mui/x-date-pickers';
import { LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { zhCN } from 'date-fns/locale';
import { format } from 'date-fns';

interface ForecastVersion {
    forecast_id: string;
    forecast_type: string;
    model_type: string;
    model_version: string;
    created_at: string;
    status: string;
}

type ChartType = 'mean_trend' | 'price_spread' | 'peak_valley';

interface MonthlyForecastControlBarProps {
    selectedMonth: Date;
    onMonthChange: (month: Date) => void;
    chartType: ChartType;
    onChartTypeChange: (type: ChartType) => void;
    versions: ForecastVersion[];
    selectedVersion: ForecastVersion | null;
    onVersionChange: (version: ForecastVersion | null) => void;
    loading: boolean;
}

export const MonthlyForecastControlBar: React.FC<MonthlyForecastControlBarProps> = ({
    selectedMonth,
    onMonthChange,
    chartType,
    onChartTypeChange,
    versions,
    selectedVersion,
    onVersionChange,
    loading,
}) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // 格式化版本选项显示文本
    const formatVersionLabel = (version: ForecastVersion) => {
        const createdAt = format(new Date(version.created_at), 'yyyy-MM-dd');
        const modelVersion = version.model_version || 'unknown';
        return `${createdAt} (${modelVersion})`;
    };

    // 图表类型标签
    const chartTypeLabels: Record<ChartType, string> = {
        mean_trend: '均价趋势',
        price_spread: '日内价差',
        peak_valley: '峰谷价格'
    };

    return (
        <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={zhCN}>
            <Box sx={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
                {/* 第一行：月份选择和版本选择 */}
                <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
                    {/* 月份选择器 */}
                    <Box sx={{ minWidth: { xs: '150px', sm: '180px' } }}>
                        <DatePicker
                            label="目标月份"
                            views={['year', 'month']}
                            value={selectedMonth}
                            onChange={(newMonth) => {
                                if (newMonth) {
                                    // 设置为该月的第一天
                                    const month = new Date(newMonth.getFullYear(), newMonth.getMonth(), 1);
                                    onMonthChange(month);
                                }
                            }}
                            disabled={loading}
                            slotProps={{
                                textField: {
                                    fullWidth: true,
                                    size: 'small'
                                }
                            }}
                        />
                    </Box>

                    {/* 预测版本选择 */}
                    <FormControl size="small" sx={{ minWidth: { xs: 200, sm: 280 }, flexGrow: 1 }}>
                        <InputLabel>预测版本</InputLabel>
                        <Select
                            value={selectedVersion?.forecast_id || ''}
                            label="预测版本"
                            onChange={(e) => {
                                const version = versions.find(v => v.forecast_id === e.target.value);
                                onVersionChange(version || null);
                            }}
                            disabled={loading || versions.length === 0}
                        >
                            {versions.length === 0 ? (
                                <MenuItem value="">
                                    <em>无可用版本</em>
                                </MenuItem>
                            ) : (
                                versions.map((version) => (
                                    <MenuItem key={version.forecast_id} value={version.forecast_id}>
                                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', width: '100%' }}>
                                            <Typography variant="body2">
                                                {formatVersionLabel(version)}
                                            </Typography>
                                            {loading && selectedVersion?.forecast_id === version.forecast_id && (
                                                <CircularProgress size={16} sx={{ ml: 1 }} />
                                            )}
                                        </Box>
                                    </MenuItem>
                                ))
                            )}
                        </Select>
                    </FormControl>

                    {/* 模型类型显示 */}
                    {selectedVersion && (
                        <Box sx={{ minWidth: { xs: 150, sm: 200 } }}>
                            <Typography variant="caption" color="text.secondary">
                                模型类型
                            </Typography>
                            <Typography variant="body2" noWrap>
                                {selectedVersion.model_type || '未知'}
                            </Typography>
                        </Box>
                    )}
                </Box>

                {/* 第二行：图表类型切换 */}
                <Box sx={{ borderBottom: 1, borderColor: 'divider' }}>
                    <Tabs
                        value={chartType}
                        onChange={(_, newValue) => onChartTypeChange(newValue)}
                        variant={isMobile ? 'scrollable' : 'standard'}
                        scrollButtons={isMobile ? 'auto' : false}
                    >
                        <Tab label={chartTypeLabels.mean_trend} value="mean_trend" />
                        <Tab label={chartTypeLabels.price_spread} value="price_spread" />
                        <Tab label={chartTypeLabels.peak_valley} value="peak_valley" />
                    </Tabs>
                </Box>
            </Box>
        </LocalizationProvider>
    );
};
