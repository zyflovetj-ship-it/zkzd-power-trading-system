import React, { useState, useEffect, useRef } from 'react';
import { Box, Tabs, Tab, Typography, Paper, useMediaQuery, useTheme, Button, Stack } from '@mui/material';
import { DatePicker, LocalizationProvider } from '@mui/x-date-pickers';
import { AdapterDateFns } from '@mui/x-date-pickers/AdapterDateFns';
import { zhCN } from 'date-fns/locale';
import { subDays, startOfMonth, endOfMonth, format } from 'date-fns';
import TimelineIcon from '@mui/icons-material/Timeline';
import CalendarMonthIcon from '@mui/icons-material/CalendarMonth';
import ShowChartIcon from '@mui/icons-material/ShowChart';
import CompareArrowsIcon from '@mui/icons-material/CompareArrows';
import { PriceTrendTab } from '../components/trend-analysis/PriceTrendTab';
import { TimeSlotAnalysisTab } from '../components/trend-analysis/TimeSlotAnalysisTab';
import { WeekdayPatternTab } from '../components/trend-analysis/WeekdayPatternTab';
import { trendAnalysisApi } from '../api/trendAnalysis';

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
            id={`trend-tabpanel-${index}`}
            aria-labelledby={`trend-tab-${index}`}
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


// 缓存数据类型定义
interface CachedData<T> {
    data: T | null;
    dateRange: string; // 格式: "startDate-endDate"
}

export const SpotTrendAnalysisPage: React.FC = () => {
    const [tabIndex, setTabIndex] = useState(0);
    const theme = useTheme();
    const isMobile = useMediaQuery(theme.breakpoints.down('sm'));
    const isTablet = useMediaQuery(theme.breakpoints.down('md'));

    // 日期区间状态 - 默认最近30天
    const [startDate, setStartDate] = useState<Date | null>(subDays(new Date(), 30));
    const [endDate, setEndDate] = useState<Date | null>(subDays(new Date(), 1));

    // ========== 状态提升：数据管理 ==========
    // 价格走势数据
    const [trendData, setTrendData] = useState<CachedData<any>>({ data: null, dateRange: '' });
    const [trendLoading, setTrendLoading] = useState(false);
    const [trendError, setTrendError] = useState<string | null>(null);

    // 时段分析数据
    const [timeSlotData, setTimeSlotData] = useState<CachedData<any>>({ data: null, dateRange: '' });
    const [timeSlotLoading, setTimeSlotLoading] = useState(false);
    const [timeSlotError, setTimeSlotError] = useState<string | null>(null);

    // 周内特性数据
    const [weekdayData, setWeekdayData] = useState<CachedData<any>>({ data: null, dateRange: '' });
    const [weekdayLoading, setWeekdayLoading] = useState(false);
    const [weekdayError, setWeekdayError] = useState<string | null>(null);

    // 获取当前日期区间标识
    const getCurrentDateRange = (): string => {
        if (!startDate || !endDate) return '';
        return `${format(startDate, 'yyyy-MM-dd')}-${format(endDate, 'yyyy-MM-dd')}`;
    };

    // 加载价格走势数据
    const fetchTrendData = async () => {
        if (!startDate || !endDate) return;

        const dateRange = getCurrentDateRange();

        // 缓存命中检查：如果数据已存在且日期区间相同，不重新加载
        if (trendData.data && trendData.dateRange === dateRange) {
            return;
        }

        setTrendLoading(true);
        setTrendError(null);

        try {
            const start = format(startDate, 'yyyy-MM-dd');
            const end = format(endDate, 'yyyy-MM-dd');
            const response = await trendAnalysisApi.fetchPriceTrend({ start_date: start, end_date: end });
            setTrendData({ data: response.data, dateRange });
        } catch (err: any) {
            console.error('Error fetching price trend:', err);
            setTrendError(err.response?.data?.detail || '获取数据失败');
        } finally {
            setTrendLoading(false);
        }
    };

    // 加载时段分析数据
    const fetchTimeSlotData = async () => {
        if (!startDate || !endDate) return;

        const dateRange = getCurrentDateRange();

        // 缓存命中检查：如果数据已存在且日期区间相同，不重新加载
        if (timeSlotData.data && timeSlotData.dateRange === dateRange) {
            return;
        }

        setTimeSlotLoading(true);
        setTimeSlotError(null);

        try {
            const start = format(startDate, 'yyyy-MM-dd');
            const end = format(endDate, 'yyyy-MM-dd');
            const response = await trendAnalysisApi.fetchTimeSlotStats({ start_date: start, end_date: end });
            setTimeSlotData({ data: response.data, dateRange });
        } catch (err: any) {
            console.error('Error fetching time slot stats:', err);
            setTimeSlotError(err.response?.data?.detail || '获取数据失败');
        } finally {
            setTimeSlotLoading(false);
        }
    };

    // 加载周内特性数据
    const fetchWeekdayData = async () => {
        if (!startDate || !endDate) return;

        const dateRange = getCurrentDateRange();

        // 缓存命中检查：如果数据已存在且日期区间相同，不重新加载
        if (weekdayData.data && weekdayData.dateRange === dateRange) {
            return;
        }

        setWeekdayLoading(true);
        setWeekdayError(null);

        try {
            const start = format(startDate, 'yyyy-MM-dd');
            const end = format(endDate, 'yyyy-MM-dd');
            const response = await trendAnalysisApi.fetchWeekdayPattern({ start_date: start, end_date: end });
            setWeekdayData({ data: response.data, dateRange });
        } catch (err: any) {
            console.error('Error fetching weekday pattern:', err);
            setWeekdayError(err.response?.data?.detail || '获取数据失败');
        } finally {
            setWeekdayLoading(false);
        }
    };

    // 日期变化时清空缓存
    useEffect(() => {
        const newDateRange = getCurrentDateRange();

        // 如果日期区间变化，清空所有缓存数据
        if (trendData.dateRange && trendData.dateRange !== newDateRange) {
            setTrendData({ data: null, dateRange: '' });
        }
        if (timeSlotData.dateRange && timeSlotData.dateRange !== newDateRange) {
            setTimeSlotData({ data: null, dateRange: '' });
        }
        if (weekdayData.dateRange && weekdayData.dateRange !== newDateRange) {
            setWeekdayData({ data: null, dateRange: '' });
        }
    }, [startDate, endDate]);

    // 根据当前 Tab 懒加载数据
    useEffect(() => {
        if (tabIndex === 0) {
            fetchTrendData();
        } else if (tabIndex === 1) {
            fetchTimeSlotData();
        } else if (tabIndex === 2) {
            fetchWeekdayData();
        }
    }, [tabIndex, startDate, endDate]);

    const handleTabChange = (event: React.SyntheticEvent, newValue: number) => {
        setTabIndex(newValue);
    };

    // 快捷按钮处理
    const handleQuickSelect = (type: 'last30' | 'last60' | 'thisMonth' | 'lastMonth') => {
        const today = new Date();
        switch (type) {
            case 'last30':
                setStartDate(subDays(today, 30));
                setEndDate(today);
                break;
            case 'last60':
                setStartDate(subDays(today, 60));
                setEndDate(today);
                break;
            case 'thisMonth':
                setStartDate(startOfMonth(today));
                setEndDate(endOfMonth(today));
                break;
            case 'lastMonth':
                const lastMonth = subDays(startOfMonth(today), 1);
                setStartDate(startOfMonth(lastMonth));
                setEndDate(endOfMonth(lastMonth));
                break;
        }
    };

    // Tab 配置
    const tabsConfig = [
        { icon: <TimelineIcon />, label: '价格走势', mobileLabel: '走势' },
        { icon: <ShowChartIcon />, label: '时段分析', mobileLabel: '时段' },
        { icon: <CalendarMonthIcon />, label: '周内特性', mobileLabel: '周内' },
        { icon: <CompareArrowsIcon />, label: '储能套利', mobileLabel: '套利' },
    ];

    return (
        <LocalizationProvider dateAdapter={AdapterDateFns} adapterLocale={zhCN}>
            <Box sx={{ width: '100%' }}>
                {/* 移动端面包屑标题 */}
                {isTablet && (
                    <Typography
                        variant="subtitle1"
                        sx={{
                            mb: 2,
                            fontWeight: 'bold',
                            color: 'text.primary'
                        }}
                    >
                        价格分析 / 现货趋势分析
                    </Typography>
                )}

                {/* 日期区间选择器 */}
                <Paper variant="outlined" sx={{ p: 2, mb: 2 }}>
                    <Stack
                        direction={{ xs: 'column', md: 'row' }}
                        spacing={{ xs: 1, md: 2 }}
                        alignItems="center"
                    >
                        {/* 日期选择器行 */}
                        <Box sx={{ display: 'flex', gap: 0.5, alignItems: 'center', justifyContent: 'center', width: { xs: '100%', md: 'auto' } }}>
                            <DatePicker
                                label="开始"
                                value={startDate}
                                onChange={(date) => setStartDate(date)}
                                slotProps={{
                                    textField: {
                                        size: "small",
                                        sx: {
                                            width: { xs: '105px', sm: '180px' },
                                            '& .MuiInputBase-input': { fontSize: { xs: '0.8rem', sm: '1rem' }, px: { xs: 1, sm: 1.5 } }
                                        }
                                    }
                                }}
                            />
                            <Typography sx={{ px: 0.5, fontSize: '0.875rem' }}>至</Typography>
                            <DatePicker
                                label="结束"
                                value={endDate}
                                onChange={(date) => setEndDate(date)}
                                slotProps={{
                                    textField: {
                                        size: "small",
                                        sx: {
                                            width: { xs: '105px', sm: '180px' },
                                            '& .MuiInputBase-input': { fontSize: { xs: '0.8rem', sm: '1rem' }, px: { xs: 1, sm: 1.5 } }
                                        }
                                    }
                                }}
                            />
                        </Box>

                        {/* 快捷按钮行 */}
                        <Box sx={{ display: 'flex', gap: 0.5, justifyContent: 'center', width: { xs: '100%', md: 'auto' } }}>
                            <Button
                                variant="outlined"
                                size="small"
                                onClick={() => handleQuickSelect('last30')}
                                sx={{
                                    minWidth: { xs: 'auto', sm: '80px' },
                                    px: { xs: 1, sm: 2 },
                                    fontSize: { xs: '0.75rem', sm: '0.875rem' }
                                }}
                            >
                                最近30天
                            </Button>
                            <Button
                                variant="outlined"
                                size="small"
                                onClick={() => handleQuickSelect('last60')}
                                sx={{
                                    minWidth: { xs: 'auto', sm: '80px' },
                                    px: { xs: 1, sm: 2 },
                                    fontSize: { xs: '0.75rem', sm: '0.875rem' }
                                }}
                            >
                                最近60天
                            </Button>
                            <Button
                                variant="outlined"
                                size="small"
                                onClick={() => handleQuickSelect('thisMonth')}
                                sx={{
                                    minWidth: { xs: 'auto', sm: '80px' },
                                    px: { xs: 1, sm: 2 },
                                    fontSize: { xs: '0.75rem', sm: '0.875rem' }
                                }}
                            >
                                本月
                            </Button>
                            <Button
                                variant="outlined"
                                size="small"
                                onClick={() => handleQuickSelect('lastMonth')}
                                sx={{
                                    minWidth: { xs: 'auto', sm: '80px' },
                                    px: { xs: 1, sm: 2 },
                                    fontSize: { xs: '0.75rem', sm: '0.875rem' }
                                }}
                            >
                                上月
                            </Button>
                        </Box>
                    </Stack>
                </Paper>

                <Paper variant="outlined" sx={{ borderColor: 'divider' }}>
                    <Tabs
                        value={tabIndex}
                        onChange={handleTabChange}
                        aria-label="spot trend analysis tabs"
                        variant="scrollable"
                        scrollButtons="auto"
                        allowScrollButtonsMobile
                        sx={{
                            '& .MuiTabs-scrollButtons': {
                                '&.Mui-disabled': { opacity: 0.3 }
                            },
                            '& .MuiTab-root': {
                                minWidth: { xs: 60, sm: 120 }, // 移动端适中宽度,容纳约5个图标
                                maxWidth: { xs: 'none', sm: 'none' },
                                fontSize: { xs: '0.75rem', sm: '0.9375rem' },
                                px: { xs: 0.5, sm: 2 }, // 移动端保留少量内边距
                                minHeight: { xs: 60, sm: 48 }, // 移动端高度
                                py: { xs: 1, sm: 1.5 }
                            }
                        }}
                    >
                        {tabsConfig.map((tab, index) => (
                            <Tab
                                key={index}
                                icon={tab.icon}
                                iconPosition="top"
                                label={isMobile ? tab.mobileLabel : tab.label}
                                id={`trend-tab-${index}`}
                                aria-controls={`trend-tabpanel-${index}`}
                            />
                        ))}
                    </Tabs>
                </Paper>

                {/* TabPanel 容器 - 需要 relative 定位以支持隐藏面板的 absolute 定位 */}
                <Box sx={{ position: 'relative' }}>
                    <TabPanel value={tabIndex} index={0}>
                        <PriceTrendTab
                            data={trendData.data}
                            loading={trendLoading}
                            error={trendError}
                        />
                    </TabPanel>
                    <TabPanel value={tabIndex} index={1}>
                        <TimeSlotAnalysisTab
                            data={timeSlotData.data}
                            loading={timeSlotLoading}
                            error={timeSlotError}
                        />
                    </TabPanel>
                    <TabPanel value={tabIndex} index={2}>
                        <WeekdayPatternTab
                            data={weekdayData.data}
                            loading={weekdayLoading}
                            error={weekdayError}
                        />
                    </TabPanel>
                    <TabPanel value={tabIndex} index={3}>
                        <Box sx={{ p: 3, textAlign: 'center' }}>储能套利分析 (开发中)</Box>
                    </TabPanel>
                </Box>
            </Box>
        </LocalizationProvider>
    );
};
