import React from 'react';
import { Card, Table, Tag, Space, Typography, Button, Select, Empty, Alert } from 'antd';
import { ReloadOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { resourcesApi, bulkApi } from '../api';

const { Title, Text } = Typography;

const STATUS_COLOR: Record<string, string> = {
  new: 'blue', contacted: 'cyan', replied: 'green',
  interested: 'orange', converted: 'green', closed: 'default',
};

const BulkInboxPage: React.FC = () => {
  const nav = useNavigate();
  const [params, setParams] = useSearchParams();
  const batchFilter = params.get('batch') ? Number(params.get('batch')) : undefined;

  const { data: batches = [] } = useQuery({
    queryKey: ['portal', 'bulk', 'batches'],
    queryFn: () => bulkApi.listBatches({ limit: 200 }),
  });

  const { data: leads = [], isLoading, refetch } = useQuery({
    queryKey: ['portal', 'bulk', 'inbox', batchFilter],
    queryFn: () => resourcesApi.leads({
      source: 'bulk',
      bulk_batch_id: batchFilter,
      limit: 200,
    }),
    refetchInterval: 10000,
  });

  const cols = [
    {
      title: 'Sender',
      key: 'sender',
      render: (_: any, r: any) => (
        <Space direction="vertical" size={0}>
          <span style={{ fontWeight: 500 }}>{r.first_name || r.username || `tg:${r.telegram_user_id}`}</span>
          {r.username && <Text type="secondary" style={{ fontSize: 12 }}>@{r.username}</Text>}
        </Space>
      ),
    },
    {
      title: 'Batch',
      dataIndex: 'bulk_batch_id',
      key: 'batch',
      render: (id: number) => id
        ? <Link to={`/portal/bulk/${id}`}>#{id}</Link>
        : <Text type="secondary">—</Text>,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => <Tag color={STATUS_COLOR[s] || 'default'}>{s}</Tag>,
    },
    {
      title: 'Tags',
      dataIndex: 'tags_json',
      key: 'tags',
      render: (j: string) => {
        try {
          return JSON.parse(j || '[]').map((t: string) => <Tag key={t}>{t}</Tag>);
        } catch { return null; }
      },
    },
    {
      title: 'Last interaction',
      dataIndex: 'last_interaction_at',
      key: 'last',
      render: (d: string) => d ? new Date(d).toLocaleString() : '',
    },
  ];

  const batchOptions = batches.map(b => ({
    value: b.id,
    label: `#${b.id} · ${b.name} (${b.replied_count} replies)`,
  }));

  return (
    <div>
      <Button type="link" icon={<ArrowLeftOutlined />} onClick={() => nav('/portal/bulk')} style={{ padding: 0, marginBottom: 8 }}>
        Back to Bulk Send
      </Button>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={3} style={{ margin: 0 }}>Bulk Inbox</Title>
        <Space>
          <Select
            allowClear
            placeholder="Filter by batch"
            style={{ width: 320 }}
            options={batchOptions}
            value={batchFilter}
            onChange={(v) => {
              if (v) setParams({ batch: String(v) });
              else setParams({});
            }}
          />
          <Button icon={<ReloadOutlined />} onClick={() => refetch()}>Refresh</Button>
        </Space>
      </div>

      <Alert
        type="info" showIcon style={{ marginBottom: 16 }}
        message="Replies to your bulk sends appear here in real time."
        description="Each reply becomes a Lead with source='bulk' and auto-flows into your CRM / handover pipeline."
      />

      <Card>
        {leads.length === 0 ? (
          <Empty description={batchFilter ? `No replies for batch #${batchFilter} yet` : 'No bulk replies yet'} />
        ) : (
          <Table
            rowKey="id"
            columns={cols as any}
            dataSource={leads}
            loading={isLoading}
            pagination={{ pageSize: 20 }}
          />
        )}
      </Card>
    </div>
  );
};

export default BulkInboxPage;
