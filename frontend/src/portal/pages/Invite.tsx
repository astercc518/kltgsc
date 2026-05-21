import React from 'react';
import {
  Card, Table, Tag, Button, Space, Statistic, Row, Col, Empty, message,
  Popconfirm, Typography, Modal, Form, Input, InputNumber, Alert, Tooltip,
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, DeleteOutlined,
  PauseCircleOutlined, PlayCircleOutlined, UsergroupAddOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { inviteApi, InviteTask, InviteCostPreview } from '../api';

const { Title, Text } = Typography;

const STATUS_COLOR: Record<string, string> = {
  pending: 'orange',
  running: 'processing',
  paused: 'gold',
  paused_no_funds: 'red',
  completed: 'green',
  failed: 'default',
};

const fmtUsd = (cents: number) => `$${(cents / 100).toFixed(2)}`;

const InvitePage: React.FC = () => {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = React.useState(false);
  const [form] = Form.useForm();
  const [preview, setPreview] = React.useState<InviteCostPreview | null>(null);

  const { data: tasks = [], isLoading, refetch } = useQuery({
    queryKey: ['portal', 'invite', 'tasks'],
    queryFn: () => inviteApi.list({ limit: 200 }),
    refetchInterval: 15000,
  });

  const pauseMut = useMutation({
    mutationFn: (id: number) => inviteApi.pause(id),
    onSuccess: () => {
      message.success('Paused');
      qc.invalidateQueries({ queryKey: ['portal', 'invite', 'tasks'] });
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Pause failed'),
  });

  const resumeMut = useMutation({
    mutationFn: (id: number) => inviteApi.resume(id),
    onSuccess: () => {
      message.success('Resumed');
      qc.invalidateQueries({ queryKey: ['portal', 'invite', 'tasks'] });
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Resume failed'),
  });

  const cancelMut = useMutation({
    mutationFn: (id: number) => inviteApi.cancel(id),
    onSuccess: () => {
      message.success('Canceled');
      qc.invalidateQueries({ queryKey: ['portal', 'invite', 'tasks'] });
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Cancel failed'),
  });

  const previewMut = useMutation({
    mutationFn: (n: number) => inviteApi.previewCost(n),
    onSuccess: (data) => setPreview(data),
  });

  const createMut = useMutation({
    mutationFn: (data: any) => inviteApi.create(data),
    onSuccess: () => {
      message.success('Task created and dispatched');
      qc.invalidateQueries({ queryKey: ['portal', 'invite', 'tasks'] });
      setCreateOpen(false);
      form.resetFields();
      setPreview(null);
    },
    onError: (e: any) => {
      const status = e?.response?.status;
      if (status === 402) {
        message.error('钱包余额不足，请先充值');
      } else {
        message.error(e?.response?.data?.detail || 'Create failed');
      }
    },
  });

  const handlePreview = () => {
    const n = form.getFieldValue('max_targets') || 100;
    previewMut.mutate(n);
  };

  const handleCreate = async () => {
    try {
      const v = await form.validateFields();
      const targets_raw: string = v.target_user_ids_raw || '';
      const target_user_ids = targets_raw
        .split(/[\s,]+/).map(s => s.trim()).filter(Boolean).map(Number).filter(n => !isNaN(n));
      createMut.mutate({
        name: v.name,
        target_channel: v.target_channel,
        target_user_ids: target_user_ids.length > 0 ? target_user_ids : undefined,
        max_targets: v.max_targets,
        min_delay: v.min_delay,
        max_delay: v.max_delay,
        max_invites_per_account: v.max_invites_per_account,
        max_invites_per_task: v.max_invites_per_task,
      });
    } catch (_) {}
  };

  const stats = React.useMemo(() => {
    const totalSuccess = tasks.reduce((s, t) => s + t.success_count, 0);
    const totalFail = tasks.reduce((s, t) => s + t.fail_count, 0);
    const totalFlood = tasks.reduce((s, t) => s + t.flood_wait_count, 0);
    const active = tasks.filter(t => ['running', 'pending'].includes(t.status)).length;
    return { totalSuccess, totalFail, totalFlood, active };
  }, [tasks]);

  const columns = [
    {
      title: 'Name',
      key: 'name',
      render: (_: any, r: InviteTask) => (
        <Space direction="vertical" size={0}>
          <Text strong>{r.name || `Task #${r.id}`}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{r.target_channel}</Text>
        </Space>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      render: (s: string) => (
        <Tag color={STATUS_COLOR[s] || 'default'}>
          {s === 'paused_no_funds' ? 'WALLET DRY' : s.toUpperCase()}
        </Tag>
      ),
    },
    {
      title: 'Progress',
      key: 'progress',
      render: (_: any, r: InviteTask) => (
        <Tooltip title={`success ${r.success_count} / fail ${r.fail_count} / flood ${r.flood_wait_count} / total ${r.total_count}`}>
          {r.success_count} / {r.total_count}
        </Tooltip>
      ),
    },
    {
      title: 'Error',
      key: 'err',
      render: (_: any, r: InviteTask) =>
        r.last_error ? <Text type="danger" style={{ fontSize: 12 }}>{r.last_error}</Text> : '—',
    },
    {
      title: 'Created',
      key: 'created',
      render: (_: any, r: InviteTask) => (
        <Text style={{ fontSize: 12 }}>{new Date(r.created_at).toLocaleString()}</Text>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, r: InviteTask) => (
        <Space>
          {['running', 'pending'].includes(r.status) && (
            <Button size="small" icon={<PauseCircleOutlined />}
              onClick={() => pauseMut.mutate(r.id)}>Pause</Button>
          )}
          {['paused', 'paused_no_funds'].includes(r.status) && (
            <Button size="small" type="primary" icon={<PlayCircleOutlined />}
              onClick={() => resumeMut.mutate(r.id)}>Resume</Button>
          )}
          {!['completed', 'failed'].includes(r.status) && (
            <Popconfirm title="Cancel this task?" onConfirm={() => cancelMut.mutate(r.id)}>
              <Button size="small" danger icon={<DeleteOutlined />}>Cancel</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>
            <UsergroupAddOutlined /> 群拉 (Invite)
          </Title>
          <Text type="secondary">
            把目标用户批量拉进指定群组，按次计费（默认 5¢/邀请，无论成功失败）
          </Text>
        </Col>
        <Col>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>Refresh</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              New Task
            </Button>
          </Space>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Card><Statistic title="Active" value={stats.active} /></Card></Col>
        <Col span={6}><Card><Statistic title="Total Success" value={stats.totalSuccess} /></Card></Col>
        <Col span={6}><Card><Statistic title="Total Fail" value={stats.totalFail} /></Card></Col>
        <Col span={6}><Card><Statistic title="Flood Wait Hits" value={stats.totalFlood} valueStyle={{ color: stats.totalFlood > 0 ? '#cf1322' : undefined }} /></Card></Col>
      </Row>

      <Card>
        <Table
          rowKey="id"
          dataSource={tasks}
          columns={columns}
          loading={isLoading}
          locale={{ emptyText: <Empty description="No invite tasks yet" /> }}
          pagination={{ pageSize: 20 }}
        />
      </Card>

      <Modal
        title="New Invite Task"
        open={createOpen}
        onCancel={() => { setCreateOpen(false); setPreview(null); }}
        onOk={handleCreate}
        confirmLoading={createMut.isPending}
        width={640}
        okText="Create & Start"
      >
        <Form form={form} layout="vertical" initialValues={{
          max_targets: 100, min_delay: 30, max_delay: 120,
          max_invites_per_account: 20, max_invites_per_task: 100,
        }}>
          <Form.Item name="name" label="Task name"
            rules={[{ required: true, message: 'Required' }]}>
            <Input placeholder="e.g. 加密用户首批拉群 2026-05" maxLength={120} />
          </Form.Item>
          <Form.Item name="target_channel" label="Target group link"
            rules={[{ required: true, message: 'Required' }]}>
            <Input placeholder="https://t.me/+abc... or https://t.me/yourgroup" />
          </Form.Item>
          <Form.Item name="target_user_ids_raw"
            label="Target user IDs (optional, one per line or comma-separated)"
            extra="Leave blank to use auto-selected untried targets up to max_targets.">
            <Input.TextArea rows={3} placeholder="123, 456, 789" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="max_targets" label="Max targets (auto-select fallback)">
                <InputNumber min={1} max={10000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="min_delay" label="Min delay (s)">
                <InputNumber min={10} max={600} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={6}>
              <Form.Item name="max_delay" label="Max delay (s)">
                <InputNumber min={10} max={600} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="max_invites_per_account" label="Per-account daily cap">
                <InputNumber min={1} max={200} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="max_invites_per_task" label="Per-task cap">
                <InputNumber min={1} max={10000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          <Space>
            <Button onClick={handlePreview} loading={previewMut.isPending}>Preview cost</Button>
          </Space>

          {preview && (
            <Alert
              style={{ marginTop: 12 }}
              type={preview.balance_sufficient ? 'success' : 'warning'}
              showIcon
              message={
                <span>
                  <b>{preview.target_count}</b> invites × {preview.unit_price_cents}¢ ={' '}
                  <b>{fmtUsd(preview.estimated_total_cents)}</b>
                </span>
              }
              description={
                <span>
                  Balance: {fmtUsd(preview.balance_cents)} ·{' '}
                  {preview.balance_sufficient
                    ? 'Sufficient'
                    : <span style={{ color: '#cf1322' }}>
                        Short by {fmtUsd(preview.shortfall_cents)}
                      </span>}
                </span>
              }
            />
          )}
        </Form>
      </Modal>
    </div>
  );
};

export default InvitePage;
