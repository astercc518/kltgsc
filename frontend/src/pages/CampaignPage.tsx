import React, { useState, useEffect } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, Select, InputNumber, 
  Tag, Space, Tabs, Statistic, Row, Col, Progress, message, Popconfirm
} from 'antd';
import { 
  PlusOutlined, EditOutlined, DeleteOutlined, 
  ThunderboltOutlined, PauseCircleOutlined, CheckCircleOutlined,
  RocketOutlined, TeamOutlined, MessageOutlined
} from '@ant-design/icons';
import api from '../services/api';

interface Campaign {
  id: number;
  name: string;
  description?: string;
  status: string;
  allowed_roles: string;
  daily_budget: number;
  daily_account_limit: number;
  ai_persona_id?: number;
  total_messages_sent: number;
  total_replies_received: number;
  total_conversions: number;
  created_at: string;
}

interface AIPersona {
  id: number;
  name: string;
  tone: string;
}

const CampaignPage: React.FC = () => {
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [personas, setPersonas] = useState<AIPersona[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingCampaign, setEditingCampaign] = useState<Campaign | null>(null);
  const [dashboardData, setDashboardData] = useState<any>(null);
  const [selectedCampaign, setSelectedCampaign] = useState<Campaign | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchCampaigns();
    fetchPersonas();
  }, []);

  const fetchCampaigns = async () => {
    setLoading(true);
    try {
      const res = await api.get('/campaigns/');
      setCampaigns(res.data);
    } catch (e) {
      message.error('获取战役列表失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchPersonas = async () => {
    try {
      const res = await api.get('/personas/');
      setPersonas(res.data);
    } catch (e) {
      console.error('获取人设失败');
    }
  };

  const fetchDashboard = async (campaignId: number) => {
    try {
      const res = await api.get(`/campaigns/${campaignId}/dashboard`);
      setDashboardData(res.data);
    } catch (e) {
      message.error('获取数据失败');
    }
  };

  const handleCreate = () => {
    setEditingCampaign(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (record: Campaign) => {
    setEditingCampaign(record);
    form.setFieldsValue({
      ...record,
      allowed_roles: record.allowed_roles?.split(',') || ['cannon']
    });
    setModalVisible(true);
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/campaigns/${id}`);
      message.success('删除成功');
      fetchCampaigns();
    } catch (e) {
      message.error('删除失败');
    }
  };

  const handleSubmit = async (values: any) => {
    try {
      const data = {
        ...values,
        allowed_roles: Array.isArray(values.allowed_roles) 
          ? values.allowed_roles.join(',') 
          : values.allowed_roles
      };
      
      if (editingCampaign) {
        await api.put(`/campaigns/${editingCampaign.id}`, data);
        message.success('更新成功');
      } else {
        await api.post('/campaigns/', data);
        message.success('创建成功');
      }
      setModalVisible(false);
      fetchCampaigns();
    } catch (e) {
      message.error('操作失败');
    }
  };

  const handleViewDashboard = (record: Campaign) => {
    setSelectedCampaign(record);
    fetchDashboard(record.id);
  };

  const getStatusTag = (status: string) => {
    const colors: Record<string, string> = {
      active: 'green',
      paused: 'orange',
      completed: 'blue'
    };
    const labels: Record<string, string> = {
      active: '进行中',
      paused: '已暂停',
      completed: '已完成'
    };
    return <Tag color={colors[status]}>{labels[status] || status}</Tag>;
  };

  const columns = [
    {
      title: '战役名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: Campaign) => (
        <a onClick={() => handleViewDashboard(record)}>{text}</a>
      )
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => getStatusTag(status)
    },
    {
      title: '允许角色',
      dataIndex: 'allowed_roles',
      key: 'allowed_roles',
      render: (roles: string) => (
        <Space>
          {roles?.split(',').map(role => {
            const roleColors: Record<string, string> = {
              cannon: 'red',
              scout: 'blue',
              actor: 'purple',
              sniper: 'gold'
            };
            const roleNames: Record<string, string> = {
              cannon: '炮灰',
              scout: '侦察',
              actor: '演员',
              sniper: '狙击'
            };
            return <Tag key={role} color={roleColors[role]}>{roleNames[role] || role}</Tag>;
          })}
        </Space>
      )
    },
    {
      title: '每日预算',
      dataIndex: 'daily_budget',
      key: 'daily_budget',
      render: (v: number) => `${v} 条/天`
    },
    {
      title: '发送/回复/转化',
      key: 'stats',
      render: (_: any, record: Campaign) => (
        <Space>
          <span>{record.total_messages_sent}</span>
          <span>/</span>
          <span style={{ color: '#52c41a' }}>{record.total_replies_received}</span>
          <span>/</span>
          <span style={{ color: '#faad14' }}>{record.total_conversions}</span>
        </Space>
      )
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: Campaign) => (
        <Space>
          <Button 
            type="link" 
            icon={<ThunderboltOutlined />}
            onClick={() => handleViewDashboard(record)}
          >
            数据
          </Button>
          <Button 
            type="link" 
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除此战役？"
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
      <Tabs
        items={[
          {
            key: 'list',
            label: '战役列表',
            children: (
              <Card
                title="战役管理"
                extra={
                  <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
                    创建战役
                  </Button>
                }
              >
                <Table
                  columns={columns}
                  dataSource={campaigns}
                  rowKey="id"
                  loading={loading}
                />
              </Card>
            )
          },
          {
            key: 'dashboard',
            label: selectedCampaign ? `数据大屏: ${selectedCampaign.name}` : '数据大屏',
            disabled: !selectedCampaign,
            children: dashboardData && (
              <div>
                <Row gutter={16} style={{ marginBottom: 24 }}>
                  <Col span={6}>
                    <Card>
                      <Statistic
                        title="总发送"
                        value={dashboardData.metrics.total_messages_sent}
                        prefix={<MessageOutlined />}
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card>
                      <Statistic
                        title="总回复"
                        value={dashboardData.metrics.total_replies_received}
                        prefix={<TeamOutlined />}
                        styles={{ content: { color: '#52c41a' } }}
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card>
                      <Statistic
                        title="回复率"
                        value={dashboardData.metrics.reply_rate}
                        suffix="%"
                        precision={2}
                      />
                    </Card>
                  </Col>
                  <Col span={6}>
                    <Card>
                      <Statistic
                        title="转化率"
                        value={dashboardData.metrics.conversion_rate}
                        suffix="%"
                        precision={2}
                        styles={{ content: { color: '#faad14' } }}
                      />
                    </Card>
                  </Col>
                </Row>

                <Card title="转化漏斗">
                  <div style={{ padding: '20px 0' }}>
                    <div style={{ marginBottom: 16 }}>
                      <span>发送 → 回复</span>
                      <Progress 
                        percent={dashboardData.metrics.reply_rate} 
                        status="active"
                        strokeColor="#52c41a"
                      />
                    </div>
                    <div>
                      <span>回复 → 转化</span>
                      <Progress 
                        percent={dashboardData.metrics.conversion_rate} 
                        status="active"
                        strokeColor="#faad14"
                      />
                    </div>
                  </div>
                </Card>

                {dashboardData.funnel_groups?.length > 0 && (
                  <Card title="关联营销群" style={{ marginTop: 16 }}>
                    <Table
                      dataSource={dashboardData.funnel_groups}
                      rowKey="id"
                      columns={[
                        { title: '群名称', dataIndex: 'name' },
                        { title: '类型', dataIndex: 'type' },
                        { title: '成员数', dataIndex: 'member_count' },
                        { title: '今日新增', dataIndex: 'today_joined' }
                      ]}
                      pagination={false}
                    />
                  </Card>
                )}
              </div>
            )
          }
        ]}
      />

      <Modal
        title={editingCampaign ? '编辑战役' : '创建战役'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="name"
            label="战役名称"
            rules={[{ required: true, message: '请输入战役名称' }]}
          >
            <Input placeholder="如：春节促销活动" />
          </Form.Item>

          <Form.Item name="description" label="描述">
            <Input.TextArea rows={3} placeholder="战役目标和说明" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="allowed_roles"
                label="允许使用的账号角色"
                initialValue={['cannon']}
              >
                <Select mode="multiple" placeholder="选择角色">
                  <Select.Option value="cannon">炮灰组</Select.Option>
                  <Select.Option value="scout">侦察组</Select.Option>
                  <Select.Option value="actor">演员组</Select.Option>
                  <Select.Option value="sniper">狙击组</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="ai_persona_id" label="关联AI人设">
                <Select allowClear placeholder="选择AI人设">
                  {personas.map(p => (
                    <Select.Option key={p.id} value={p.id}>
                      {p.name} ({p.tone})
                    </Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="daily_budget"
                label="每日消息上限"
                initialValue={1000}
              >
                <InputNumber min={0} max={100000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item
                name="daily_account_limit"
                label="每日账号消耗上限"
                initialValue={100}
              >
                <InputNumber min={0} max={10000} style={{ width: '100%' }} />
              </Form.Item>
            </Col>
          </Row>

          {editingCampaign && (
            <Form.Item name="status" label="状态">
              <Select>
                <Select.Option value="active">进行中</Select.Option>
                <Select.Option value="paused">暂停</Select.Option>
                <Select.Option value="completed">已完成</Select.Option>
              </Select>
            </Form.Item>
          )}
        </Form>
      </Modal>
    </div>
  );
};

export default CampaignPage;
