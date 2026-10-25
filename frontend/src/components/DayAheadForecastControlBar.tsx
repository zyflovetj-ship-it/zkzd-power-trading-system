import React from 'react';
import {
    Box,
    FormControl,
    InputLabel,
    Select,
    MenuItem,
    CircularProgress,
    Typography,
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
    target_date: string;
}

interface DayAheadForecastControlBarProps {
    selectedDate: Date | null;
    onDateChange: (date: Date | null) => void;
    forecastType: 'd1_price' | 'd2_price';
    onForecastTypeChange: (type: 'd1_price' | 'd2_price') => void;
    versions: ForecastVersion[];
    selectedVersion: ForecastVersion | null;
    onVersionChange: (version: ForecastVersion | null) => void;
    loading: boolean;
}

export const DayAheadForecastControlBar: React.FC<DayAheadForecastControlBarProps> = ({
    selectedDate,
    onDateChange,
    forecastType,
    onForecastTypeChange,
    versions,
    selectedVersion,
    onVersionChange,
    loading,
}) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // 格式化版本选项显示文本
    const formatVersionLabel = (version: ForecastVersion) => {
        const createdAt = format(new Date(version.created_at), 'HH:mm');
        const modelVersion = version.model_version || 'unknown';
        return `${createdAt} (${modelVersion})`;
    };

    return (
        <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={zhCN}>
            <Box sx={{ display: 'flex', gap: 2, flexWrap: 'wrap', alignItems: 'center' }}>
                {/* 日期选择器 */}
                <Box sx={{ minWidth: { xs: '150px', sm: '200px' } }}>
                    <DatePicker
                        label="目标日期"
                        value={selectedDate}
                        onChange={onDateChange}
                        disabled={loading}
                        slotProps={{
                            textField: {
                                fullWidth: true,
                                size: 'small'
                            }
                        }}
                    />
                </Box>

                {/* 预测类型选择 */}
                <FormControl size="small" sx={{ minWidth: { xs: 140, sm: 180 } }}>
                    <InputLabel>预测类型</InputLabel>
                    <Select
                        value={forecastType}
                        label="预测类型"
                        onChange={(e) => onForecastTypeChange(e.target.value as 'd1_price' | 'd2_price')}
                        disabled={loading}
                    >
                        <MenuItem value="d1_price">D-1 日前预测</MenuItem>
                        <MenuItem value="d2_price">D-2 价格预测</MenuItem>
                    </Select>
                </FormControl>

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
        </LocalizationProvider>
    );
};
