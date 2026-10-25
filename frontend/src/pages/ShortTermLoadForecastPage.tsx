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
import { ShortTermForecastCurveTab } from '../components/ShortTermForecastCurveTab';
import { ShortTermForecastComparisonTab } from '../components/ShortTermForecastComparisonTab';
import { ShortTermForecastAccuracyTab } from '../components/ShortTermForecastAccuracyTab';

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
            id={`short-term-forecast-tabpanel-${index}`}
            aria-labelledby={`short-term-forecast-tab-${index}`}
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

export const ShortTermLoadForecastPage: React.FC = () => {
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
                    负荷预测 / 短期负荷预测
                </Typography>
            )}

            {/* 主内容卡片 */}
            <Paper variant="outlined" sx={{ borderColor: 'divider' }}>
                <Tabs
                    value={activeTab}
                    onChange={handleTabChange}
                    aria-label="short term load forecast tabs"
                >
                    <Tab label="预测曲线" id="short-term-forecast-tab-0" aria-controls="short-term-forecast-tabpanel-0" />
                    <Tab label="对比分析" id="short-term-forecast-tab-1" aria-controls="short-term-forecast-tabpanel-1"/>
                    <Tab label="精度统计" id="short-term-forecast-tab-2" aria-controls="short-term-forecast-tabpanel-2"/>
                </Tabs>
            </Paper>

            <TabPanel value={activeTab} index={0}>
                <ShortTermForecastCurveTab />
            </TabPanel>
            <TabPanel value={activeTab} index={1}>
                <ShortTermForecastComparisonTab />
            </TabPanel>
            <TabPanel value={activeTab} index={2}>
                <ShortTermForecastAccuracyTab />
            </TabPanel>
        </Box>
    );
};
