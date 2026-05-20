import React from 'react';
import { Form, Input, Button, Card, Typography, message } from 'antd';
import { LockOutlined, MailOutlined } from '@ant-design/icons';
import { Link, useNavigate } from 'react-router-dom';
import { useMutation } from '@tanstack/react-query';
import { authApi } from '../api';
import { setCustomerToken } from '../auth';

const { Title, Text } = Typography;

const PortalLogin: React.FC = () => {
  const navigate = useNavigate();
  const [form] = Form.useForm();

  const mutation = useMutation({
    mutationFn: (values: { email: string; password: string }) =>
      authApi.login(values.email, values.password),
    onSuccess: (data) => {
      setCustomerToken(data.access_token);
      message.success('Welcome back!');
      navigate('/portal/dashboard');
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.detail || 'Login failed');
    },
  });

  return (
    <div style={{
      minHeight: '100vh',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      background: 'linear-gradient(135deg, #0F172A 0%, #1e293b 100%)',
    }}>
      <Card style={{ width: 420, padding: 12 }} bordered={false}>
        <div style={{ textAlign: 'center', marginBottom: 24 }}>
          <div style={{ fontSize: 32, fontWeight: 800, color: '#0F172A', letterSpacing: 1 }}>
            TG1<span style={{ color: '#0066FF' }}>.AI</span>
          </div>
          <Text type="secondary" style={{ fontSize: 12, letterSpacing: 2, textTransform: 'uppercase' }}>
            The #1 AI Growth OS for Telegram
          </Text>
        </div>
        <Title level={4} style={{ textAlign: 'center', marginBottom: 24 }}>
          Customer Login
        </Title>
        <Form form={form} layout="vertical" onFinish={(v) => mutation.mutate(v)}>
          <Form.Item
            name="email"
            rules={[{ required: true, message: 'Please input your email' }]}
          >
            <Input prefix={<MailOutlined />} placeholder="Email" size="large" />
          </Form.Item>
          <Form.Item
            name="password"
            rules={[{ required: true, message: 'Please input your password' }]}
          >
            <Input.Password prefix={<LockOutlined />} placeholder="Password" size="large" />
          </Form.Item>
          <Button
            type="primary"
            htmlType="submit"
            block
            size="large"
            loading={mutation.isPending}
            style={{ background: '#0066FF', borderColor: '#0066FF' }}
          >
            Sign In
          </Button>
        </Form>
        <div style={{ textAlign: 'center', marginTop: 16 }}>
          <Text type="secondary">No account? </Text>
          <Link to="/portal/register">Create one</Link>
        </div>
      </Card>
    </div>
  );
};

export default PortalLogin;
