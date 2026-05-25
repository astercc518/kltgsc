import React from 'react';
import { Form, Input, Button, Card, Typography, message, Select, Alert } from 'antd';
import { LockOutlined, MailOutlined, UserOutlined, ShopOutlined, GiftOutlined } from '@ant-design/icons';
import { Link, useNavigate, useSearchParams } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { authApi } from '../api';
import { setCustomerToken } from '../auth';

const { Title, Text } = Typography;

const INDUSTRIES = [
  { value: 'crypto', label: 'Crypto / Web3' },
  { value: 'ecommerce', label: 'Cross-border E-commerce' },
  { value: 'b2b', label: 'B2B Export' },
  { value: 'gaming', label: 'Gaming / SaaS' },
  { value: 'mcn', label: 'MCN / KOL' },
  { value: 'other', label: 'Other' },
];

const PortalRegister: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();
  const [searchParams] = useSearchParams();

  // Landing-driven trial credit. If the URL carries ?ref=landing&trial=20,
  // show a confirmation banner + pass `ref=landing` to the register API
  // so the backend issues a $20 wallet grant atomically with account
  // creation. The dollar amount is server-side fixed at $20 regardless of
  // the trial query param — we forward `trial` only for the banner copy.
  const trialCents = parseInt(searchParams.get('trial') ?? '0', 10) || 0;
  const refSource = searchParams.get('ref');
  const trialFromLanding = trialCents > 0 && refSource === 'landing';

  const mutation = useMutation({
    mutationFn: (values: any) => authApi.register(values),
    onSuccess: (data) => {
      setCustomerToken(data.access_token);
      message.success('Account created! Welcome.');
      navigate('/portal/billing');
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.detail || 'Registration failed');
    },
  });

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #0F172A 0%, #1e293b 100%)',
      padding: '32px 0',
    }}>
      <Card style={{ width: 480 }} bordered={false}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 32, fontWeight: 800, color: '#0F172A', letterSpacing: 1 }}>
            TG1<span style={{ color: '#0066FF' }}>.AI</span>
          </div>
          <Text type="secondary" style={{ fontSize: 12, letterSpacing: 2, textTransform: 'uppercase' }}>
            5-minute setup. Start growing today.
          </Text>
        </div>
        <Title level={4} style={{ textAlign: 'center', marginBottom: 16 }}>
          Create Customer Account
        </Title>

        {trialFromLanding && (
          <Alert
            type="success"
            showIcon
            icon={<GiftOutlined />}
            style={{ marginBottom: 16 }}
            message={`$${trialCents} wallet credit on signup`}
            description={
              `Welcome from the landing page — your wallet starts with ` +
              `$${trialCents} USDT equivalent. Enough for ~2,000 scraped members ` +
              `or ~40 AI auto-leads. No card required.`
            }
          />
        )}
        <Form
          form={form}
          layout="vertical"
          onFinish={(v) => mutation.mutate({ ...v, ref: refSource ?? undefined })}
        >
          <Form.Item
            name="email"
            rules={[
              { required: true, message: 'Email is required' },
              { type: 'email', message: 'Invalid email format' },
            ]}
          >
            <Input prefix={<MailOutlined />} placeholder="Email" size="large" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[
              { required: true, message: 'Password is required' },
              { min: 8, message: 'Minimum 8 characters' },
            ]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="Password (min 8 chars)" size="large" />
          </Form.Item>
          <Form.Item name="name">
            <Input prefix={<UserOutlined />} placeholder="Your name (optional)" size="large" />
          </Form.Item>
          <Form.Item name="company">
            <Input prefix={<ShopOutlined />} placeholder="Company (optional)" size="large" />
          </Form.Item>
          <Form.Item name="industry">
            <Select
              size="large"
              placeholder="Industry — drives AI persona & KB customization"
              options={INDUSTRIES}
              allowClear
            />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            block
            size="large"
            loading={mutation.isPending}
            style={{ background: '#0066FF', borderColor: '#0066FF' }}
          >
            Create Account
          </Button>
        </Form>
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <Text type="secondary">Already a customer? </Text>
          <Link to="/login">Sign in</Link>
        </div>
      </Card>
    </div>
  );
};

export default PortalRegister;
