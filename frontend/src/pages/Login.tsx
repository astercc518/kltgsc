import React, { useState, useEffect, useCallback } from 'react';
import { Form, Input, Button, Card, message, Typography, Space } from 'antd';
import { UserOutlined, LockOutlined, SafetyCertificateOutlined, ReloadOutlined } from '@ant-design/icons';
import { login } from '../services/api';
import { useNavigate } from 'react-router-dom';

const { Title, Text } = Typography;

// 生成随机数学验证码
const generateCaptcha = () => {
  const num1 = Math.floor(Math.random() * 20) + 1;
  const num2 = Math.floor(Math.random() * 20) + 1;
  const operators = ['+', '-', '×'];
  const operator = operators[Math.floor(Math.random() * operators.length)];
  
  let answer: number;
  switch (operator) {
    case '+':
      answer = num1 + num2;
      break;
    case '-':
      answer = num1 - num2;
      break;
    case '×':
      answer = num1 * num2;
      break;
    default:
      answer = num1 + num2;
  }
  
  return {
    question: `${num1} ${operator} ${num2} = ?`,
    answer: answer.toString()
  };
};

const Login: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [captcha, setCaptcha] = useState({ question: '', answer: '' });
  const navigate = useNavigate();
  const [form] = Form.useForm();

  // 刷新验证码
  const refreshCaptcha = useCallback(() => {
    setCaptcha(generateCaptcha());
    form.setFieldValue('captcha', '');
  }, [form]);

  useEffect(() => {
    refreshCaptcha();
  }, [refreshCaptcha]);

  const onFinish = async (values: any) => {
    // 验证验证码
    if (values.captcha !== captcha.answer) {
      message.error('验证码错误，请重新计算');
      refreshCaptcha();
      return;
    }

    setLoading(true);
    try {
      const data = await login(values.username, values.password);
      localStorage.setItem('token', data.access_token);
      message.success('登录成功');
      window.location.href = '/';
    } catch (error: any) {
      const errorMsg = error.response?.data?.detail || '登录失败';
      if (errorMsg.includes('Too many')) {
        message.error('登录尝试次数过多，请15分钟后再试');
      } else {
        message.error(errorMsg);
      }
      refreshCaptcha();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ 
      display: 'flex', 
      justifyContent: 'center', 
      alignItems: 'center', 
      height: '100vh', 
      background: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #0f3460 100%)'
    }}>
      <Card 
        style={{ 
          width: 420, 
          boxShadow: '0 8px 32px rgba(0,0,0,0.3)',
          borderRadius: 12,
          border: 'none'
        }}
      >
        <div style={{ textAlign: 'center', marginBottom: 32 }}>
          <div style={{
            width: 64,
            height: 64,
            margin: '0 auto 16px',
            background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
            borderRadius: 16,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: 28,
            color: '#fff',
            fontWeight: 'bold'
          }}>
            TG
          </div>
          <Title level={3} style={{ margin: 0, color: '#1a1a2e' }}>
            Telegram SC Platform
          </Title>
          <Text type="secondary">安全登录</Text>
        </div>
        
        <Form
          form={form}
          name="login"
          initialValues={{ remember: true }}
          onFinish={onFinish}
          size="large"
        >
          <Form.Item
            name="username"
            rules={[{ required: true, message: '请输入用户名!' }]}
          >
            <Input 
              prefix={<UserOutlined style={{ color: '#bfbfbf' }} />} 
              placeholder="用户名" 
              autoComplete="username"
            />
          </Form.Item>

          <Form.Item
            name="password"
            rules={[{ required: true, message: '请输入密码!' }]}
          >
            <Input.Password 
              prefix={<LockOutlined style={{ color: '#bfbfbf' }} />} 
              placeholder="密码" 
              autoComplete="current-password"
            />
          </Form.Item>

          <Form.Item>
            <Space.Compact style={{ width: '100%' }}>
              <div style={{
                width: 140,
                height: 40,
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                color: '#fff',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                fontWeight: 'bold',
                fontSize: 16,
                borderRadius: '6px 0 0 6px',
                userSelect: 'none',
                letterSpacing: 1
              }}>
                {captcha.question}
              </div>
              <Form.Item
                name="captcha"
                noStyle
                rules={[{ required: true, message: '请输入验证码!' }]}
              >
                <Input 
                  prefix={<SafetyCertificateOutlined style={{ color: '#bfbfbf' }} />} 
                  placeholder="计算结果" 
                  style={{ flex: 1 }}
                  autoComplete="off"
                />
              </Form.Item>
              <Button 
                icon={<ReloadOutlined />} 
                onClick={refreshCaptcha}
                title="刷新验证码"
                style={{ borderRadius: '0 6px 6px 0' }}
              />
            </Space.Compact>
          </Form.Item>

          <Form.Item style={{ marginBottom: 12 }}>
            <Button 
              type="primary" 
              htmlType="submit" 
              loading={loading} 
              block
              style={{
                height: 44,
                background: 'linear-gradient(135deg, #667eea 0%, #764ba2 100%)',
                border: 'none',
                fontWeight: 500
              }}
            >
              登录
            </Button>
          </Form.Item>
        </Form>
        
        <div style={{ textAlign: 'center' }}>
          <Text type="secondary" style={{ fontSize: 12 }}>
            🔒 已启用登录保护：连续5次失败将锁定15分钟
          </Text>
        </div>
      </Card>
    </div>
  );
};

export default Login;
