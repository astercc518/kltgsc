import React, { useState, useEffect } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, Select, Tag, Space,
  Tabs, Statistic, Row, Col, message, Popconfirm, Upload, Progress
} from 'antd';
import {
  PlusOutlined, DeleteOutlined, SearchOutlined, UploadOutlined,
  AimOutlined, TeamOutlined, RadarChartOutlined, RobotOutlined
} from '@ant-design/icons';
import api from '../services/api';

interface SourceGroup {
  id: number;
  link: string;
  name?: string;
  type: string;
  risk_level: string;
  status: string;
  member_count: number;
  total_scraped: number;
  high_value_count: number;
  ai_score?: number;
  ai_analysis?: string;
  last_scraped_at?: string;
  created_at: string;
}

interface Account {
  id: number;
  phone_number: string;
  status: string;
  combat_role: string;
}

const SourceGroupPage: React.FC = () => {
  const [groups, setGroups] = useState<SourceGroup[]>([]);
  const [loading, setLoading] = useState(false);
  const [scoutAccounts, setScoutAccounts] = useState<Account[]>([]);
  const [scrapeModalVisible, setScrapeModalVisible] = useState(false);
  const [selectedGroupForScrape, setSelectedGroupForScrape] = useState<SourceGroup | null>(null);
  const [selectedAccountId, setSelectedAccountId] = useState<number | null>(null);
  const [scrapeLoading, setScrapeLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [batchModalVisible, setBatchModalVisible] = useState(false);
  const [selectedType, setSelectedType] = useState<string | null>(null);
  const [stats, setStats] = useState<any>(null);
  const [form] = Form.useForm();
  const [batchForm] = Form.useForm();

  useEffect(() => {
    fetchGroups();
    fetchStats();
  }, [selectedType]);

  const fetchGroups = async () => {
    setLoading(true);
    try {
      const params: any = {};
      if (selectedType) params.type = selectedType;
      const res = await api.get('/source-groups/', { params });
      setGroups(res.data);
    } catch (e) {
      message.error('获取列表失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await api.get('/source-groups/stats/summary');
      setStats(res.data);
    } catch (e) {
      console.error('获取统计失败');
    }
  };

  const handleCreate = async (values: any) => {
    try {
      await api.post('/source-groups/', values);
      message.success('添加成功');
      setModalVisible(false);
      form.resetFields();
      fetchGroups();
      fetchStats();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '添加失败');
    }
  };

  const handleBatchCreate = async (values: any) => {
    try {
      const links = values.links.split('\n').filter((l: string) => l.trim());
      const res = await api.post('/source-groups/batch', links, {
        params: { type: values.type }
      });
      message.success(`成功添加 ${res.data.created} 个，跳过 ${res.data.skipped} 个`);
      setBatchModalVisible(false);
      batchForm.resetFields();
      fetchGroups();
      fetchStats();
    } catch (e) {
      message.error('批量添加失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/source-groups/${id}`);
      message.success('删除成功');
      fetchGroups();
      fetchStats();
    } catch (e) {
      message.error('删除失败');
    }
  };

  const fetchScoutAccounts = async () => {
    try {
      // 优先获取scout角色账号，否则获取所有活跃账号
      const res = await api.get('/accounts/', { params: { status: 'active', limit: 100 } });
      const scouts = res.data.filter((a: Account) => a.combat_role === 'scout' || a.combat_role === 'cannon');
      setScoutAccounts(scouts.length > 0 ? scouts : res.data);
    } catch (e) {
      console.error('获取账号失败');
    }
  };

  const handleOpenScrapeModal = (group: SourceGroup) => {
    setSelectedGroupForScrape(group);
    fetchScoutAccounts();
    setScrapeModalVisible(true);
  };

  const handleScrape = async () => {
    if (!selectedGroupForScrape || !selectedAccountId) {
      message.warning('请选择采集账号');
      return;
    }
    
    setScrapeLoading(true);
    try {
      const res = await api.post(`/scraping/source-group/${selectedGroupForScrape.id}/scrape`, null, {
        params: {
          account_id: selectedAccountId,
          limit: 500,
          filter_has_username: true
        }
      });
      message.success(`采集成功！新增 ${res.data.new_saved} 个用户，高价值 ${res.data.high_value} 个`);
      setScrapeModalVisible(false);
      fetchGroups();
      fetchStats();
    } catch (e: any) {
      message.error(e.response?.data?.detail || '采集失败');
    } finally {
      setScrapeLoading(false);
    }
  };

  const getTypeTag = (type: string) => {
    const config: Record<string, { color: string; label: string }> = {
      competitor: { color: 'red', label: '竞品群' },
      industry: { color: 'blue', label: '行业群' },
      traffic: { color: 'green', label: '泛流量' }
    };
    const c = config[type] || { color: 'default', label: type };
    return <Tag color={c.color}>{c.label}</Tag>;
  };

  const getStatusTag = (status: string) => {
    const config: Record<string, { color: string; label: string }> = {
      active: { color: 'green', label: '活跃' },
      exhausted: { color: 'orange', label: '已耗尽' },
      banned: { color: 'red', label: '被封' },
      honeypot: { color: 'purple', label: '蜜罐' }
    };
    const c = config[status] || { color: 'default', label: status };
    return <Tag color={c.color}>{c.label}</Tag>;
  };

  const getRiskTag = (level: string) => {
    const config: Record<string, { color: string; label: string }> = {
      low: { color: 'green', label: '低风险' },
      medium: { color: 'orange', label: '中风险' },
      high: { color: 'red', label: '高风险' }
    };
    const c = config[level] || { color: 'default', label: level };
    return <Tag color={c.color}>{c.label}</Tag>;
  };

  const columns = [
    {
      title: '群链接/名称',
      key: 'info',
      render: (_: any, record: SourceGroup) => (
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
      render: (type: string) => getTypeTag(type)
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (status: string) => getStatusTag(status)
    },
    {
      title: '风险',
      dataIndex: 'risk_level',
      key: 'risk_level',
      render: (level: string) => getRiskTag(level)
    },
    {
      title: '成员数',
      dataIndex: 'member_count',
      key: 'member_count',
      sorter: (a: SourceGroup, b: SourceGroup) => a.member_count - b.member_count
    },
    {
      title: '已采集',
      key: 'scraped',
      render: (_: any, record: SourceGroup) => (
        <div style={{ display: 'flex', flexDirection: 'column' }}>
          <span>总计: {record.total_scraped}</span>
          <span style={{ color: '#52c41a', fontSize: 12 }}>
            高价值: {record.high_value_count}
          </span>
        </div>
      )
    },
    {
      title: 'AI评分',
      dataIndex: 'ai_score',
      key: 'ai_score',
      render: (score: number) => score ? (
        <Progress 
          type="circle" 
          percent={score} 
          width={40}
          format={p => p}
          strokeColor={score >= 70 ? '#52c41a' : score >= 40 ? '#faad14' : '#ff4d4f'}
        />
      ) : <Tag>未评估</Tag>
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: SourceGroup) => (
        <Space>
          <Button
            type="link"
            icon={<SearchOutlined />}
            onClick={() => handleOpenScrapeModal(record)}
          >
            采集
          </Button>
          <Button
            type="link"
            icon={<RobotOutlined />}
            disabled={!record.total_scraped}
          >
            AI分析
          </Button>
          <Popconfirm
            title="确定删除？"
            onConfirm={() => handleDelete(record.id)}
          >
            <Button type="link" danger icon={<DeleteOutlined />} />
          </Popconfirm>
        </Space>
      )
    }
  ];

  return (
    <div>
      {/* 统计卡片 */}
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="总流量源"
              value={stats?.total_groups || 0}
              prefix={<RadarChartOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card onClick={() => setSelectedType('competitor')} style={{ cursor: 'pointer' }}>
            <Statistic
              title="竞品群"
              value={stats?.by_type?.competitor?.count || 0}
              styles={{ content: { color: '#cf1322' } }}
              prefix={<AimOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card onClick={() => setSelectedType('industry')} style={{ cursor: 'pointer' }}>
            <Statistic
              title="行业群"
              value={stats?.by_type?.industry?.count || 0}
              styles={{ content: { color: '#1890ff' } }}
              prefix={<TeamOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card onClick={() => setSelectedType('traffic')} style={{ cursor: 'pointer' }}>
            <Statistic
              title="泛流量"
              value={stats?.by_type?.traffic?.count || 0}
              styles={{ content: { color: '#52c41a' } }}
              prefix={<TeamOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Card
        title={
          <Space>
            <span>流量源管理</span>
            {selectedType && (
              <Tag 
                closable 
                onClose={() => setSelectedType(null)}
                color="blue"
              >
                {selectedType === 'competitor' ? '竞品群' : 
                 selectedType === 'industry' ? '行业群' : '泛流量'}
              </Tag>
            )}
          </Space>
        }
        extra={
          <Space>
            <Button 
              icon={<UploadOutlined />}
              onClick={() => setBatchModalVisible(true)}
            >
              批量导入
            </Button>
            <Button 
              type="primary" 
              icon={<PlusOutlined />}
              onClick={() => setModalVisible(true)}
            >
              添加群组
            </Button>
          </Space>
        }
      >
        <Table
          columns={columns}
          dataSource={groups}
          rowKey="id"
          loading={loading}
        />
      </Card>

      {/* 添加单个群组 */}
      <Modal
        title="添加流量源"
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
      >
        <Form form={form} layout="vertical" onFinish={handleCreate}>
          <Form.Item
            name="link"
            label="群链接"
            rules={[{ required: true, message: '请输入群链接' }]}
          >
            <Input placeholder="https://t.me/xxx 或 @xxx" />
          </Form.Item>
          <Form.Item name="name" label="群名称">
            <Input placeholder="可选，便于识别" />
          </Form.Item>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item name="type" label="类型" initialValue="traffic">
                <Select>
                  <Select.Option value="competitor">竞品群</Select.Option>
                  <Select.Option value="industry">行业群</Select.Option>
                  <Select.Option value="traffic">泛流量</Select.Option>
                </Select>
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="risk_level" label="风险等级" initialValue="low">
                <Select>
                  <Select.Option value="low">低风险</Select.Option>
                  <Select.Option value="medium">中风险</Select.Option>
                  <Select.Option value="high">高风险</Select.Option>
                </Select>
              </Form.Item>
            </Col>
          </Row>
        </Form>
      </Modal>

      {/* 批量导入 */}
      <Modal
        title="批量导入流量源"
        open={batchModalVisible}
        onCancel={() => setBatchModalVisible(false)}
        onOk={() => batchForm.submit()}
        width={600}
      >
        <Form form={batchForm} layout="vertical" onFinish={handleBatchCreate}>
          <Form.Item
            name="links"
            label="群链接列表（每行一个）"
            rules={[{ required: true, message: '请输入群链接' }]}
          >
            <Input.TextArea 
              rows={10} 
              placeholder="https://t.me/group1&#10;https://t.me/group2&#10;@group3" 
            />
          </Form.Item>
          <Form.Item name="type" label="统一类型" initialValue="traffic">
            <Select>
              <Select.Option value="competitor">竞品群</Select.Option>
              <Select.Option value="industry">行业群</Select.Option>
              <Select.Option value="traffic">泛流量</Select.Option>
            </Select>
          </Form.Item>
        </Form>
      </Modal>

      {/* 采集弹窗 */}
      <Modal
        title={`采集成员 - ${selectedGroupForScrape?.name || selectedGroupForScrape?.link}`}
        open={scrapeModalVisible}
        onCancel={() => setScrapeModalVisible(false)}
        onOk={handleScrape}
        confirmLoading={scrapeLoading}
        okText="开始采集"
      >
        <div style={{ marginBottom: 16 }}>
          <p>将使用选定账号从该群组采集成员信息</p>
        </div>
        
        <Form layout="vertical">
          <Form.Item label="选择采集账号（推荐使用侦察组）" required>
            <Select
              placeholder="选择账号"
              value={selectedAccountId}
              onChange={setSelectedAccountId}
              showSearch
              optionFilterProp="children"
            >
              {scoutAccounts.map(acc => (
                <Select.Option key={acc.id} value={acc.id}>
                  {acc.phone_number} 
                  <Tag color={acc.combat_role === 'scout' ? 'blue' : 'red'} style={{ marginLeft: 8 }}>
                    {acc.combat_role === 'scout' ? '侦察' : '炮灰'}
                  </Tag>
                </Select.Option>
              ))}
            </Select>
          </Form.Item>
        </Form>

        <div style={{ fontSize: 12, color: '#888', marginTop: 16 }}>
          <p>采集说明：</p>
          <ul style={{ paddingLeft: 16 }}>
            <li>将采集最多500个成员信息</li>
            <li>自动过滤无用户名的用户</li>
            <li>新用户将保存到目标用户池</li>
            <li>统计数据将自动更新</li>
          </ul>
        </div>
      </Modal>
    </div>
  );
};

export default SourceGroupPage;
