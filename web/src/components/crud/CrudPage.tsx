import { useCallback, useEffect, useRef, useState } from 'react';
import {
  App,
  Button,
  Card,
  Col,
  DatePicker,
  Form,
  Input,
  InputNumber,
  Modal,
  Popconfirm,
  Row,
  Select,
  Space,
  Switch,
  Table,
} from 'antd';
import type { ColumnsType } from 'antd/es/table';
import type { CrudField, CrudPageProps, SearchField } from './types';

function renderFieldInner(field: CrudField & { dynamicOptions?: { label: string; value: string }[] }) {
  switch (field.type) {
    case 'textarea':
      return <Input.TextArea rows={3} placeholder={field.placeholder} />;
    case 'number':
      return <InputNumber style={{ width: '100%' }} placeholder={field.placeholder} />;
    case 'select':
      return <Select options={field.dynamicOptions ?? field.options} placeholder={field.placeholder} allowClear />;
    case 'switch':
      return <Switch />;
    case 'month':
      return <DatePicker picker="month" style={{ width: '100%' }} placeholder={field.placeholder} />;
    case 'text':
    default:
      return <Input placeholder={field.placeholder} />;
  }
}

/**
 * 通用 CRUD 页面骨架：搜索栏 + 表格 + 新增/编辑弹窗（Modal+Form）+ 删除确认。
 * 通过泛型 + 配置驱动，客户/合同/套餐三类页面复用同一套交互逻辑。
 */
export function CrudPage<T extends Record<string, any>>(props: CrudPageProps<T>) {
  const { message } = App.useApp();
  const {
    title,
    rowKey = 'id',
    columns,
    searchFields = [],
    formFields,
    fetcher,
    creator,
    updater,
    remover,
    actions,
    rowActions,
    toolbarExtra,
    toFormValues,
    fromFormValues,
    disableCreate,
    reloadRef,
    editRef,
    renderExtraFormContent,
    onBeforeEdit,
  } = props;

  const [form] = Form.useForm();
  const [modalOpen, setModalOpen] = useState(false);
  const [editing, setEditing] = useState<T | null>(null);
  const [filters, setFilters] = useState<Record<string, any>>({});
  const [pagination, setPagination] = useState({ current: 1, pageSize: 10, total: 0 });
  const [data, setData] = useState<T[]>([]);
  const [loading, setLoading] = useState(false);
  // 动态选项缓存：{ fieldName: options[] }
  const [dynamicOptions, setDynamicOptions] = useState<Record<string, { label: string; value: string }[]>>({});

  // 级联字段：收集所有有 dependsOn 的字段（用 ref 避免每次渲染产生新引用导致无限循环）
  const cascadeFieldsRef = useRef<CrudField[]>([]);
  cascadeFieldsRef.current = formFields.filter((f) => f.dependsOn && f.fetchOptions);

  // 独立下拉字段：有 fetchOptions 但无 dependsOn 的字段
  const standaloneFieldsRef = useRef<CrudField[]>([]);
  standaloneFieldsRef.current = formFields.filter((f) => f.fetchOptions && !f.dependsOn);

  // 加载级联选项
  const loadCascadeOptions = useCallback(async (field: CrudField, formValues: any) => {
    if (!field.dependsOn || !field.fetchOptions) return;
    const depsValue = formValues[field.dependsOn];
    if (!depsValue) {
      setDynamicOptions((prev) => ({ ...prev, [field.name]: [] }));
      return;
    }
    try {
      const opts = await field.fetchOptions(depsValue, formValues);
      setDynamicOptions((prev) => ({ ...prev, [field.name]: opts }));
    } catch {
      setDynamicOptions((prev) => ({ ...prev, [field.name]: [] }));
    }
  }, []);

  // 加载独立下拉字段的选项
  const loadStandaloneOptions = useCallback(async () => {
    const fields = standaloneFieldsRef.current;
    if (fields.length === 0) return;
    const results = await Promise.allSettled(
      fields.map(async (f) => {
        try {
          const opts = await f.fetchOptions!(undefined, {});
          console.log(`[CrudPage] loadStandaloneOptions: field=${f.name}, options=${opts?.length ?? 0}`);
          return opts;
        } catch (err) {
          console.error(`[CrudPage] loadStandaloneOptions error: field=${f.name}`, err);
          return [];
        }
      })
    );
    const updates: Record<string, { label: string; value: string }[]> = {};
    fields.forEach((f, i) => {
      updates[f.name] = results[i].status === 'fulfilled' ? results[i].value : [];
    });
    console.log('[CrudPage] loadStandaloneOptions updates:', Object.keys(updates), Object.values(updates).map(v => v.length));
    setDynamicOptions((prev) => ({ ...prev, ...updates }));
  }, []);

  // 打开弹窗时，为所有级联字段和独立下拉字段加载初始选项
  useEffect(() => {
    if (modalOpen) {
      const values = form.getFieldsValue();
      cascadeFieldsRef.current.forEach((f) => loadCascadeOptions(f, values));
      loadStandaloneOptions();
    }
  }, [modalOpen, form, loadCascadeOptions, loadStandaloneOptions]);

  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const load = async () => {
    setLoading(true);
    try {
      const res = await fetcherRef.current({
        page: pagination.current,
        pageSize: pagination.pageSize,
        filters,
      });
      setData(res.items ?? []);
      setPagination((p) => ({ ...p, total: res.total ?? 0 }));
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '加载失败');
      setData([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
    if (reloadRef) reloadRef.current = load;
    if (editRef) editRef.current = openEdit;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pagination.current, pagination.pageSize, filters]);

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    setModalOpen(true);
  };

  const openEdit = async (record: T) => {
    setEditing(record);
    let init: Record<string, any> = record as Record<string, any>;
    if (toFormValues) {
      init = toFormValues(record);
    } else if (onBeforeEdit) {
      try {
        init = await onBeforeEdit(record);
      } catch {
        init = record as Record<string, any>;
      }
    }
    form.setFieldsValue(init);
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    const values = await form.validateFields();
    const payload = fromFormValues ? fromFormValues(values) : values;
    try {
      if (editing) {
        await updater?.(String(editing[rowKey]), payload);
        message.success('更新成功');
      } else {
        await creator?.(payload);
        message.success('创建成功');
      }
      setModalOpen(false);
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '保存失败');
    }
  };

  const handleDelete = async (record: T) => {
    try {
      await remover?.(String(record[rowKey]));
      message.success('删除成功');
      load();
    } catch (e: any) {
      message.error(e?.response?.data?.detail || e?.message || '删除失败');
    }
  };

  const handleSearch = (vals: Record<string, any>) => {
    const cleaned: Record<string, any> = {};
    Object.entries(vals || {}).forEach(([k, v]) => {
      if (v !== undefined && v !== null && v !== '') cleaned[k] = v;
    });
    setPagination((p) => ({ ...p, current: 1 }));
    setFilters(cleaned);
  };

  const handleReset = () => {
    setFilters({});
    setPagination((p) => ({ ...p, current: 1 }));
  };

  const actionColumn: ColumnsType<T>[number] = {
    title: '操作',
    key: '__actions',
    fixed: 'right',
    width: 160,
    render: (_: unknown, record: T) => {
      if (actions) return actions(record);
      return (
        <Space size="small">
          {updater && (
            <Button type="link" size="small" onClick={() => openEdit(record)}>
              编辑
            </Button>
          )}
          {rowActions && rowActions(record)}
          {remover && (
            <Popconfirm title="确认删除该记录？" onConfirm={() => handleDelete(record)} okText="删除" cancelText="取消">
              <Button type="link" size="small" danger>
                删除
              </Button>
            </Popconfirm>
          )}
        </Space>
      );
    },
  };

  return (
    <Card
      title={title}
      extra={
        <Space>
          {toolbarExtra}
          {!disableCreate && creator && (
            <Button type="primary" onClick={openCreate}>
              新增
            </Button>
          )}
        </Space>
      }
    >
      {searchFields.length > 0 && (
        <Form layout="inline" style={{ marginBottom: 16, rowGap: 12 }} onFinish={handleSearch}>
          <Row gutter={[12, 12]} style={{ width: '100%' }}>
            {searchFields.map((sf: SearchField) => (
              <Col key={sf.name} xs={24} sm={12} md={6} lg={5}>
                <Form.Item name={sf.name} label={sf.label} style={{ marginBottom: 0 }}>
                  {sf.type === 'select' ? (
                    <Select options={sf.options} placeholder={sf.placeholder ?? `请选择${sf.label}`} allowClear style={{ width: '100%' }} />
                  ) : (
                    <Input placeholder={sf.placeholder ?? `请输入${sf.label}`} allowClear />
                  )}
                </Form.Item>
              </Col>
            ))}
            <Col key="__ops" xs={24} sm={12} md={6} lg={5}>
              <Space>
                <Button type="primary" htmlType="submit">
                  查询
                </Button>
                <Button onClick={handleReset}>重置</Button>
              </Space>
            </Col>
          </Row>
        </Form>
      )}

      <Table<T>
        rowKey={rowKey}
        columns={[...columns, actionColumn]}
        dataSource={data}
        loading={loading}
        scroll={{ x: 'max-content' }}
        pagination={{
          current: pagination.current,
          pageSize: pagination.pageSize,
          total: pagination.total,
          showSizeChanger: true,
          showTotal: (t) => `共 ${t} 条`,
          onChange: (current, pageSize) => setPagination((p) => ({ ...p, current, pageSize })),
        }}
      />

      <Modal
        open={modalOpen}
        title={editing ? `编辑${title}` : `新增${title}`}
        onOk={handleSubmit}
        onCancel={() => setModalOpen(false)}
        destroyOnClose
        maskClosable={false}
        width={720}
      >
        <Form
          form={form}
          layout="vertical"
          preserve={false}
          style={{ marginTop: 12 }}
          onValuesChange={(changedValues) => {
            // 当依赖字段值变化时，重新加载级联选项并清空已选值
            cascadeFieldsRef.current.forEach((f) => {
              if (f.dependsOn && changedValues[f.dependsOn] !== undefined) {
                form.setFieldsValue({ [f.name]: undefined });
                loadCascadeOptions(f, { ...form.getFieldsValue(), ...changedValues });
              }
            });
          }}
        >
          <Row gutter={16}>
            {formFields.map((f) => {
              const isDisabled = editing ? f.disabledOnEdit : false;
              return (
                <Col key={f.name} span={f.span ?? 24}>
                  <Form.Item
                    name={f.name}
                    label={f.label}
                    valuePropName={f.type === 'switch' ? 'checked' : 'value'}
                    rules={f.required ? [{ required: true, message: `请输入${f.label}` }] : []}
                  >
                    {renderFieldInner({
                      ...f,
                      disabledOnEdit: isDisabled,
                      dynamicOptions: f.fetchOptions ? dynamicOptions[f.name] : undefined,
                    })}
                  </Form.Item>
                </Col>
              );
            })}
          </Row>
          {renderExtraFormContent?.(!!editing)}
        </Form>
      </Modal>
    </Card>
  );
}
