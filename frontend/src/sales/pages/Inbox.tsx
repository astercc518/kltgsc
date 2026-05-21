import React from 'react';
import {
  Card, Table, Tag, Button, Space, Select, Input, Empty, Typography,
  Tooltip, Row, Col, Statistic,
} from 'antd';
import { EyeOutlined, ReloadOutlined, CheckCircleOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { LeadCard, leadsApi, walletApi } from '../api';
import { useT } from '../i18n';

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
  const t = useT();
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
      title: t('inbox.col.lead'),
      key: 'name',
      render: (_: any, r: LeadCard) => (
        <Space direction="vertical" size={0}>
          <Text strong>{r.first_name_hint || '—'} · {r.username_hint || '—'}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            {t('inbox.phone')} {r.phone_hint || '—'} · {t('inbox.lead')} #{r.id}
          </Text>
        </Space>
      ),
    },
    {
      title: t('inbox.col.industry'),
      dataIndex: 'industry',
      key: 'industry',
      render: (i: string | null) => i ? <Tag color="cyan">{i}</Tag> : '—',
    },
    {
      title: t('inbox.col.source'),
      dataIndex: 'source',
      render: (s: string) => <Tag>{s}</Tag>,
    },
    {
      title: t('inbox.col.status'),
      dataIndex: 'status',
      render: (s: string) => <Tag color={STATUS_COLOR[s] || 'default'}>{s}</Tag>,
    },
    {
      title: t('inbox.col.views'),
      dataIndex: 'view_count',
      render: (n: number) => n,
    },
    {
      title: t('inbox.col.last'),
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
          {r.already_viewed_today ? t('inbox.action.openFree') : t('inbox.action.view')}
        </Button>
      ),
    },
  ];

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>{t('inbox.title')}</Title>
          <Text type="secondary">{t('inbox.subtitle')}</Text>
        </Col>
        <Col>
          <Space>
            <Statistic
              valueStyle={{ fontSize: 16 }}
              title={t('inbox.balance')}
              value={wallet ? `$${(wallet.balance_cents / 100).toFixed(2)}` : '—'}
            />
            <Button icon={<ReloadOutlined />} onClick={() => refetch()}>{t('common.refresh')}</Button>
          </Space>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}><Card><Statistic title={t('inbox.stat.total')} value={stats.total} /></Card></Col>
        <Col span={6}><Card><Statistic title={t('inbox.stat.viewedToday')} value={stats.viewed} /></Card></Col>
        <Col span={6}><Card><Statistic title={t('inbox.stat.replied')} value={stats.replied} /></Card></Col>
        <Col span={6}>
          <Card>
            <Statistic
              title={t('inbox.stat.industries')}
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
            allowClear placeholder={t('inbox.filter.industry')}
            value={industry}
            onChange={setIndustry}
            style={{ width: 200 }}
            options={industries.map(i => ({ value: i.industry, label: `${i.industry} (${i.count})` }))}
          />
          <Select
            allowClear placeholder={t('inbox.filter.status')}
            value={status}
            onChange={setStatus}
            style={{ width: 160 }}
            options={['new', 'contacted', 'replied', 'interested', 'converted', 'closed']
              .map(s => ({ value: s, label: s }))}
          />
          <Input.Search
            placeholder={t('inbox.filter.search')}
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
          locale={{ emptyText: <Empty description={t('inbox.empty')} /> }}
          pagination={{ pageSize: 20 }}
        />
      </Card>
    </div>
  );
};

export default Inbox;
