import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Descriptions, Table, Tag, Space, Button, Modal, Form, Select, Input, InputNumber, Statistic, Typography, message } from 'antd';

const { Text } = Typography;
import dayjs from 'dayjs';
import {
  getCustomerById,
  getCustomerWallet,
  creditWallet,
  listInvoices,
  quickProvision,
  AdminApiError,
  type Plan,
  type AdminInvoice,
} from '../../../services/adminCustomers';

const PLAN_LABELS: Record<Plan, string> = {
  starter: 'Starter ($199)',
  growth: 'Growth ($299)',
  pro: 'Pro ($599)',
};

const BillingTab: React.FC<{ customerId: number }> = ({ customerId }) => {
  const queryClient = useQueryClient();
  const [renewModal, setRenewModal] = React.useState(false);
  const [renewForm] = Form.useForm<{ plan: Plan; note?: string }>();
  const [topupModal, setTopupModal] = React.useState(false);
  const [topupForm] = Form.useForm<{ amount_usd: number; note?: string }>();

  const { data: customer } = useQuery({
    queryKey: ['admin-customer', customerId],
    queryFn: () => getCustomerById(customerId),
  });
  const { data: invoices } = useQuery({
    queryKey: ['admin-customer', customerId, 'invoices'],
    queryFn: () => listInvoices(customerId),
  });
  // Wallet endpoint may be absent on older backends — degrade gracefully (no retry,
  // hide the wallet/top-up UI) instead of surfacing a 404.
  const { data: wallet, isError: walletUnavailable } = useQuery({
    queryKey: ['admin-customer', customerId, 'wallet'],
    queryFn: () => getCustomerWallet(customerId),
    retry: false,
  });

  const topupMutation = useMutation({
    mutationFn: (vals: { amount_usd: number; note?: string }) =>
      creditWallet(customerId, Math.round(vals.amount_usd * 100), vals.note),
    onSuccess: (res) => {
      message.success(`充值成功，当前余额 $${(res.wallet_balance_cents / 100).toFixed(2)}`);
      setTopupModal(false);
      topupForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['admin-customer', customerId, 'wallet'] });
    },
    onError: (err: unknown) => {
      message.error(err instanceof AdminApiError ? err.message : '充值失败');
    },
  });

  const renewMutation = useMutation({
    mutationFn: async (vals: { plan: Plan; note?: string }) =>
      quickProvision({
        customer_id: customerId,
        plan: vals.plan,
        note: vals.note ?? `admin renew ${dayjs().format('YYYY-MM-DD')}`,
      }),
    onSuccess: () => {
      message.success('续期成功');
      setRenewModal(false);
      renewForm.resetFields();
      queryClient.invalidateQueries({ queryKey: ['admin-customer', customerId] });
      queryClient.invalidateQueries({ queryKey: ['admin-customer', customerId, 'invoices'] });
    },
    onError: (err: unknown) => {
      message.error(err instanceof AdminApiError ? err.message : '续期失败');
    },
  });

  const invoiceColumns = [
    { title: 'Invoice ID', dataIndex: 'id', key: 'id' },
    {
      title: '套餐',
      dataIndex: 'plan',
      key: 'plan',
    },
    {
      title: '金额',
      dataIndex: 'amount_usd',
      key: 'amount',
      render: (usd: number) => `$${usd.toFixed(2)}`,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: string) => <Tag color={s === 'paid' ? 'green' : 'default'}>{s}</Tag>,
    },
    {
      title: 'Tx Hash',
      dataIndex: 'tx_hash',
      key: 'tx_hash',
      render: (h: string | null) => h ?? '—',
    },
    {
      title: '说明',
      dataIndex: 'description',
      key: 'description',
      render: (v: string) => v || '—',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (t: string) => dayjs(t).format('YYYY-MM-DD HH:mm'),
    },
  ];

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card
        size="small"
        title="当前订阅"
        extra={
          <Button
            type="primary"
            onClick={() => {
              renewForm.setFieldsValue({ plan: customer?.plan ?? 'starter' });
              setRenewModal(true);
            }}
          >
            手动续期 / 切套餐
          </Button>
        }
      >
        <Descriptions size="small" column={3}>
          <Descriptions.Item label="套餐">
            {customer?.plan ? PLAN_LABELS[customer.plan] : '无'}
          </Descriptions.Item>
          <Descriptions.Item label="订阅状态">{customer?.subscription_status ?? '—'}</Descriptions.Item>
          <Descriptions.Item label="当前周期截至">
            {customer?.current_period_end
              ? dayjs(customer.current_period_end).format('YYYY-MM-DD')
              : '—'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {walletUnavailable ? (
        <Card size="small" title="钱包余额">
          <Text type="secondary">钱包 / 充值功能待发布（当前后端未提供该接口）。</Text>
        </Card>
      ) : (
      <Card
        size="small"
        title="钱包余额"
        extra={
          <Button type="primary" onClick={() => setTopupModal(true)}>
            钱包充值
          </Button>
        }
      >
        <Space size="large">
          <Statistic
            title="可用余额"
            value={(wallet?.balance_cents ?? 0) / 100}
            precision={2}
            prefix="$"
          />
          <Statistic
            title="累计充值"
            value={(wallet?.total_topup_cents ?? 0) / 100}
            precision={2}
            prefix="$"
          />
          <Statistic
            title="累计消费"
            value={(wallet?.total_spent_cents ?? 0) / 100}
            precision={2}
            prefix="$"
          />
        </Space>
      </Card>
      )}

      <Card size="small" title="账单历史">
        <Table<AdminInvoice>
          rowKey="id"
          dataSource={invoices ?? []}
          columns={invoiceColumns}
          pagination={{ pageSize: 10 }}
          size="small"
        />
      </Card>

      <Modal
        title="手动续期 / 切套餐"
        open={renewModal}
        onCancel={() => {
          renewForm.resetFields();
          setRenewModal(false);
        }}
        onOk={() => renewForm.submit()}
        confirmLoading={renewMutation.isPending}
      >
        <Form form={renewForm} layout="vertical" onFinish={(v) => renewMutation.mutate(v)}>
          <Form.Item label="套餐" name="plan" rules={[{ required: true }]}>
            <Select
              options={[
                { value: 'starter', label: PLAN_LABELS.starter },
                { value: 'growth', label: PLAN_LABELS.growth },
                { value: 'pro', label: PLAN_LABELS.pro },
              ]}
            />
          </Form.Item>
          <Form.Item label="备注" name="note">
            <Input placeholder="选填，将写入 invoice note" />
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="钱包充值"
        open={topupModal}
        onCancel={() => {
          topupForm.resetFields();
          setTopupModal(false);
        }}
        onOk={() => topupForm.submit()}
        confirmLoading={topupMutation.isPending}
      >
        <Form form={topupForm} layout="vertical" onFinish={(v) => topupMutation.mutate(v)}>
          <Form.Item
            label="充值金额 (USD)"
            name="amount_usd"
            rules={[{ required: true, type: 'number', min: 0.01, message: '请输入正数金额' }]}
          >
            <InputNumber min={0.01} step={10} precision={2} prefix="$" style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item label="备注" name="note">
            <Input placeholder="选填，将写入钱包流水说明" />
          </Form.Item>
        </Form>
      </Modal>
    </Space>
  );
};

export default BillingTab;
