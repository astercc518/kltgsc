import React, { useEffect, useState } from 'react';
import {
  Card,
  Form,
  Input,
  Button,
  Select,
  message,
  Tabs,
  Table,
  Tag,
  Slider,
  Row,
  Col,
  Statistic,
  InputNumber,
  Modal,
  Space,
  Popconfirm,
  Divider,
  Empty,
  Checkbox
} from 'antd';
import {
  CoffeeOutlined,
  HistoryOutlined,
  UserOutlined,
  ReloadOutlined,
  SaveOutlined,
  DeleteOutlined,
  StarOutlined,
  StarFilled,
  EditOutlined,
  PlusOutlined
} from '@ant-design/icons';
import {
  getAccounts,
  createWarmupTask,
  getWarmupTasks,
  getWarmupTemplates,
  createWarmupTemplate,
  updateWarmupTemplate,
  deleteWarmupTemplate,
  Account,
  WarmupTask,
  WarmupTemplate
} from '../services/api';

const { TextArea } = Input;
const { Option } = Select;

const Warmup: React.FC = () => {
  const [activeTab, setActiveTab] = useState('create');
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [tasks, setTasks] = useState<WarmupTask[]>([]);
  const [templates, setTemplates] = useState<WarmupTemplate[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedAccountIds, setSelectedAccountIds] = useState<React.Key[]>([]);
  const [selectedTemplateId, setSelectedTemplateId] = useState<number | null>(null);
  const [form] = Form.useForm();
  
  // Template Modal
  const [isTemplateModalVisible, setIsTemplateModalVisible] = useState(false);
  const [editingTemplate, setEditingTemplate] = useState<WarmupTemplate | null>(null);
  const [templateForm] = Form.useForm();
  const [templateLoading, setTemplateLoading] = useState(false);

  useEffect(() => {
    fetchAccounts();
    fetchTasks();
    fetchTemplates();
  }, []);

  const fetchAccounts = async () => {
    try {
      // 直接请求活跃账号 (后端限制 limit 最大 100)
      const data = await getAccounts(0, 100, 'active');
      setAccounts(data);
    } catch (e) {
      console.error('Failed to fetch accounts:', e);
      message.error('获取账号列表失败');
    }
  };

  const fetchTasks = async () => {
    try {
      const data = await getWarmupTasks();
      setTasks(data);
    } catch (e) {
      // ignore
    }
  };

  const fetchTemplates = async () => {
    try {
      const data = await getWarmupTemplates();
      setTemplates(data);
      // 自动选择默认模板
      const defaultTemplate = data.find(t => t.is_default);
      if (defaultTemplate) {
        setSelectedTemplateId(defaultTemplate.id);
        applyTemplate(defaultTemplate);
      }
    } catch (e) {
      // ignore
    }
  };

  const applyTemplate = (template: WarmupTemplate) => {
    form.setFieldsValue({
      name: `${template.name} - ${new Date().toLocaleDateString()}`,
      action_type: template.action_type,
      target_channels: template.target_channels,
      duration_minutes: template.duration_minutes,
      delay: [template.min_delay, template.max_delay]
    });
  };

  const handleTemplateSelect = (templateId: number) => {
    setSelectedTemplateId(templateId);
    const template = templates.find(t => t.id === templateId);
    if (template) {
      applyTemplate(template);
    }
  };

  const handleCreateTask = async (values: any) => {
    if (selectedAccountIds.length === 0) {
      message.error('请至少选择一个账号');
      return;
    }

    setLoading(true);
    try {
      await createWarmupTask({
        name: values.name,
        action_type: values.action_type,
        account_ids: selectedAccountIds as number[],
        min_delay: values.delay[0],
        max_delay: values.delay[1],
        duration_minutes: values.duration_minutes,
        target_channels: values.target_channels
      });
      message.success('养号任务创建成功');
      setSelectedAccountIds([]);
      setActiveTab('history');
      fetchTasks();
    } catch (error: any) {
      message.error(`创建失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setLoading(false);
    }
  };

  // Template CRUD
  const handleSaveTemplate = async (values: any) => {
    setTemplateLoading(true);
    try {
      if (editingTemplate) {
        await updateWarmupTemplate(editingTemplate.id, {
          name: values.name,
          description: values.description,
          action_type: values.action_type,
          min_delay: values.delay[0],
          max_delay: values.delay[1],
          duration_minutes: values.duration_minutes,
          target_channels: values.target_channels,
          is_default: values.is_default
        });
        message.success('模板已更新');
      } else {
        await createWarmupTemplate({
          name: values.name,
          description: values.description,
          action_type: values.action_type,
          min_delay: values.delay[0],
          max_delay: values.delay[1],
          duration_minutes: values.duration_minutes,
          target_channels: values.target_channels,
          is_default: values.is_default
        });
        message.success('模板已创建');
      }
      setIsTemplateModalVisible(false);
      setEditingTemplate(null);
      templateForm.resetFields();
      fetchTemplates();
    } catch (error: any) {
      message.error(`操作失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setTemplateLoading(false);
    }
  };

  const handleEditTemplate = (template: WarmupTemplate) => {
    setEditingTemplate(template);
    templateForm.setFieldsValue({
      name: template.name,
      description: template.description,
      action_type: template.action_type,
      delay: [template.min_delay, template.max_delay],
      duration_minutes: template.duration_minutes,
      target_channels: template.target_channels,
      is_default: template.is_default
    });
    setIsTemplateModalVisible(true);
  };

  const handleDeleteTemplate = async (id: number) => {
    try {
      await deleteWarmupTemplate(id);
      message.success('模板已删除');
      if (selectedTemplateId === id) {
        setSelectedTemplateId(null);
      }
      fetchTemplates();
    } catch (error: any) {
      message.error(`删除失败: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleSetDefault = async (template: WarmupTemplate) => {
    try {
      await updateWarmupTemplate(template.id, { is_default: true });
      message.success(`已将 "${template.name}" 设为默认模板`);
      fetchTemplates();
    } catch (error: any) {
      message.error('设置失败');
    }
  };

  const handleSaveCurrentAsTemplate = () => {
    const values = form.getFieldsValue();
    templateForm.setFieldsValue({
      name: values.name?.replace(/ - \d{4}.*$/, '') || '新模板',
      action_type: values.action_type,
      delay: values.delay,
      duration_minutes: values.duration_minutes,
      target_channels: values.target_channels,
      is_default: false
    });
    setEditingTemplate(null);
    setIsTemplateModalVisible(true);
  };

  const accountColumns = [
    { title: '手机号', dataIndex: 'phone_number', key: 'phone' },
    { title: '状态', dataIndex: 'status', key: 'status', render: (t: string) => <Tag color="green">{t}</Tag> },
    { title: '最后活跃', dataIndex: 'last_active', key: 'active', render: (t: string) => t ? new Date(t).toLocaleString() : '-' },
  ];

  const taskColumns = [
    { title: '任务名称', dataIndex: 'name', key: 'name' },
    { title: '账号数量', key: 'count', render: (_: any, r: WarmupTask) => r.account_ids?.length || 0 },
    { 
      title: '状态', 
      dataIndex: 'status', 
      key: 'status',
      render: (t: string) => {
        const colors: any = { running: 'processing', completed: 'success', failed: 'error', pending: 'default' };
        return <Tag color={colors[t]}>{t.toUpperCase()}</Tag>;
      }
    },
    { title: '成功/失败', key: 'result', render: (_: any, r: WarmupTask) => <span>{r.success_count || 0} / {r.fail_count || 0}</span> },
    { title: '持续时长', dataIndex: 'duration_minutes', key: 'duration', render: (t: number) => `${t} 分钟` },
    { title: '创建时间', dataIndex: 'created_at', key: 'created', render: (t: string) => new Date(t).toLocaleString() },
  ];

  return (
    <div>
      <Tabs
        activeKey={activeTab}
        onChange={setActiveTab}
        type="card"
        items={[
          {
            key: 'create',
            label: <span><CoffeeOutlined /> 创建养号任务</span>,
            children: (
              <Row gutter={24}>
                <Col span={14}>
                  <Card title="选择养号账号" style={{ minHeight: 600 }} extra={
                    <Button size="small" onClick={() => setSelectedAccountIds(accounts.map(a => a.id))}>
                      全选
                    </Button>
                  }>
                    <Table
                      size="small"
                      rowSelection={{
                        type: 'checkbox',
                        selectedRowKeys: selectedAccountIds,
                        onChange: (keys) => setSelectedAccountIds(keys),
                      }}
                      columns={accountColumns}
                      dataSource={accounts}
                      rowKey="id"
                      pagination={{ pageSize: 10 }}
                    />
                  </Card>
                </Col>
                <Col span={10}>
                  <Card 
                    title="养号策略配置" 
                    style={{ minHeight: 600 }}
                    extra={
                      <Button 
                        type="link" 
                        icon={<SaveOutlined />} 
                        onClick={handleSaveCurrentAsTemplate}
                      >
                        保存为模板
                      </Button>
                    }
                  >
                    {/* Template Selection */}
                    <div style={{ marginBottom: 16 }}>
                      <div style={{ marginBottom: 8, fontWeight: 500 }}>快速选择模板</div>
                      {templates.length === 0 ? (
                        <Empty 
                          image={Empty.PRESENTED_IMAGE_SIMPLE} 
                          description="暂无模板"
                          style={{ margin: '10px 0' }}
                        >
                          <Button 
                            type="dashed" 
                            icon={<PlusOutlined />}
                            onClick={() => {
                              setEditingTemplate(null);
                              templateForm.resetFields();
                              setIsTemplateModalVisible(true);
                            }}
                          >
                            创建模板
                          </Button>
                        </Empty>
                      ) : (
                        <Space wrap>
                          {templates.map(t => (
                            <Tag
                              key={t.id}
                              color={selectedTemplateId === t.id ? 'blue' : 'default'}
                              style={{ cursor: 'pointer', padding: '4px 12px' }}
                              onClick={() => handleTemplateSelect(t.id)}
                            >
                              {t.is_default && <StarFilled style={{ color: '#faad14', marginRight: 4 }} />}
                              {t.name}
                            </Tag>
                          ))}
                          <Tag 
                            style={{ cursor: 'pointer', borderStyle: 'dashed' }}
                            onClick={() => {
                              setEditingTemplate(null);
                              templateForm.resetFields();
                              setIsTemplateModalVisible(true);
                            }}
                          >
                            <PlusOutlined /> 新建
                          </Tag>
                        </Space>
                      )}
                    </div>
                    
                    <Divider style={{ margin: '12px 0' }} />
                    
                    <Form form={form} layout="vertical" onFinish={handleCreateTask} initialValues={{ 
                        delay: [5, 30],
                        action_type: 'mixed',
                        duration_minutes: 30
                    }}>
                      <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
                        <Input placeholder="例如: 日常浏览养号" />
                      </Form.Item>
                      <Form.Item name="action_type" label="操作类型">
                        <Select>
                          <Option value="mixed">混合模式 (浏览 + 随机点赞)</Option>
                          <Option value="view_channel">仅浏览频道</Option>
                        </Select>
                      </Form.Item>
                      <Form.Item name="target_channels" label="目标频道 (逗号分隔)" rules={[{ required: true }]} tooltip="输入频道 Username，例如: kltgsc, telegram">
                         <TextArea rows={3} placeholder="kltgsc, telegram, durov" />
                      </Form.Item>
                      <Form.Item name="duration_minutes" label="持续时长 (分钟)">
                         <InputNumber min={5} max={180} style={{ width: '100%' }} />
                      </Form.Item>
                      <Form.Item name="delay" label="操作随机延迟 (秒)">
                        <Slider range min={1} max={60} marks={{ 5: '5s', 30: '30s', 60: '60s' }} />
                      </Form.Item>
                      <div style={{ marginTop: 20 }}>
                        <Statistic title="选中账号数" value={selectedAccountIds.length} prefix={<UserOutlined />} />
                      </div>
                      <Form.Item style={{ marginTop: 40 }}>
                        <Button type="primary" htmlType="submit" size="large" block loading={loading} icon={<CoffeeOutlined />}>
                          启动养号
                        </Button>
                      </Form.Item>
                    </Form>
                  </Card>
                </Col>
              </Row>
            )
          },
          {
            key: 'templates',
            label: <span><StarOutlined /> 模板管理</span>,
            children: (
              <Card
                extra={
                  <Button 
                    type="primary" 
                    icon={<PlusOutlined />}
                    onClick={() => {
                      setEditingTemplate(null);
                      templateForm.resetFields();
                      setIsTemplateModalVisible(true);
                    }}
                  >
                    新建模板
                  </Button>
                }
              >
                <Table
                  dataSource={templates}
                  rowKey="id"
                  columns={[
                    { 
                      title: '模板名称', 
                      dataIndex: 'name', 
                      key: 'name',
                      render: (name: string, record: WarmupTemplate) => (
                        <span>
                          {record.is_default && <StarFilled style={{ color: '#faad14', marginRight: 8 }} />}
                          {name}
                        </span>
                      )
                    },
                    { title: '描述', dataIndex: 'description', key: 'desc', render: (t: string) => t || '-' },
                    { 
                      title: '操作类型', 
                      dataIndex: 'action_type', 
                      key: 'type',
                      render: (t: string) => t === 'mixed' ? '混合模式' : '仅浏览'
                    },
                    { title: '目标频道', dataIndex: 'target_channels', key: 'channels', ellipsis: true },
                    { title: '时长', dataIndex: 'duration_minutes', key: 'duration', render: (t: number) => `${t} 分钟` },
                    { title: '延迟', key: 'delay', render: (_: any, r: WarmupTemplate) => `${r.min_delay}-${r.max_delay}s` },
                    {
                      title: '操作',
                      key: 'actions',
                      render: (_: any, record: WarmupTemplate) => (
                        <Space>
                          {!record.is_default && (
                            <Button 
                              type="link" 
                              size="small" 
                              icon={<StarOutlined />}
                              onClick={() => handleSetDefault(record)}
                            >
                              设为默认
                            </Button>
                          )}
                          <Button 
                            type="link" 
                            size="small" 
                            icon={<EditOutlined />}
                            onClick={() => handleEditTemplate(record)}
                          >
                            编辑
                          </Button>
                          <Popconfirm
                            title="确定删除此模板？"
                            onConfirm={() => handleDeleteTemplate(record.id)}
                          >
                            <Button type="link" size="small" danger icon={<DeleteOutlined />}>
                              删除
                            </Button>
                          </Popconfirm>
                        </Space>
                      )
                    }
                  ]}
                />
              </Card>
            )
          },
          {
            key: 'history',
            label: <span><HistoryOutlined /> 养号记录</span>,
            children: (
              <Card>
                <div style={{ marginBottom: 16, textAlign: 'right' }}>
                  <Button icon={<ReloadOutlined />} onClick={fetchTasks}>刷新</Button>
                </div>
                <Table
                  columns={taskColumns}
                  dataSource={tasks}
                  rowKey="id"
                />
              </Card>
            )
          }
        ]}
      />

      {/* Template Modal */}
      <Modal
        title={editingTemplate ? '编辑模板' : '创建模板'}
        open={isTemplateModalVisible}
        onCancel={() => {
          setIsTemplateModalVisible(false);
          setEditingTemplate(null);
          templateForm.resetFields();
        }}
        footer={null}
        width={500}
      >
        <Form
          form={templateForm}
          layout="vertical"
          onFinish={handleSaveTemplate}
          initialValues={{
            delay: [5, 30],
            action_type: 'mixed',
            duration_minutes: 30,
            is_default: false
          }}
        >
          <Form.Item name="name" label="模板名称" rules={[{ required: true }]}>
            <Input placeholder="例如: 日常养号" />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input placeholder="可选的描述信息" />
          </Form.Item>
          <Form.Item name="action_type" label="操作类型">
            <Select>
              <Option value="mixed">混合模式 (浏览 + 随机点赞)</Option>
              <Option value="view_channel">仅浏览频道</Option>
            </Select>
          </Form.Item>
          <Form.Item name="target_channels" label="目标频道 (逗号分隔)" rules={[{ required: true }]}>
            <TextArea rows={3} placeholder="kltgsc, telegram, durov" />
          </Form.Item>
          <Form.Item name="duration_minutes" label="持续时长 (分钟)">
            <InputNumber min={5} max={180} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="delay" label="操作随机延迟 (秒)">
            <Slider range min={1} max={60} marks={{ 5: '5s', 30: '30s', 60: '60s' }} />
          </Form.Item>
          <Form.Item name="is_default" valuePropName="checked">
            <Checkbox>设为默认模板</Checkbox>
          </Form.Item>
          <Form.Item style={{ marginTop: 24 }}>
            <Space style={{ width: '100%', justifyContent: 'flex-end' }}>
              <Button onClick={() => setIsTemplateModalVisible(false)}>取消</Button>
              <Button type="primary" htmlType="submit" loading={templateLoading}>
                {editingTemplate ? '更新' : '创建'}
              </Button>
            </Space>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default Warmup;
