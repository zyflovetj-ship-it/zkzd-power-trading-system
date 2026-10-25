import { useMemo, useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Button, Card, Form, Input, Modal, Segmented, Select, Space, Table, Tag, App as AntdApp, Popconfirm } from 'antd';
import type { ColumnsType } from 'antd/es/table';
import { PlusOutlined, EditOutlined, DeleteOutlined, KeyOutlined } from '@ant-design/icons';
import { ChartCard } from '@/components/charts/ChartCard';
import { KpiCards } from '@/components/charts/KpiCards';
import { baseGrid, baseLegend, baseTooltip, CHART_COLORS } from '@/components/charts/chartTheme';
import type { EChartsOption } from 'echarts';
import { getSystemUsers, createUser, updateUser, deleteUser, resetPassword, type Role, type UserRecord } from '@/api/users';

const ROLE_COLOR: Record<Role, string> = {
  管理员: 'red',
  交易员: 'blue',
  风控: 'purple',
  只读: 'default',
};

const ROLE_OPTIONS: (Role | '全部')[] = ['全部', '管理员', '交易员', '风控', '只读'];

type ModalMode = 'create' | 'edit' | 'resetPwd' | null;

export default function UserPermissionsPage() {
  const { message } = AntdApp.useApp();
  const queryClient = useQueryClient();
  const q = useQuery({ queryKey: ['systemUsers'], queryFn: () => getSystemUsers() });
  const users = q.data?.items ?? [];
  const [roleFilter, setRoleFilter] = useState<Role | '全部'>('全部');
  const [modalOpen, setModalOpen] = useState(false);
  const [modalMode, setModalMode] = useState<ModalMode>(null);
  const [editingUser, setEditingUser] = useState<UserRecord | null>(null);
  const [form] = Form.useForm();

  const filtered = useMemo(
    () => (roleFilter === '全部' ? users : users.filter((u) => u.role === roleFilter)),
    [roleFilter, users],
  );

  const roleCounts = useMemo(() => {
    const map: Record<Role, number> = { 管理员: 0, 交易员: 0, 风控: 0, 只读: 0 };
    users.forEach((u) => (map[u.role] += 1));
    return map;
  }, [users]);

  const roleLabels = Object.keys(roleCounts) as Role[];

  const roleDistOption: EChartsOption = useMemo(
    () => ({
      color: CHART_COLORS,
      tooltip: { ...baseTooltip },
      legend: { ...baseLegend, data: ['用户数'] },
      grid: baseGrid,
      xAxis: { type: 'category', data: roleLabels, name: '角色' },
      yAxis: { type: 'value', name: '用户数', minInterval: 1 },
      series: [
        { name: '用户数', type: 'bar', data: roleLabels.map((k) => roleCounts[k]), itemStyle: { color: CHART_COLORS[1] } },
      ],
    }),
    [roleCounts],
  );

  const totalUsers = users.length;
  const roleNum = roleLabels.length;
  const activeCount = users.filter((u) => u.is_active).length;
  const inactiveCount = users.filter((u) => !u.is_active).length;

  const createMut = useMutation({
    mutationFn: (vals: any) => createUser(vals),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['systemUsers'] }); message.success('用户创建成功'); setModalOpen(false); },
    onError: (err: any) => message.error(err.response?.data?.detail || '创建失败'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, data }: { id: string; data: any }) => updateUser(id, data),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['systemUsers'] }); message.success('用户更新成功'); setModalOpen(false); },
    onError: (err: any) => message.error(err.response?.data?.detail || '更新失败'),
  });

  const deleteMut = useMutation({
    mutationFn: (id: string) => deleteUser(id),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ['systemUsers'] }); message.success('用户已删除'); },
    onError: (err: any) => message.error(err.response?.data?.detail || '删除失败'),
  });

  const resetPwdMut = useMutation({
    mutationFn: ({ id, password }: { id: string; password: string }) => resetPassword(id, password),
    onSuccess: () => { message.success('密码已重置'); setModalOpen(false); },
    onError: (err: any) => message.error(err.response?.data?.detail || '重置失败'),
  });

  const openCreate = () => {
    setEditingUser(null);
    setModalMode('create');
    form.resetFields();
    form.setFieldsValue({ role: '交易员' });
    setModalOpen(true);
  };

  const openEdit = (user: UserRecord) => {
    setEditingUser(user);
    setModalMode('edit');
    form.setFieldsValue(user);
    setModalOpen(true);
  };

  const openResetPwd = (user: UserRecord) => {
    setEditingUser(user);
    setModalMode('resetPwd');
    form.resetFields();
    setModalOpen(true);
  };

  const handleSubmit = async () => {
    const vals = await form.validateFields();
    if (modalMode === 'create') {
      createMut.mutate(vals);
    } else if (modalMode === 'edit' && editingUser) {
      const { username, ...rest } = vals;
      updateMut.mutate({ id: editingUser.id, data: rest });
    } else if (modalMode === 'resetPwd' && editingUser) {
      resetPwdMut.mutate({ id: editingUser.id, password: vals.password });
    }
  };

  const handleDelete = (id: string) => {
    deleteMut.mutate(id);
  };

  const columns: ColumnsType<UserRecord> = [
    { title: '用户名', dataIndex: 'username', width: 140 },
    { title: '姓名', dataIndex: 'full_name', width: 100, render: (v: string) => v || '-' },
    { title: '邮箱', dataIndex: 'email', width: 180, render: (v: string) => v || '-' },
    { title: '部门', dataIndex: 'department', width: 120, render: (v: string) => v || '-' },
    { title: '角色', dataIndex: 'role', width: 100, render: (r: Role) => <Tag color={ROLE_COLOR[r]}>{r}</Tag> },
    {
      title: '状态', dataIndex: 'is_active', width: 80,
      render: (v: boolean) => v ? <Tag color="success">启用</Tag> : <Tag color="default">停用</Tag>,
    },
    { title: '最近登录', dataIndex: 'last_login', width: 160, render: (v: string) => v || '—' },
    {
      title: '操作', key: 'action', width: 160, fixed: 'right',
      render: (_: any, record: UserRecord) => (
        <Space size="small">
          <Button type="link" size="small" icon={<EditOutlined />} onClick={() => openEdit(record)}>编辑</Button>
          <Button type="link" size="small" icon={<KeyOutlined />} onClick={() => openResetPwd(record)}>改密</Button>
          <Popconfirm title="确定删除该用户？" onConfirm={() => handleDelete(record.id)} okText="确定" cancelText="取消">
            <Button type="link" size="small" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const modalTitle = modalMode === 'create' ? '新建用户' : modalMode === 'edit' ? '编辑用户' : '重置密码';

  return (
    <div>
      <KpiCards
        loading={q.isLoading}
        items={[
          { label: '用户总数', value: totalUsers, suffix: '人', color: CHART_COLORS[0] },
          { label: '角色数', value: roleNum, suffix: '种', color: CHART_COLORS[1] },
          { label: '启用数', value: activeCount, suffix: '人', color: CHART_COLORS[3] },
          { label: '停用数', value: inactiveCount, suffix: '人', color: CHART_COLORS[2] },
        ]}
      />

      <ChartCard title="角色分布" option={roleDistOption} loading={q.isLoading} height={320} />

      <Card
        size="small"
        title="用户明细"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建用户</Button>
            <span>按角色筛选：</span>
            <Segmented options={ROLE_OPTIONS} value={roleFilter} onChange={(v) => setRoleFilter(v as Role | '全部')} />
          </Space>
        }
      >
        <Table<UserRecord>
          rowKey={(r) => r.id}
          columns={columns}
          dataSource={filtered}
          pagination={{ pageSize: 20, showSizeChanger: true, showTotal: (t) => `共 ${t} 条` }}
          scroll={{ x: 'max-content' }}
          size="small"
        />
      </Card>

      <Modal title={modalTitle} open={modalOpen} onCancel={() => setModalOpen(false)} onOk={handleSubmit} confirmLoading={createMut.isPending || updateMut.isPending || resetPwdMut.isPending} destroyOnClose>
        <Form form={form} layout="vertical" style={{ marginTop: 16 }}>
          {modalMode !== 'resetPwd' ? (
            <>
              <Form.Item name="username" label="用户名" rules={[{ required: true, message: '请输入用户名' }]}>
                <Input disabled={modalMode === 'edit'} placeholder="字母或数字，至少2位" />
              </Form.Item>
              <Form.Item name="full_name" label="姓名">
                <Input placeholder="用户全名" />
              </Form.Item>
              <Form.Item name="email" label="邮箱" rules={[{ type: 'email', message: '邮箱格式不正确' }]}>
                <Input placeholder="user@example.com" />
              </Form.Item>
              <Form.Item name="department" label="部门">
                <Input placeholder="所属部门" />
              </Form.Item>
              <Form.Item name="role" label="角色" rules={[{ required: true, message: '请选择角色' }]}>
                <Select options={[
                  { value: '管理员', label: '管理员' },
                  { value: '交易员', label: '交易员' },
                  { value: '风控', label: '风控' },
                  { value: '只读', label: '只读' },
                ]} />
              </Form.Item>
              {modalMode === 'create' && (
                <Form.Item name="password" label="密码" rules={[
                  { required: true, message: '请输入密码' },
                  { min: 6, message: '密码至少6位' },
                ]}>
                  <Input.Password placeholder="至少6位" />
                </Form.Item>
              )}
              {modalMode === 'edit' && (
                <Form.Item name="is_active" label="状态">
                  <Select options={[
                    { value: true, label: '启用' },
                    { value: false, label: '停用' },
                  ]} />
                </Form.Item>
              )}
            </>
          ) : (
            <Form.Item name="password" label="新密码" rules={[
              { required: true, message: '请输入新密码' },
              { min: 6, message: '密码至少6位' },
            ]}>
              <Input.Password placeholder="至少6位" />
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  );
}
