import React, { useState } from 'react';
import {
  Card, Row, Col, Button, Typography, Tag, Space, Alert, Modal,
  Table, Statistic, message, Tooltip, Divider, Radio, Input,
  Empty, DatePicker,
} from 'antd';
import {
  CopyOutlined, WalletOutlined, GiftOutlined,
  ArrowUpOutlined, ArrowDownOutlined, DownloadOutlined, BarChartOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import {
  Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer,
  Tooltip as ReTooltip, XAxis, YAxis,
} from 'recharts';
import dayjs from 'dayjs';
import { walletApi, TopupResponse, WalletTransaction } from '../api';

const { Title, Text, Paragraph } = Typography;

const TOPUP_TIERS = [
  { amount: 100, bonus_pct: 0, label: 'Trial' },
  { amount: 500, bonus_pct: 2, label: 'Starter' },
  { amount: 1000, bonus_pct: 5, label: 'Growth', popular: true },
  { amount: 5000, bonus_pct: 10, label: 'Pro' },
];

const NETWORKS = [
  { value: 'TRC20', label: 'USDT-TRC20 (low fee, recommended)' },
  { value: 'ERC20', label: 'USDT-ERC20' },
  { value: 'BEP20', label: 'USDT-BEP20' },
];

const TXN_COLOR: Record<string, string> = {
  topup: 'green', charge: 'orange', refund: 'blue', adjust: 'purple',
};

const formatUsd = (cents: number) => `$${(cents / 100).toFixed(2)}`;

const TopupModal: React.FC<{ topup: TopupResponse | null; onClose: () => void }> = ({ topup, onClose }) => {
  const qc = useQueryClient();
  if (!topup) return null;

  const copy = (text: string, label: string) => {
    navigator.clipboard.writeText(text);
    message.success(`${label} copied`);
  };

  return (
    <Modal
      open={true}
      onCancel={() => { qc.invalidateQueries({ queryKey: ['portal', 'wallet'] }); onClose(); }}
      footer={
        <Button onClick={() => { qc.invalidateQueries({ queryKey: ['portal', 'wallet'] }); onClose(); }}>
          Close (auto-credits once confirmed)
        </Button>
      }
      title={`Topup Invoice #${topup.invoice_id}`}
      width={560}
    >
      <Alert
        type="info" showIcon style={{ marginBottom: 16 }}
        message="Send the exact amount below to credit your wallet"
        description="Wallet auto-credits within minutes of on-chain confirmation."
      />

      <Row gutter={[16, 16]}>
        <Col span={12}>
          <Statistic
            title="Send"
            value={topup.amount_crypto}
            precision={2}
            suffix={topup.currency}
            valueStyle={{ color: '#0066FF', fontWeight: 700 }}
          />
        </Col>
        <Col span={12}>
          <Statistic title="Network" value={topup.network} />
        </Col>
      </Row>

      {topup.bonus_pct > 0 && (
        <Alert
          type="success" showIcon icon={<GiftOutlined />}
          style={{ marginTop: 16 }}
          message={`Bonus +${topup.bonus_pct}%`}
          description={`You'll receive ${formatUsd(topup.final_credit_cents)} total (${formatUsd(topup.bonus_cents)} bonus).`}
        />
      )}

      <Divider />

      <Text strong>Recipient Address:</Text>
      <div style={{
        background: '#f8fafc', padding: 12, borderRadius: 6, marginTop: 8,
        fontFamily: 'monospace', wordBreak: 'break-all',
        display: 'flex', alignItems: 'center', gap: 8,
      }}>
        <span style={{ flex: 1 }}>{topup.payment_address}</span>
        <Tooltip title="Copy address">
          <Button icon={<CopyOutlined />} size="small"
                  onClick={() => copy(topup.payment_address, 'Address')} />
        </Tooltip>
      </div>

      <Paragraph type="warning" style={{ marginTop: 16 }}>
        <strong>Important:</strong> Send <strong>exactly {topup.amount_crypto} {topup.currency}</strong> —
        the fractional suffix is how we match your transfer to this order.
        Expires at {new Date(topup.expires_at).toLocaleString()}.
      </Paragraph>
    </Modal>
  );
};

// ─── Monthly Report Card (S1.3) ─────────────────────────────────────────

const SOURCE_LABEL: Record<string, string> = {
  scrape: '群采集',
  bulk_send: '群发',
  invite: '群拉',
  ai_marketing: 'AI 营销助手',
  other_feature: '其他付费功能',
  other: '其他',
};

const MonthlyReportCard: React.FC = () => {
  const [month, setMonth] = useState<dayjs.Dayjs>(dayjs());
  const monthStr = month.format('YYYY-MM');

  const reportQuery = useQuery({
    queryKey: ['portal', 'wallet', 'report', monthStr],
    queryFn: () => walletApi.report(monthStr),
  });

  const report = reportQuery.data;
  const sourceData = report
    ? Object.entries(report.by_source)
        .filter(([, c]) => c > 0)
        .map(([k, c]) => ({
          source: SOURCE_LABEL[k] || k,
          key: k,
          amount: c / 100,
        }))
    : [];

  const handleDownloadCsv = () => {
    // Same-origin /api/v1/customer/wallet/report.csv carries the bearer
    // header via fetch, then trigger a Blob download.
    const url = walletApi.reportCsvUrl(monthStr);
    const token = localStorage.getItem('tg1_customer_token') || '';
    fetch(url, { headers: { Authorization: `Bearer ${token}` } })
      .then(r => {
        if (!r.ok) throw new Error(`HTTP ${r.status}`);
        return r.blob();
      })
      .then(blob => {
        const link = document.createElement('a');
        link.href = URL.createObjectURL(blob);
        link.download = `wallet-${monthStr}.csv`;
        document.body.appendChild(link);
        link.click();
        link.remove();
      })
      .catch(e => message.error(`Download failed: ${e.message}`));
  };

  return (
    <Card
      title={
        <Space>
          <BarChartOutlined />
          <span>月度报表</span>
        </Space>
      }
      extra={
        <Space>
          <DatePicker
            picker="month"
            value={month}
            onChange={d => d && setMonth(d)}
            allowClear={false}
          />
          <Button icon={<DownloadOutlined />} onClick={handleDownloadCsv} disabled={!report}>
            导出 CSV
          </Button>
        </Space>
      }
      loading={reportQuery.isLoading}
      style={{ marginBottom: 24 }}
    >
      {report && (
        <>
          <Row gutter={16} style={{ marginBottom: 16 }}>
            <Col span={6}>
              <Statistic title="本月充值" value={report.topup_total_cents / 100} precision={2} prefix="$" valueStyle={{ color: '#22C55E' }} />
            </Col>
            <Col span={6}>
              <Statistic title="本月消费" value={report.charge_total_cents / 100} precision={2} prefix="$" valueStyle={{ color: '#EF4444' }} />
            </Col>
            <Col span={6}>
              <Statistic
                title="净现金流"
                value={(report.topup_total_cents - report.charge_total_cents) / 100}
                precision={2} prefix="$"
              />
            </Col>
            <Col span={6}>
              <Statistic title="交易笔数" value={report.txn_count} />
            </Col>
          </Row>

          {sourceData.length === 0 ? (
            <Empty description="本月暂无消费" />
          ) : (
            <div style={{ width: '100%', height: 260 }}>
              <ResponsiveContainer>
                <BarChart data={sourceData}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="source" />
                  <YAxis tickFormatter={(v) => `$${v}`} />
                  <ReTooltip formatter={(v: number) => `$${v.toFixed(2)}`} />
                  <Legend />
                  <Bar dataKey="amount" name="消费 (USD)" fill="#0066FF" />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </>
      )}
    </Card>
  );
};


const PortalWallet: React.FC = () => {
  const [selectedTier, setSelectedTier] = useState<number>(500);
  const [customAmount, setCustomAmount] = useState<string>('');
  const [network, setNetwork] = useState<string>('TRC20');
  const [activeTopup, setActiveTopup] = useState<TopupResponse | null>(null);

  const walletQuery = useQuery({
    queryKey: ['portal', 'wallet'],
    queryFn: walletApi.get,
    refetchInterval: 15000,
  });

  const txnsQuery = useQuery({
    queryKey: ['portal', 'wallet', 'transactions'],
    queryFn: () => walletApi.transactions({ limit: 100 }),
    refetchInterval: 15000,
  });

  const topupMut = useMutation({
    mutationFn: ({ amount_usd, network }: { amount_usd: number; network: string }) =>
      walletApi.topup(amount_usd, network),
    onSuccess: (data) => {
      setActiveTopup(data);
      message.success('Topup invoice created');
    },
    onError: (e: any) => {
      message.error(e.response?.data?.message || e.response?.data?.detail || 'Topup failed');
    },
  });

  const handleTopup = () => {
    const amount = customAmount ? parseFloat(customAmount) : selectedTier;
    if (!amount || amount < 100) {
      message.error('Minimum topup is $100');
      return;
    }
    topupMut.mutate({ amount_usd: amount, network });
  };

  const wallet = walletQuery.data;
  const txns = txnsQuery.data || [];

  const txnColumns = [
    {
      title: 'Time', dataIndex: 'created_at', key: 'created_at',
      render: (v: string) => new Date(v).toLocaleString(),
      width: 160,
    },
    {
      title: 'Type', dataIndex: 'type', key: 'type',
      render: (t: string) => <Tag color={TXN_COLOR[t]}>{t.toUpperCase()}</Tag>,
      width: 100,
    },
    {
      title: 'Amount', dataIndex: 'amount_cents', key: 'amount_cents',
      render: (c: number) => (
        <Text strong style={{ color: c > 0 ? '#22C55E' : '#EF4444' }}>
          {c > 0 ? <ArrowUpOutlined /> : <ArrowDownOutlined />}
          {' '}{formatUsd(Math.abs(c))}
        </Text>
      ),
      width: 120,
    },
    {
      title: 'Balance After', dataIndex: 'balance_after_cents', key: 'balance_after_cents',
      render: (c: number) => formatUsd(c),
      width: 130,
    },
    { title: 'Description', dataIndex: 'description', key: 'description' },
    {
      title: 'Reference', key: 'ref',
      render: (_: any, row: WalletTransaction) => {
        if (row.invoice_id) return <Tag>Invoice #{row.invoice_id}</Tag>;
        if (row.bulk_batch_id) return <Tag color="blue">Batch #{row.bulk_batch_id}</Tag>;
        return <Text type="secondary">—</Text>;
      },
      width: 120,
    },
  ];

  return (
    <div>
      <Title level={2}>
        <WalletOutlined /> Wallet
      </Title>
      <Paragraph type="secondary">
        Prepaid balance for TG Bulk Send (per-message billing).
        Topup with USDT, auto-credits after on-chain confirmation.
      </Paragraph>

      {/* Balance card */}
      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={8}>
          <Card loading={walletQuery.isLoading}>
            <Statistic
              title="Current Balance"
              value={wallet ? wallet.balance_cents / 100 : 0}
              precision={2}
              prefix="$"
              valueStyle={{ color: '#0066FF', fontSize: 32, fontWeight: 700 }}
            />
            {wallet && wallet.balance_cents < 2000 && (
              <Alert
                type="warning" showIcon style={{ marginTop: 12 }}
                message="Balance low" description="Topup recommended to avoid task pauses."
              />
            )}
          </Card>
        </Col>
        <Col span={8}>
          <Card loading={walletQuery.isLoading}>
            <Statistic
              title="Total Topup"
              value={wallet ? wallet.total_topup_cents / 100 : 0}
              precision={2} prefix="$"
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card loading={walletQuery.isLoading}>
            <Statistic
              title="Total Spent"
              value={wallet ? wallet.total_spent_cents / 100 : 0}
              precision={2} prefix="$"
              valueStyle={{ color: '#EF4444' }}
            />
          </Card>
        </Col>
      </Row>

      {/* Topup section */}
      <Card title="Topup Wallet" style={{ marginBottom: 24 }}>
        <Title level={5}>1. Choose amount</Title>
        <Row gutter={16} style={{ marginBottom: 16 }}>
          {TOPUP_TIERS.map(tier => (
            <Col span={6} key={tier.amount}>
              <Card
                hoverable
                onClick={() => { setSelectedTier(tier.amount); setCustomAmount(''); }}
                style={{
                  cursor: 'pointer',
                  borderColor: selectedTier === tier.amount && !customAmount ? '#0066FF' : undefined,
                  borderWidth: selectedTier === tier.amount && !customAmount ? 2 : 1,
                  position: 'relative',
                }}
              >
                {tier.popular && (
                  <Tag color="green" style={{ position: 'absolute', top: 8, right: 8 }}>
                    Popular
                  </Tag>
                )}
                <div style={{ textAlign: 'center' }}>
                  <Title level={4} style={{ margin: 0 }}>${tier.amount}</Title>
                  <Text type="secondary">{tier.label}</Text>
                  {tier.bonus_pct > 0 && (
                    <div style={{ marginTop: 8 }}>
                      <Tag color="gold" icon={<GiftOutlined />}>
                        +{tier.bonus_pct}% bonus
                      </Tag>
                      <div style={{ fontSize: 12, color: '#22C55E', marginTop: 4 }}>
                        Receive ${tier.amount * (1 + tier.bonus_pct / 100)}
                      </div>
                    </div>
                  )}
                </div>
              </Card>
            </Col>
          ))}
        </Row>

        <Text type="secondary">Or enter custom amount ($100-50,000):</Text>
        <Input
          type="number" min={100} max={50000} placeholder="e.g. 250"
          value={customAmount} onChange={e => setCustomAmount(e.target.value)}
          prefix="$" style={{ maxWidth: 240, marginTop: 8 }}
        />

        <Divider />

        <Title level={5}>2. Choose network</Title>
        <Radio.Group value={network} onChange={e => setNetwork(e.target.value)}>
          <Space direction="vertical">
            {NETWORKS.map(n => (
              <Radio key={n.value} value={n.value}>{n.label}</Radio>
            ))}
          </Space>
        </Radio.Group>

        <Divider />

        <Button
          type="primary" size="large"
          loading={topupMut.isPending}
          onClick={handleTopup}
          disabled={!selectedTier && !customAmount}
        >
          Create Topup Invoice
        </Button>
      </Card>

      {/* Monthly report */}
      <MonthlyReportCard />

      {/* Transactions */}
      <Card title="Transaction History" loading={txnsQuery.isLoading}>
        {txns.length === 0 ? (
          <Empty description="No transactions yet" />
        ) : (
          <Table
            dataSource={txns} columns={txnColumns} rowKey="id"
            pagination={{ pageSize: 20, showSizeChanger: false }}
            size="middle"
          />
        )}
      </Card>

      <TopupModal topup={activeTopup} onClose={() => setActiveTopup(null)} />
    </div>
  );
};

export default PortalWallet;
