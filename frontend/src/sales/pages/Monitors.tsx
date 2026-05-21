import React from 'react';
import {
  Card, Table, Tag, Button, Space, Switch, Typography, Empty, Modal, Form,
  Input, InputNumber, Select, Popconfirm, message, Drawer, List, Tooltip,
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, ThunderboltOutlined,
  ReloadOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { monitorsApi, SalesMonitor } from '../api';
import { useT } from '../i18n';

const { Title, Text, Paragraph } = Typography;

const MonitorsPage: React.FC = () => {
  const qc = useQueryClient();
  const t = useT();
  const [editing, setEditing] = React.useState<SalesMonitor | null>(null);
  const [open, setOpen] = React.useState(false);
  const [hitsFor, setHitsFor] = React.useState<SalesMonitor | null>(null);
  const [form] = Form.useForm();

  const { data: monitors = [], isLoading, refetch } = useQuery({
    queryKey: ['sales', 'monitors'],
    queryFn: () => monitorsApi.list(),
  });

  const { data: hits = [], isLoading: hitsLoading } = useQuery({
    queryKey: ['sales', 'monitor-hits', hitsFor?.id],
    queryFn: () => hitsFor ? monitorsApi.recentHits(hitsFor.id, 24) : Promise.resolve([]),
    enabled: !!hitsFor,
  });

  const saveMut = useMutation({
    mutationFn: (body: Partial<SalesMonitor>) =>
      editing ? monitorsApi.update(editing.id, body) : monitorsApi.create(body),
    onSuccess: () => {
      message.success(editing ? 'Updated' : 'Created');
      qc.invalidateQueries({ queryKey: ['sales', 'monitors'] });
      setOpen(false); setEditing(null); form.resetFields();
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Failed'),
  });

  const toggleMut = useMutation({
    mutationFn: ({ id, is_active }: { id: number; is_active: boolean }) =>
      monitorsApi.update(id, { is_active }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['sales', 'monitors'] }),
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Toggle failed'),
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => monitorsApi.remove(id),
    onSuccess: () => {
      message.success('Deleted');
      qc.invalidateQueries({ queryKey: ['sales', 'monitors'] });
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Delete failed'),
  });

  const openNew = () => {
    setEditing(null);
    form.resetFields();
    form.setFieldsValue({
      match_type: 'partial', cooldown_seconds: 300,
      score_weight: 10, similarity_threshold: 70,
      auto_capture_lead: true,
    });
    setOpen(true);
  };

  const openEdit = (m: SalesMonitor) => {
    setEditing(m);
    form.setFieldsValue(m);
    setOpen(true);
  };

  const handleSave = async () => {
    try {
      const v = await form.validateFields();
      // marketing_mode is locked to 'passive' for sales-owned rules.
      saveMut.mutate({ ...v, marketing_mode: 'passive' });
    } catch (_) {}
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>{t('monitors.title')}</Title>
          <Text type="secondary">{t('monitors.subtitle')}</Text>
        </div>
        <Space>
          <Button icon={<ReloadOutlined />} onClick={() => refetch()}>{t('common.refresh')}</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={openNew}>{t('monitors.new')}</Button>
        </Space>
      </div>

      <Card>
        <Table
          rowKey="id"
          dataSource={monitors}
          loading={isLoading}
          pagination={{ pageSize: 20 }}
          locale={{ emptyText: <Empty description={t('monitors.empty')} /> }}
          columns={[
            { title: t('monitors.col.keyword'), dataIndex: 'keyword',
              render: (k: string, r: SalesMonitor) => (
                <Space direction="vertical" size={0}>
                  <Text strong>{k}</Text>
                  {r.description && <Text type="secondary" style={{ fontSize: 12 }}>{r.description}</Text>}
                </Space>
              )},
            { title: t('monitors.col.match'), dataIndex: 'match_type', width: 110,
              render: (m: string) => <Tag>{m}</Tag> },
            { title: t('monitors.col.industry'), dataIndex: 'industry', width: 120,
              render: (i: string | null) => i ? <Tag color="cyan">{i}</Tag> : '—' },
            { title: t('monitors.col.cooldown'), dataIndex: 'cooldown_seconds', width: 90,
              render: (c: number) => `${c}s` },
            { title: t('monitors.col.active'), dataIndex: 'is_active', width: 90,
              render: (active: boolean, r: SalesMonitor) => (
                <Switch checked={active}
                  loading={toggleMut.isPending && toggleMut.variables?.id === r.id}
                  onChange={(v) => toggleMut.mutate({ id: r.id, is_active: v })} />
              )},
            { title: t('monitors.col.actions'), key: 'actions', width: 280,
              render: (_: any, r: SalesMonitor) => (
                <Space>
                  <Button size="small" icon={<EditOutlined />} onClick={() => openEdit(r)}>
                    {t('monitors.action.edit')}
                  </Button>
                  <Button size="small" icon={<ThunderboltOutlined />}
                    onClick={() => setHitsFor(r)}>
                    {t('monitors.action.hits')}
                  </Button>
                  <Popconfirm title={t('monitors.deleteConfirm')}
                    onConfirm={() => deleteMut.mutate(r.id)}>
                    <Button size="small" danger icon={<DeleteOutlined />}>
                      {t('monitors.action.delete')}
                    </Button>
                  </Popconfirm>
                </Space>
              )},
          ]}
        />
      </Card>

      <Modal
        title={editing ? t('monitors.modal.edit') : t('monitors.modal.create')}
        open={open} onCancel={() => { setOpen(false); setEditing(null); }}
        onOk={handleSave} confirmLoading={saveMut.isPending}
        width={640}
      >
        <Form form={form} layout="vertical">
          <Form.Item name="keyword" label={t('monitors.field.keyword')}
            rules={[{ required: true, message: 'required' }]}>
            <Input placeholder={t('monitors.field.keywordPh')} maxLength={200} />
          </Form.Item>
          <Form.Item name="match_type" label={t('monitors.field.matchType')}
            rules={[{ required: true }]}>
            <Select options={[
              { value: 'partial', label: t('monitors.field.match.partial') },
              { value: 'exact', label: t('monitors.field.match.exact') },
              { value: 'regex', label: t('monitors.field.match.regex') },
              { value: 'semantic', label: t('monitors.field.match.semantic') },
            ]} />
          </Form.Item>
          <Form.Item name="industry" label={t('monitors.field.industry')}
            extra={t('monitors.field.industryHelp')}>
            <Input maxLength={50} placeholder="crypto / forex / saas / ..." />
          </Form.Item>
          <Form.Item name="target_groups" label={t('monitors.field.targetGroups')}>
            <Input.TextArea rows={2} placeholder={t('monitors.field.targetGroupsPh')} maxLength={500} />
          </Form.Item>
          <Form.Item name="scenario_description" label={t('monitors.field.scenarioDesc')}>
            <Input.TextArea rows={2} placeholder={t('monitors.field.scenarioDescPh')} maxLength={500} />
          </Form.Item>
          <Form.Item name="cooldown_seconds" label={t('monitors.field.cooldown')}>
            <InputNumber min={30} max={3600} step={30} style={{ width: 200 }} />
          </Form.Item>
          <Form.Item name="auto_capture_lead" valuePropName="checked" label={t('monitors.field.autoLead')}>
            <Switch />
          </Form.Item>
          <Form.Item name="score_weight" label={t('monitors.field.scoreWeight')}>
            <InputNumber min={1} max={100} style={{ width: 200 }} />
          </Form.Item>
          <Form.Item name="description" label={t('monitors.field.description')}>
            <Input maxLength={200} />
          </Form.Item>
        </Form>
      </Modal>

      <Drawer
        open={!!hitsFor}
        onClose={() => setHitsFor(null)}
        title={`${t('monitors.recentHits')} — ${hitsFor?.keyword || ''}`}
        width={520}
      >
        {hitsLoading ? null : hits.length === 0 ? (
          <Empty description={t('monitors.recentEmpty')} />
        ) : (
          <List
            dataSource={hits}
            renderItem={(h) => (
              <List.Item>
                <List.Item.Meta
                  title={
                    <Space>
                      <Text strong>{h.source_group_name || '—'}</Text>
                      <Tooltip title={new Date(h.detected_at).toLocaleString()}>
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {new Date(h.detected_at).toLocaleTimeString()}
                        </Text>
                      </Tooltip>
                    </Space>
                  }
                  description={
                    <>
                      <Text type="secondary" style={{ fontSize: 12 }}>{h.source_user_name || '?'}</Text>
                      <Paragraph style={{ marginTop: 4 }}>{h.snippet}</Paragraph>
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

export default MonitorsPage;
