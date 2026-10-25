// 分时电价（TOU）时段语义配色 —— 复用原前端常量，作为图表与标签统一语义色。
// 尖峰/高峰/平段/低谷/深谷
export const touPeriodColors: Record<string, string> = {
  sharp_peak: '#cf1322', // 尖峰 - 红
  peak: '#fa8c16', // 高峰 - 橙
  flat: '#1890ff', // 平段 - 蓝
  valley: '#52c41a', // 低谷 - 绿
  deep_valley: '#13c2c2', // 深谷 - 青
};

// 中文标签
export const touPeriodLabels: Record<string, string> = {
  sharp_peak: '尖峰',
  peak: '高峰',
  flat: '平段',
  valley: '低谷',
  deep_valley: '深谷',
};

// 状态色映射（沿用原前端开发规范：成功/生效/执行中=success，草稿/待处理=warning，终止/归档=default，错误=error，意向/信息=info，暂停=warning）
export const statusColorMap: Record<string, 'success' | 'warning' | 'default' | 'error' | 'info'> = {
  // 客户状态
  prospect: 'info',
  pending: 'warning',
  active: 'success',
  suspended: 'warning',
  terminated: 'default',
  // 套餐状态
  draft: 'warning',
  effective: 'success',
  archived: 'default',
  // 合同状态
  signed: 'success',
  expired: 'default',
};

export const statusLabelMap: Record<string, string> = {
  prospect: '意向客户',
  pending: '待生效',
  active: '执行中',
  suspended: '已暂停',
  terminated: '已终止',
  draft: '草稿',
  effective: '生效',
  archived: '已归档',
  signed: '已签约',
  expired: '已过期',
};
