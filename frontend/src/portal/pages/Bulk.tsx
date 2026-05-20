import React from 'react';
import { Card, Table, Tag, Button, Space, Statistic, Row, Col, Empty, message, Popconfirm, Typography, Tooltip } from 'antd';
import { PlusOutlined, ReloadOutlined, DeleteOutlined, EyeOutlined, InboxOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { Link, useNavigate } from 'react-router-dom';
import { bulkApi, BulkBatch } from '../api';

const { Title, Text } = Typography;

const STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  pending: 'orange',
  running: 'processing',
  paused: 'gold',
  completed: 'green',
  failed: 'red',
  canceled: 'default',
};

const formatUsd = (cents: number) => `$${(cents / 100).toFixed(2)}`;

const BulkPage: React.FC = () => {
  const nav = useNavigate();
  const qc = useQueryClient();

  const { data: batches = [], isLoading, refetch } = useQuery({
    queryKey: ['portal', 'bulk', 'batches'],
    queryFn: () => bulkApi.listBatches({ limit: 200 }),
    refetchInterval: 15000,
  });

  const cancelMut = useMutation({
    mutationFn: (id: number) => bulkApi.cancelBatch(id),
    onSuccess: () => {
      message.success('Draft canceled');
      qc.invalidateQueries({ queryKey: ['portal', 'bulk', 'batches'] });
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Cancel failed'),
  });

  const stats = React.useMemo(() => {
    const totalSent = batches.reduce((s, b) => s + b.sent_count, 0);
    const totalReplied = batches.reduce((s, b) => s + b.replied_count, 0);
    const totalDraft = batches.filter(b => b.status === 'draft').length;
    const totalActive = batches.filter(b => ['running', 'pending'].includes(b.status)).length;
    return { totalSent, totalReplied, totalDraft, totalActive };
  }, [batches]);

  const columns = [
    {
      title: 'Name',
      dataIndex: 'name',
      key: 'name',
      render: (n: string, r: BulkBatch) => (
        <Space direction="vertical" size={0}>
          <Link to={`/portal/bulk/${r.id}`} style={{ fontWeight: 500 }}>{n || `Batch #${r.id}`}</Link>
          <Text type="secondary" style={{ fontSize: 12 }}>{new Date(r.created_at).toLocaleString()}</Text>
        </Space>
      ),
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => <Tag color={STATUS_COLOR[s] || 'default'}>{s}</Tag>,
    },
    {
      title: 'Targets',
      key: 'targets',
      render: (_: any, r: BulkBatch) => (
        <Space direction="vertical" size={0}>
          <span>{r.total_targets} total</span>
          {r.skipped_count > 0 && <Text type="secondary" style={{ fontSize: 12 }}>{r.skipped_count} dedup</Text>}
        </Space>
      ),
    },
    {
      title: 'Progress',
      key: 'progress',
      render: (_: any, r: BulkBatch) => (
        <Space direction="vertical" size={0}>
          <span>{r.sent_count} sent · {r.failed_count} failed</span>
          {r.replied_count > 0 && <Text style={{ color: '#22c55e', fontSize: 12 }}>{r.replied_count} replied</Text>}
        </Space>
      ),
    },
    {
      title: 'Est. cost',
      key: 'cost',
      render: (_: any, r: BulkBatch) => (
        <Tooltip title={`Unit: ${r.estimated_unit_price_cents}¢ at creation time`}>
          <span>{formatUsd(r.estimated_total_cents)}</span>
        </Tooltip>
      ),
    },
    {
      title: '',
      key: 'actions',
      width: 160,
      render: (_: any, r: BulkBatch) => (
        <Space>
          <Button size="small" icon={<EyeOutlined />} onClick={() => nav(`/portal/bulk/${r.id}`)}>Detail</Button>
          {(r.status === 'draft' || r.status === 'pending') && (
            <Popconfirm
              title="Delete this draft batch?"
              onConfirm={() => cancelMut.mutate(r.id)}
            >
              <Button size="small" danger icon={<DeleteOutlined />} />
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Bulk Send</Title>
        <Space>
          <Button icon={<InboxOutlined />} onClick={() => nav('/portal/bulk/inbox')}>
            Inbox{stats.totalReplied > 0 ? ` (${stats.totalReplied})` : ''}
          </Button>
          <Button icon={<ReloadOutlined />} onClick={() => refetch()}>Refresh</Button>
          <Button type="primary" icon={<PlusOutlined />} onClick={() => nav('/portal/bulk/new')}>
            New Batch
          </Button>
        </Space>
      </div>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Card><Statistic title="Total sent" value={stats.totalSent} /></Card></Col>
        <Col span={6}><Card><Statistic title="Total replies" value={stats.totalReplied} valueStyle={{ color: '#22c55e' }} /></Card></Col>
        <Col span={6}><Card><Statistic title="Drafts" value={stats.totalDraft} /></Card></Col>
        <Col span={6}><Card><Statistic title="Active batches" value={stats.totalActive} /></Card></Col>
      </Row>

      <Card>
        {batches.length === 0 && !isLoading ? (
          <Empty
            description={
              <Space direction="vertical">
                <span>No batches yet</span>
                <Button type="primary" icon={<PlusOutlined />} onClick={() => nav('/portal/bulk/new')}>
                  Create your first batch
                </Button>
              </Space>
            }
          />
        ) : (
          <Table
            rowKey="id"
            loading={isLoading}
            columns={columns as any}
            dataSource={batches}
            pagination={{ pageSize: 20 }}
          />
        )}
      </Card>
    </div>
  );
};

export default BulkPage;
