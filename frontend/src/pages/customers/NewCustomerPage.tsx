import React, { useState } from 'react';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Card, Form, Input, InputNumber, Select, Radio, Button, Modal, message, Space, Typography } from 'antd';
import { ReloadOutlined, CopyOutlined } from '@ant-design/icons';
import {
  quickProvision,
  listCustomers,
  generateRandomPassword,
  AdminApiError,
  type Customer,
  type Plan,
} from '../../services/adminCustomers';

const { Text, Paragraph } = Typography;

const INDUSTRIES = ['crypto', 'ecommerce', 'b2b', 'gaming', 'mcn'];

interface FormValues {
  email: string;
  password: string;
  name?: string;
  industry: string;
  plan: Plan;
  wallet_credit_usd?: number;
  note?: string;
}

const PLANS: Array<{ value: Plan; label: string; desc: string }> = [
  { value: 'starter', label: 'Starter ($199)', desc: '3 账号 / 500 群 / 200 万 token' },
  { value: 'growth', label: 'Growth ($299)', desc: '5 账号 / 1000 群 / 500 万 token' },
  { value: 'pro', label: 'Pro ($599)', desc: '10 账号 / 3000 群 / 1500 万 token' },
];

const NewCustomerPage: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm<FormValues>();
  const [credentials, setCredentials] = useState<{ customer: Customer; password: string } | null>(null);
  const blurSeqRef = React.useRef(0);

  const mutation = useMutation({
    mutationFn: async (vals: FormValues) =>
      quickProvision({
        new_customer_email: vals.email,
        new_customer_password: vals.password,
        new_customer_name: vals.name,
        new_customer_industry: vals.industry,
        plan: vals.plan,
        wallet_credit_cents: vals.wallet_credit_usd
          ? Math.round(vals.wallet_credit_usd * 100)
          : undefined,
        note: vals.note,
      }),
    onSuccess: (customer, vars) => {
      setCredentials({ customer, password: vars.password });
    },
    onError: (err: unknown) => {
      if (err instanceof AdminApiError) {
        if (err.status === 409 || err.status === 400) {
          form.setFields([{ name: 'email', errors: [err.message] }]);
          return;
        }
        message.error(err.message);
      } else {
        message.error('网络错误，请重试');
      }
    },
  });

  const handleEmailBlur = async () => {
    const email = form.getFieldValue('email');
    if (!email) return;
    const mySeq = ++blurSeqRef.current;
    try {
      const all = await listCustomers({ limit: 500 });
      if (mySeq !== blurSeqRef.current) return;  // a newer blur has run; ignore this result
      const dup = all.find((c) => c.email.toLowerCase() === email.toLowerCase());
      if (dup) {
        form.setFields([
          {
            name: 'email',
            errors: [`邮箱已存在 (id=${dup.id})。请前往客户详情。`],
          },
        ]);
      }
    } catch {
      // non-blocking; submission will surface the real error
    }
  };

  const handleGeneratePassword = () => {
    form.setFieldValue('password', generateRandomPassword());
  };

  const portalUrl = `${window.location.origin}/portal/login`;

  const copy = async (s: string, label: string) => {
    try {
      await navigator.clipboard.writeText(s);
      message.success(`${label} 已复制`);
    } catch {
      message.error('复制失败');
    }
  };

  return (
    <Card title="客户运营 / 新建客户">
      <Form<FormValues>
        form={form}
        layout="vertical"
        onFinish={(vals) => mutation.mutate(vals)}
        initialValues={{ plan: 'starter' }}
        style={{ maxWidth: 640 }}
      >
        <Form.Item
          label="Email"
          name="email"
          rules={[
            { required: true, message: '请输入邮箱' },
            { type: 'email', message: '邮箱格式不正确' },
          ]}
        >
          <Input onBlur={handleEmailBlur} placeholder="customer@example.com" />
        </Form.Item>
        <Form.Item
          label="初始密码"
          name="password"
          rules={[
            { required: true, message: '请输入密码' },
            { min: 8, message: '至少 8 位' },
          ]}
          extra="此密码仅在创建完成时展示一次。"
        >
          <Input.Password
            placeholder="至少 8 位"
            addonAfter={
              <Button size="small" type="link" icon={<ReloadOutlined />} onClick={handleGeneratePassword}>
                生成 12 位随机密码
              </Button>
            }
          />
        </Form.Item>
        <Form.Item label="姓名" name="name">
          <Input placeholder="留空则使用邮箱前缀" />
        </Form.Item>
        <Form.Item label="行业" name="industry" rules={[{ required: true, message: '请选择行业' }]}>
          <Select placeholder="选择行业" options={INDUSTRIES.map((v) => ({ value: v, label: v }))} />
        </Form.Item>
        <Form.Item label="套餐" name="plan" rules={[{ required: true }]}>
          <Radio.Group>
            <Space direction="vertical">
              {PLANS.map((p) => (
                <Radio key={p.value} value={p.value}>
                  <strong>{p.label}</strong> — {p.desc}
                </Radio>
              ))}
            </Space>
          </Radio.Group>
        </Form.Item>
        <Form.Item
          label="初始充值 (USD)"
          name="wallet_credit_usd"
          extra="选填。开户时直接给钱包充值，群发/采集/拉群按量从余额扣费。"
        >
          <InputNumber min={0} step={50} precision={2} prefix="$" style={{ width: '100%' }} placeholder="留空则不充值" />
        </Form.Item>
        <Form.Item label="备注" name="note">
          <Input.TextArea rows={2} placeholder="线下付款/试用/内部 QA 等" maxLength={200} showCount />
        </Form.Item>
        <Form.Item>
          <Space>
            <Button type="primary" htmlType="submit" loading={mutation.isPending}>
              开户并激活
            </Button>
            <Button disabled={mutation.isPending} onClick={() => navigate('/customers')}>取消</Button>
          </Space>
        </Form.Item>
      </Form>

      <Modal
        title="✅ 客户已创建并激活"
        open={credentials !== null}
        closable={false}
        maskClosable={false}
        footer={
          <Space>
            <Button onClick={() => setCredentials(null)}>关闭</Button>
            <Button
              type="primary"
              onClick={() => credentials && navigate(`/customers/${credentials.customer.id}`)}
            >
              前往客户详情
            </Button>
          </Space>
        }
      >
        {credentials && (
          <Space direction="vertical" style={{ width: '100%' }}>
            <Paragraph>
              <Text strong>Email:</Text> {credentials.customer.email}{' '}
              <Button size="small" icon={<CopyOutlined />} onClick={() => copy(credentials.customer.email, 'Email')} />
            </Paragraph>
            <Paragraph>
              <Text strong>初始密码:</Text>{' '}
              <Text code copyable={{ text: credentials.password }}>{credentials.password}</Text>
            </Paragraph>
            <Paragraph>
              <Text strong>Portal:</Text>{' '}
              <Text code copyable={{ text: portalUrl }}>{portalUrl}</Text>
            </Paragraph>
            <Text type="warning">
              ⚠ 此密码仅在本窗口显示。关闭后无法再次查看，请立即通过其他途径转交客户。
            </Text>
          </Space>
        )}
      </Modal>
    </Card>
  );
};

export default NewCustomerPage;
