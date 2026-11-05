import { useEffect, useMemo, useState } from 'react';
import { App, Card, Col, Empty, Row, Select, Statistic, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { getTouSummary, getTouVersions, TOU_PERIOD_LABEL, type TouSummary } from '@/api/tou';

const PERIOD_COLOR: Record<string, string> = {
  // 中文（后端 tou_rules 实际使用的时段名）
  尖峰: '#820014',
  峰: '#cf1322',
  平: '#595959',
  谷: '#08979c',
  深谷: '#0050b3',
  // 英文/编码（兼容旧数据）
  peak: '#cf1322',
  P: '#cf1322',
  sharp: '#820014',
  S: '#820014',
  flat: '#595959',
  F: '#595959',
  valley: '#08979c',
  V: '#08979c',
  deep: '#0050b3',
};

const PERIOD_ORDER = ['尖峰', '峰', '平', '谷', '深谷'];
const MONTH_KEYS = ['1', '2', '3', '4', '5', '6', '7', '8', '9', '10', '11', '12'];

function fmtMinute(total: number): string {
  if (total === 1440) return '24:00';
  const h = Math.floor(total / 60);
  const m = total % 60;
  return String(h).padStart(2, '0') + ':' + String(m).padStart(2, '0');
}

function pointLabel(i: number): string {
  return fmtMinute(i * 15) + '-' + fmtMinute((i + 1) * 15);
}

export default function TouRulePage() {
  const { message } = App.useApp();
  const [versions, setVersions] = useState<string[]>([]);
  const [version, setVersion] = useState<string>('');
  const [summary, setSummary] = useState<TouSummary | null>(null);
  const [month, setMonth] = useState<string>('1');
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    getTouVersions()
      .then((vs) => {
        setVersions(vs);
        if (vs.length) setVersion(vs[vs.length - 1]);
      })
      .catch((e) => message.error(e?.response?.data?.detail || e?.message || '加载版本失败'));
  }, [message]);

  useEffect(() => {
    if (!version) return;
    setLoading(true);
    getTouSummary(version)
      .then((s) => setSummary(s))
      .catch((e) => message.error(e?.response?.data?.detail || e?.message || '加载摘要失败'))
      .finally(() => setLoading(false));
  }, [version, message]);

  const monthPoints = useMemo(() => summary?.months?.[month] ?? [], [summary, month]);

  // 统计该月各时段类型数量
  const counts = useMemo(() => {
    const c: Record<string, number> = {};
    monthPoints.forEach((p) => {
      c[p] = (c[p] ?? 0) + 1;
    });
    return c;
  }, [monthPoints]);

  const coefColumns: ColumnsType<[string, number]> = [
    { title: '系数项', dataIndex: 0, key: 'k', render: (k: string) => <Tag>{k}</Tag> },
    { title: '数值', dataIndex: 1, key: 'v', render: (v: number) => v.toFixed(4) },
  ];

  const coefData = summary ? Object.entries(summary.coefficients) : [];

  const expandRows = useMemo(() => {
    if (!summary) return [];
    return Array.from({ length: 96 }, (_, i) => {
      const row: Record<string, unknown> = { idx: i, time: pointLabel(i) };
      MONTH_KEYS.forEach((m) => {
        row['m' + m] = summary.months?.[m]?.[i] ?? '';
      });
      return row;
    });
  }, [summary]);

  const expandColumns: ColumnsType<Record<string, unknown>> = [
    { title: '时段', dataIndex: 'time', width: 108, fixed: 'left' },
    ...MONTH_KEYS.map((m) => ({
      title: m + '月',
      dataIndex: 'm' + m,
      width: 64,
      align: 'center' as const,
      render: (v: string) =>
        v ? (
          <span
            style={{
              display: 'inline-block',
              minWidth: 34,
              padding: '0 4px',
              borderRadius: 3,
              background: PERIOD_COLOR[v] ?? '#595959',
              color: '#fff',
              fontSize: 12,
              lineHeight: '18px',
            }}
          >
            {TOU_PERIOD_LABEL[v] ?? v}
          </span>
        ) : (
          '-'
        ),
    })),
  ];

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16} align="middle">
          <Col>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>规则版本</div>
            <Select
              style={{ width: 220 }}
              value={version || undefined}
              placeholder="选择版本"
              options={versions.map((v) => ({ label: v, value: v }))}
              onChange={setVersion}
              loading={loading}
            />
          </Col>
          <Col>
            <div style={{ marginBottom: 4, color: 'rgba(0,0,0,0.45)' }}>查看月份</div>
            <Select
              style={{ width: 120 }}
              value={month}
              options={Array.from({ length: 12 }, (_, i) => ({ label: `${i + 1}月`, value: String(i + 1) }))}
              onChange={setMonth}
            />
          </Col>
        </Row>
      </Card>

      {!summary ? (
        <Card>
          <Empty description="暂无分时电价数据（该模块为只读，规则由数据脚本维护）" />
        </Card>
      ) : (
        <>
        <Row gutter={16}>
          <Col xs={24} lg={10}>
            <Card title="峰谷系数" style={{ marginBottom: 16 }}>
              <Table
                rowKey={(r) => r[0]}
                columns={coefColumns}
                dataSource={coefData}
                pagination={false}
                size="small"
              />
            </Card>
            <Card title={`${month}月 时段类型统计`}>
              <Row gutter={[8, 8]}>
                {Object.entries(counts).map(([k, v]) => (
                  <Col key={k} xs={12} sm={8}>
                    <Statistic
                      title={`${TOU_PERIOD_LABEL[k] ?? k} (${k})`}
                      value={v}
                      suffix="点"
                      valueStyle={{ color: PERIOD_COLOR[k] ?? '#595959' }}
                    />
                  </Col>
                ))}
              </Row>
            </Card>
          </Col>
          <Col xs={24} lg={14}>
            <Card title={`${month}月 96 点时段类型分布`}>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 2 }}>
                {monthPoints.map((p, i) => (
                  <div
                    key={i}
                    title={`第${i + 1}点: ${TOU_PERIOD_LABEL[p] ?? p}`}
                    style={{
                      width: 10,
                      height: 22,
                      backgroundColor: PERIOD_COLOR[p] ?? '#595959',
                      borderRadius: 2,
                    }}
                  />
                ))}
              </div>
              <div style={{ marginTop: 12 }}>
                {PERIOD_ORDER.filter((k) => counts[k])
                  .concat(Object.keys(counts).filter((k) => !PERIOD_ORDER.includes(k)))
                  .map((k) => (
                    <Tag key={k} color={PERIOD_COLOR[k] ?? '#595959'} style={{ marginBottom: 4 }}>
                      {TOU_PERIOD_LABEL[k] ?? k} {counts[k]}点
                    </Tag>
                  ))}
              </div>
            </Card>
          </Col>
        </Row>

        <Card title="96 点时段展开表（12 个月对照）" style={{ marginTop: 16 }}>
          <Table
            rowKey="idx"
            size="small"
            bordered
            pagination={false}
            scroll={{ x: 'max-content', y: 520 }}
            dataSource={expandRows}
            columns={expandColumns}
          />
        </Card>
        </>
      )}
    </div>
  );
}
