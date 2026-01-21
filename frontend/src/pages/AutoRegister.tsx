import React, { useEffect, useState } from 'react';
import {
  Card,
  Form,
  Input,
  Button,
  Select,
  Checkbox,
  message,
  Radio,
  Typography,
  Divider,
  Alert
} from 'antd';
import {
  startAutoRegistration,
  refreshProxiesFromIP2World,
  getSystemConfigByKey,
  setSystemConfig
} from '../services/api';

const { Option } = Select;
const { Title, Text } = Typography;

const AutoRegister: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [configLoading, setConfigLoading] = useState(false);
  const [apiKey, setApiKey] = useState('');
  const [form] = Form.useForm();

  // Load API Key
  useEffect(() => {
    const loadConfig = async () => {
      try {
        const config = await getSystemConfigByKey('sms_activate_api_key');
        if (config) {
          setApiKey(config.value);
        }
      } catch (error) {
        // Ignore 404
      }
    };
    loadConfig();
  }, []);

  const handleSaveConfig = async () => {
    if (!apiKey) {
      message.error('请输入 API Key');
      return;
    }
    setConfigLoading(true);
    try {
      await setSystemConfig('sms_activate_api_key', apiKey, 'SMS Activate API Key');
      message.success('配置已保存');
    } catch (error: any) {
      message.error(`保存失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setConfigLoading(false);
    }
  };

  const handleStartTask = async (values: any) => {
    setLoading(true);
    try {
      // 1. 先尝试刷新代理
      if (values.refresh_proxies) {
        try {
          const proxyRes = await refreshProxiesFromIP2World();
          message.info(`已刷新代理池，新增 ${proxyRes.added_count} 个代理`);
        } catch (e) {
          message.warning('刷新代理失败，尝试使用现有代理');
        }
      }
      
      // 2. 启动注册任务
      const res = await startAutoRegistration({
        count: values.count,
        country: values.country,
        proxy_category: values.proxy_category
      });
      message.success(res.message);
    } catch (error: any) {
      message.error(`启动失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <Title level={2}>自动注册配置与任务</Title>
      
      <Card title="API 配置" style={{ marginBottom: 24 }}>
        <div style={{ marginBottom: 16 }}>
          <Text strong>SMS-Activate API Key</Text>
          <div style={{ display: 'flex', marginTop: 8, gap: 16 }}>
            <Input.Password 
              placeholder="请输入 SMS-Activate API Key" 
              value={apiKey} 
              onChange={(e) => setApiKey(e.target.value)}
            />
            <Button type="primary" onClick={handleSaveConfig} loading={configLoading}>
              保存配置
            </Button>
          </div>
          <div style={{ marginTop: 8, color: '#999', fontSize: '12px' }}>
            从 <a href="https://sms-activate.org/cn/api2" target="_blank" rel="noopener noreferrer">sms-activate.org</a> 获取 API Key。
          </div>
        </div>
      </Card>

      <Card title="启动注册任务">
        <Alert
          title="使用说明"
          description="全自动注册流程：提取 IP2World 代理 -> SMS-Activate 接码 -> 注册 -> 启用 2FA -> 入库。"
          type="info"
          showIcon
          style={{ marginBottom: 24 }}
        />
        
        <Form
          form={form}
          onFinish={handleStartTask}
          layout="vertical"
          initialValues={{ 
            count: 1, 
            country: 0, 
            refresh_proxies: true, 
            proxy_category: 'rotating' 
          }}
        >
          <Form.Item 
            name="count" 
            label="注册数量" 
            rules={[{ required: true, message: '请输入数量' }]}
            extra="单次建议不超过 5 个，避免并发过高"
          >
            <Input type="number" min={1} max={50} />
          </Form.Item>

          <Form.Item name="country" label="国家 (SMS-Activate)">
            <Select>
              <Option value={0}>俄罗斯 (0)</Option>
              <Option value={6}>印度尼西亚 (6)</Option>
              <Option value={187}>美国 (187)</Option>
              <Option value={16}>英国 (16)</Option>
              <Option value={73}>巴西 (73)</Option>
              <Option value={2}>哈萨克斯坦 (2)</Option>
            </Select>
          </Form.Item>

          <Form.Item name="proxy_category" label="使用代理类型">
            <Radio.Group>
              <Radio value="rotating">短期 (Rotating)</Radio>
              <Radio value="static">长期 (Static)</Radio>
            </Radio.Group>
          </Form.Item>

          <Form.Item name="refresh_proxies" valuePropName="checked">
            <Checkbox>任务开始前从 IP2World 提取新代理</Checkbox>
          </Form.Item>

          <Divider />

          <Form.Item>
            <Button type="primary" htmlType="submit" loading={loading} block size="large">
              启动后台注册任务
            </Button>
          </Form.Item>
        </Form>
      </Card>
    </div>
  );
};

export default AutoRegister;
