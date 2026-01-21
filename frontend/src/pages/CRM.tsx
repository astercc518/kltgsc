import React, { useEffect, useState } from 'react';
import {
  Table,
  Card,
  Button,
  Tag,
  Space,
  Select,
  Modal,
  Form,
  Input,
  message,
  Drawer,
  Descriptions,
  Timeline,
  Badge,
  Tabs,
  Row,
  Col,
  Statistic,
  Typography
} from 'antd';
import {
  UserOutlined,
  MessageOutlined,
  EditOutlined,
  ReloadOutlined,
  SendOutlined,
  PhoneOutlined,
  ClockCircleOutlined,
  CheckCircleOutlined,
  StarOutlined,
  FireOutlined
} from '@ant-design/icons';
import { getLeads, getLead, updateLead, sendLeadMessage, Lead, LeadInteraction } from '../services/api';

const { Option } = Select;
const { TextArea } = Input;
const { Text, Title } = Typography;

const CRM: React.FC = () => {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [loading, setLoading] = useState(false);
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  
  // Detail Drawer
  const [detailVisible, setDetailVisible] = useState(false);
  const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
  
  // Message Modal
  const [messageModalVisible, setMessageModalVisible] = useState(false);
  const [messageContent, setMessageContent] = useState('');
  const [sendingMessage, setSendingMessage] = useState(false);
  
  // Edit Modal
  const [editModalVisible, setEditModalVisible] = useState(false);
  const [editForm] = Form.useForm();
  const [editLoading, setEditLoading] = useState(false);

  const fetchLeads = async (page: number = 1, pageSize: number = 20) => {
    setLoading(true);
    try {
      const skip = (page - 1) * pageSize;
      const data = await getLeads(skip, pageSize, statusFilter);
      setLeads(data);
      setPagination(prev => ({ ...prev, current: page, pageSize, total: data.length + skip }));
    } catch (error) {
      message.error('获取线索列表失败');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchLeads();
  }, [statusFilter]);

  const getStatusTag = (status: string) => {
    const statusConfig: Record<string, { color: string; text: string }> = {
      new: { color: 'blue', text: '新线索' },
      contacted: { color: 'cyan', text: '已联系' },
      replied: { color: 'green', text: '已回复' },
      interested: { color: 'gold', text: '有意向' },
      converted: { color: 'green', text: '已转化' },
      closed: { color: 'default', text: '已关闭' },
    };
    const config = statusConfig[status] || { color: 'default', text: status };
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  const handleViewDetail = async (lead: Lead) => {
    setSelectedLead(lead);
    setDetailVisible(true);
  };

  const handleShowMessageModal = (lead: Lead) => {
    setSelectedLead(lead);
    setMessageContent('');
    setMessageModalVisible(true);
  };

  const handleSendMessage = async () => {
    if (!selectedLead || !messageContent.trim()) {
      message.warning('请输入消息内容');
      return;
    }
    setSendingMessage(true);
    try {
      await sendLeadMessage(selectedLead.id, messageContent);
      message.success('消息发送成功');
      setMessageModalVisible(false);
      setMessageContent('');
      fetchLeads(pagination.current, pagination.pageSize);
    } catch (error: any) {
      message.error(`发送失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setSendingMessage(false);
    }
  };

  const handleShowEditModal = (lead: Lead) => {
    setSelectedLead(lead);
    editForm.setFieldsValue({
      status: lead.status,
      notes: lead.notes,
      tags_json: lead.tags_json
    });
    setEditModalVisible(true);
  };

  const handleUpdateLead = async (values: any) => {
    if (!selectedLead) return;
    setEditLoading(true);
    try {
      await updateLead(selectedLead.id, values);
      message.success('更新成功');
      setEditModalVisible(false);
      fetchLeads(pagination.current, pagination.pageSize);
    } catch (error: any) {
      message.error(`更新失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setEditLoading(false);
    }
  };

  const parseTags = (tagsJson: string): string[] => {
    try {
      return JSON.parse(tagsJson);
    } catch {
      return [];
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: '用户名',
      key: 'username',
      render: (_: any, record: Lead) => (
        <Space>
          <UserOutlined />
          {record.username ? `@${record.username}` : record.first_name || `TG#${record.telegram_user_id}`}
        </Space>
      ),
    },
    {
      title: '姓名',
      key: 'name',
      render: (_: any, record: Lead) => 
        [record.first_name, record.last_name].filter(Boolean).join(' ') || '-',
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '标签',
      key: 'tags',
      width: 150,
      render: (_: any, record: Lead) => {
        const tags = parseTags(record.tags_json);
        return tags.length > 0 ? (
          <Space wrap>
            {tags.slice(0, 5).map(tag => {
                const isHighIntent = tag.includes('intent:inquiry') || tag.includes('intent:purchase');
                return (
                    <Tag key={tag} color={isHighIntent ? 'red' : 'default'} icon={isHighIntent ? <FireOutlined /> : null}>
                        {tag}
                    </Tag>
                );
            })}
            {tags.length > 5 && <Tag>+{tags.length - 5}</Tag>}
          </Space>
        ) : '-';
      },
    },
    {
      title: '最后互动',
      dataIndex: 'last_interaction_at',
      key: 'last_interaction_at',
      width: 160,
      render: (text: string) => text ? new Date(text).toLocaleString() : '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 160,
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: Lead) => (
        <Space>
          <Button
            size="small"
            icon={<MessageOutlined />}
            onClick={() => handleShowMessageModal(record)}
          >
            发消息
          </Button>
          <Button
            size="small"
            icon={<EditOutlined />}
            onClick={() => handleShowEditModal(record)}
          >
            编辑
          </Button>
          <Button
            size="small"
            onClick={() => handleViewDetail(record)}
          >
            详情
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={6}>
            <Statistic 
              title="全部线索" 
              value={leads.length} 
              prefix={<UserOutlined />}
            />
          </Col>
          <Col span={6}>
            <Statistic 
              title="新线索" 
              value={leads.filter(l => l.status === 'new').length} 
              valueStyle={{ color: '#1890ff' }}
            />
          </Col>
          <Col span={6}>
            <Statistic 
              title="有意向" 
              value={leads.filter(l => l.status === 'interested' || (l.tags_json && l.tags_json.includes('intent'))).length} 
              valueStyle={{ color: '#faad14' }}
              prefix={<StarOutlined />}
            />
          </Col>
          <Col span={6}>
            <Statistic 
              title="已转化" 
              value={leads.filter(l => l.status === 'converted').length} 
              valueStyle={{ color: '#52c41a' }}
              prefix={<CheckCircleOutlined />}
            />
          </Col>
        </Row>
      </Card>

      <Card>
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
          <Space>
            <Button 
              icon={<ReloadOutlined />} 
              onClick={() => fetchLeads(pagination.current, pagination.pageSize)}
            >
              刷新
            </Button>
          </Space>
          <Select
            style={{ width: 150 }}
            placeholder="筛选状态"
            allowClear
            value={statusFilter}
            onChange={(value) => {
              setStatusFilter(value);
              setPagination(prev => ({ ...prev, current: 1 }));
            }}
          >
            <Option value="new">新线索</Option>
            <Option value="contacted">已联系</Option>
            <Option value="replied">已回复</Option>
            <Option value="interested">有意向</Option>
            <Option value="converted">已转化</Option>
            <Option value="closed">已关闭</Option>
          </Select>
        </div>

        <Table
          columns={columns}
          dataSource={leads}
          rowKey="id"
          loading={loading}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: pagination.total,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) => {
              setPagination(prev => ({ ...prev, current: page, pageSize }));
              fetchLeads(page, pageSize);
            },
          }}
        />
      </Card>

      {/* Detail Drawer */}
      <Drawer
        title="线索详情"
        placement="right"
        onClose={() => setDetailVisible(false)}
        open={detailVisible}
        width={500}
      >
        {selectedLead && (
          <div>
            <Descriptions column={1} bordered size="small">
              <Descriptions.Item label="ID">{selectedLead.id}</Descriptions.Item>
              <Descriptions.Item label="Telegram ID">{selectedLead.telegram_user_id}</Descriptions.Item>
              <Descriptions.Item label="用户名">
                {selectedLead.username ? `@${selectedLead.username}` : '-'}
              </Descriptions.Item>
              <Descriptions.Item label="姓名">
                {[selectedLead.first_name, selectedLead.last_name].filter(Boolean).join(' ') || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="手机号">
                {selectedLead.phone || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="状态">
                {getStatusTag(selectedLead.status)}
              </Descriptions.Item>
              <Descriptions.Item label="标签">
                {parseTags(selectedLead.tags_json).map(tag => (
                  <Tag key={tag}>{tag}</Tag>
                ))}
              </Descriptions.Item>
              <Descriptions.Item label="备注">
                {selectedLead.notes || '-'}
              </Descriptions.Item>
              <Descriptions.Item label="创建时间">
                {new Date(selectedLead.created_at).toLocaleString()}
              </Descriptions.Item>
              <Descriptions.Item label="最后互动">
                {new Date(selectedLead.last_interaction_at).toLocaleString()}
              </Descriptions.Item>
            </Descriptions>

            <div style={{ marginTop: 24 }}>
              <Title level={5}>操作</Title>
              <Space>
                <Button 
                  type="primary" 
                  icon={<MessageOutlined />}
                  onClick={() => {
                    setDetailVisible(false);
                    handleShowMessageModal(selectedLead);
                  }}
                >
                  发送消息
                </Button>
                <Button 
                  icon={<EditOutlined />}
                  onClick={() => {
                    setDetailVisible(false);
                    handleShowEditModal(selectedLead);
                  }}
                >
                  编辑信息
                </Button>
              </Space>
            </div>
          </div>
        )}
      </Drawer>

      {/* Message Modal */}
      <Modal
        title={`发送消息给 ${selectedLead?.username ? '@' + selectedLead.username : selectedLead?.first_name || 'Unknown'}`}
        open={messageModalVisible}
        onCancel={() => setMessageModalVisible(false)}
        onOk={handleSendMessage}
        confirmLoading={sendingMessage}
        okText="发送"
      >
        <TextArea
          rows={4}
          value={messageContent}
          onChange={(e) => setMessageContent(e.target.value)}
          placeholder="输入消息内容..."
        />
      </Modal>

      {/* Edit Modal */}
      <Modal
        title="编辑线索信息"
        open={editModalVisible}
        onCancel={() => setEditModalVisible(false)}
        footer={null}
      >
        <Form form={editForm} onFinish={handleUpdateLead} layout="vertical">
          <Form.Item name="status" label="状态" rules={[{ required: true }]}>
            <Select>
              <Option value="new">新线索</Option>
              <Option value="contacted">已联系</Option>
              <Option value="replied">已回复</Option>
              <Option value="interested">有意向</Option>
              <Option value="converted">已转化</Option>
              <Option value="closed">已关闭</Option>
            </Select>
          </Form.Item>
          <Form.Item name="tags_json" label="标签 (JSON 格式)" help='例如: ["VIP", "crypto"]'>
            <Input placeholder='["tag1", "tag2"]' />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <TextArea rows={4} placeholder="添加跟进备注..." />
          </Form.Item>
          <Form.Item>
            <Button type="primary" htmlType="submit" loading={editLoading} block>
              保存
            </Button>
          </Form.Item>
        </Form>
      </Modal>
    </div>
  );
};

export default CRM;
