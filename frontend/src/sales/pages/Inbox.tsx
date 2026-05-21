import React from 'react';
import {
  Card, Table, Tag, Button, Space, Select, Input, Empty, Typography,
  Tooltip, Row, Col, Statistic,
} from 'antd';
import { EyeOutlined, ReloadOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { LeadCard, leadsApi, walletApi } from '../api';

const { Title, Text } = Typography;

const STATUS_COLOR: Record<string, string> = {
  new: 'blue',
  contacted: 'gold',
  replied: 'green',
  interested: 'lime',
  converted: 'magenta',
  closed: 'default',
};

const Inbox: React.FC = () => {
  const nav = useNavigate();
  const [industry, setIndustry] = React.useState<string | undefined>(undefined);
  const [status, setStatus] = React.useState<string | undefined>(undefined);
  const [search, setSearch] = React.useState('');

  const { data: industries = [] } = useQuery({
    queryKey: ['sales', 'industries'],
    queryFn: () => leadsApi.industries(),
  });
  const { data: leads = [], isLoading, refetch } = useQuery({
    queryKey: ['sales', 'leads', industry, status],
    queryFn: () => leadsApi.list({ industry, status, limit: 200 }),
    refetchInterval: 20000,
  });
  const { data: wallet } = useQuery({
    queryKey: ['sales', 'wallet'],
    queryFn: () => walletApi.get(),
  });

  const filtered = React.useMemo(() => {
    if (!search) return leads;
    const q = search.toLowerCase();
    return leads.filter(l =>
      (l.first_name_hint || '').toLowerCase().includes(q) ||
      (l.username_hint || '').toLowerCase().includes(q) ||
      String(l.id).includes(q)
    );
  }, [leads, search]);

  const stats = React.useMemo(() => {
    const viewed = filtered.filter(l => l.already_viewed_today).length;
    const replied = filtered.filter(l => l.status === 'replied' || l.status === 'interested').length;
    return { total: filtered.length, viewed, replied };
  }, [filtered]);

  const columns = [
    {
      title: 'Lead',
      key: 'name',
      render: (_: any, r: LeadCard) => (
        <Space direction="vertical" size={0}>
          <Text strong>{r.first_name_hint || '—'} · {r.username_hint || '—'}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            phone {r.phone_hint || '—'} · lead #{r.id}
          </Text>
        </Space>
      ),
    },
    {
      title: 'Industry',
      dataIndex: 'industry',
      key: 'industry',
      render: (i: string | null) => i ? <Tag color="cyan">{i}</Tag> : '—',
    },
    {
      title: 'Source',
      dataIndex: 'source',
      render: (s: string) => <Tag>{s}</Tag>,
    },
    {
      title: 'Status',
      dataIndex: 'status',
      render: (s: string) => <Tag color={STATUS_COLOR[s] || 'default'}>{s}</Tag>,
    },
    {
      title: 'Views',
      dataIndex: 'view_count',
      render: (n: number) => n,
    },
    {
      title: 'Last',
      key: 'last',
      render: (_: any, r: LeadCard) => (
        <Tooltip title={new Date(r.last_interaction_at).toLocaleString()}>
          {new Date(r.last_interaction_at).toLocaleDateString()}
        </Tooltip>
      ),
    },
    {
      title: '',
      key: 'actions',
      render: (_: any, r: LeadCard) => (
        <Button
          size="small"
          type={r.already_viewed_today ? 'default' : 'primary'}
          icon={r.already_viewed_today ? <CheckCircleOutlined /> : <EyeOutlined />}
          onClick={() => nav(`/sales/leads/${r.id}`)}
        >
          {r.already_viewed_today ? 'Open (free)' : 'View ($0.50)'}
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>Lead Inbox</Title>
          <Text type="secondary">
            Click View to unlock contact info — $0.50 per lead per day.
            Same-day re-opens are free.
          </Text>
        </Col>
        <Col>
          <Space>
            <Statistic
              valueStyle={{ fontSize: 16 }}
              title="Balance"
              value={wallet ? `$${(wallet.balance_cents / 100).toFixed(2)}` : '—'}
            />
            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>Refresh</Button>
          </Space>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Card><Statistic title="Total" value={stats.total} /></Card></Col>
        <Col span={6}><Card><Statistic title="Viewed Today" value={stats.viewed} /></Card></Col>
        <Col span={6}><Card><Statistic title="Replied/Interested" value={stats.replied} /></Card></Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="Industries"
              value={industries.length}
              suffix={industries.length ? `(${industries.map(i => i.industry).join(', ')})` : ''}
              valueStyle={{ fontSize: 16 }}
            />
          </Card>
        </Col>
      </Row>

      <Card>
        <Space style={{ marginBottom: 16 }}>
          <Select
            allowClear placeholder="Industry"
            value={industry}
            onChange={setIndustry}
            style={{ width: 200 }}
            options={industries.map(i => ({ value: i.industry, label: `${i.industry} (${i.count})` }))}
          />
          <Select
            allowClear placeholder="Status"
            value={status}
            onChange={setStatus}
            style={{ width: 160 }}
            options={['new', 'contacted', 'replied', 'interested', 'converted', 'closed']
              .map(s => ({ value: s, label: s }))}
          />
          <Input.Search
            placeholder="Search masked hints"
            value={search}
            onChange={e => setSearch(e.target.value)}
            style={{ width: 240 }}
          />
        </Space>
        <Table
          rowKey="id"
          dataSource={filtered}
          columns={columns}
          loading={isLoading}
          locale={{ emptyText: <Empty description="No leads in your scope" /> }}
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  );
};

export default Inbox;
