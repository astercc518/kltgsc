import React from 'react';
import {
  Card, Row, Col, Statistic, Button, Table, Tag, Modal, Form, InputNumber,
  Select, Typography, Empty, Alert, Space, message, Result,
} from 'antd';
import { PlusOutlined, ReloadOutlined, DollarOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { decodeJwtPayload, SalesWalletTxn, walletApi } from '../api';
import { useT } from '../i18n';

const { Title, Text } = Typography;

const fmtUsd = (cents: number) => `$${(cents/100).toFixed(2)}`;

const SalesWalletPage: React.FC = () => {
  const qc = useQueryClient();
  const t = useT();
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
      message.success(t('wallet.invoiceSuccess'));
      refetchWallet(); refetchTxns();
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || t('wallet.topupFailed')),
  });

  if (profile?.kind === 'platform') {
    return (
      <Result
        status="info"
        title={t('wallet.platformTitle')}
        subTitle={t('wallet.platformDesc')}
        extra={
          <Card style={{ maxWidth: 480, margin: '0 auto', textAlign: 'left' }}>
            <Statistic title={t('wallet.currentBalance')} value={wallet ? fmtUsd(wallet.balance_cents) : '—'} />
            <Statistic title={t('wallet.totalCredited')} value={wallet ? fmtUsd(wallet.total_topup_cents) : '—'} />
            <Statistic title={t('wallet.totalSpent')} value={wallet ? fmtUsd(wallet.total_spent_cents) : '—'} />
          </Card>
        }
      />
    );
  }

  return (
    <div>
      <Row justify="space-between" align="middle" style={{ marginBottom: 16 }}>
        <Col>
          <Title level={3} style={{ margin: 0 }}>{t('wallet.title')}</Title>
          <Text type="secondary">{t('wallet.subtitle')}</Text>
        </Col>
        <Col>
          <Space>
            <Button icon={<ReloadOutlined />} onClick={() => { refetchWallet(); refetchTxns(); }}>
              {t('common.refresh')}
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={() => setTopupOpen(true)}>
              {t('wallet.topup')}
            </Button>
          </Space>
        </Col>
      </Row>

      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card>
            <Statistic
              title={t('wallet.balance')}
              value={wallet ? fmtUsd(wallet.balance_cents) : '—'}
              valueStyle={{ color: (wallet?.balance_cents || 0) < 500 ? '#cf1322' : '#3f8600' }}
              prefix={<DollarOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title={t('wallet.totalCredited')} value={wallet ? fmtUsd(wallet.total_topup_cents) : '—'} />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title={t('wallet.totalSpent')} value={wallet ? fmtUsd(wallet.total_spent_cents) : '—'} />
          </Card>
        </Col>
      </Row>

      <Card title={t('wallet.txTable')}>
        <Table
          rowKey="id"
          dataSource={txns}
          locale={{ emptyText: <Empty description={t('wallet.txEmpty')} /> }}
          pagination={{ pageSize: 20 }}
          columns={[
            { title: t('wallet.col.type'), dataIndex: 'type',
              render: (typ: string) => <Tag color={typ === 'topup' ? 'green' : typ === 'charge' ? 'red' : 'default'}>{typ}</Tag> },
            { title: t('wallet.col.amount'), dataIndex: 'amount_cents',
              render: (c: number) => (
                <Text type={c > 0 ? 'success' : 'danger'}>
                  {c > 0 ? '+' : ''}{fmtUsd(c)}
                </Text>
              )},
            { title: t('wallet.col.balanceAfter'), dataIndex: 'balance_after_cents',
              render: fmtUsd },
            { title: t('wallet.col.desc'), dataIndex: 'description' },
            { title: t('wallet.col.lead'), dataIndex: 'lead_id', render: (n: number | null) => n ?? '—' },
            { title: t('wallet.col.when'), key: 'when',
              render: (_: any, r: SalesWalletTxn) => new Date(r.created_at).toLocaleString() },
          ]}
        />
      </Card>

      <Modal
        title={t('wallet.modal.title')}
        open={topupOpen}
        onCancel={() => { setTopupOpen(false); setTopupResp(null); form.resetFields(); }}
        onOk={async () => {
          try {
            const v = await form.validateFields();
            topupMut.mutate({ amount: v.amount, network: v.network });
          } catch {}
        }}
        confirmLoading={topupMut.isPending}
        okText={t('wallet.modal.create')}
      >
        <Form form={form} layout="vertical" initialValues={{ amount: 50, network: 'TRC20' }}>
          <Form.Item name="amount" label={t('wallet.modal.amount')} rules={[{ required: true }]}>
            <InputNumber min={20} max={5000} step={10} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="network" label={t('wallet.modal.network')} rules={[{ required: true }]}>
            <Select options={['TRC20', 'ERC20', 'BEP20'].map(n => ({ value: n, label: n }))} />
          </Form.Item>
        </Form>
        {topupResp && (
          <Alert
            type="success" showIcon style={{ marginTop: 16 }}
            message={<>{t('wallet.modal.invoiceCreated')}{topupResp.invoice.id}{t('wallet.modal.invoiceCreated2')}</>}
            description={
              <div>
                {t('wallet.modal.sendUsdt')} <b>{topupResp.invoice.amount_crypto} USDT</b>{' '}
                {t('wallet.modal.on')} <b>{topupResp.invoice.network}</b> {t('wallet.modal.to')}
                <pre style={{ background: '#f5f5f5', padding: 8, marginTop: 8 }}>
                  {topupResp.invoice.payment_address}
                </pre>
                {topupResp.bonus_cents > 0 && (
                  <Text type="secondary">
                    +{fmtUsd(topupResp.bonus_cents)} {t('wallet.modal.bonus')} ({topupResp.bonus_pct}%).
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
