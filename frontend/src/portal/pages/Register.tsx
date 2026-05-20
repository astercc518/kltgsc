import React from 'react';
import { Form, Input, Button, Card, Typography, message, Select } from 'antd';
import { LockOutlined, MailOutlined, UserOutlined, ShopOutlined } from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';
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
        <Title level={4} style={{ textAlign: 'center', marginBottom: 24 }}>
          Create Customer Account
        </Title>
        <Form form={form} layout="vertical" onFinish={(v) => mutation.mutate(v)}>
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
          <Link to="/portal/login">Sign in</Link>
        </div>
      </Card>
    </div>
  );
};

export default PortalRegister;
