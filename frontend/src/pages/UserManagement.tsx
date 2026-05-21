import React, { useState } from 'react';
import {
  Card, Row, Col, Table, Button, Modal, Form, Input, Radio, Switch,
  Tag, Space, Statistic, Popconfirm, Typography, message, Alert,
} from 'antd';
import {
  UserAddOutlined, EditOutlined, KeyOutlined, DeleteOutlined,
  UserSwitchOutlined, CrownOutlined, ShopOutlined, LoginOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  getUsers, createUser, updateUser, deleteUser, resetUserPassword,
  impersonateUser, getCurrentUser, UserInfo,
} from '../services/api';

const { Title, Text } = Typography;

const ROLE_LABEL: Record<string, { color: string; text: string }> = {
  admin: { color: 'red', text: '管理员' },
  sales: { color: 'blue', text: '销售' },
};

type ModalMode = 'create' | 'edit' | 'reset-password' | null;

const UserManagement: React.FC = () => {
  const qc = useQueryClient();
  const [mode, setMode] = useState<ModalMode>(null);
  const [activeRow, setActiveRow] = useState<UserInfo | null>(null);
  const [form] = Form.useForm();

  const usersQuery = useQuery({ queryKey: ['users'], queryFn: getUsers });
  const meQuery = useQuery({ queryKey: ['me'], queryFn: getCurrentUser });

  const allUsers = usersQuery.data || [];
  const me = meQuery.data;

  // Hide superuser rows from the list — admin runs the page; they don't need to
  // manage themselves through this UI. Stats below still count from allUsers
  // so the "Active 管理员" tile reflects the true number including superusers.
  const users = allUsers.filter(u => !u.is_superuser);

  const adminCount = allUsers.filter(u => u.role === 'admin' && u.is_active).length;
  const salesCount = allUsers.filter(u => u.role === 'sales' && u.is_active).length;

  // ── Mutations ─────────────────────────────────────────────────
  const createMut = useMutation({
    mutationFn: (body: any) => createUser(body),
    onSuccess: () => {
      message.success('用户创建成功');
      qc.invalidateQueries({ queryKey: ['users'] });
      closeModal();
    },
    onError: (e: any) => message.error(e.response?.data?.message || e.response?.data?.detail || '创建失败'),
  });

  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: any }) => updateUser(id, body),
    onSuccess: () => {
      message.success('用户已更新');
      qc.invalidateQueries({ queryKey: ['users'] });
      closeModal();
    },
    onError: (e: any) => message.error(e.response?.data?.message || e.response?.data?.detail || '更新失败'),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => deleteUser(id),
    onSuccess: () => {
      message.success('用户已删除');
      qc.invalidateQueries({ queryKey: ['users'] });
    },
    onError: (e: any) => message.error(e.response?.data?.message || e.response?.data?.detail || '删除失败'),
  });

  const resetPwdMut = useMutation({
    mutationFn: ({ id, pwd }: { id: number; pwd: string }) => resetUserPassword(id, pwd),
    onSuccess: () => {
      message.success('密码已重置');
      closeModal();
    },
    onError: (e: any) => message.error(e.response?.data?.message || e.response?.data?.detail || '重置失败'),
  });

  const impersonateMut = useMutation({
    mutationFn: (userId: number) => impersonateUser(userId),
    onSuccess: (data) => {
      // Open in a new tab with token in the URL hash; the App.tsx
      // impersonation handoff reads the hash and stashes the token to
      // the right localStorage key, then redirects. Hash isn't sent to
      // server logs so it's safer than a query string.
      const hash = `impersonate=${encodeURIComponent(data.access_token)}`
        + `&role=${encodeURIComponent(data.target_role)}`
        + `&to=${encodeURIComponent(data.redirect_to)}`;
      const url = `${data.redirect_to}#${hash}`;
      window.open(url, '_blank', 'noopener');
      message.success(`已为 ${data.target_username} 打开新会话标签`);
    },
    onError: (e: any) =>
      message.error(e.response?.data?.message || e.response?.data?.detail || '账号登录失败'),
  });

  // ── Handlers ──────────────────────────────────────────────────
  const closeModal = () => { setMode(null); setActiveRow(null); form.resetFields(); };

  const openCreate = () => {
    form.setFieldsValue({ role: 'sales', is_active: true });
    setMode('create');
  };

  const openEdit = (row: UserInfo) => {
    setActiveRow(row);
    form.setFieldsValue({ role: row.role, is_active: row.is_active });
    setMode('edit');
  };

  const openResetPassword = (row: UserInfo) => {
    setActiveRow(row);
    form.resetFields();
    setMode('reset-password');
  };

  const handleSubmit = async () => {
    try {
      const values = await form.validateFields();
      if (mode === 'create') {
        createMut.mutate(values);
      } else if (mode === 'edit' && activeRow) {
        updateMut.mutate({ id: activeRow.id, body: values });
      } else if (mode === 'reset-password' && activeRow) {
        if (values.new_password !== values.confirm_password) {
          message.error('两次密码不一致'); return;
        }
        resetPwdMut.mutate({ id: activeRow.id, pwd: values.new_password });
      }
    } catch {
      /* form validation error already shown */
    }
  };

  const handleToggleActive = (row: UserInfo, checked: boolean) => {
    updateMut.mutate({ id: row.id, body: { is_active: checked } });
  };

  // ── Columns ───────────────────────────────────────────────────
  const columns = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    {
      title: '用户名', dataIndex: 'username', key: 'username',
      render: (v: string, row: UserInfo) => (
        <Space>
          <Text strong>{v}</Text>
          {me?.id === row.id && <Tag color="orange">我自己</Tag>}
          {row.is_superuser && <Tag color="purple">Superuser</Tag>}
        </Space>
      ),
    },
    {
      title: '角色', dataIndex: 'role', key: 'role', width: 100,
      render: (r: string) => {
        const info = ROLE_LABEL[r] || { color: 'default', text: r };
        return <Tag color={info.color}>{info.text}</Tag>;
      },
    },
    {
      title: '状态', dataIndex: 'is_active', key: 'is_active', width: 100,
      render: (active: boolean, row: UserInfo) => (
        <Switch
          checked={active}
          checkedChildren="启用"
          unCheckedChildren="禁用"
          disabled={me?.id === row.id}
          loading={updateMut.isPending && updateMut.variables?.id === row.id}
          onChange={(v) => handleToggleActive(row, v)}
        />
      ),
    },
    {
      title: '操作', key: 'actions', width: 380,
      render: (_: any, row: UserInfo) => {
        const isSelf = me?.id === row.id;
        return (
          <Space>
            <Button
              size="small" icon={<EditOutlined />}
              disabled={isSelf}
              onClick={() => openEdit(row)}
            >
              编辑
            </Button>
            <Button
              size="small" icon={<KeyOutlined />}
              onClick={() => openResetPassword(row)}
            >
              重置密码
            </Button>
            <Popconfirm
              title={`以「${row.username}」身份登录？`}
              description="将在新标签页打开该用户的工作界面。当前 admin 会话保持不变。"
              okText="确认登录" cancelText="取消"
              disabled={isSelf || !row.is_active}
              onConfirm={() => impersonateMut.mutate(row.id)}
            >
              <Button
                size="small" type="primary" ghost icon={<LoginOutlined />}
                disabled={isSelf || !row.is_active}
                loading={impersonateMut.isPending && impersonateMut.variables === row.id}
              >
                账号登录
              </Button>
            </Popconfirm>
            <Popconfirm
              title="确认删除该用户？"
              description={
                <div>
                  <div>用户 <strong>{row.username}</strong> 会被永久删除。</div>
                  <div>已认领的 lead / 历史发票引用将置为 NULL（保留业务数据）。</div>
                </div>
              }
              okText="删除" cancelText="取消"
              okButtonProps={{ danger: true }}
              disabled={isSelf}
              onConfirm={() => deleteMut.mutate(row.id)}
            >
              <Button size="small" icon={<DeleteOutlined />} danger disabled={isSelf}>
                删除
              </Button>
            </Popconfirm>
          </Space>
        );
      },
    },
  ];

  return (
    <div style={{ padding: 24 }}>
      <Title level={3}>
        <UserSwitchOutlined /> 账号中心 · 用户管理
      </Title>
      <Text type="secondary">
        管理内部运营与销售账号。仅 admin 可见。密码不可还原，重置后需立即告知本人。
      </Text>

      {/* 统计 */}
      <Row gutter={16} style={{ margin: '24px 0' }}>
        <Col span={8}>
          <Card>
            <Statistic title="总用户数" value={users.length} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Active 管理员" value={adminCount}
              prefix={<CrownOutlined style={{ color: '#EF4444' }} />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="Active 销售" value={salesCount}
              prefix={<ShopOutlined style={{ color: '#3B82F6' }} />}
            />
          </Card>
        </Col>
      </Row>

      {adminCount <= 1 && (
        <Alert
          type="warning" showIcon style={{ marginBottom: 16 }}
          message="当前只有 1 个 active 管理员"
          description="为避免被系统锁定建议至少保留 2 个 admin。后端会拒绝删除或降级最后一个 admin。"
        />
      )}

      <Card
        title="用户列表"
        extra={
          <Button type="primary" icon={<UserAddOutlined />} onClick={openCreate}>
            创建用户
          </Button>
        }
      >
        <Table
          dataSource={users} columns={columns} rowKey="id"
          loading={usersQuery.isLoading}
          pagination={{ pageSize: 20, showSizeChanger: false }}
        />
      </Card>

      {/* Create Modal */}
      <Modal
        open={mode === 'create'} title="创建用户"
        onCancel={closeModal} onOk={handleSubmit}
        okText="创建" confirmLoading={createMut.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item
            name="username" label="用户名"
            rules={[
              { required: true, message: '请输入用户名' },
              { min: 3, max: 64, message: '3-64 个字符' },
              { pattern: /^[a-zA-Z0-9_]+$/, message: '仅允许字母数字下划线' },
            ]}
          >
            <Input placeholder="例如：alice" />
          </Form.Item>
          <Form.Item
            name="password" label="初始密码"
            rules={[
              { required: true, message: '请输入密码' },
              { min: 8, max: 128, message: '至少 8 位' },
              {
                pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$/,
                message: '必须包含大写字母、小写字母、数字',
              },
            ]}
            extra="创建后请立即告知本人，密码不能找回"
          >
            <Input.Password placeholder="≥8 位，含大写、小写、数字" />
          </Form.Item>
          <Form.Item name="role" label="角色" initialValue="sales" rules={[{ required: true }]}>
            <Radio.Group>
              <Radio value="sales">销售（仅 CRM/Inbox）</Radio>
              <Radio value="admin">管理员（全权）</Radio>
            </Radio.Group>
          </Form.Item>
          <Form.Item name="is_active" label="状态" valuePropName="checked" initialValue={true}>
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Edit Modal */}
      <Modal
        open={mode === 'edit'} title={`编辑用户：${activeRow?.username}`}
        onCancel={closeModal} onOk={handleSubmit}
        okText="保存" confirmLoading={updateMut.isPending}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Alert
            type="info" showIcon style={{ marginBottom: 16 }}
            message="用户名不可修改" description="如需更换用户名请删除后重建。"
          />
          <Form.Item name="role" label="角色" rules={[{ required: true }]}>
            <Radio.Group>
              <Radio value="sales">销售</Radio>
              <Radio value="admin">管理员</Radio>
            </Radio.Group>
          </Form.Item>
          <Form.Item name="is_active" label="状态" valuePropName="checked">
            <Switch checkedChildren="启用" unCheckedChildren="禁用" />
          </Form.Item>
        </Form>
      </Modal>

      {/* Reset Password Modal */}
      <Modal
        open={mode === 'reset-password'} title={`重置密码：${activeRow?.username}`}
        onCancel={closeModal} onOk={handleSubmit}
        okText="确认重置" confirmLoading={resetPwdMut.isPending}
        destroyOnClose
      >
        <Alert
          type="warning" showIcon style={{ marginBottom: 16 }}
          message="管理员重置密码"
          description="此操作会立即生效，原密码失效。请通过安全渠道告知本人新密码。"
        />
        <Form form={form} layout="vertical">
          <Form.Item
            name="new_password" label="新密码"
            rules={[
              { required: true, message: '请输入新密码' },
              { min: 8, max: 128, message: '至少 8 位' },
              {
                pattern: /^(?=.*[a-z])(?=.*[A-Z])(?=.*\d).+$/,
                message: '必须包含大写字母、小写字母、数字',
              },
            ]}
          >
            <Input.Password placeholder="≥8 位，含大写、小写、数字" />
          </Form.Item>
          <Form.Item
            name="confirm_password" label="确认新密码"
            dependencies={['new_password']}
            rules={[
              { required: true, message: '请再次输入新密码' },
              ({ getFieldValue }) => ({
                validator(_, value) {
                  if (!value || getFieldValue('new_password') === value) return Promise.resolve();
                  return Promise.reject(new Error('两次密码不一致'));
                },
              }),
            ]}
          >
            <Input.Password />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default UserManagement;
