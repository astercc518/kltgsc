import React, { useState, useEffect } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, Select, Tag, Space,
  Tabs, Statistic, Row, Col, message, Popconfirm, Switch
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, EditOutlined,
  TeamOutlined, FilterOutlined, CrownOutlined, HomeOutlined
} from '@ant-design/icons';
import api from '../services/api';

interface FunnelGroup {
  id: number;
  link: string;
  name?: string;
  type: string;
  campaign_id?: number;
  welcome_message?: string;
  auto_kick_ads: boolean;
  member_count: number;
  today_joined: number;
  today_left: number;
  created_at: string;
}

interface Campaign {
  id: number;
  name: string;
}

const FunnelGroupPage: React.FC = () => {
  const [groups, setGroups] = useState<FunnelGroup[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingGroup, setEditingGroup] = useState<FunnelGroup | null>(null);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchGroups();
    fetchCampaigns();
  }, [selectedType]);

  const fetchGroups = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (selectedType) params.type = selectedType;
      const res = await api.get('/funnel-groups/', { params });
      setGroups(res.data);
    } catch (e) {
      message.error('获取列表失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchCampaigns = async () => {
    try {
      const res = await api.get('/campaigns/');
      setCampaigns(res.data);
    } catch (e) {
      console.error('获取战役列表失败');
    }
  };

  const handleCreate = () => {
    setEditingGroup(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (record: FunnelGroup) => {
    setEditingGroup(record);
    form.setFieldsValue(record);
    setModalVisible(true);
  };

  const handleSubmit = async (values: any) => {
    try {
      if (editingGroup) {
        await api.put(`/funnel-groups/${editingGroup.id}`, values);
        message.success('更新成功');
      } else {
        await api.post('/funnel-groups/', values);
        message.success('创建成功');
      }
      setModalVisible(false);
      fetchGroups();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '操作失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/funnel-groups/${id}`);
      message.success('删除成功');
      fetchGroups();
    } catch (e) {
      message.error('删除失败');
    }
  };

  const getTypeConfig = (type: string) => {
    const config: Record<string, { color: string; label: string; icon: React.ReactNode }> = {
      filter: { color: 'blue', label: '过滤群', icon: <FilterOutlined /> },
      nurture: { color: 'green', label: '养鱼群', icon: <HomeOutlined /> },
      vip: { color: 'gold', label: 'VIP群', icon: <CrownOutlined /> }
    };
    return config[type] || { color: 'default', label: type, icon: null };
  };

  const columns = [
    {
      title: '群名称/链接',
      key: 'info',
      render: (_: any, record: FunnelGroup) => (
        <div>
          <div style={{ fontWeight: 500 }}>{record.name || '未命名'}</div>
          <div style={{ fontSize: 12, color: '#999' }}>{record.link}</div>
        </div>
      )
    },
    {
      title: '类型',
      dataIndex: 'type',
      key: 'type',
      render: (type: string) => {
        const c = getTypeConfig(type);
        return <Tag color={c.color} icon={c.icon}>{c.label}</Tag>;
      }
    },
    {
      title: '关联战役',
      dataIndex: 'campaign_id',
      key: 'campaign_id',
      render: (id: number) => {
        const campaign = campaigns.find(c => c.id === id);
        return campaign ? <Tag color="purple">{campaign.name}</Tag> : <Tag>未关联</Tag>;
      }
    },
    {
      title: '成员数',
      dataIndex: 'member_count',
      key: 'member_count',
      sorter: (a: FunnelGroup, b: FunnelGroup) => a.member_count - b.member_count
    },
    {
      title: '今日变化',
      key: 'change',
      render: (_: any, record: FunnelGroup) => {
        const net = record.today_joined - record.today_left;
        return (
          <Space>
            <span style={{ color: '#52c41a' }}>+{record.today_joined}</span>
            <span style={{ color: '#ff4d4f' }}>-{record.today_left}</span>
            <span style={{ color: net >= 0 ? '#52c41a' : '#ff4d4f', fontWeight: 'bold' }}>
              ({net >= 0 ? '+' : ''}{net})
            </span>
          </Space>
        );
      }
    },
    {
      title: '自动踢广告',
      dataIndex: 'auto_kick_ads',
      key: 'auto_kick_ads',
      render: (v: boolean) => v ? <Tag color="green">开启</Tag> : <Tag>关闭</Tag>
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: FunnelGroup) => (
        <Space>
          <Button
            type="link"
            icon={<EditOutlined />}
            onClick={() => handleEdit(record)}
          >
            编辑
          </Button>
          <Popconfirm
            title="确定删除？"
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

  // 统计
  const stats = {
    total: groups.length,
    filter: groups.filter(g => g.type === 'filter').length,
    nurture: groups.filter(g => g.type === 'nurture').length,
    vip: groups.filter(g => g.type === 'vip').length,
    totalMembers: groups.reduce((sum, g) => sum + g.member_count, 0),
    todayGrowth: groups.reduce((sum, g) => sum + g.today_joined - g.today_left, 0)
  };

  return (
    <div>
      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={4}>
          <Card>
            <Statistic
              title="总群数"
              value={stats.total}
              prefix={<TeamOutlined />}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card onClick={() => setSelectedType('filter')} style={{ cursor: 'pointer' }}>
            <Statistic
              title="过滤群"
              value={stats.filter}
              styles={{ content: { color: '#1890ff' } }}
              prefix={<FilterOutlined />}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card onClick={() => setSelectedType('nurture')} style={{ cursor: 'pointer' }}>
            <Statistic
              title="养鱼群"
              value={stats.nurture}
              styles={{ content: { color: '#52c41a' } }}
              prefix={<HomeOutlined />}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card onClick={() => setSelectedType('vip')} style={{ cursor: 'pointer' }}>
            <Statistic
              title="VIP群"
              value={stats.vip}
              styles={{ content: { color: '#faad14' } }}
              prefix={<CrownOutlined />}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="总成员"
              value={stats.totalMembers}
            />
          </Card>
        </Col>
        <Col span={4}>
          <Card>
            <Statistic
              title="今日净增"
              value={stats.todayGrowth}
              styles={{ content: { color: stats.todayGrowth >= 0 ? '#52c41a' : '#ff4d4f' } }}
              prefix={stats.todayGrowth >= 0 ? '+' : ''}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title={
          <Space>
            <span>营销群管理 (私塘)</span>
            {selectedType && (
              <Tag
                closable
                onClose={() => setSelectedType(null)}
                color="blue"
              >
                {getTypeConfig(selectedType).label}
              </Tag>
            )}
          </Space>
        }
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            添加群组
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={groups}
          rowKey="id"
          loading={loading}
        />
      </Card>

      {/* 创建/编辑弹窗 */}
      <Modal
        title={editingGroup ? '编辑营销群' : '添加营销群'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
        width={600}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Form.Item
            name="link"
            label="群链接"
            rules={[{ required: true, message: '请输入群链接' }]}
          >
            <Input placeholder="https://t.me/xxx 或 @xxx" />
          </Form.Item>

          <Form.Item name="name" label="群名称">
            <Input placeholder="便于识别的名称" />
          </Form.Item>

          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="type" label="群组类型" initialValue="nurture">
                <Select>
                  <Select.Option value="filter">
                    <FilterOutlined /> 过滤群 - 验证真人
                  </Select.Option>
                  <Select.Option value="nurture">
                    <HomeOutlined /> 养鱼群 - 培育信任
                  </Select.Option>
                  <Select.Option value="vip">
                    <CrownOutlined /> VIP群 - 付费服务
                  </Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="campaign_id" label="关联战役">
                <Select allowClear placeholder="选择关联的战役">
                  {campaigns.map(c => (
                    <Select.Option key={c.id} value={c.id}>{c.name}</Select.Option>
                  ))}
                </Select>
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="welcome_message" label="入群欢迎语">
            <Input.TextArea
              rows={3}
              placeholder="新成员加入时自动发送的消息"
            />
          </Form.Item>

          <Form.Item
            name="auto_kick_ads"
            label="自动踢广告"
            valuePropName="checked"
            initialValue={true}
          >
            <Switch checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default FunnelGroupPage;
