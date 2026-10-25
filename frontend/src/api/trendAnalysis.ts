import apiClient from './client';

export interface PriceTrendParams {
    start_date: string;
    end_date: string;
}

export const trendAnalysisApi = {
    // 1. 价格趋势分析
    fetchPriceTrend: (params: PriceTrendParams) => {
        return apiClient.get('/api/v1/trend-analysis/price-trend', { params });
    },

    // 2. 星期特性分析
    fetchWeekdayPattern: (params: PriceTrendParams) => {
        return apiClient.get('/api/v1/trend-analysis/weekday-pattern', { params });
    },

    // 3. 波动性分析
    fetchVolatility: (params: PriceTrendParams) => {
        return apiClient.get('/api/v1/trend-analysis/volatility', { params });
    },

    // 4. 储能套利分析
    fetchArbitrage: (params: PriceTrendParams) => {
        return apiClient.get('/api/v1/trend-analysis/arbitrage', { params });
    },

    // 5. 价格异常分析
    fetchAnomaly: (params: PriceTrendParams) => {
        return apiClient.get('/api/v1/trend-analysis/anomaly', { params });
    },

    // 6. 时段统计分析
    fetchTimeSlotStats: (params: PriceTrendParams) => {
        return apiClient.get('/api/v1/trend-analysis/timeslot-stats', { params });
    }
};

