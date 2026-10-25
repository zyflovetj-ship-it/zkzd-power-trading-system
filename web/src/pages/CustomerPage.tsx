import React, { useEffect, useRef, useState } from 'react';
import { App, Button, Card, Col, Divider, Dropdown, Form, Input, InputNumber, Row, Space, Tag, Typography } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { DeleteOutlined, DownOutlined, PlusOutlined } from '@ant-design/icons';
import { CrudPage } from '@/components/crud/CrudPage';
import type { CrudField, SearchField } from '@/components/crud/types';

import {
  CUSTOMER_STATUS_OPTIONS,
  INDUSTRIES,
  REGIONS,
  USER_TYPES,
  VOLTAGE_LEVELS,
  activateCustomer,
  cancelContract,
  createCustomer,
  deleteCustomer,
  fetchCustomers,
  getCustomer,
  resumeCustomer,
  signContract,
  suspendCustomer,
  terminateCustomer,
  updateCustomer,
  type CustomerListItem,
  type CustomerStatus,
} from '@/api/customers';

const STATUS_COLOR: Record<CustomerStatus, string> = {
  prospect: 'default',
  pending: 'blue',
  active: 'green',
  suspended: 'orange',
  terminated: 'red',
};
const STATUS_LABEL: Record<CustomerStatus, string> = {
  prospect: '意向',
  pending: '待生效',
  active: '执行中',
  suspended: '已暂停',
  terminated: '已终止',
};

const searchFields: SearchField[] = [
  { name: 'keyword', label: '关键字', type: 'text', placeholder: '客户名称' },
  { name: 'user_type', label: '用户类型', type: 'select', options: USER_TYPES.map((v) => ({ label: v, value: v })) },
  { name: 'industry', label: '行业', type: 'select', options: INDUSTRIES.map((v) => ({ label: v, value: v })) },
  { name: 'region', label: '地区', type: 'select', options: REGIONS.map((v) => ({ label: v, value: v })) },
  { name: 'status', label: '状态', type: 'select', options: CUSTOMER_STATUS_OPTIONS },
];

export default function CustomerPage() {
  const [administrativeDivisions, setAdministrativeDivisions] = useState<{ city: string; divisions: string[] }[]>([]);

  useEffect(() => {
    fetch('/jiangsu_administrative_divisions.json')
      .then((r) => r.json())
      .then((data) => setAdministrativeDivisions(data))
      .catch(() => {});
  }, []);

  const formFields: CrudField[] = [
    { name: 'user_name', label: '客户名称', type: 'text', required: true, span: 12 },
    { name: 'short_name', label: '简称', type: 'text', span: 12 },
    { name: 'user_type', label: '用户类型', type: 'select', options: USER_TYPES.map((v) => ({ label: v, value: v })), span: 12 },
    { name: 'industry', label: '行业', type: 'select', options: INDUSTRIES.map((v) => ({ label: v, value: v })), span: 12 },
    { name: 'voltage', label: '电压等级', type: 'select', options: VOLTAGE_LEVELS.map((v) => ({ label: v, value: v })), span: 12 },
    { name: 'region', label: '地区', type: 'select', options: REGIONS.map((v) => ({ label: v, value: v })), span: 12 },
    {
      name: 'district',
      label: '区县',
      type: 'select',
      span: 12,
      dependsOn: 'region',
      fetchOptions: async (region: string) => {
        const city = administrativeDivisions.find((d) => d.city === region);
        return (city?.divisions ?? []).map((d) => ({ label: d, value: d }));
      },
    },
    { name: 'address', label: '地址', type: 'text', span: 24 },
    { name: 'contact_person', label: '联系人', type: 'text', span: 12 },
    { name: 'contact_phone', label: '联系电话', type: 'text', span: 12 },

  ];

  const reloadRef = useRef(() => {});
  const { message, modal } = App.useApp();

  const runAction = async (fn: () => Promise<unknown>, label: string) => {
    try {
      await fn();
      message.success(`${label}成功`);
      reloadRef.current();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || `${label}失败`);
    }
  };

  const showConfirm = (
    title: string,
    label: string,
    action: (reason: string) => Promise<unknown>,
  ) => {
    let reason = '';
    modal.confirm({
      title,
      content: (
        <Input.TextArea
          placeholder="请输入原因（选填）"
          rows={3}
          onChange={(e) => { reason = e.target.value; }}
        />
      ),
      onOk: () => {
        runAction(() => action(reason), label);
      },
    });
  };

  const columns: ColumnsType<CustomerListItem> = [
    { title: '客户名称', dataIndex: 'user_name', width: 180, fixed: 'left' },

    { title: '简称', dataIndex: 'short_name', width: 120 },
    { title: '用户类型', dataIndex: 'user_type', width: 120 },
    { title: '行业', dataIndex: 'industry', width: 160 },
    { title: '地区', dataIndex: 'region', width: 100 },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (s: CustomerStatus) => <Tag color={STATUS_COLOR[s]}>{STATUS_LABEL[s]}</Tag>,
    },
    { title: '计量点数', dataIndex: 'metering_point_count', width: 90 },
    { title: '创建时间', dataIndex: 'created_at', width: 170, render: (v: string) => v?.replace('T', ' ').slice(0, 19) },
  ];

  function statusActions(
    status: CustomerStatus,
    id: string,
  ) {
    const items: { key: string; label: string; onClick: () => void }[] = [];
    if (status === 'prospect')
      items.push({ key: 'sign', label: '签约', onClick: () => showConfirm('签约确认', '签约', (r) => signContract(id, r)) });
    if (status === 'pending') {
      items.push({ key: 'activate', label: '生效', onClick: () => runAction(() => activateCustomer(id), '生效') });
      items.push({ key: 'cancel', label: '撤销', onClick: () => showConfirm('撤销确认', '撤销', (r) => cancelContract(id, r)) });
    }
    if (status === 'active') {
      items.push({ key: 'suspend', label: '暂停', onClick: () => showConfirm('暂停确认', '暂停', (r) => suspendCustomer(id, r)) });
      items.push({ key: 'terminate', label: '终止', onClick: () => showConfirm('终止确认', '终止', (r) => terminateCustomer(id, r)) });
    }
    if (status === 'suspended') {
      items.push({ key: 'resume', label: '恢复', onClick: () => runAction(() => resumeCustomer(id), '恢复') });
      items.push({ key: 'terminate', label: '终止', onClick: () => showConfirm('终止确认', '终止', (r) => terminateCustomer(id, r)) });
    }
    if (items.length === 0)
      return <Typography.Text type="secondary">-</Typography.Text>;
    return (
      <Dropdown menu={{ items }} trigger={['click']}>
        <Button size="small" type="link">
          状态流转 <DownOutlined />
        </Button>
      </Dropdown>
    );
  }

  const renderExtraFormContent = () => (
    <>
      <Divider />
      <Form.List name="utility_accounts">
        {(fields, { add, remove }) => (
          <div style={{ marginBottom: 16 }}>
            <Typography.Text strong style={{ fontSize: 16, display: 'block', marginBottom: 12 }}>
              户号与计量点
            </Typography.Text>
            {fields.map(({ key, name, ...restField }) => (
              <Card
                key={key}
                size="small"
                title={`户号 #${name + 1}`}
                extra={
                  <Button type="link" danger icon={<DeleteOutlined />} onClick={() => remove(name)} size="small">
                    删除户号
                  </Button>
                }
                style={{ marginBottom: 12 }}
              >
                <Form.Item
                  {...restField}
                  name={[name, 'account_id']}
                  label="户号"
                  rules={[{ required: true, message: '请输入户号' }]}
                >
                  <Input placeholder="请输入户号" />
                </Form.Item>

                <Divider orientation="left" style={{ fontSize: 13 }}>计量点</Divider>
                <Form.List name={[name, 'metering_points']}>
                  {(mpFields, { add: addMp, remove: removeMp }) => (
                    <>
                      {mpFields.map(({ key: mpKey, name: mpName, ...mpRestField }) => (
                        <Row key={mpKey} gutter={8} align="middle" style={{ marginBottom: 8, flexWrap: 'nowrap' }}>
                          <Col flex="1 1 150px">
                            <Form.Item
                              {...mpRestField}
                              name={[mpName, 'metering_point_id']}
                              rules={[{ required: true, message: '请输入计量点ID' }]}
                              noStyle
                            >
                              <Input placeholder="计量点ID" size="small" />
                            </Form.Item>
                          </Col>
                          <Col flex="1 1 150px">
                            <Form.Item
                              {...mpRestField}
                              name={[mpName, 'meter', 'meter_id']}
                              rules={[{ required: true, message: '请输入电表资产号' }]}
                              noStyle
                            >
                              <Input placeholder="电表资产号" size="small" />
                            </Form.Item>
                          </Col>
                          <Col flex="0 0 90px">
                            <Form.Item
                              {...mpRestField}
                              name={[mpName, 'meter', 'multiplier']}
                              rules={[{ required: true, message: '请输入倍率' }]}
                              noStyle
                            >
                              <InputNumber placeholder="倍率" size="small" style={{ width: '100%' }} min={0.1} step={0.1} />
                            </Form.Item>
                          </Col>
                          <Col flex="0 0 100px">
                            <Form.Item
                              {...mpRestField}
                              name={[mpName, 'allocation_percentage']}
                              rules={[{ required: true, message: '请输入分摊比例' }]}
                              noStyle
                            >
                              <InputNumber
                                placeholder="分摊比例"
                                size="small"
                                style={{ width: '100%' }}
                                min={0}
                                max={100}
                                addonAfter="%"
                              />
                            </Form.Item>
                          </Col>
                          <Col flex="0 0 32px">
                            <Button type="link" danger icon={<DeleteOutlined />} onClick={() => removeMp(mpName)} size="small" />
                          </Col>
                        </Row>
                      ))}
                      <Button
                        type="dashed"
                        onClick={() => addMp({ metering_point_id: '', allocation_percentage: 100, meter: { meter_id: '', multiplier: 1 } })}
                        block
                        icon={<PlusOutlined />}
                        size="small"
                      >
                        添加计量点
                      </Button>
                    </>
                  )}
                </Form.List>
              </Card>
            ))}
            <Button type="dashed" onClick={() => add({ account_id: '', metering_points: [] })} block icon={<PlusOutlined />}>
              添加户号
            </Button>
          </div>
        )}
      </Form.List>
    </>
  );

  return (
    <React.Fragment><CrudPage<CustomerListItem>
      title="客户档案管理"
      rowKey="id"
      columns={columns}
      searchFields={searchFields}
      formFields={formFields}
      reloadRef={reloadRef}
      fetcher={async ({ page, pageSize, filters }) => {
        const res = await fetchCustomers({ ...filters, page, page_size: pageSize });
        return { items: res.items, total: res.total };
      }}
      creator={async (v) => createCustomer(v as any)}
      updater={async (id, v) => updateCustomer(id, v)}
      remover={async (id) => deleteCustomer(id)}
      rowActions={(record) => statusActions(record.status, record.id)}
      renderExtraFormContent={renderExtraFormContent}
      onBeforeEdit={async (record) => {
        const detail = await getCustomer(record.id);
        return detail as unknown as Record<string, any>;
      }}
    />
    </React.Fragment>
  );
}
