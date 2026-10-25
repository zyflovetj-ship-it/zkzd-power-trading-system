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

interface MonthlyForecastAccuracyProps {
    data: AccuracyData;
}

export const MonthlyForecastAccuracy: React.FC<MonthlyForecastAccuracyProps> = ({ data }) => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));

    // 获取 MAPE 的颜色
    const getMAPEColor = (mape: number) => {
        if (mape < 10) return 'success';
        if (mape < 15) return 'warning';
        return 'error';
    };

    // 获取 MAPE 的背景色
    const getMAPEBgColor = (mape: number) => {
        if (mape < 10) return 'success.main';
        if (mape < 15) return 'warning.main';
        return 'error.main';
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
                {/* 月度 MAPE */}
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card
                        sx={{
                            bgcolor: `${getMAPEBgColor(data.mape)}.10`,
                            border: 2,
                            borderColor: getMAPEBgColor(data.mape)
                        }}
                    >
                        <CardContent>
                            <Typography variant="caption" color="text.secondary" gutterBottom>
                                月度 MAPE
                            </Typography>
                            <Typography variant="h4" sx={{ color: getMAPEBgColor(data.mape), fontWeight: 'bold' }}>
                                {data.mape.toFixed(2)}%
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

                {/* WMAPE 准确率 */}
                <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                    <Card variant="outlined">
                        <CardContent>
                            <Typography variant="caption" color="text.secondary" gutterBottom>
                                WMAPE 准确率
                            </Typography>
                            <Typography variant="h5">
                                {data.wmape_accuracy.toFixed(2)}%
                            </Typography>
                            <Typography variant="caption" color="text.secondary">
                                综合准确度
                            </Typography>
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

                {/* 波动率预测 */}
                {data.stats.volatility !== undefined && (
                    <Grid size={{ xs: 12, sm: 6, md: 3 }}>
                        <Card variant="outlined">
                            <CardContent>
                                <Typography variant="caption" color="text.secondary" gutterBottom>
                                    月度波动率
                                </Typography>
                                <Typography variant="h5">
                                    {(data.stats.volatility * 100).toFixed(1)}%
                                </Typography>
                                <Typography variant="caption" color="text.secondary">
                                    价格波动幅度
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

                {/* 月度统计特征 */}
                <Grid size={{ xs: 12, md: 6 }}>
                    <Card variant="outlined" sx={{ height: '100%' }}>
                        <CardContent>
                            <Typography variant="subtitle1" gutterBottom fontWeight="bold">
                                月度统计特征
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
                                {data.stats.volatility !== undefined && (
                                    <ListItem disablePadding>
                                        <ListItemText
                                            primary="波动率"
                                            secondary={`${(data.stats.volatility * 100).toFixed(2)}%`}
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

                {/* 误差统计 */}
                {data.mae !== undefined && data.rmse !== undefined && (
                    <Grid size={{ xs: 12 }}>
                        <Card variant="outlined">
                            <CardContent>
                                <Typography variant="subtitle1" gutterBottom fontWeight="bold">
                                    误差统计
                                </Typography>
                                <Divider sx={{ mb: 2 }} />
                                <Grid container spacing={2}>
                                    <Grid size={{ xs: 6, sm: 3 }}>
                                        <Typography variant="body2" color="text.secondary">
                                            平均绝对误差
                                        </Typography>
                                        <Typography variant="h6">
                                            MAE: {data.mae.toFixed(2)}
                                        </Typography>
                                    </Grid>
                                    <Grid size={{ xs: 6, sm: 3 }}>
                                        <Typography variant="body2" color="text.secondary">
                                            均方根误差
                                        </Typography>
                                        <Typography variant="h6">
                                            RMSE: {data.rmse.toFixed(2)}
                                        </Typography>
                                    </Grid>
                                    {data.r2_score !== undefined && data.r2_score !== 0 && (
                                        <Grid size={{ xs: 6, sm: 3 }}>
                                            <Box sx={{ display: 'flex', alignItems: 'center', mb: 1 }}>
                                                <ShowChart sx={{ mr: 1, color: 'action.active' }} />
                                                <Typography variant="body2" color="text.secondary">
                                                    拟合度
                                                </Typography>
                                            </Box>
                                            <Typography variant="h6">
                                                {data.r2_score.toFixed(3)}
                                            </Typography>
                                        </Grid>
                                    )}
                                </Grid>
                            </CardContent>
                        </Card>
                    </Grid>
                )}
            </Grid>
        </Box>
    );
};
