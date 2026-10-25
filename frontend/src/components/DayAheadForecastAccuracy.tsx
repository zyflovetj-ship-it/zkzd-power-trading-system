import React from 'react';
import {
    Box,
    Grid,
    Card,
    CardContent,
    Typography,
    Chip,
    List,
    ListItem,
    ListItemText,
    Divider,
    useTheme,
    useMediaQuery,
} from '@mui/material';
import {
    CheckCircle,
    Cancel,
    Warning,
    TrendingUp,
    ShowChart,
} from '@mui/icons-material';

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

interface DayAheadForecastAccuracyProps {
    data: AccuracyData;
}

export const DayAheadForecastAccuracy: React.FC<DayAheadForecastAccuracyProps> = ({ data }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // 获取 WMAPE 准确率的颜色
    const getWMAPEColor = (accuracy: number) => {
        if (accuracy >= 90) return 'success';
        if (accuracy >= 85) return 'warning';
        return 'error';
    };

    // 获取 WMAPE 准确率的背景色
    const getWMAPEBgColor = (accuracy: number) => {
        if (accuracy >= 90) return 'success.main';
        if (accuracy >= 85) return 'warning.main';
        return 'error.main';
    };

    return (
        <Box>
            {/* 第一行：核心指标概览 */}
            <Grid container spacing={2} sx={{ mb: 3 }}>
                {/* WMAPE 准确率 */}
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card
                        sx={{
                            bgcolor: `${getWMAPEBgColor(data.wmape_accuracy)}.10`,
                            border: 2,
                            borderColor: getWMAPEBgColor(data.wmape_accuracy)
                        }}
                    >
                        <CardContent>
                            <Typography variant="caption" color="text.secondary" gutterBottom>
                                综合准确率 (WMAPE)
                            </Typography>
                            <Typography variant="h4" sx={{ color: getWMAPEBgColor(data.wmape_accuracy), fontWeight: 'bold' }}>
                                {data.wmape_accuracy.toFixed(2)}%
                            </Typography>
                            <Box sx={{ mt: 1, display: 'flex', gap: 0.5, flexWrap: 'wrap' }}>
                                {data.rate_90_pass !== undefined && (
                                    <Chip
                                        size="small"
                                        icon={data.rate_90_pass ? <CheckCircle /> : <Cancel />}
                                        label={data.rate_90_pass ? '90%达标' : '90%未达标'}
                                        color={data.rate_90_pass ? 'success' : 'error'}
                                    />
                                )}
                                {data.rate_85_pass !== undefined && (
                                    <Chip
                                        size="small"
                                        icon={data.rate_85_pass ? <CheckCircle /> : <Cancel />}
                                        label={data.rate_85_pass ? '85%达标' : '85%未达标'}
                                        color={data.rate_85_pass ? 'success' : 'error'}
                                    />
                                )}
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>

                {/* 方向准确率 */}
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card variant="outlined">
                        <CardContent>
                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                <TrendingUp sx={{ mr: 1, color: 'action.active' }} />
                                <Typography variant="caption" color="text.secondary">
                                    方向准确率
                                </Typography>
                            </Box>
                            <Typography variant="h5">
                                {data.direction_accuracy.toFixed(2)}%
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                涨跌趋势预测
                            </Typography>
                        </CardContent>
                    </Card>
                </Grid>

                {/* 绝对误差 */}
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card variant="outlined">
                        <CardContent>
                            <Typography variant="caption" color="text.secondary" gutterBottom>
                                绝对误差
                            </Typography>
                            <Box sx={{ mb: 0.5 }}>
                                <Typography variant="body1">
                                    <strong>MAE:</strong> {data.mae.toFixed(2)}
                                </Typography>
                            </Box>
                            <Box>
                                <Typography variant="body1">
                                    <strong>RMSE:</strong> {data.rmse.toFixed(2)}
                                </Typography>
                            </Box>
                        </CardContent>
                    </Card>
                </Grid>

                {/* 拟合度 R² */}
                {data.r2_score !== undefined && data.r2_score !== 0 && (
                    <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                        <Card variant="outlined">
                            <CardContent>
                                <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                    <ShowChart sx={{ mr: 1, color: 'action.active' }} />
                                    <Typography variant="caption" color="text.secondary">
                                        拟合度
                                    </Typography>
                                </Box>
                                <Typography variant="h5">
                                    {data.r2_score.toFixed(3)}
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                    R² Score
                                </Typography>
                            </CardContent>
                        </Card>
                    </Grid>
                )}
            </Grid>

            {/* 第二行：详细分析 */}
            <Grid container spacing={2}>
                {/* 分时段准确度 */}
                <Grid size={{ xs: 12, md: 6 }}>
                    <Card variant="outlined" sx={{ height: '100%' }}>
                        <CardContent>
                            <Typography variant="subtitle1" gutterBottom fontWeight="bold">
                                分时段表现
                            </Typography>
                            <Divider sx={{ mb: 2 }} />
                            {Object.keys(data.period_accuracy).length > 0 ? (
                                <List dense>
                                    {Object.entries(data.period_accuracy)
                                        .sort(([, a], [, b]) => b - a)  // 按准确率降序排列
                                        .map(([period, accuracy]) => (
                                            <ListItem key={period} disablePadding>
                                                <ListItemText
                                                    primary={
                                                        <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                                                            <Typography variant="body2">
                                                                {period}
                                                            </Typography>
                                                            <Typography
                                                                variant="body2"
                                                                sx={{
                                                                    color: getWMAPEBgColor(accuracy),
                                                                    fontWeight: 'bold'
                                                                }}
                                                            >
                                                                {accuracy.toFixed(2)}%
                                                            </Typography>
                                                        </Box>
                                                    }
                                                    secondary={
                                                        <Box
                                                            sx={{
                                                                mt: 0.5,
                                                                width: '100%',
                                                                height: 6,
                                                                bgcolor: 'grey.200',
                                                                borderRadius: 1,
                                                                overflow: 'hidden'
                                                            }}
                                                        >
                                                            <Box
                                                                sx={{
                                                                    width: `${accuracy}%`,
                                                                    height: '100%',
                                                                    bgcolor: getWMAPEBgColor(accuracy)
                                                                }}
                                                            />
                                                        </Box>
                                                    }
                                                />
                                            </ListItem>
                                        ))}
                                </List>
                            ) : (
                                <Typography variant="body2" color="text.secondary">
                                    无分时段数据
                                </Typography>
                            )}
                        </CardContent>
                    </Card>
                </Grid>

                {/* 当日数据特征 */}
                <Grid size={{ xs: 12, md: 6 }}>
                    <Card variant="outlined" sx={{ height: '100%' }}>
                        <CardContent>
                            <Typography variant="subtitle1" gutterBottom fontWeight="bold">
                                当日数据特征
                            </Typography>
                            <Divider sx={{ mb: 2 }} />
                            <List dense>
                                {data.stats.max_value !== undefined && (
                                    <ListItem disablePadding>
                                        <ListItemText
                                            primary="最高价"
                                            secondary={`${data.stats.max_value.toFixed(2)} 元/MWh`}
                                        />
                                    </ListItem>
                                )}
                                {data.stats.min_value !== undefined && (
                                    <ListItem disablePadding>
                                        <ListItemText
                                            primary="最低价"
                                            secondary={`${data.stats.min_value.toFixed(2)} 元/MWh`}
                                        />
                                    </ListItem>
                                )}
                                {data.stats.mean_value !== undefined && (
                                    <ListItem disablePadding>
                                        <ListItemText
                                            primary="平均价"
                                            secondary={`${data.stats.mean_value.toFixed(2)} 元/MWh`}
                                        />
                                    </ListItem>
                                )}
                                {data.stats.has_negative !== undefined && (
                                    <ListItem disablePadding>
                                        <ListItemText
                                            primary={
                                                <Box sx={{ display: 'flex', alignItems: 'center' }}>
                                                    负电价
                                                    {data.stats.has_negative ? (
                                                        <Warning sx={{ ml: 1, color: 'warning.main' }} />
                                                    ) : (
                                                        <CheckCircle sx={{ ml: 1, color: 'success.main' }} />
                                                    )}
                                                </Box>
                                            }
                                            secondary={
                                                data.stats.has_negative
                                                    ? '包含负电价，预测难度较大'
                                                    : '无负电价风险'
                                            }
                                        />
                                    </ListItem>
                                )}
                            </List>
                        </CardContent>
                    </Card>
                </Grid>
            </Grid>
        </Box>
    );
};
