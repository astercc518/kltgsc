import React, { useState } from 'react';
import {
  Card, Row, Col, Button, Typography, Tag, Space, Alert, Modal,
  Table, Statistic, message, Tooltip, Divider, Radio,
} from 'antd';
import { CheckCircleOutlined, CopyOutlined, CrownOutlined, ClockCircleOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { billingApi, Invoice } from '../api';

const { Title, Text, Paragraph } = Typography;

const PLANS = [
  {
    code: 'starter', name: 'Starter', price: 199, color: '#0066FF',
    accounts: 3, groups: 500, tokens: '2M', seats: 1, sla: '24h',
    description: 'Individuals & small teams getting started with TG lead-gen.',
  },
  {
    code: 'growth', name: 'Growth', price: 299, color: '#22C55E', popular: true,
    accounts: 5, groups: 1000, tokens: '5M', seats: 3, sla: '12h',
    description: 'Mid-size export businesses scaling lead generation.',
  },
  {
    code: 'pro', name: 'Pro', price: 599, color: '#FFB020',
    accounts: 10, groups: 3000, tokens: '15M', seats: 10, sla: '4h',
    description: 'Crypto projects, large export operations, MCN.',
  },
];

const NETWORKS = [
  { value: 'TRC20', label: 'USDT-TRC20 (low fee, recommended)' },
  { value: 'ERC20', label: 'USDT-ERC20' },
  { value: 'BEP20', label: 'USDT-BEP20' },
];

const STATUS_COLOR: Record<string, string> = {
  pending: 'orange', paid: 'green', expired: 'default', refunded: 'purple',
};

const InvoiceModal: React.FC<{ invoice: Invoice | null; onClose: () => void }> = ({ invoice, onClose }) => {
  const qc = useQueryClient();
  if (!invoice) return null;

  // Auto-poll this invoice's status every 5s while modal is open
  useQuery({
    queryKey: ['portal', 'invoice', invoice.id],
    queryFn: () => billingApi.getInvoice(invoice.id),
    refetchInterval: 5000,
    enabled: invoice.status === 'pending',
    refetchOnWindowFocus: false,
    onSuccess: (latest: Invoice) => {
      if (latest.status === 'paid') {
        qc.invalidateQueries({ queryKey: ['portal'] });
        message.success(`Payment confirmed! Your ${latest.plan.toUpperCase()} plan is now active.`);
        onClose();
      }
    },
  } as any);

  const copy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    message.success(`${label} copied`);
  };

  return (
    <Modal
      open={true}
      onCancel={onClose}
      footer={<Button onClick={onClose}>Close</Button>}
      title={`Invoice #${invoice.id} · ${invoice.description}`}
      width={560}
    >
      <Alert
        type={invoice.status === 'paid' ? 'success' : 'info'}
        showIcon
        style={{ marginBottom: 16 }}
        message={
          invoice.status === 'paid'
            ? 'Payment received — plan activated'
            : `Send the exact amount below. Ops will confirm within minutes.`
        }
      />

      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Statistic
            title="Amount to send"
            value={invoice.amount_crypto}
            precision={2}
            suffix={invoice.currency}
            valueStyle={{ color: '#0066FF', fontWeight: 700 }}
          />
        </Col>
        <Col span={12}>
          <Statistic title="Network" value={invoice.network} />
        </Col>
      </Row>

      <Divider />

      <Text strong>Recipient Address:</Text>
      <div style={{
        background: '#f8fafc',
        padding: 12,
        borderRadius: 6,
        marginTop: 8,
        fontFamily: 'monospace',
        wordBreak: 'break-all',
        display: 'flex',
        alignItems: 'center',
        gap: 8,
      }}>
        <span style={{ flex: 1 }}>{invoice.payment_address}</span>
        <Tooltip title="Copy address">
          <Button icon={<CopyOutlined />} size="small" onClick={() => copy(invoice.payment_address, 'Address')} />
        </Tooltip>
      </div>

      <Paragraph type="warning" style={{ marginTop: 16 }}>
        <strong>Important:</strong> Send <strong>exactly {invoice.amount_crypto} {invoice.currency}</strong> —
        the fractional suffix is how we match your transfer to this order.
        Expires at {new Date(invoice.expires_at).toLocaleString()}.
      </Paragraph>

      <Tag color={STATUS_COLOR[invoice.status]} style={{ marginTop: 8 }}>
        <ClockCircleOutlined /> Status: {invoice.status.toUpperCase()}
      </Tag>
    </Modal>
  );
};

const PortalBilling: React.FC = () => {
  const [network, setNetwork] = useState('TRC20');
  const [activeInvoice, setActiveInvoice] = useState<Invoice | null>(null);

  const { data: invoices = [] } = useQuery({
    queryKey: ['portal', 'invoices'],
    queryFn: billingApi.listInvoices,
  });

  const subscribe = useMutation({
    mutationFn: (plan: string) => billingApi.subscribe(plan, network),
    onSuccess: (invoice) => setActiveInvoice(invoice),
    onError: (err: any) => {
      message.error(err?.response?.data?.detail || 'Failed to create invoice');
    },
  });

  return (
    <div>
      <Title level={3}>Subscription Plans</Title>
      <Paragraph type="secondary">
        Each plan gives you ready-to-use TG accounts, AI persona, industry KB,
        and access to thousands of target groups. Pay monthly in USDT.
      </Paragraph>

      <div style={{ margin: '16px 0' }}>
        <Text strong style={{ marginRight: 12 }}>Payment Network:</Text>
        <Radio.Group value={network} onChange={(e) => setNetwork(e.target.value)}>
          {NETWORKS.map(n => <Radio.Button key={n.value} value={n.value}>{n.label}</Radio.Button>)}
        </Radio.Group>
      </div>

      <Row gutter={[16, 16]} style={{ marginTop: 24 }}>
        {PLANS.map(p => (
          <Col xs={24} md={8} key={p.code}>
            <Card
              hoverable
              style={{
                borderTop: `4px solid ${p.color}`,
                position: 'relative',
              }}
              title={
                <Space>
                  <CrownOutlined style={{ color: p.color }} />
                  <span style={{ fontSize: 18, fontWeight: 700 }}>{p.name}</span>
                  {p.popular && <Tag color="green">Popular</Tag>}
                </Space>
              }
            >
              <div style={{ fontSize: 36, fontWeight: 800, color: p.color }}>
                ${p.price}<Text type="secondary" style={{ fontSize: 14, fontWeight: 400 }}>/mo</Text>
              </div>
              <Paragraph type="secondary" style={{ minHeight: 44 }}>{p.description}</Paragraph>
              <ul style={{ listStyle: 'none', padding: 0, margin: '12px 0' }}>
                <li><CheckCircleOutlined style={{ color: p.color }} /> {p.accounts} TG accounts (industry-customized)</li>
                <li><CheckCircleOutlined style={{ color: p.color }} /> {p.groups.toLocaleString()} AI target groups</li>
                <li><CheckCircleOutlined style={{ color: p.color }} /> {p.tokens} AI tokens / month</li>
                <li><CheckCircleOutlined style={{ color: p.color }} /> {p.seats} sales workbench seat{p.seats > 1 ? 's' : ''}</li>
                <li><CheckCircleOutlined style={{ color: p.color }} /> Replacement SLA: {p.sla}</li>
              </ul>
              <Button
                type="primary"
                block
                size="large"
                loading={subscribe.isPending && subscribe.variables === p.code}
                onClick={() => subscribe.mutate(p.code)}
                style={{ background: p.color, borderColor: p.color }}
              >
                Subscribe
              </Button>
            </Card>
          </Col>
        ))}
      </Row>

      <Title level={4} style={{ marginTop: 32 }}>Invoice History</Title>
      <Table
        dataSource={invoices}
        rowKey="id"
        size="small"
        columns={[
          { title: '#', dataIndex: 'id', width: 60 },
          { title: 'Plan', dataIndex: 'plan', render: (v) => v?.toUpperCase() },
          { title: 'Amount', render: (_, r) => `${r.amount_crypto} ${r.currency}` },
          { title: 'Network', dataIndex: 'network' },
          { title: 'Status', dataIndex: 'status', render: (s) => <Tag color={STATUS_COLOR[s]}>{s}</Tag> },
          {
            title: 'Created',
            dataIndex: 'created_at',
            render: (v) => new Date(v).toLocaleString(),
          },
          {
            title: '',
            render: (_, r) => (
              <Button size="small" onClick={() => setActiveInvoice(r)}>View</Button>
            ),
          },
        ]}
        pagination={{ pageSize: 10 }}
      />

      <InvoiceModal invoice={activeInvoice} onClose={() => setActiveInvoice(null)} />
    </div>
  );
};

export default PortalBilling;
