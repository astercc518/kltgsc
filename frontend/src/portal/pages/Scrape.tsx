import React from 'react';
import {
  Card, Table, Tag, Button, Space, Statistic, Row, Col, Empty, message,
  Popconfirm, Typography, Modal, Form, Input, InputNumber, Checkbox, Alert,
} from 'antd';
import {
  PlusOutlined, ReloadOutlined, DeleteOutlined, PlayCircleOutlined,
  CloudDownloadOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { scrapeApi, ScrapeBatch, ScrapeCostPreview } from '../api';

const { Title, Text } = Typography;
const { TextArea } = Input;

const STATUS_COLOR: Record<string, string> = {
  pending: 'orange',
  running: 'processing',
  completed: 'green',
  failed: 'red',
  canceled: 'default',
};

const fmtUsd = (cents: number) => `$${(cents / 100).toFixed(2)}`;

const ScrapePage: React.FC = () => {
  const qc = useQueryClient();
  const [createOpen, setCreateOpen] = React.useState(false);
  const [form] = Form.useForm();
  const [preview, setPreview] = React.useState<ScrapeCostPreview | null>(null);

  const { data: batches = [], isLoading, refetch } = useQuery({
    queryKey: ['portal', 'scrape', 'batches'],
    queryFn: () => scrapeApi.list({ limit: 200 }),
    refetchInterval: 15000,
  });

  const cancelMut = useMutation({
    mutationFn: (id: number) => scrapeApi.cancel(id),
    onSuccess: () => {
      message.success('Batch canceled');
      qc.invalidateQueries({ queryKey: ['portal', 'scrape', 'batches'] });
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Cancel failed'),
  });

  const startMut = useMutation({
    mutationFn: (id: number) => scrapeApi.start(id),
    onSuccess: () => {
      message.success('Scrape started');
      qc.invalidateQueries({ queryKey: ['portal', 'scrape', 'batches'] });
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Start failed'),
  });

  const createMut = useMutation({
    mutationFn: (data: any) => scrapeApi.create(data),
    onSuccess: () => {
      message.success('Batch created (pending). Click Start to dispatch.');
      qc.invalidateQueries({ queryKey: ['portal', 'scrape', 'batches'] });
      setCreateOpen(false);
      form.resetFields();
      setPreview(null);
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Create failed'),
  });

  const previewMut = useMutation({
    mutationFn: ({ links, limit }: { links: string[]; limit: number }) =>
      scrapeApi.previewCost(links, limit),
    onSuccess: (data) => setPreview(data),
  });

  const handlePreview = () => {
    const raw = form.getFieldValue('source_links_raw') as string || '';
    const links = raw.split('\n').map(s => s.trim()).filter(Boolean);
    const limit = form.getFieldValue('limit_per_group') || 200;
    if (links.length === 0) {
      message.warning('Please enter at least one group link');
      return;
    }
    previewMut.mutate({ links, limit });
  };

  const handleCreate = async () => {
    try {
      const values = await form.validateFields();
      const links = (values.source_links_raw as string)
        .split('\n').map(s => s.trim()).filter(Boolean);
      createMut.mutate({
        name: values.name,
        source_links: links,
        limit_per_group: values.limit_per_group,
        filter_active_only: !!values.filter_active_only,
        filter_has_photo: !!values.filter_has_photo,
        filter_has_username: !!values.filter_has_username,
      });
    } catch (_) { /* validation */ }
  };

  const stats = React.useMemo(() => {
    const totalScraped = batches.reduce((s, b) => s + b.scraped_count, 0);
    const totalNewUsers = batches.reduce((s, b) => s + b.new_users_count, 0);
    const totalCharged = batches.reduce((s, b) => s + b.charged_cents, 0);
    const active = batches.filter(b => ['running', 'pending'].includes(b.status)).length;
    return { totalScraped, totalNewUsers, totalCharged, active };
  }, [batches]);

  const columns = [
    {
      title: 'Name',
      key: 'name',
      render: (_: any, r: ScrapeBatch) => (
        <Space direction="vertical" size={0}>
          <Text strong>{r.name || `Batch #${r.id}`}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {new Date(r.created_at).toLocaleString()}
          </Text>
        </Space>
      ),
    },
    {
      title: 'Groups',
      key: 'groups',
      render: (_: any, r: ScrapeBatch) => (
        <Tag>{r.source_links.length} × {r.limit_per_group}</Tag>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => <Tag color={STATUS_COLOR[s] || 'default'}>{s.toUpperCase()}</Tag>,
    },
    {
      title: 'Scraped / New',
      key: 'scraped',
      render: (_: any, r: ScrapeBatch) =>
        `${r.scraped_count.toLocaleString()} / ${r.new_users_count.toLocaleString()}`,
    },
    {
      title: 'Est. / Charged',
      key: 'cost',
      render: (_: any, r: ScrapeBatch) => (
        <Space direction="vertical" size={0}>
          <Text type="secondary" style={{ fontSize: 12 }}>est. {fmtUsd(r.estimated_total_cents)}</Text>
          <Text>{r.charged_cents ? fmtUsd(r.charged_cents) : '—'}</Text>
        </Space>
      ),
    },
    {
      title: 'Actions',
      key: 'actions',
      render: (_: any, r: ScrapeBatch) => (
        <Space>
          {r.status === 'pending' && (
            <>
              <Button
                size="small" type="primary" icon={<PlayCircleOutlined />}
                loading={startMut.isPending && startMut.variables === r.id}
                onClick={() => startMut.mutate(r.id)}
              >Start</Button>
              <Popconfirm
                title="Cancel this batch?"
                onConfirm={() => cancelMut.mutate(r.id)}
              >
                <Button size="small" danger icon={<DeleteOutlined />}>Cancel</Button>
              </Popconfirm>
            </>
          )}
          {r.error_message && (
            <Text type="danger" style={{ fontSize: 12 }}>{r.error_message}</Text>
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
            <CloudDownloadOutlined /> 群采集 (Scrape)
          </Title>
          <Text type="secondary">从公开群批量采集成员，按采集到的成员数计费（默认 1¢/成员）</Text>
        </Col>
        <Col>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>Refresh</Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setCreateOpen(true)}>
              New Batch
            </Button>
          </Space>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Card><Statistic title="Active" value={stats.active} /></Card></Col>
        <Col span={6}><Card><Statistic title="Total Scraped" value={stats.totalScraped} /></Card></Col>
        <Col span={6}><Card><Statistic title="New Users" value={stats.totalNewUsers} /></Card></Col>
        <Col span={6}><Card><Statistic title="Total Charged" value={fmtUsd(stats.totalCharged)} /></Card></Col>
      </Row>

      <Card>
        <Table
          rowKey="id"
          dataSource={batches}
          columns={columns}
          loading={isLoading}
          locale={{ emptyText: <Empty description="No batches yet — click New Batch to start" /> }}
          pagination={{ pageSize: 20 }}
        />
      </Card>

      <Modal
        title="New Scrape Batch"
        open={createOpen}
        onCancel={() => { setCreateOpen(false); setPreview(null); }}
        onOk={handleCreate}
        confirmLoading={createMut.isPending}
        width={640}
        okText="Create (Pending)"
      >
        <Form form={form} layout="vertical" initialValues={{ limit_per_group: 200 }}>
          <Form.Item
            name="name" label="Batch name"
            rules={[{ required: true, message: 'Required' }]}
          >
            <Input placeholder="e.g. 加密交易群 2026-05" maxLength={120} />
          </Form.Item>
          <Form.Item
            name="source_links_raw" label="Group links (one per line)"
            rules={[{ required: true, message: 'At least one link' }]}
          >
            <TextArea rows={4} placeholder="https://t.me/foo&#10;https://t.me/bar" />
          </Form.Item>
          <Form.Item name="limit_per_group" label="Max members per group">
            <InputNumber min={1} max={10000} style={{ width: 200 }} />
          </Form.Item>
          <Form.Item label="Filters">
            <Form.Item name="filter_active_only" valuePropName="checked" noStyle>
              <Checkbox>Active in last 7d</Checkbox>
            </Form.Item>{' '}
            <Form.Item name="filter_has_photo" valuePropName="checked" noStyle>
              <Checkbox>Has avatar</Checkbox>
            </Form.Item>{' '}
            <Form.Item name="filter_has_username" valuePropName="checked" noStyle>
              <Checkbox>Has @username</Checkbox>
            </Form.Item>
          </Form.Item>

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
                  Est. <b>{preview.estimated_member_count.toLocaleString()}</b> members
                  × {preview.unit_price_cents}¢ ={' '}
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

export default ScrapePage;
