import React, { useState, useEffect } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, Select, Tag, Space,
  message, Popconfirm, Tooltip, Row, Col, Statistic
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, RobotOutlined,
  SmileOutlined, SafetyOutlined, CoffeeOutlined
} from '@ant-design/icons';
import api from '../services/api';

interface AIPersona {
  id: number;
  name: string;
  description?: string;
  system_prompt: string;
  tone: string;
  language: string;
  forbidden_topics?: string;
  required_keywords?: string;
  usage_count: number;
  avg_reply_rate?: number;
  created_at: string;
}

const PersonaPage: React.FC = () => {
  const [personas, setPersonas] = useState<AIPersona[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingPersona, setEditingPersona] = useState<AIPersona | null>(null);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [previewPersona, setPreviewPersona] = useState<AIPersona | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchPersonas();
  }, []);

  const fetchPersonas = async () => {
    setLoading(true);
    try {
      const res = await api.get('/personas/');
      setPersonas(res.data);
    } catch (e) {
      message.error('获取人设列表失败');
    } finally {
      setLoading(false);
    }
  };

  const handleCreate = () => {
    setEditingPersona(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (record: AIPersona) => {
    setEditingPersona(record);
    form.setFieldsValue(record);
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/personas/${id}`);
      message.success('删除成功');
      fetchPersonas();
    } catch (e) {
      message.error('删除失败');
    }
  };

  const handleSubmit = async (values: any) => {
    try {
      if (editingPersona) {
        await api.put(`/personas/${editingPersona.id}`, values);
        message.success('更新成功');
      } else {
        await api.post('/personas/', values);
        message.success('创建成功');
      }
      setModalVisible(false);
      fetchPersonas();
    } catch (e) {
      message.error('操作失败');
    }
  };

  const handleInitDefaults = async () => {
    try {
      const res = await api.post('/personas/init-defaults');
      message.success(res.data.message);
      fetchPersonas();
    } catch (e) {
      message.error('初始化失败');
    }
  };

  const getToneTag = (tone: string) => {
    const config: Record<string, { color: string; icon: React.ReactNode; label: string }> = {
      friendly: { color: 'green', icon: <SmileOutlined />, label: '友好热情' },
      professional: { color: 'blue', icon: <SafetyOutlined />, label: '专业严谨' },
      casual: { color: 'orange', icon: <CoffeeOutlined />, label: '轻松随意' }
    };
    const c = config[tone] || { color: 'default', icon: null, label: tone };
    return <Tag color={c.color} icon={c.icon}>{c.label}</Tag>;
  };

  const columns = [
    {
      title: '人设名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: AIPersona) => (
        <Space>
          <RobotOutlined style={{ color: '#1890ff' }} />
          <a onClick={() => {
            setPreviewPersona(record);
            setPreviewVisible(true);
          }}>
            {text}
          </a>
        </Space>
      )
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true
    },
    {
      title: '语气风格',
      dataIndex: 'tone',
      key: 'tone',
      render: (tone: string) => getToneTag(tone)
    },
    {
      title: '使用次数',
      dataIndex: 'usage_count',
      key: 'usage_count',
      sorter: (a: AIPersona, b: AIPersona) => a.usage_count - b.usage_count
    },
    {
      title: '回复率',
      dataIndex: 'avg_reply_rate',
      key: 'avg_reply_rate',
      render: (rate: number) => rate ? `${rate.toFixed(1)}%` : '-'
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: AIPersona) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除此人设？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      )
    }
  ];

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={8}>
          <Card>
            <Statistic
              title="总人设数"
              value={personas.length}
              prefix={<RobotOutlined />}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="总使用次数"
              value={personas.reduce((sum, p) => sum + p.usage_count, 0)}
            />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic
              title="平均回复率"
              value={
                personas.filter(p => p.avg_reply_rate)
                  .reduce((sum, p) => sum + (p.avg_reply_rate || 0), 0) /
                (personas.filter(p => p.avg_reply_rate).length || 1)
              }
              suffix="%"
              precision={1}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title="AI 人设管理"
        extra={
          <Space>
            <Button onClick={handleInitDefaults}>
              初始化默认人设
            </Button>
            <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
              创建人设
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={personas}
          rowKey="id"
          loading={loading}
        />
      </Card>

      {/* 创建/编辑弹窗 */}
      <Modal
        title={editingPersona ? '编辑人设' : '创建人设'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
        width={700}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="人设名称"
                rules={[{ required: true, message: '请输入名称' }]}
              >
                <Input placeholder="如：金牌销售" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="tone" label="语气风格" initialValue="friendly">
                <Select>
                  <Select.Option value="friendly">友好热情</Select.Option>
                  <Select.Option value="professional">专业严谨</Select.Option>
                  <Select.Option value="casual">轻松随意</Select.Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="description" label="简短描述">
            <Input placeholder="一句话描述这个人设的特点" />
          </Form.Item>

          <Form.Item
            name="system_prompt"
            label="系统提示词（System Prompt）"
            rules={[{ required: true, message: '请输入提示词' }]}
            extra="AI 会按照这个提示词的指示进行对话"
          >
            <Input.TextArea
              rows={6}
              placeholder="你是一个专业的加密货币投资顾问，热情友好，善于倾听客户需求..."
            />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="forbidden_topics"
                label="禁止话题"
                extra="JSON数组格式，如 [&quot;政治&quot;, &quot;宗教&quot;]"
              >
                <Input.TextArea rows={3} placeholder='["政治", "违法"]' />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="required_keywords"
                label="必须包含关键词"
                extra="JSON数组格式"
              >
                <Input.TextArea rows={3} placeholder='["官网", "注册"]' />
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* 预览弹窗 */}
      <Modal
        title={`人设预览: ${previewPersona?.name}`}
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        footer={null}
        width={600}
      >
        {previewPersona && (
          <div>
            <div style={{ marginBottom: 16 }}>
              <Space>
                {getToneTag(previewPersona.tone)}
                <Tag>使用 {previewPersona.usage_count} 次</Tag>
                {previewPersona.avg_reply_rate && (
                  <Tag color="green">回复率 {previewPersona.avg_reply_rate}%</Tag>
                )}
              </Space>
            </div>
            
            <div style={{ marginBottom: 16 }}>
              <strong>描述：</strong>
              <p>{previewPersona.description || '无描述'}</p>
            </div>

            <div style={{ marginBottom: 16 }}>
              <strong>系统提示词：</strong>
              <pre style={{ 
                background: '#f5f5f5', 
                padding: 12, 
                borderRadius: 4,
                whiteSpace: 'pre-wrap'
              }}>
                {previewPersona.system_prompt}
              </pre>
            </div>

            {previewPersona.forbidden_topics && (
              <div style={{ marginBottom: 16 }}>
                <strong>禁止话题：</strong>
                <p>{previewPersona.forbidden_topics}</p>
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default PersonaPage;
