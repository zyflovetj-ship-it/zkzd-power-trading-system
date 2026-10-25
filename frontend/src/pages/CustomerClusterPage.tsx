import React, { useState } from 'react';
import {
    Box, Typography, Paper, Button, TextField, CircularProgress, Alert, Card, CardContent, Chip,
    Table, TableBody, TableCell, TableContainer, TableHead, TableRow, Grid
} from '@mui/material';
import {
    ScatterChart, Scatter, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
    RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar
} from 'recharts';
import DownloadIcon from '@mui/icons-material/Download';
import apiClient from '../api/client';

const CLUSTER_COLORS = ['#1976d2', '#2e7d32', '#ed6c02', '#9c27b0', '#d32f2f', '#0097a7', '#7b1fa2', '#f57c00', '#388e3c', '#c62828'];

export const CustomerClusterPage: React.FC = () => {
    const [nClusters, setNClusters] = useState(3);
    const [data, setData] = useState<any>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const handleCluster = () => {
        setLoading(true);
        setError(null);
        apiClient.post('/api/v1/customer-cluster', { n_clusters: nClusters, features: ['peak_valley_ratio', 'load_rate', 'volatility'] })
            .then(res => setData(res.data))
            .catch(err => setError(err.response?.data?.detail || err.message))
            .finally(() => setLoading(false));
    };

    const handleExport = () => {
        window.open(`/api/v1/customer-cluster/export?n_clusters=${nClusters}`, '_blank');
    };

    const scatterData = (data?.results || []).map((r: any) => ({
        x: r.features?.peak_valley_ratio || 0,
        y: r.features?.load_rate || 0,
        z: r.features?.volatility || 0,
        name: r.customer_name,
        cluster: r.cluster
    }));

    const radarData = (data?.summary || []).map((s: any) => ({
        cluster: `簇${s.cluster_id}`,
        peak_valley_ratio: s.avg_peak_valley_ratio,
        load_rate: s.avg_load_rate,
        volatility: s.avg_volatility
    }));

    const chartRadarInput = [
        { feature: '峰谷比', ...Object.fromEntries(radarData.map((r: any) => [r.cluster, r.peak_valley_ratio])) },
        { feature: '负荷率', ...Object.fromEntries(radarData.map((r: any) => [r.cluster, r.load_rate])) },
        { feature: '波动性', ...Object.fromEntries(radarData.map((r: any) => [r.cluster, r.volatility])) },
    ];

    return (
        <Box>
            <Typography variant="h5" gutterBottom>客户聚类分析</Typography>

            <Paper variant="outlined" sx={{ p: 2, mb: 2, display: 'flex', gap: 2, alignItems: 'center', flexWrap: 'wrap' }}>
                <TextField
                    label="聚类数"
                    type="number"
                    size="small"
                    value={nClusters}
                    onChange={e => setNClusters(parseInt(e.target.value) || 3)}
                    inputProps={{ min: 2, max: 10 }}
                    sx={{ width: 100 }}
                    disabled={loading}
                />
                <Button variant="contained" onClick={handleCluster} disabled={loading}>
                    {loading ? '聚类中...' : '执行聚类'}
                </Button>
                {data && (
                    <Button variant="outlined" startIcon={<DownloadIcon />} onClick={handleExport} disabled={loading}>
                        导出
                    </Button>
                )}
            </Paper>

            {error && <Alert severity="error" sx={{ mb: 2 }}>{error}</Alert>}

            {loading && !data && (
                <Box display="flex" justifyContent="center" alignItems="center" minHeight={300}>
                    <CircularProgress />
                </Box>
            )}

            {loading && data && (
                <Box sx={{ position: 'relative' }}>
                    <Box sx={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', backgroundColor: 'rgba(255, 255, 255, 0.7)', zIndex: 1000 }}>
                        <CircularProgress />
                    </Box>
                </Box>
            )}

            {data && (
                <>
                    <Grid container spacing={{ xs: 1, sm: 2 }} sx={{ mb: 2 }}>
                        {(data.summary || []).map((s: any) => (
                            <Grid size={{ xs: 12, sm: 6, md: 4 }} key={s.cluster_id}>
                                <Card variant="outlined">
                                    <CardContent sx={{ p: { xs: 1, sm: 2 }, '&:last-child': { pb: { xs: 1, sm: 2 } } }}>
                                        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 1 }}>
                                            <Chip label={`簇 ${s.cluster_id}`} size="small"
                                                sx={{ bgcolor: CLUSTER_COLORS[s.cluster_id % CLUSTER_COLORS.length], color: '#fff' }} />
                                            <Typography variant="body2">{s.count} 个客户</Typography>
                                        </Box>
                                        <Typography variant="caption" display="block">平均峰谷比: {s.avg_peak_valley_ratio}</Typography>
                                        <Typography variant="caption" display="block">平均负荷率: {s.avg_load_rate}</Typography>
                                        <Typography variant="caption" display="block">平均波动性: {s.avg_volatility}</Typography>
                                    </CardContent>
                                </Card>
                            </Grid>
                        ))}
                    </Grid>

                    <Grid container spacing={{ xs: 1, sm: 2 }} sx={{ mb: 2 }}>
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Paper variant="outlined" sx={{ p: { xs: 1, sm: 2 } }}>
                                <Typography variant="subtitle1" gutterBottom>聚类散点图</Typography>
                                <Box sx={{ height: { xs: 300, sm: 350 } }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <ScatterChart>
                                            <CartesianGrid strokeDasharray="3 3" />
                                            <XAxis dataKey="x" name="峰谷比" tick={{ fontSize: 10 }} />
                                            <YAxis dataKey="y" name="负荷率" tick={{ fontSize: 10 }} />
                                            <Tooltip cursor={{ strokeDasharray: '3 3' }} />
                                            <Legend />
                                            {Array.from({ length: nClusters }, (_, i) => (
                                                <Scatter key={i} name={`簇${i}`} data={scatterData.filter((d: any) => d.cluster === i)}
                                                    fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]} />
                                            ))}
                                        </ScatterChart>
                                    </ResponsiveContainer>
                                </Box>
                            </Paper>
                        </Grid>
                        <Grid size={{ xs: 12, md: 6 }}>
                            <Paper variant="outlined" sx={{ p: { xs: 1, sm: 2 } }}>
                                <Typography variant="subtitle1" gutterBottom>特征对比雷达图</Typography>
                                <Box sx={{ height: { xs: 300, sm: 350 } }}>
                                    <ResponsiveContainer width="100%" height="100%">
                                        <RadarChart data={chartRadarInput}>
                                            <PolarGrid />
                                            <PolarAngleAxis dataKey="feature" tick={{ fontSize: 11 }} />
                                            <PolarRadiusAxis />
                                            {radarData.map((r: any, i: number) => (
                                                <Radar key={i} name={r.cluster} dataKey={r.cluster}
                                                    stroke={CLUSTER_COLORS[i % CLUSTER_COLORS.length]}
                                                    fill={CLUSTER_COLORS[i % CLUSTER_COLORS.length]} fillOpacity={0.2} />
                                            ))}
                                            <Legend />
                                            <Tooltip />
                                        </RadarChart>
                                    </ResponsiveContainer>
                                </Box>
                            </Paper>
                        </Grid>
                    </Grid>

                    <TableContainer component={Paper} variant="outlined" sx={{ overflowX: 'auto' }}>
                        <Table size="small" sx={{ '& .MuiTableCell-root': { fontSize: { xs: '0.75rem', sm: '0.875rem' }, px: { xs: 0.5, sm: 2 } } }}>
                            <TableHead>
                                <TableRow>
                                    <TableCell>客户</TableCell>
                                    <TableCell>簇</TableCell>
                                    <TableCell>峰谷比</TableCell>
                                    <TableCell>负荷率</TableCell>
                                    <TableCell>波动性</TableCell>
                                </TableRow>
                            </TableHead>
                            <TableBody>
                                {(data.results || []).map((r: any) => (
                                    <TableRow key={r.customer_id}>
                                        <TableCell>{r.customer_name}</TableCell>
                                        <TableCell>
                                            <Chip label={`簇${r.cluster}`} size="small"
                                                sx={{ bgcolor: CLUSTER_COLORS[r.cluster % CLUSTER_COLORS.length], color: '#fff' }} />
                                        </TableCell>
                                        <TableCell>{r.features?.peak_valley_ratio}</TableCell>
                                        <TableCell>{r.features?.load_rate}</TableCell>
                                        <TableCell>{r.features?.volatility}</TableCell>
                                    </TableRow>
                                ))}
                            </TableBody>
                        </Table>
                    </TableContainer>
                </>
            )}
        </Box>
    );
};

export default CustomerClusterPage;
