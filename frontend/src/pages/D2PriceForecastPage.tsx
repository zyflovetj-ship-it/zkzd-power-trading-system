import React, { useState } from 'react';
import {
    Box,
    Typography,
    Tabs,
    Tab,
    Paper,
    useTheme,
    useMediaQuery,
} from '@mui/material';
import { D2ForecastCurveTab } from '../components/D2ForecastCurveTab';
import { D2ComparisonTab } from '../components/D2ComparisonTab';
import { D2AccuracyTab } from '../components/D2AccuracyTab';

// TabPanel组件
interface TabPanelProps {
    children?: React.ReactNode;
    index: number;
    value: number;
}

function TabPanel(props: TabPanelProps) {
    const { children, value, index, ...other } = props;
    return (
        <div
            role="tabpanel"
            hidden={value !== index}
            id={`d2-price-forecast-tabpanel-${index}`}
            aria-labelledby={`d2-price-forecast-tab-${index}`}
            {...other}
        >
            {value === index && (
                <Box sx={{ pt: 3 }}>
                    {children}
                </Box>
            )}
        </div>
    );
}

export const D2PriceForecastPage: React.FC = () => {
    const [activeTab, setActiveTab] = useState(0);
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('md'));

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setActiveTab(newValue);
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
                    价格预测 / D-2价格预测
                </Typography>
            )}

            {/* 主内容卡片 */}
            <Paper variant="outlined" sx={{ borderColor: 'divider' }}>
                <Tabs
                    value={activeTab}
                    onChange={handleTabChange}
                    aria-label="D-2 price forecast tabs"
                >
                    <Tab label="预测曲线" id="d2-price-forecast-tab-0" aria-controls="d2-price-forecast-tabpanel-0" />
                    <Tab label="对比分析" id="d2-price-forecast-tab-1" aria-controls="d2-price-forecast-tabpanel-1" />
                    <Tab label="精度统计" id="d2-price-forecast-tab-2" aria-controls="d2-price-forecast-tabpanel-2" />
                </Tabs>
            </Paper>

            <TabPanel value={activeTab} index={0}>
                <D2ForecastCurveTab />
            </TabPanel>
            <TabPanel value={activeTab} index={1}>
                <D2ComparisonTab />
            </TabPanel>
            <TabPanel value={activeTab} index={2}>
                <D2AccuracyTab />
            </TabPanel>
        </Box>
    );
};
