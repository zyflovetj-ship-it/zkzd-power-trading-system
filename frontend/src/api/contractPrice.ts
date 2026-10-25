/**
 * 中长期合同价格分析 API 客户端
 */
import apiClient from './client';

// 类型定义
export interface CurvePoint {
    period: number;
    time_str: string;
    price: number;
    quantity?: number;
}

export interface ContractTypeSummary {
    contract_type: string;
    contract_period: string;
    daily_total_quantity: number;
    daily_avg_price: number;
    max_price: number | null;
    min_price: number | null;
    peak_valley_spread: number | null;
}

export interface DailySummaryKPIs {
    total_quantity: number;
    overall_avg_price: number;
    price_range_min: number;
    price_range_max: number;
    yearly_ratio: number;
    monthly_ratio: number;
    within_month_ratio: number;
    yearly_avg_price: number | null;
    monthly_avg_price: number | null;
    within_month_avg_price: number | null;
}

export interface DailySummaryResponse {
    date: string;
    kpis: DailySummaryKPIs;
    contract_curves: CurvePoint[];
    spot_curves: CurvePoint[];
    type_summary: ContractTypeSummary[];
    curves_by_type: { [key: string]: CurvePoint[] };
    curves_by_period: { [key: string]: CurvePoint[] };
}


// API 方法
export const contractPriceApi = {
    /**
     * 获取单日汇总数据
     * @param date 日期 YYYY-MM-DD
     * @param entity 实体名称，默认"全市场"
     * @param spotType 现货类型："day_ahead"(日前) 或 "real_time"(实时)
     */
    fetchDailySummary: (date: string, entity: string = '全市场', spotType: string = 'day_ahead') => {
        return apiClient.get<DailySummaryResponse>('/api/v1/contract-price/daily-summary', {
            params: { date, entity, spot_type: spotType }
        });
    }


};
