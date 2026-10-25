import { Card, Col, Row, Statistic } from 'antd';

export interface KpiItem {
  label: string;
  value: number | string;
  precision?: number;
  prefix?: string;
  suffix?: string;
  color?: string;
  valueStyle?: React.CSSProperties;
}

interface KpiCardsProps {
  items: KpiItem[];
  loading?: boolean;
  columns?: number;
}

// 指标卡片组：一行多列展示关键 KPI。
export function KpiCards({ items, loading, columns = 4 }: KpiCardsProps) {
  return (
    <Row gutter={[16, 16]} style={{ marginBottom: 16 }}>
      {items.map((it) => (
        <Col key={it.label} flex={`1 1 calc(${100 / columns}% - 16px)`} style={{ minWidth: 180 }}>
          <Card size="small" loading={loading}>
            <Statistic
              title={it.label}
              value={it.value}
              precision={it.precision}
              prefix={it.prefix}
              suffix={it.suffix}
              valueStyle={it.color ? { color: it.color, ...it.valueStyle } : it.valueStyle}
            />
          </Card>
        </Col>
      ))}
    </Row>
  );
}
