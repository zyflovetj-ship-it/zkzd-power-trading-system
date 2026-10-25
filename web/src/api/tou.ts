import apiClient from './client';

// 分时电价规则（tou_rules）—— 后端仅提供版本列表 + 指定版本摘要（只读）
export interface TouSummary {
  version: string;
  months: { [monthIndex: string]: string[] }; // key: "1".."12"，value: 96 个时段类型字符串
  coefficients: { [key: string]: number };
}

export async function getTouVersions(): Promise<string[]> {
  const r = await apiClient.get('/api/v1/tou-rules/versions');
  return r.data;
}

export async function getTouSummary(version: string): Promise<TouSummary> {
  const r = await apiClient.get('/api/v1/tou-rules/summary', { params: { version } });
  return r.data;
}

// 时段类型中文映射（与后端 day_type / period_type 对齐，按需扩展）
export const TOU_PERIOD_LABEL: Record<string, string> = {
  peak: '峰',
  flat: '平',
  valley: '谷',
  sharp: '尖',
  deep: '深谷',
  P: '峰',
  F: '平',
  V: '谷',
  S: '尖',
};
