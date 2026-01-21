import React, { useEffect, useState } from 'react';
import { Card, Form, Input, Button, Switch, List, Typography, Space, message, Divider, Tag } from 'antd';
import { RobotOutlined, ThunderboltOutlined, SettingOutlined } from '@ant-design/icons';
import { testAIConnection, getSystemConfigByKey, setSystemConfig, SystemConfig } from '../services/api';
import api from '../services/api';

const { Text, Title, Paragraph } = Typography;

// Add triggerAutoReply to api service first? 
// Or just use axios directly here for the new endpoint if not yet in api.ts
// Ideally update api.ts. For now I will extend api.ts locally in my mind or use api instance.

const AIPage: React.FC = () => {
  const [loading, setLoading] = useState(false);
  const [connectionStatus, setConnectionStatus] = useState<'unknown' | 'success' | 'failed'>('unknown');
  const [configForm] = Form.useForm();
  
  useEffect(() => {
    fetchConfig();
  }, []);

  const fetchConfig = async () => {
    try {
      const [apiKeyRes, baseUrlRes, modelRes] = await Promise.all([
        getSystemConfigByKey('llm_api_key').catch(() => ({ value: '' })),
        getSystemConfigByKey('llm_base_url').catch(() => ({ value: '' })),
        getSystemConfigByKey('llm_model').catch(() => ({ value: '' })),
      ]);
      
      configForm.setFieldsValue({
        llm_api_key: apiKeyRes.value,
        llm_base_url: baseUrlRes.value || 'https://api.openai.com/v1',
        llm_model: modelRes.value || 'gpt-3.5-turbo',
      });
    } catch (e) {
      // ignore
    }
  };

  const handleSaveConfig = async (values: any) => {
    setLoading(true);
    try {
      await Promise.all([
        setSystemConfig('llm_api_key', values.llm_api_key, 'LLM API Key'),
        setSystemConfig('llm_base_url', values.llm_base_url, 'LLM Base URL'),
        setSystemConfig('llm_model', values.llm_model, 'LLM Model Name'),
      ]);
      message.success('配置已保存');
      handleTestConnection();
    } catch (e) {
      message.error('保存失败');
    } finally {
      setLoading(false);
    }
  };

  const handleTestConnection = async () => {
    setLoading(true);
    try {
      const res = await testAIConnection();
      if (res.status === 'success') {
        setConnectionStatus('success');
        message.success('连接成功');
      } else {
        setConnectionStatus('failed');
        message.error('连接失败: ' + res.message);
      }
    } catch (e) {
      setConnectionStatus('failed');
      message.error('连接测试出错');
    } finally {
      setLoading(false);
    }
  };

  const handleTriggerAutoReply = async () => {
      try {
          // Need to add this to api.ts or call directly
          const res = await api.post('/ai/trigger_auto_reply');
          message.success(`已触发检查，任务数: ${res.data.task_ids.length}`);
      } catch (e) {
          message.error('触发失败');
      }
  }

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <Card title={<span><RobotOutlined /> AI 智能营销配置</span>}>
        <Paragraph>
            配置 OpenAI 兼容的 LLM 服务，用于自动回复私信和生成营销文案。
        </Paragraph>
        
        <Divider orientation="left"><SettingOutlined /> 服务配置</Divider>
        
        <Form form={configForm} layout="vertical" onFinish={handleSaveConfig}>
          <Form.Item name="llm_base_url" label="API Base URL" help="例如: https://api.openai.com/v1 或第三方中转地址">
            <Input placeholder="https://api.openai.com/v1" />
          </Form.Item>
          
          <Form.Item name="llm_api_key" label="API Key" rules={[{ required: true }]}>
            <Input.Password placeholder="sk-..." />
          </Form.Item>
          
          <Form.Item name="llm_model" label="模型名称" help="例如: gpt-3.5-turbo, gpt-4o, claude-3-sonnet">
            <Input placeholder="gpt-3.5-turbo" />
          </Form.Item>
          
          <Form.Item>
            <Space>
                <Button type="primary" htmlType="submit" loading={loading}>
                保存配置
                </Button>
                <Button onClick={handleTestConnection} loading={loading}>
                测试连接
                </Button>
                {connectionStatus === 'success' && <Tag color="success">连接正常</Tag>}
                {connectionStatus === 'failed' && <Tag color="error">连接失败</Tag>}
            </Space>
          </Form.Item>
        </Form>
        
        <Divider orientation="left"><ThunderboltOutlined /> 调试与操作</Divider>
        
        <Space orientation="vertical" style={{ width: '100%' }}>
            <Card type="inner" size="small" title="自动回复测试">
                <p>手动触发所有开启了"自动回复"功能的活跃账号进行一次消息检查与回复。</p>
                <Button type="primary" onClick={handleTriggerAutoReply}>
                    立即触发全量检查
                </Button>
            </Card>
        </Space>
      </Card>
    </div>
  );
};

export default AIPage;
