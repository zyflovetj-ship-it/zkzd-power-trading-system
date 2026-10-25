import { useEffect, useMemo, useState } from 'react';
import { App, Card, Col, Empty, Row, Select, Statistic, Table, Tag } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { getTouSummary, getTouVersions, TOU_PERIOD_LABEL, type TouSummary } from '@/api/tou';

const PERIOD_COLOR: Record<string, string> = {
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
                {Object.keys(PERIOD_COLOR).map((k) => (
                  <Tag key={k} color={PERIOD_COLOR[k]} style={{ marginBottom: 4 }}>
                    {TOU_PERIOD_LABEL[k] ?? k}
                  </Tag>
                ))}
              </div>
            </Card>
          </Col>
        </Row>
      )}
    </div>
  );
}
