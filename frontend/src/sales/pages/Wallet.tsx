import React from 'react';
import {
  Card, Row, Col, Statistic, Button, Table, Tag, Modal, Form, InputNumber,
  Select, Typography, Empty, Alert, Space, message, Result,
} from 'antd';
import { PlusOutlined, ReloadOutlined, DollarOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { decodeJwtPayload, SalesWalletTxn, walletApi } from '../api';

const { Title, Text } = Typography;

const fmtUsd = (cents: number) => `$${(cents/100).toFixed(2)}`;

const SalesWalletPage: React.FC = () => {
  const qc = useQueryClient();
  const profile = decodeJwtPayload();
  const [topupOpen, setTopupOpen] = React.useState(false);
  const [topupResp, setTopupResp] = React.useState<any>(null);
  const [form] = Form.useForm();

  const { data: wallet, refetch: refetchWallet } = useQuery({
    queryKey: ['sales', 'wallet'],
    queryFn: () => walletApi.get(),
  });
  const { data: txns = [], refetch: refetchTxns } = useQuery({
    queryKey: ['sales', 'wallet', 'txns'],
    queryFn: () => walletApi.transactions({ limit: 100 }),
  });

  const topupMut = useMutation({
    mutationFn: (data: { amount: number; network: string }) =>
      walletApi.topup(data.amount, data.network),
    onSuccess: (data) => {
      setTopupResp(data);
      message.success('Invoice created — send USDT to complete topup');
      refetchWallet(); refetchTxns();
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Topup failed'),
  });

  if (profile?.kind === 'platform') {
    return (
      <Result
        status="info"
        title="Platform sales wallet"
        subTitle="Self-topup isn't enabled for platform sales accounts. Ask an admin to credit your viewing budget."
        extra={
          <Card style={{ maxWidth: 480, margin: '0 auto', textAlign: 'left' }}>
            <Statistic title="Current balance" value={wallet ? fmtUsd(wallet.balance_cents) : '—'} />
            <Statistic title="Total credited" value={wallet ? fmtUsd(wallet.total_topup_cents) : '—'} />
            <Statistic title="Total spent" value={wallet ? fmtUsd(wallet.total_spent_cents) : '—'} />
          </Card>
        }
      />
    );
  }

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>My Wallet</Title>
          <Text type="secondary">
            Lead views are billed from this wallet (default $0.50/view, $0 for same-day re-views).
          </Text>
        </Col>
        <Col>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => { refetchWallet(); refetchTxns(); }}>
              Refresh
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setTopupOpen(true)}>
              Topup
            </Button>
          </Space>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card>
            <Statistic
              title="Balance"
              value={wallet ? fmtUsd(wallet.balance_cents) : '—'}
              valueStyle={{ color: (wallet?.balance_cents || 0) < 500 ? '#cf1322' : '#3f8600' }}
              prefix={<DollarOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="Total topped up" value={wallet ? fmtUsd(wallet.total_topup_cents) : '—'} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="Total spent" value={wallet ? fmtUsd(wallet.total_spent_cents) : '—'} />
          </Card>
        </Col>
      </Row>

      <Card title="Transactions">
        <Table
          rowKey="id"
          dataSource={txns}
          locale={{ emptyText: <Empty description="No transactions yet" /> }}
          pagination={{ pageSize: 20 }}
          columns={[
            { title: 'Type', dataIndex: 'type',
              render: (t: string) => <Tag color={t === 'topup' ? 'green' : t === 'charge' ? 'red' : 'default'}>{t}</Tag> },
            { title: 'Amount', dataIndex: 'amount_cents',
              render: (c: number) => (
                <Text type={c > 0 ? 'success' : 'danger'}>
                  {c > 0 ? '+' : ''}{fmtUsd(c)}
                </Text>
              )},
            { title: 'Balance after', dataIndex: 'balance_after_cents',
              render: fmtUsd },
            { title: 'Description', dataIndex: 'description' },
            { title: 'Lead', dataIndex: 'lead_id', render: (n: number | null) => n ?? '—' },
            { title: 'When', key: 'when',
              render: (_: any, r: SalesWalletTxn) => new Date(r.created_at).toLocaleString() },
          ]}
        />
      </Card>

      <Modal
        title="Topup sales wallet"
        open={topupOpen}
        onCancel={() => { setTopupOpen(false); setTopupResp(null); form.resetFields(); }}
        onOk={async () => {
          try {
            const v = await form.validateFields();
            topupMut.mutate({ amount: v.amount, network: v.network });
          } catch {}
        }}
        confirmLoading={topupMut.isPending}
        okText="Create invoice"
      >
        <Form form={form} layout="vertical" initialValues={{ amount: 50, network: 'TRC20' }}>
          <Form.Item name="amount" label="Amount (USD)" rules={[{ required: true }]}>
            <InputNumber min={20} max={5000} step={10} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="network" label="USDT network" rules={[{ required: true }]}>
            <Select options={['TRC20', 'ERC20', 'BEP20'].map(n => ({ value: n, label: n }))} />
          </Form.Item>
        </Form>
        {topupResp && (
          <Alert
            type="success" showIcon style={{ marginTop: 16 }}
            message={<>Invoice #{topupResp.invoice.id} created</>}
            description={
              <div>
                Send <b>{topupResp.invoice.amount_crypto} USDT</b> on{' '}
                <b>{topupResp.invoice.network}</b> to:
                <pre style={{ background: '#f5f5f5', padding: 8, marginTop: 8 }}>
                  {topupResp.invoice.payment_address}
                </pre>
                {topupResp.bonus_cents > 0 && (
                  <Text type="secondary">
                    +{fmtUsd(topupResp.bonus_cents)} bonus ({topupResp.bonus_pct}%) on confirmation.
                  </Text>
                )}
              </div>
            }
          />
        )}
      </Modal>
    </div>
  );
};

export default SalesWalletPage;
