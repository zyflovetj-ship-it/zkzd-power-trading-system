import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Alert, Card, DatePicker, Select, Space, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import dayjs, { Dayjs } from 'dayjs';
import { KpiCards } from '@/components/charts/KpiCards';
import { getShortTermAccuracy, getShortTermList } from '@/api/loadForecast';
import { CHART_COLORS } from '@/components/charts/chartTheme';
import type { ShortTermListRow } from '@/api/loadForecast';

const TYPES = [
  { value: 'd+1', label: 'D+1' },
  { value: 'd+2', label: 'D+2' },
  { value: 'd+3', label: 'D+3' },
];

// 预测精度分析：单日精度指标 + 近期预测批次列表。
export default function LoadForecastAccuracyPage() {
  const [date, setDate] = useState<Dayjs>(dayjs().subtract(1, 'day'));
  const [type, setType] = useState<string>('d+1');
  const [range, setRange] = useState<[Dayjs, Dayjs]>([dayjs().subtract(30, 'day'), dayjs()]);

  const accQ = useQuery({
    queryKey: ['accPage', date.format('YYYY-MM-DD'), type],
    queryFn: () => getShortTermAccuracy(date.format('YYYY-MM-DD'), type),
  });
  const listQ = useQuery({
    queryKey: ['listPage', range[0].format('YYYY-MM-DD'), range[1].format('YYYY-MM-DD')],
    queryFn: () => getShortTermList(range[0].format('YYYY-MM-DD'), range[1].format('YYYY-MM-DD')),
  });

  const rows: ShortTermListRow[] = listQ.data ?? [];

  const columns: ColumnsType<ShortTermListRow> = [
    { title: '预测生成日期', dataIndex: 'forecast_date', key: 'forecast_date' },
    { title: '预测目标日期', dataIndex: 'forecast_target_date', key: 'forecast_target_date' },
    {
      title: '预测类型',
      dataIndex: 'forecast_types',
      key: 'forecast_types',
      render: (v: string[]) => v.map((t) => <Tag key={t}>{t}</Tag>),
    },
    {
      title: '含实际值',
      dataIndex: 'has_actual',
      key: 'has_actual',
      render: (v: boolean) => (v ? <Tag color="green">是</Tag> : <Tag>否</Tag>),
    },
  ];

  return (
    <div>
      <Card size="small" title="单日预测精度" style={{ marginBottom: 16 }}>
        <Space wrap style={{ marginBottom: 12 }}>
          <DatePicker value={date} onChange={(d) => d && setDate(d)} allowClear={false} />
          <Select value={type} onChange={setType} options={TYPES} style={{ width: 120 }} />
        </Space>
        {accQ.isError && <Alert type="warning" showIcon message={(accQ.error as any)?.response?.data?.detail || '该日期暂无精度数据，请选择有实际数据的预测日期'} style={{ marginBottom: 12 }} />}
        {accQ.data && (
          <KpiCards
            loading={accQ.isLoading}
            items={[
              { label: 'MAE', value: accQ.data.mae, precision: 2, suffix: 'MW', color: CHART_COLORS[0] },
              { label: 'MAPE', value: accQ.data.mape, precision: 2, suffix: '%', color: CHART_COLORS[1] },
              { label: 'RMSE', value: accQ.data.rmse, precision: 2, suffix: 'MW', color: CHART_COLORS[2] },
              { label: '最大误差', value: accQ.data.max_error, precision: 2, suffix: 'MW', color: CHART_COLORS[3] },
              { label: '最大误差时刻', value: accQ.data.max_error_time || '-' },
            ]}
          />
        )}
      </Card>

      <Card size="small" title="预测批次列表">
        <Space wrap style={{ marginBottom: 12 }}>
          <DatePicker.RangePicker value={range} onChange={(r) => { const [a, b] = r ?? [null, null]; if (a && b) setRange([a, b]); }} />
        </Space>
        {listQ.isError && <Alert type="error" showIcon message="加载预测批次失败" />}
        <Table
          rowKey="forecast_date"
          size="small"
          columns={columns}
          dataSource={rows}
          loading={listQ.isLoading}
          pagination={{ pageSize: 10, hideOnSinglePage: true }}
        />
      </Card>
    </div>
  );
}
