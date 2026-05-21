/**
 * S2.6 — Customer-facing AI marketing monitor rules.
 *
 * Mirrors src/sales/pages/Monitors.tsx but talks to /customer/monitors
 * (portal token) and exposes the half-automatic `marketing_mode='active'`
 * + `reply_mode='group_reply'` combination that lets the AI reply in the
 * source group when keywords are hit. private_dm is explicitly omitted
 * from the form — the backend rejects it for customer-owned rules.
 *
 * Visibility of this page is gated by the `ai_marketing_assistant`
 * feature being enabled (handled by PortalLayout's menu builder).
 */
import React from 'react';
import {
  Card, Table, Tag, Button, Space, Switch, Typography, Empty, Modal, Form,
  Input, InputNumber, Select, Popconfirm, message, Drawer, List, Alert,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ThunderboltOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { monitorsApi, CustomerMonitor } from '../api';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const MARKETING_MODE_OPTIONS = [
  { value: 'passive', label: '被动监听（只命中、不回复）' },
  { value: 'active', label: '主动 AI 群内回话（半自动，群内回应）' },
];

const MATCH_TYPE_OPTIONS = [
  { value: 'partial', label: '部分匹配' },
  { value: 'exact', label: '精确匹配' },
  { value: 'regex', label: '正则' },
  { value: 'semantic', label: '语义匹配（AI）' },
];

const PortalMonitors: React.FC = () => {
  const qc = useQueryClient();
  const [editing, setEditing] = React.useState<CustomerMonitor | null>(null);
  const [open, setOpen] = React.useState(false);
  const [hitsFor, setHitsFor] = React.useState<CustomerMonitor | null>(null);
  const [form] = Form.useForm();

  const { data: monitors = [], isLoading, refetch } = useQuery({
    queryKey: ['portal', 'monitors'],
    queryFn: () => monitorsApi.list(),
  });

  const { data: hits = [], isLoading: hitsLoading } = useQuery({
    queryKey: ['portal', 'monitor-hits', hitsFor?.id],
    queryFn: () => hitsFor ? monitorsApi.recentHits(hitsFor.id, 50) : Promise.resolve([]),
    enabled: !!hitsFor,
  });

  const saveMut = useMutation({
    mutationFn: (body: Partial<CustomerMonitor>) =>
      editing ? monitorsApi.update(editing.id, body) : monitorsApi.create(body),
    onSuccess: () => {
      message.success(editing ? '已更新' : '已创建');
      qc.invalidateQueries({ queryKey: ['portal', 'monitors'] });
      setOpen(false);
      setEditing(null);
      form.resetFields();
    },
    onError: (e: any) => {
      const detail = e?.response?.data?.detail;
      if (e?.response?.status === 402) {
        message.error(`AI 营销助手未开通：${detail || '请检查订阅状态'}`);
      } else {
        message.error(detail || '保存失败');
      }
    },
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      monitorsApi.update(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portal', 'monitors'] }),
    onError: (e: any) => message.error(e?.response?.data?.detail || '操作失败'),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => monitorsApi.remove(id),
    onSuccess: () => {
      message.success('已删除');
      qc.invalidateQueries({ queryKey: ['portal', 'monitors'] });
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || '删除失败'),
  });

  const openCreate = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      match_type: 'partial',
      marketing_mode: 'passive',
      reply_mode: 'group_reply',
      cooldown_seconds: 300,
      max_replies_per_day: 10,
      delay_min_seconds: 30,
      delay_max_seconds: 180,
      ai_persona: 'helpful',
      score_weight: 10,
      similarity_threshold: 70,
      is_active: true,
    });
    setOpen(true);
  };

  const openEdit = (m: CustomerMonitor) => {
    setEditing(m);
    form.setFieldsValue(m);
    setOpen(true);
  };

  const onSubmit = () => {
    form.validateFields().then(values => {
      // Customer-owned rules always reply in-group; the backend rejects
      // private_dm explicitly. Pin it here so the user can't get a 400.
      const body: Partial<CustomerMonitor> = {
        ...values,
        reply_mode: 'group_reply',
      };
      saveMut.mutate(body);
    });
  };

  const columns = [
    { title: 'ID', dataIndex: 'id', width: 60 },
    { title: '关键词', dataIndex: 'keyword', width: 160,
      render: (v: string) => <Text strong>{v}</Text> },
    {
      title: '匹配方式', dataIndex: 'match_type', width: 100,
      render: (v: string) =>
        <Tag>{MATCH_TYPE_OPTIONS.find(o => o.value === v)?.label || v}</Tag>,
    },
    {
      title: '模式', dataIndex: 'marketing_mode', width: 110,
      render: (v: string) => (
        v === 'active'
          ? <Tag color="purple" icon={<ThunderboltOutlined />}>主动群内回话</Tag>
          : <Tag>被动监听</Tag>
      ),
    },
    { title: '目标群组', dataIndex: 'target_groups', ellipsis: true },
    { title: '行业', dataIndex: 'industry', width: 100,
      render: (v?: string) => v ? <Tag color="cyan">{v}</Tag> : <Text type="secondary">—</Text> },
    {
      title: '启用', dataIndex: 'is_active', width: 80,
      render: (v: boolean, row: CustomerMonitor) => (
        <Switch checked={v} size="small"
          onChange={(checked) => toggleMut.mutate({ id: row.id, is_active: checked })} />
      ),
    },
    {
      title: '操作', width: 220, fixed: 'right' as const,
      render: (_: any, row: CustomerMonitor) => (
        <Space>
          <Button size="small" onClick={() => setHitsFor(row)}>近 50 命中</Button>
          <Button size="small" type="link" icon={<EditOutlined />} onClick={() => openEdit(row)}>编辑</Button>
          <Popconfirm title="删除该规则？" onConfirm={() => deleteMut.mutate(row.id)}>
            <Button size="small" type="link" danger icon={<DeleteOutlined />}>删除</Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Title level={2}><ThunderboltOutlined /> AI 营销助手 — 监听规则</Title>
      <Paragraph type="secondary">
        在你的 TG 账号已经潜伏的目标群里，AI 会监听符合关键词/语义的群消息。
        命中后可选择仅记录线索（被动），或主动在群内 @ 回复（半自动）。
        主动私聊用户的决定 <strong>必须由销售人工</strong> 在 /sales/inbox 接管会话后做。
      </Paragraph>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 16 }}
        message="计费提示"
        description={
          <span>
            主动模式下，每条 AI 群内回话与每条 AI 自动产出的线索 <strong>分别按条扣 wallet</strong>。
            余额不足时计费会跳过（但仍记录命中），可在 Wallet 页查看实时余额。
          </span>
        }
      />

      <Card
        title={`监听规则 (${monitors.length})`}
        extra={
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>刷新</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={openCreate}>新建规则</Button>
          </Space>
        }
      >
        {monitors.length === 0 ? (
          <Empty description="还没有监听规则" />
        ) : (
          <Table
            dataSource={monitors}
            columns={columns}
            rowKey="id"
            loading={isLoading}
            pagination={false}
            scroll={{ x: 1100 }}
          />
        )}
      </Card>

      <Modal
        open={open}
        title={editing ? `编辑规则 #${editing.id}` : '新建监听规则'}
        onCancel={() => { setOpen(false); setEditing(null); form.resetFields(); }}
        onOk={onSubmit}
        confirmLoading={saveMut.isPending}
        width={680}
        destroyOnClose
      >
        <Form form={form} layout="vertical">
          <Form.Item name="keyword" label="关键词" rules={[{ required: true, message: '关键词必填' }]}>
            <Input placeholder="如：crypto exchange / 跨境收款 / etc." />
          </Form.Item>
          <Form.Item name="match_type" label="匹配方式">
            <Select options={MATCH_TYPE_OPTIONS} />
          </Form.Item>
          <Form.Item name="target_groups" label="目标群组" rules={[{ required: true, message: '必须指定目标群组（避免监听全网）' }]}>
            <TextArea rows={2} placeholder="逗号分隔群组链接或 ID，如 @group_a, @group_b" />
          </Form.Item>
          <Form.Item name="marketing_mode" label="工作模式">
            <Select options={MARKETING_MODE_OPTIONS} />
          </Form.Item>
          <Form.Item name="industry" label="行业（可选）">
            <Input placeholder="如：crypto / fintech，会写入命中的 Lead 用于销售分流" />
          </Form.Item>
          <Form.Item name="ai_persona" label="AI 人设">
            <Select options={[
              { value: 'helpful', label: '热心群友 (helpful)' },
              { value: 'expert', label: '行业老鸟 (expert)' },
              { value: 'curious', label: '好奇小白 (curious)' },
              { value: 'custom', label: '自定义（在战役/Persona 配）' },
            ]} />
          </Form.Item>
          <Space size="large" style={{ display: 'flex' }}>
            <Form.Item name="cooldown_seconds" label="冷却(秒)">
              <InputNumber min={0} max={86400} />
            </Form.Item>
            <Form.Item name="max_replies_per_day" label="每日上限(条)">
              <InputNumber min={1} max={500} />
            </Form.Item>
            <Form.Item name="delay_min_seconds" label="最小延迟(秒)">
              <InputNumber min={0} max={3600} />
            </Form.Item>
            <Form.Item name="delay_max_seconds" label="最大延迟(秒)">
              <InputNumber min={0} max={3600} />
            </Form.Item>
          </Space>
          <Form.Item name="description" label="备注">
            <TextArea rows={2} />
          </Form.Item>
          <Form.Item name="is_active" label="启用" valuePropName="checked">
            <Switch />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        open={!!hitsFor}
        onClose={() => setHitsFor(null)}
        title={hitsFor ? `近 50 命中 — ${hitsFor.keyword}` : ''}
        width={560}
      >
        {hitsLoading ? '加载中...' :
          hits.length === 0 ? <Empty description="尚无命中记录" /> : (
            <List
              dataSource={hits}
              renderItem={hit => (
                <List.Item>
                  <List.Item.Meta
                    title={
                      <Space>
                        <Tag>{hit.status}</Tag>
                        <Text>{hit.source_group_name || hit.source_group_id}</Text>
                        <Text type="secondary">@{hit.source_user_name || hit.source_user_id}</Text>
                      </Space>
                    }
                    description={
                      <>
                        <div style={{ marginBottom: 4 }}>{hit.message_content}</div>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {new Date(hit.detected_at).toLocaleString()}
                        </Text>
                      </>
                    }
                  />
                </List.Item>
              )}
            />
          )}
      </Drawer>
    </div>
  );
};

export default PortalMonitors;
