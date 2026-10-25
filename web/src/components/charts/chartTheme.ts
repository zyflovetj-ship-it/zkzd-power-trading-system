// 图表通用样式片段与配色，统一各页面 ECharts 视觉风格。

export const CHART_COLORS = [
  '#0958d9', // 电力蓝
  '#13c2c2', // 青
  '#fa8c16', // 橙
  '#52c41a', // 绿
  '#eb2f96', // 品红
  '#722ed1', // 紫
  '#faad14', // 金
  '#f5222d', // 红
];

export const baseGrid = {
  left: 52,
  right: 28,
  top: 56,
  bottom: 44,
  containLabel: true,
} as const;

export const baseTooltip = {
  trigger: 'axis' as const,
  axisPointer: { type: 'cross' as const, label: { backgroundColor: '#6a7985' } },
  confine: true,
};

export const baseLegend = {
  top: 10,
  type: 'scroll' as const,
  icon: 'roundRect' as const,
};

export const baseTextStyle = {
  fontFamily:
    "-apple-system, BlinkMacSystemFont, 'Segoe UI', 'PingFang SC', 'Hiragino Sans GB', 'Microsoft YaHei', sans-serif",
};

// 置信带（预测区间）辅助：返回两条堆叠面积序列，底层透明、上层填充，
// 在 lower 与 upper 之间渲染色带。predicted 线作为独立（非堆叠）序列叠加。
// 调用方需在 legend.data 中排除 `${name}_base` / `${name}` 这两个内部序列名。
export function confidenceBand(name: string, lower: number[], upper: number[], color: string) {
  return [
    {
      name: `${name}_base`,
      type: 'line' as const,
      data: lower,
      stack: `${name}_band`,
      symbol: 'none',
      lineStyle: { opacity: 0 },
      areaStyle: { opacity: 0 },
      silent: true,
      tooltip: { show: false },
      z: 1,
    },
    {
      name,
      type: 'line' as const,
      data: upper.map((u, i) => +(u - (lower[i] ?? u)).toFixed(4)),
      stack: `${name}_band`,
      symbol: 'none',
      lineStyle: { opacity: 0 },
      areaStyle: { color },
      silent: true,
      tooltip: { show: false },
      z: 1,
    },
  ];
}
