import React, { useEffect, useState } from 'react';
import {
    Box,
    Typography,
    Select,
    MenuItem,
    FormControl,
    InputLabel,
    Paper,
    useMediaQuery,
    useTheme,
    CircularProgress,
    Alert,
    Grid,
    Divider
} from '@mui/material';
import { getTouVersions, getTouSummary, TouSummary } from '../api/tou';
import { TouHeatmap } from '../components/TouHeatmap';

const TouRulesPage: React.FC = () => {
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));
    const isLandscape = useMediaQuery('(orientation: landscape)');

    // Determine orientation based on device and screen orientation
    const orientation = isMobile && !isLandscape ? 'vertical' : 'horizontal';

    const [versions, setVersions] = useState<string[]>([]);
    const [selectedVersion, setSelectedVersion] = useState<string>('');
    const [summary, setSummary] = useState<TouSummary | null>(null);
    const [loading, setLoading] = useState<boolean>(false);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        const fetchVersions = async () => {
            try {
                const v = await getTouVersions();
                setVersions(v);
                if (v.length > 0) {
                    setSelectedVersion(v[0]);
                }
            } catch (err) {
                console.error("Failed to fetch TOU versions", err);
                setError("无法获取分时电价版本列表");
            }
        };
        fetchVersions();
    }, []);

    useEffect(() => {
        if (!selectedVersion) return;

        const fetchSummary = async () => {
            setLoading(true);
            setError(null);
            try {
                const data = await getTouSummary(selectedVersion);
                setSummary(data);
            } catch (err) {
                console.error("Failed to fetch TOU summary", err);
                setError("无法获取分时电价规则详情");
            } finally {
                setLoading(false);
            }
        };
        fetchSummary();
    }, [selectedVersion]);

    const renderContent = () => {
        return (
            <Paper sx={{ p: 2, position: 'relative', minHeight: 400, display: 'flex', flexDirection: 'column' }} elevation={2}>
                {/* Header inside Paper */}
                <Box sx={{ display: 'flex', alignItems: 'center', mb: 2 }}>
                    <Typography variant="body2" sx={{ mr: 1, fontWeight: 'bold' }}>
                        政策版本:
                    </Typography>
                    <FormControl size="small" sx={{ minWidth: 150 }}>
                        <Select
                            value={selectedVersion}
                            onChange={(e) => setSelectedVersion(e.target.value)}
                            displayEmpty
                        >
                            {versions.map((v) => (
                                <MenuItem key={v} value={v}>{v}</MenuItem>
                            ))}
                        </Select>
                    </FormControl>
                </Box>
                <Divider sx={{ mb: 2 }} />

                {/* Loading Overlay */}
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

                {error ? (
                    <Alert severity="error">{error}</Alert>
                ) : summary ? (
                    <Box sx={{ flex: 1, width: '100%', overflow: 'auto', display: 'flex', flexDirection: 'column', alignItems: 'center', opacity: loading ? 0.5 : 1 }}>
                        {/* Legend */}
                        <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap', justifyContent: 'center' }}>
                            {['尖峰', '高峰', '平段', '低谷', '深谷']
                                .filter(type => type in summary.coefficients)
                                .map(type => {
                                    const coeff = summary.coefficients[type];
                                    return (
                                        <Box key={type} sx={{ display: 'flex', alignItems: 'center', gap: 1, bgcolor: 'action.hover', px: 1, py: 0.5, borderRadius: 1 }}>
                                            <Box sx={{
                                                width: 12,
                                                height: 12,
                                                borderRadius: '50%',
                                                bgcolor: type === '尖峰' ? '#d32f2f' :
                                                    type === '高峰' ? '#ed6c02' :
                                                        type === '平段' ? '#0288d1' :
                                                            type === '低谷' ? '#2e7d32' :
                                                                '#9c27b0'
                                            }} />
                                            <Typography variant="body2" fontWeight="medium">
                                                {type}
                                            </Typography>
                                            <Typography variant="caption" color="text.secondary">
                                                ({coeff})
                                            </Typography>
                                        </Box>
                                    );
                                })}
                        </Box>

                        <Box sx={{ flex: 1, display: 'flex', justifyContent: 'center', width: '100%', overflow: 'auto' }}>
                            <TouHeatmap
                                data={summary}
                                orientation={orientation}
                            />
                        </Box>

                        <Box sx={{ mt: 3, width: '100%', p: 2, bgcolor: 'background.default', borderRadius: 1 }}>
                            <Typography variant="subtitle2" gutterBottom color="text.primary">
                                说明
                            </Typography>
                            <Typography variant="body2" color="text.secondary" display="block">
                                1. 图表展示了全年各月、各时段的电价类型分布。
                            </Typography>
                            {summary.version >= '2024-01-01' && (
                                <Typography variant="body2" color="text.secondary" display="block">
                                    2. 节假日政策：春节、"五一"国际劳动节、国庆节期间，12:00-14:00执行深谷电价。
                                </Typography>
                            )}
                        </Box>
                    </Box>
                ) : (
                    !loading && <Alert severity="info">请选择版本查看详情</Alert>
                )}
            </Paper>
        );
    };

    return (
        <Box sx={{ width: '100%' }}>
            {/* Mobile Breadcrumb */}
            {isTablet && (
                <Typography
                    variant="subtitle1"
                    sx={{
                        mb: 2,
                        fontWeight: 'bold',
                        color: 'text.primary'
                    }}
                >
                    基础数据 / 时段电价分布
                </Typography>
            )}

            <Grid container spacing={3}>
                <Grid size={{ xs: 12 }}>
                    {renderContent()}
                </Grid>
            </Grid>
        </Box>
    );
};

export default TouRulesPage;
