import ReactECharts from 'echarts-for-react';
import type { EChartsOption } from 'echarts';
import type { CSSProperties } from 'react';

interface EChartProps {
  option: EChartsOption;
  style?: CSSProperties;
  height?: number | string;
  loading?: boolean;
  notMerge?: boolean;
  onEvents?: Record<string, (params: unknown) => void>;
}

// 通用 ECharts 封装：自适应尺寸、支持 loading、事件绑定。
export function EChart({
  option,
  style,
  height = 400,
  loading = false,
  notMerge = true,
  onEvents,
}: EChartProps) {
  return (
    <ReactECharts
      option={option}
      notMerge={notMerge}
      lazyUpdate
      showLoading={loading}
      loadingOption={{
        text: '加载中...',
        color: '#0958d9',
        textColor: '#595959',
        maskColor: 'rgba(255,255,255,0.6)',
      }}
      style={{ height, width: '100%', ...style }}
      onEvents={onEvents}
    />
  );
}
