import apiClient from './client';

// 现货交易复盘（后端 webapp/api/v1_spot_review.py，挂在 /api/v1/review/spot）

export interface NinetySixPointRow {
  time: string;
  actual_volume: number;
  actual_price: number;
  actual_cost: number;
  forecast_volume: number;
  forecast_price: number;
  forecast_cost: number;
  volume_deviation: number;
  volume_deviation_rate: number;
  price_deviation: number;
}

export interface NinetySixPointResp {
  customer_id: string;
  review_date: string;
  data: NinetySixPointRow[];
}

export interface TimeSlotRow {
  slot_name: string;
  volume_ratio: number;
  cost_ratio: number;
  avg_price: number;
}

export interface TimeSlotResp {
  customer_id: string;
  review_date: string;
  time_slot_analysis: TimeSlotRow[];
}

export interface ForecastAccuracy {
  mae: number;
  mape: number;
  rmse: number;
  within_5pct_rate: number;
}

export interface ForecastAccuracyResp {
  customer_id: string;
  review_date: string;
  forecast_accuracy: ForecastAccuracy;
}

const q = (customerId: string, date: string) =>
  '?customer_id=' + encodeURIComponent(customerId) + '&review_date=' + date;

export const get96PointData = (customerId: string, date: string) =>
  apiClient
    .get<NinetySixPointResp>('/api/v1/review/spot/96-point-data' + q(customerId, date))
    .then((r) => r.data);

export const getTimeSlotAnalysis = (customerId: string, date: string) =>
  apiClient
    .get<TimeSlotResp>('/api/v1/review/spot/time-slot-analysis' + q(customerId, date))
    .then((r) => r.data);

export const getReviewForecastAccuracy = (customerId: string, date: string) =>
  apiClient
    .get<ForecastAccuracyResp>('/api/v1/review/spot/forecast-accuracy' + q(customerId, date))
    .then((r) => r.data);
