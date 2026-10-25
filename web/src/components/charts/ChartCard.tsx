import { Card } from 'antd';
import type { CSSProperties, ReactNode } from 'react';
import type { EChartsOption } from 'echarts';
import { EChart } from '@/components/charts/EChart';

interface ChartCardProps {
  title: string;
  option: EChartsOption;
  height?: number;
  loading?: boolean;
  extra?: ReactNode;
  style?: CSSProperties;
  bodyStyle?: CSSProperties;
}

// 带标题的图表卡片：统一卡片容器 + ECharts 封装。
export function ChartCard({ title, option, height = 360, loading, extra, style, bodyStyle }: ChartCardProps) {
  return (
    <Card
      size="small"
      title={title}
      extra={extra}
      style={{ marginBottom: 16, ...style }}
      styles={{ body: { padding: 12, ...bodyStyle } }}
    >
      <EChart option={option} height={height} loading={loading} />
    </Card>
  );
}
