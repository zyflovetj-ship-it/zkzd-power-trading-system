import React, { useMemo, useState } from 'react';
import { Box, Typography, Paper, useTheme, Tooltip } from '@mui/material';
import { TouSummary } from '../api/tou';

interface TouHeatmapProps {
    data: TouSummary;
    orientation: 'horizontal' | 'vertical';
    onPeriodClick?: (month: number, timeIndex: number, period: string) => void;
}

const PERIOD_COLORS: { [key: string]: string } = {
    '尖峰': '#d32f2f', // error.main
    '高峰': '#ed6c02', // warning.main
    '平段': '#0288d1', // info.main
    '低谷': '#2e7d32', // success.main
    '深谷': '#9c27b0', // secondary.main
};

const TIME_LABELS = ['00:00', '06:00', '12:00', '18:00', '24:00'];

export const TouHeatmap: React.FC<TouHeatmapProps> = ({ data, orientation, onPeriodClick }) => {
    const theme = useTheme();
    const months = useMemo(() => Array.from({ length: 12 }, (_, i) => i + 1), []);

    // Cell dimensions
    // Horizontal: Width (Time 48 periods) ~22, Height (Months) 36*0.9 ~32
    const cellWidth = orientation === 'horizontal' ? 22 : 22;
    const cellHeight = orientation === 'horizontal' ? 32 : 18;
    const gap = 1;

    // SVG dimensions
    // Time axis now has 48 periods (30 min intervals)
    const timePeriods = 48;
    const xCount = orientation === 'horizontal' ? timePeriods : 12;
    const yCount = orientation === 'horizontal' ? 12 : timePeriods;

    const width = xCount * (cellWidth + gap);
    const height = yCount * (cellHeight + gap);

    // Axis labels
    const renderXAxis = () => {
        if (orientation === 'horizontal') {
            // Time on X
            return (
                <Box sx={{ display: 'flex', justifyContent: 'space-between', width: '100%', mt: 1 }}>
                    {TIME_LABELS.map((label, i) => (
                        <Typography key={i} variant="caption" color="text.secondary">
                            {label}
                        </Typography>
                    ))}
                </Box>
            );
        } else {
            // Months on X
            return (
                <Box sx={{ display: 'flex', width: '100%', mt: 1 }}>
                    {months.map((m) => (
                        <Box key={m} sx={{ flex: 1, textAlign: 'center' }}>
                            <Typography variant="caption" color="text.secondary">
                                {m}
                            </Typography>
                        </Box>
                    ))}
                </Box>
            );
        }
    };

    const renderYAxis = () => {
        if (orientation === 'horizontal') {
            // Months on Y
            return (
                <Box sx={{ display: 'flex', flexDirection: 'column', mr: 1, height: '100%', justifyContent: 'space-between', py: 0.5 }}>
                    {months.map((m) => (
                        <Box key={m} sx={{ flex: 1, display: 'flex', alignItems: 'center' }}>
                            <Typography variant="caption" color="text.secondary">
                                {m}月
                            </Typography>
                        </Box>
                    ))}
                </Box>
            );
        } else {
            // Time on Y
            return (
                <Box sx={{ display: 'flex', flexDirection: 'column', mr: 1, height: '100%', justifyContent: 'space-between' }}>
                    {TIME_LABELS.map((label, i) => (
                        <Typography key={i} variant="caption" color="text.secondary" sx={{ transform: 'translateY(-50%)' }}>
                            {label}
                        </Typography>
                    ))}
                </Box>
            );
        }
    };

    return (
        <Box sx={{ display: 'flex', flexDirection: 'column', alignItems: 'center', width: '100%', maxWidth: orientation === 'horizontal' ? 1320 : 660 }}>
            <Box sx={{ display: 'flex', width: '100%', pt: 2 }}>
                {renderYAxis()}
                <Box sx={{ flex: 1 }}>
                    <svg viewBox={`0 0 ${width} ${height}`} style={{ width: '100%', height: 'auto', display: 'block' }}>
                        {months.map((month) => {
                            const monthData = data.months[month.toString()] || Array(96).fill('平段');
                            // Create 48 periods from 96 data points
                            const periods = Array.from({ length: 48 }, (_, i) => {
                                // Use the value of the first 15-min slot for the 30-min block
                                // Ideally we should check if they differ, but for visualization we merge
                                return monthData[i * 2];
                            });

                            return periods.map((period, index) => {
                                let x, y;
                                if (orientation === 'horizontal') {
                                    x = index * (cellWidth + gap);
                                    y = (month - 1) * (cellHeight + gap);
                                } else {
                                    x = (month - 1) * (cellWidth + gap);
                                    y = index * (cellHeight + gap);
                                }

                                const color = PERIOD_COLORS[period] || '#ccc';
                                // Format time range (e.g., 00:00 - 00:30)
                                const startHour = Math.floor(index / 2).toString().padStart(2, '0');
                                const startMin = ((index % 2) * 30).toString().padStart(2, '0');
                                const endHour = Math.floor((index * 30 + 30) / 60).toString().padStart(2, '0');
                                const endMin = ((index * 30 + 30) % 60).toString().padStart(2, '0');
                                const timeStr = `${startHour}:${startMin}-${endHour}:${endMin}`;

                                return (
                                    <Tooltip
                                        key={`${month}-${index}`}
                                        title={`${month}月 ${timeStr} ${period} (系数: ${data.coefficients[period] || '-'})`}
                                        enterTouchDelay={0}
                                        leaveTouchDelay={3000}
                                    >
                                        <rect
                                            x={x}
                                            y={y}
                                            width={cellWidth}
                                            height={cellHeight}
                                            fill={color}
                                            rx={2}
                                            ry={2}
                                            onClick={() => onPeriodClick && onPeriodClick(month, index * 2, period)}
                                            style={{ cursor: 'pointer', transition: 'opacity 0.2s' }}
                                            onMouseEnter={(e) => e.currentTarget.style.opacity = '0.8'}
                                            onMouseLeave={(e) => e.currentTarget.style.opacity = '1'}
                                        />
                                    </Tooltip>
                                );
                            });
                        })}
                    </svg>
                </Box>
            </Box>
            {renderXAxis()}
        </Box>
    );
};
