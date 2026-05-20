/**
 * Epic 6.0 — Admin BusinessOps Dashboard
 *
 * Six panels:
 *   1. Top-line KPI cards (customers, MRR, accounts, leads)
 *   2. Customer health table
 *   3. Lead funnel chart
 *   4. Account pool breakdown
 *   5. LLM cost (daily bar chart)
 *   6. Epic 5.2 handover stats
 */
import React from 'react';
import {
  Card, Row, Col, Statistic, Table, Tag, Typography, Spin, Empty, Tooltip, Progress,
} from 'antd';
import {
  UserOutlined, DollarOutlined, TeamOutlined, MessageOutlined,
  WarningOutlined, ThunderboltOutlined, CheckCircleOutlined,
  RocketOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip as ChartTip, ResponsiveContainer,
  Cell, PieChart, Pie, Legend,
} from 'recharts';
import api from '../services/api';

const { Title, Text } = Typography;

const REFETCH = 30_000;  // 30s
const PLAN_COLOR: Record<string, string> = {
  starter: '#0066FF', growth: '#22C55E', pro: '#FFB020',
};
const STATUS_COLOR: Record<string, string> = {
  pending: 'orange', active: 'green', suspended: 'red', canceled: 'default',
};

// ── API helpers ─────────────────────────────────────────────────────────
const opsApi = {
  overview: () => api.get('/admin/dashboard/overview').then(r => r.data),
  customers: () => api.get('/admin/dashboard/customers?limit=100').then(r => r.data),
  funnel: (days = 30) => api.get(`/admin/dashboard/lead-funnel?days=${days}`).then(r => r.data),
  pool: () => api.get('/admin/dashboard/account-pool').then(r => r.data),
  llmCost: (days = 14) => api.get(`/admin/dashboard/llm-usage?days=${days}`).then(r => r.data),
  handover: (days = 30) => api.get(`/admin/dashboard/handover-stats?days=${days}`).then(r => r.data),
};

// ── KPI cards ───────────────────────────────────────────────────────────
const KPIRow: React.FC<{ data: any }> = ({ data }) => (
  <Row gutter={[16, 16]}>
    <Col xs={24} sm={12} md={6}>
      <Card>
        <Statistic
          title={<span><UserOutlined /> Active Customers</span>}
          value={data.customers.by_status?.active || 0}
          suffix={`/ ${data.customers.total}`}
          valueStyle={{ color: '#0066FF' }}
        />
        <Text type="secondary" style={{ fontSize: 12 }}>
          Subs active: {data.customers.active_subs}
          {data.pending_invoices > 0 && (
            <Tag color="orange" style={{ marginLeft: 8 }}>
              {data.pending_invoices} pending invoices
            </Tag>
          )}
        </Text>
      </Card>
    </Col>
    <Col xs={24} sm={12} md={6}>
      <Card>
        <Statistic
          title={<span><DollarOutlined /> MRR (USD)</span>}
          value={data.mrr_usd}
          precision={2}
          prefix="$"
          valueStyle={{ color: '#22C55E' }}
        />
        <Text type="secondary" style={{ fontSize: 12 }}>
          {Object.entries(data.customers.by_plan || {}).map(([p, n]: any) =>
            <Tag key={p} color={PLAN_COLOR[p]} style={{ marginRight: 4 }}>{p}: {n}</Tag>
          )}
        </Text>
      </Card>
    </Col>
    <Col xs={24} sm={12} md={6}>
      <Card>
        <Statistic
          title={<span><TeamOutlined /> Accounts</span>}
          value={data.accounts.allocated}
          suffix={`/ ${data.accounts.total}`}
        />
        <Text type="secondary" style={{ fontSize: 12 }}>
          Free: {data.accounts.free} ·
          Main: {data.accounts.main_accounts}
          {data.accounts.banned > 0 && (
            <Tag color="red" style={{ marginLeft: 4 }}>
              <WarningOutlined /> {data.accounts.banned} banned
            </Tag>
          )}
        </Text>
      </Card>
    </Col>
    <Col xs={24} sm={12} md={6}>
      <Card>
        <Statistic
          title={<span><MessageOutlined /> Leads</span>}
          value={data.leads.total}
          suffix={
            <span style={{ fontSize: 14, color: '#22C55E' }}>
              +{data.leads.last_24h}/24h
            </span>
          }
        />
        <Text type="secondary" style={{ fontSize: 12 }}>
          KB: {data.knowledge_base_total} · Groups: {data.source_groups_total}
        </Text>
      </Card>
    </Col>
  </Row>
);

// ── Lead funnel ─────────────────────────────────────────────────────────
const FunnelChart: React.FC<{ data: any }> = ({ data }) => {
  const rows = Object.entries(data.stages).map(([stage, count]: any) => ({
    stage, count,
  }));
  const FUNNEL_COLORS = ['#94a3b8', '#0ea5e9', '#22c55e', '#f59e0b', '#dc2626', '#64748b'];

  return (
    <Card title={<><RocketOutlined /> Lead Funnel (last {data.window_days} days)</>}>
      <ResponsiveContainer width="100%" height={220}>
        <BarChart data={rows} layout="vertical" margin={{ left: 8 }}>
          <XAxis type="number" />
          <YAxis dataKey="stage" type="category" width={90} />
          <ChartTip />
          <Bar dataKey="count">
            {rows.map((_, i) => <Cell key={i} fill={FUNNEL_COLORS[i % FUNNEL_COLORS.length]} />)}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
      <div style={{ marginTop: 8 }}>
        {Object.entries(data.conversion_rates_pct).map(([k, v]: any) => (
          <Tag key={k} style={{ marginBottom: 4 }}>{k}: {v}%</Tag>
        ))}
      </div>
    </Card>
  );
};

// ── Account pool ────────────────────────────────────────────────────────
const PoolPanel: React.FC<{ data: any }> = ({ data }) => {
  const roleData = Object.entries(data.by_role).map(([name, value]: any) => ({ name, value }));
  const ROLE_COLORS: Record<string, string> = {
    worker: '#0ea5e9', listener: '#22c55e', support: '#f59e0b',
    sales: '#dc2626', collector: '#a855f7', main: '#ec4899',
    master: '#64748b',
  };
  const healthData = Object.entries(data.health_score_buckets).map(([bucket, count]: any) => ({
    bucket, count,
  }));

  return (
    <Card title={<><CheckCircleOutlined /> Account Pool</>}>
      <Row gutter={16}>
        <Col xs={24} md={12}>
          <Text strong>By role:</Text>
          <ResponsiveContainer width="100%" height={200}>
            <PieChart>
              <Pie data={roleData} dataKey="value" nameKey="name" outerRadius={70} label>
                {roleData.map((r, i) => (
                  <Cell key={i} fill={ROLE_COLORS[r.name] || '#94a3b8'} />
                ))}
              </Pie>
              <Legend />
            </PieChart>
          </ResponsiveContainer>
        </Col>
        <Col xs={24} md={12}>
          <Text strong>Health score distribution:</Text>
          <ResponsiveContainer width="100%" height={200}>
            <BarChart data={healthData}>
              <XAxis dataKey="bucket" />
              <YAxis />
              <ChartTip />
              <Bar dataKey="count" fill="#0066FF" />
            </BarChart>
          </ResponsiveContainer>
        </Col>
      </Row>
      <Text type="secondary">
        Free for allocation: <strong>{data.free_for_allocation}</strong>
      </Text>
    </Card>
  );
};

// ── LLM cost ────────────────────────────────────────────────────────────
const LLMCostPanel: React.FC<{ data: any }> = ({ data }) => (
  <Card title={
    <span>
      <ThunderboltOutlined /> LLM Cost — last {data.window_days} days ·
      total <Text strong type="warning">${data.total_cost_usd.toFixed(2)}</Text>
    </span>
  }>
    {data.daily?.length > 0 ? (
      <>
        <ResponsiveContainer width="100%" height={220}>
          <BarChart data={data.daily}>
            <XAxis dataKey="day" tick={{ fontSize: 10 }} />
            <YAxis />
            <ChartTip />
            <Bar dataKey="cost_usd" fill="#FFB020" />
          </BarChart>
        </ResponsiveContainer>
        <div style={{ marginTop: 8 }}>
          <Text strong style={{ marginRight: 8 }}>By source:</Text>
          {Object.entries(data.by_source).map(([k, v]: any) => (
            <Tag key={k}>{k}: ${(+v).toFixed(2)}</Tag>
          ))}
        </div>
      </>
    ) : (
      <Empty description="No LLM usage in this window" />
    )}
  </Card>
);

// ── Handover stats ──────────────────────────────────────────────────────
const HandoverPanel: React.FC<{ data: any }> = ({ data }) => (
  <Card title={<><WarningOutlined /> Handover Stats (last {data.window_days} days)</>}>
    <Row gutter={16}>
      <Col xs={12} md={6}>
        <Statistic title="Notified" value={data.notified} />
      </Col>
      <Col xs={12} md={6}>
        <Statistic title="Claimed in time" value={data.claimed_in_time}
          suffix={<Text type="secondary">{data.claim_rate_pct}%</Text>} />
      </Col>
      <Col xs={12} md={6}>
        <Statistic title="Handover sent" value={data.handover_link_sent}
          suffix={<Text type="secondary">{data.escalation_rate_pct}%</Text>}
          valueStyle={{ color: '#FFB020' }} />
      </Col>
      <Col xs={12} md={6}>
        <Statistic title="Converted" value={data.converted}
          suffix={<Text type="secondary">{data.conversion_rate_pct}%</Text>}
          valueStyle={{ color: '#22C55E' }} />
      </Col>
    </Row>
    <Progress
      style={{ marginTop: 16 }}
      percent={data.claim_rate_pct + data.escalation_rate_pct}
      success={{ percent: data.claim_rate_pct }}
      format={() => `claim+escalate coverage`}
    />
  </Card>
);

// ── Customer health table ───────────────────────────────────────────────
const CustomerTable: React.FC<{ data: any[] }> = ({ data }) => (
  <Card title={<><UserOutlined /> Customer Health</>}>
    <Table
      dataSource={data}
      rowKey="id"
      size="small"
      pagination={{ pageSize: 20 }}
      columns={[
        { title: 'ID', dataIndex: 'id', width: 60 },
        { title: 'Email', dataIndex: 'email', ellipsis: true },
        { title: 'Industry', dataIndex: 'industry',
          render: (v) => v ? <Tag>{v}</Tag> : '—', width: 100 },
        { title: 'Status', dataIndex: 'status',
          render: (s) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>, width: 100 },
        { title: 'Plan', dataIndex: 'plan',
          render: (p) => p ? <Tag color={PLAN_COLOR[p]}>{p}</Tag> : '—', width: 90 },
        {
          title: 'Accounts',
          dataIndex: 'accounts',
          render: (a: any) => (
            <Tooltip title={`${a.used}/${a.quota} (${a.pct}%)`}>
              <Progress percent={a.pct} size="small" status={a.pct > 90 ? 'exception' : 'normal'} />
            </Tooltip>
          ),
          width: 140,
        },
        { title: 'KB', dataIndex: 'kb_entries', width: 70 },
        { title: 'Leads', dataIndex: 'leads', width: 80 },
        {
          title: 'Main',
          dataIndex: 'main_account_bound',
          render: (v) => v ? <Tag color="green">✓</Tag> : <Tag>—</Tag>,
          width: 70,
        },
        {
          title: 'Renews',
          dataIndex: 'current_period_end',
          render: (v) => v ? new Date(v).toLocaleDateString() : '—',
          width: 120,
        },
      ]}
    />
  </Card>
);

// ── Page root ───────────────────────────────────────────────────────────
const BusinessOps: React.FC = () => {
  const overview = useQuery({ queryKey: ['ops', 'overview'], queryFn: opsApi.overview, refetchInterval: REFETCH });
  const customers = useQuery({ queryKey: ['ops', 'customers'], queryFn: opsApi.customers });
  const funnel = useQuery({ queryKey: ['ops', 'funnel'], queryFn: () => opsApi.funnel(30) });
  const pool = useQuery({ queryKey: ['ops', 'pool'], queryFn: opsApi.pool, refetchInterval: REFETCH });
  const llm = useQuery({ queryKey: ['ops', 'llm'], queryFn: () => opsApi.llmCost(14) });
  const handover = useQuery({ queryKey: ['ops', 'handover'], queryFn: () => opsApi.handover(30) });

  return (
    <div>
      <Title level={3} style={{ marginBottom: 4 }}>Business Operations</Title>
      <Text type="secondary">SaaS-wide operational view. Refreshes every 30s.</Text>

      <div style={{ marginTop: 24 }}>
        {overview.isLoading ? <Spin /> :
          overview.data && <KPIRow data={overview.data} />}
      </div>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={12}>
          {funnel.data && <FunnelChart data={funnel.data} />}
        </Col>
        <Col xs={24} md={12}>
          {handover.data && <HandoverPanel data={handover.data} />}
        </Col>
      </Row>

      <Row gutter={[16, 16]} style={{ marginTop: 16 }}>
        <Col xs={24} md={14}>
          {pool.data && <PoolPanel data={pool.data} />}
        </Col>
        <Col xs={24} md={10}>
          {llm.data && <LLMCostPanel data={llm.data} />}
        </Col>
      </Row>

      <div style={{ marginTop: 16 }}>
        {customers.data && <CustomerTable data={customers.data} />}
      </div>
    </div>
  );
};

export default BusinessOps;
