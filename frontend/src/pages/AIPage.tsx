import React, { useEffect, useState } from 'react';
import { 
  Card, Form, Input, Button, Select, Typography, Space, message, 
  Modal, Table, Tag, Popconfirm, Row, Col, Badge, Tooltip, Alert
} from 'antd';
import { 
  RobotOutlined, PlusOutlined, EditOutlined, DeleteOutlined, 
  CheckCircleOutlined, ApiOutlined, StarOutlined, StarFilled
} from '@ant-design/icons';
import { 
  getAIConfigs, createAIConfig, updateAIConfig, deleteAIConfig, 
  setDefaultAIConfig, testAIConfigConnection,
  AIConfigData, AIConfigCreate, AIConfigUpdate
} from '../services/api';

const { Paragraph } = Typography;

const AIPage: React.FC = () => {
  const [configs, setConfigs] = useState<AIConfigData[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingConfig, setEditingConfig] = useState<AIConfigData | null>(null);
  const [testingId, setTestingId] = useState<number | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchConfigs();
  }, []);

  const fetchConfigs = async () => {
    setLoading(true);
    try {
      const data = await getAIConfigs();
      setConfigs(data);
    } catch (e) {
      message.error('获取AI配置列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleAdd = () => {
    setEditingConfig(null);
    form.resetFields();
    form.setFieldsValue({
      provider: 'openai',
      base_url: 'https://api.openai.com/v1',
      model: 'gpt-4o',
      is_default: configs.length === 0, // 第一个配置自动设为默认
    });
    setModalVisible(true);
  };

  const handleEdit = (config: AIConfigData) => {
    setEditingConfig(config);
    form.setFieldsValue({
      name: config.name,
      provider: config.provider,
      base_url: config.base_url,
      model: config.model,
      is_default: config.is_default,
      api_key: '', // 不回显 API Key
    });
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteAIConfig(id);
      message.success('删除成功');
      fetchConfigs();
    } catch (e) {
      message.error('删除失败');
    }
  };

  const handleSetDefault = async (id: number) => {
    try {
      await setDefaultAIConfig(id);
      message.success('已设为默认');
      fetchConfigs();
    } catch (e) {
      message.error('设置失败');
    }
  };

  const handleTest = async (id: number) => {
    setTestingId(id);
    try {
      const res = await testAIConfigConnection(id);
      if (res.status === 'success') {
        message.success('连接成功');
      } else {
        message.error('连接失败: ' + res.message);
      }
    } catch (e) {
      message.error('测试失败');
    } finally {
      setTestingId(null);
    }
  };

  const handleSubmit = async (values: any) => {
    setLoading(true);
    try {
      if (editingConfig) {
        // 更新
        const updateData: AIConfigUpdate = {
          name: values.name,
          provider: values.provider,
          base_url: values.base_url,
          model: values.model,
          is_default: values.is_default,
        };
        // 只有填写了新的 API Key 才更新
        if (values.api_key) {
          updateData.api_key = values.api_key;
        }
        await updateAIConfig(editingConfig.id, updateData);
        message.success('更新成功');
      } else {
        // 创建
        const createData: AIConfigCreate = {
          name: values.name,
          provider: values.provider,
          api_key: values.api_key,
          base_url: values.base_url || '',
          model: values.model,
          is_default: values.is_default || false,
        };
        await createAIConfig(createData);
        message.success('创建成功');
      }
      setModalVisible(false);
      fetchConfigs();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '操作失败');
    } finally {
      setLoading(false);
    }
  };

  const handleProviderChange = (value: string) => {
    const defaultUrls: Record<string, string> = {
      openai: 'https://api.openai.com/v1',
      gemini: '',
      anthropic: 'https://api.anthropic.com/v1',
      deepseek: 'https://api.deepseek.com/v1',
      qwen: 'https://dashscope.aliyuncs.com/compatible-mode/v1',
      moonshot: 'https://api.moonshot.cn/v1',
      zhipu: 'https://open.bigmodel.cn/api/paas/v4',
      doubao: 'https://ark.cn-beijing.volces.com/api/v3',
      openrouter: 'https://openrouter.ai/api/v1',
      custom: '',
    };
    const defaultModels: Record<string, string> = {
      openai: 'gpt-4o',
      gemini: 'gemini-2.5-flash',
      anthropic: 'claude-sonnet-4-20250514',
      deepseek: 'deepseek-chat',
      qwen: 'qwen-plus',
      moonshot: 'moonshot-v1-32k',
      zhipu: 'glm-4-flash',
      doubao: 'doubao-pro-32k',
      openrouter: 'google/gemini-2.5-flash',
      custom: '',
    };
    form.setFieldsValue({
      base_url: defaultUrls[value] || '',
      model: defaultModels[value] || '',
    });
  };

  const providerOptions = [
    { value: 'openai', label: 'OpenAI' },
    { value: 'gemini', label: 'Google Gemini' },
    { value: 'anthropic', label: 'Anthropic Claude' },
    { value: 'deepseek', label: 'DeepSeek 深度求索' },
    { value: 'qwen', label: '阿里通义千问' },
    { value: 'moonshot', label: 'Moonshot Kimi' },
    { value: 'zhipu', label: '智谱 GLM' },
    { value: 'doubao', label: '字节豆包' },
    { value: 'openrouter', label: 'OpenRouter' },
    { value: 'custom', label: '自定义' },
  ];

  const modelsByProvider: Record<string, string[]> = {
    openai: ['gpt-4.1', 'gpt-4.1-mini', 'gpt-4o', 'gpt-4o-mini', 'gpt-4-turbo', 'gpt-3.5-turbo', 'o3-mini', 'o1'],
    gemini: ['gemini-2.5-pro', 'gemini-2.5-flash', 'gemini-2.5-flash-lite', 'gemini-2.0-flash', 'gemini-1.5-pro'],
    anthropic: ['claude-sonnet-4-20250514', 'claude-opus-4-20250514', 'claude-3-5-sonnet-20241022', 'claude-3-opus-20240229'],
    deepseek: ['deepseek-chat', 'deepseek-reasoner'],
    qwen: ['qwen-max', 'qwen-plus', 'qwen-turbo', 'qwen-long'],
    moonshot: ['moonshot-v1-128k', 'moonshot-v1-32k', 'moonshot-v1-8k'],
    zhipu: ['glm-4-plus', 'glm-4', 'glm-4-air', 'glm-4-flash'],
    doubao: ['doubao-pro-256k', 'doubao-pro-128k', 'doubao-pro-32k', 'doubao-lite-32k'],
    openrouter: ['google/gemini-2.5-flash', 'anthropic/claude-sonnet-4', 'openai/gpt-4o', 'deepseek/deepseek-chat'],
    custom: [],
  };

  const getProviderLabel = (provider: string) => {
    const option = providerOptions.find(p => p.value === provider);
    return option?.label || provider;
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: AIConfigData) => (
        <Space>
          {text}
          {record.is_default && (
            <Tag color="gold" icon={<StarFilled />}>默认</Tag>
          )}
        </Space>
      ),
    },
    {
      title: '提供商',
      dataIndex: 'provider',
      key: 'provider',
      render: (provider: string) => (
        <Tag color="blue">{getProviderLabel(provider)}</Tag>
      ),
    },
    {
      title: '模型',
      dataIndex: 'model',
      key: 'model',
      render: (model: string) => <code>{model}</code>,
    },
    {
      title: '状态',
      key: 'status',
      render: (_: any, record: AIConfigData) => (
        <Space>
          {record.is_active ? (
            <Badge status="success" text="启用" />
          ) : (
            <Badge status="default" text="禁用" />
          )}
          {record.has_api_key ? (
            <Tooltip title="API Key 已配置">
              <CheckCircleOutlined style={{ color: '#52c41a' }} />
            </Tooltip>
          ) : (
            <Tooltip title="缺少 API Key">
              <ApiOutlined style={{ color: '#ff4d4f' }} />
            </Tooltip>
          )}
        </Space>
      ),
    },
    {
      title: '操作',
      key: 'action',
      width: 280,
      render: (_: any, record: AIConfigData) => (
        <Space>
          <Button 
            size="small" 
            onClick={() => handleTest(record.id)}
            loading={testingId === record.id}
          >
            测试
          </Button>
          {!record.is_default && (
            <Button 
              size="small" 
              icon={<StarOutlined />}
              onClick={() => handleSetDefault(record.id)}
            >
              设为默认
            </Button>
          )}
          <Button 
            size="small" 
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除此配置?"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  const selectedProvider = Form.useWatch('provider', form);

  return (
    <div>
      <Card 
        title={<span><RobotOutlined /> AI 配置管理</span>}
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
            添加配置
          </Button>
        }
      >
        <Paragraph>
          管理多个 AI 服务配置，在不同功能模块中可选择使用不同的 AI 服务。
        </Paragraph>

        {configs.length === 0 && !loading && (
          <Alert
            title="尚未配置任何 AI 服务"
            description="点击右上角「添加配置」按钮来添加您的第一个 AI 配置。"
            type="info"
            showIcon
            style={{ marginBottom: 16 }}
          />
        )}

        <Table
          columns={columns}
          dataSource={configs}
          rowKey="id"
          loading={loading}
          pagination={false}
        />
      </Card>

      <Modal
        title={editingConfig ? '编辑 AI 配置' : '添加 AI 配置'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        footer={null}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item 
            name="name" 
            label="配置名称" 
            rules={[{ required: true, message: '请输入配置名称' }]}
          >
            <Input placeholder="例如：GPT-4o 主力、DeepSeek 备用" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item 
                name="provider" 
                label="服务提供商" 
                rules={[{ required: true }]}
              >
                <Select 
                  options={providerOptions}
                  onChange={handleProviderChange}
                />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item 
                name="model" 
                label="模型" 
                rules={[{ required: true, message: '请选择或输入模型' }]}
              >
                <Select
                  showSearch
                  allowClear
                  placeholder="选择或输入模型"
                  options={(modelsByProvider[selectedProvider] || []).map(m => ({ value: m, label: m }))}
                />
              </Form.Item>
            </Col>
          </Row>

          {selectedProvider !== 'gemini' && (
            <Form.Item 
              name="base_url" 
              label="API Base URL"
              help="Gemini 使用原生 SDK，无需填写"
            >
              <Input placeholder="https://api.openai.com/v1" />
            </Form.Item>
          )}

          <Form.Item 
            name="api_key" 
            label="API Key"
            rules={editingConfig ? [] : [{ required: true, message: '请输入 API Key' }]}
            help={editingConfig ? '留空表示不修改现有 API Key' : ''}
          >
            <Input.Password placeholder={editingConfig ? '留空不修改' : '输入 API Key'} />
          </Form.Item>

          <Form.Item name="is_default" valuePropName="checked">
            <label>
              <input 
                type="checkbox" 
                checked={form.getFieldValue('is_default')} 
                onChange={(e) => form.setFieldsValue({ is_default: e.target.checked })}
                style={{ marginRight: 8 }}
              />
              设为默认配置
            </label>
          </Form.Item>

          <Form.Item>
            <Space>
              <Button type="primary" htmlType="submit" loading={loading}>
                {editingConfig ? '保存' : '创建'}
              </Button>
              <Button onClick={() => setModalVisible(false)}>取消</Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default AIPage;
