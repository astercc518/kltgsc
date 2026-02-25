import React, { useState, useEffect } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, Select, Tag, Space,
  Tabs, Statistic, Row, Col, message, Popconfirm, Switch, List, Typography
} from 'antd';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, BookOutlined,
  LinkOutlined, SearchOutlined, RobotOutlined
} from '@ant-design/icons';
import api from '../services/api';

const { TextArea } = Input;
const { Text, Paragraph } = Typography;

interface KnowledgeBase {
  id: number;
  name: string;
  description?: string;
  content: string;
  auto_update: boolean;
  source_url?: string;
  created_at: string;
  updated_at: string;
}

interface Campaign {
  id: number;
  name: string;
  status: string;
}

const KnowledgeBasePage: React.FC = () => {
  const [knowledgeBases, setKnowledgeBases] = useState<KnowledgeBase[]>([]);
  const [campaigns, setCampaigns] = useState<Campaign[]>([]);
  const [loading, setLoading] = useState(false);
  const [modalVisible, setModalVisible] = useState(false);
  const [editingKB, setEditingKB] = useState<KnowledgeBase | null>(null);
  const [previewKB, setPreviewKB] = useState<KnowledgeBase | null>(null);
  const [previewVisible, setPreviewVisible] = useState(false);
  const [linkedCampaigns, setLinkedCampaigns] = useState<Campaign[]>([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<any[]>([]);
  const [form] = Form.useForm();

  useEffect(() => {
    fetchKnowledgeBases();
    fetchCampaigns();
  }, []);

  const fetchKnowledgeBases = async () => {
    setLoading(true);
    try {
      const res = await api.get('/knowledge-bases/');
      setKnowledgeBases(res.data);
    } catch (e) {
      message.error('获取知识库列表失败');
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
    setEditingKB(null);
    form.resetFields();
    setModalVisible(true);
  };

  const handleEdit = (record: KnowledgeBase) => {
    setEditingKB(record);
    form.setFieldsValue(record);
    setModalVisible(true);
  };

  const handleSubmit = async (values: any) => {
    try {
      if (editingKB) {
        await api.put(`/knowledge-bases/${editingKB.id}`, values);
        message.success('更新成功');
      } else {
        await api.post('/knowledge-bases/', values);
        message.success('创建成功');
      }
      setModalVisible(false);
      fetchKnowledgeBases();
    } catch (e) {
      message.error('操作失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await api.delete(`/knowledge-bases/${id}`);
      message.success('删除成功');
      fetchKnowledgeBases();
    } catch (e) {
      message.error('删除失败');
    }
  };

  const handlePreview = async (record: KnowledgeBase) => {
    setPreviewKB(record);
    setPreviewVisible(true);
    try {
      const res = await api.get(`/knowledge-bases/${record.id}/campaigns`);
      setLinkedCampaigns(res.data);
    } catch (e) {
      setLinkedCampaigns([]);
    }
  };

  const handleLinkCampaign = async (kbId: number, campaignId: number) => {
    try {
      await api.post(`/knowledge-bases/${kbId}/link-campaign/${campaignId}`);
      message.success('关联成功');
      handlePreview(previewKB!);
    } catch (e) {
      message.error('关联失败');
    }
  };

  const handleUnlinkCampaign = async (kbId: number, campaignId: number) => {
    try {
      await api.delete(`/knowledge-bases/${kbId}/unlink-campaign/${campaignId}`);
      message.success('取消关联成功');
      handlePreview(previewKB!);
    } catch (e) {
      message.error('操作失败');
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      message.warning('请输入搜索关键词');
      return;
    }
    try {
      const res = await api.get('/knowledge-bases/search/content', {
        params: { query: searchQuery }
      });
      setSearchResults(res.data);
    } catch (e) {
      message.error('搜索失败');
    }
  };

  const handleTestRAG = async (kbId: number) => {
    const question = prompt('输入测试问题:');
    if (!question) return;
    
    try {
      // 先搜索知识库内容
      const searchRes = await api.get('/knowledge-bases/search/content', {
        params: { query: question }
      });
      
      if (searchRes.data.length === 0) {
        message.warning('知识库中没有找到相关内容');
        return;
      }
      
      // 使用AI生成回复
      const knowledge = searchRes.data.map((r: any) => r.snippet).join('\n\n');
      const res = await api.post('/ai/engine/generate-reply', {
        conversation: [{ role: 'user', content: question }],
        knowledge: knowledge
      });
      
      Modal.info({
        title: 'RAG 测试结果',
        width: 600,
        content: (
          <div>
            <p><strong>问题：</strong>{question}</p>
            <p><strong>检索到的知识：</strong></p>
            <pre style={{ background: '#f5f5f5', padding: 8, fontSize: 12, maxHeight: 150, overflow: 'auto' }}>
              {knowledge}
            </pre>
            <p><strong>AI 回复：</strong></p>
            <p style={{ background: '#e6f7ff', padding: 12, borderRadius: 4 }}>{res.data.reply}</p>
          </div>
        )
      });
    } catch (e) {
      message.error('测试失败');
    }
  };

  const columns = [
    {
      title: '名称',
      dataIndex: 'name',
      key: 'name',
      render: (text: string, record: KnowledgeBase) => (
        <a onClick={() => handlePreview(record)}>
          <BookOutlined style={{ marginRight: 8 }} />
          {text}
        </a>
      )
    },
    {
      title: '描述',
      dataIndex: 'description',
      key: 'description',
      ellipsis: true
    },
    {
      title: '内容长度',
      key: 'length',
      render: (_: any, record: KnowledgeBase) => (
        <Tag>{record.content.length} 字符</Tag>
      )
    },
    {
      title: '自动更新',
      dataIndex: 'auto_update',
      key: 'auto_update',
      render: (v: boolean) => v ? <Tag color="green">开启</Tag> : <Tag>关闭</Tag>
    },
    {
      title: '更新时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      render: (text: string) => new Date(text).toLocaleString()
    },
    {
      title: '操作',
      key: 'action',
      render: (_: any, record: KnowledgeBase) => (
        <Space>
          <Button
            type="link"
            icon={<RobotOutlined />}
            onClick={() => handleTestRAG(record.id)}
          >
            测试RAG
          </Button>
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

  return (
    <div>
      <Row gutter={16} style={{ marginBottom: 16 }}>
        <Col span={6}>
          <Card>
            <Statistic
              title="知识库总数"
              value={knowledgeBases.length}
              prefix={<BookOutlined />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic
              title="总字符数"
              value={knowledgeBases.reduce((sum, kb) => sum + kb.content.length, 0)}
            />
          </Card>
        </Col>
        <Col span={12}>
          <Card>
            <Space.Compact style={{ width: '100%' }}>
              <Input
                placeholder="搜索知识库内容..."
                value={searchQuery}
                onChange={e => setSearchQuery(e.target.value)}
                onPressEnter={handleSearch}
              />
              <Button type="primary" icon={<SearchOutlined />} onClick={handleSearch}>
                搜索
              </Button>
            </Space.Compact>
            {searchResults.length > 0 && (
              <List
                size="small"
                style={{ marginTop: 8, maxHeight: 150, overflow: 'auto' }}
                dataSource={searchResults}
                renderItem={item => (
                  <List.Item>
                    <Text strong>{item.name}:</Text> {item.snippet}
                  </List.Item>
                )}
              />
            )}
          </Card>
        </Col>
      </Row>

      <Card
        title="知识库管理"
        extra={
          <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
            创建知识库
          </Button>
        }
      >
        <Table
          columns={columns}
          dataSource={knowledgeBases}
          rowKey="id"
          loading={loading}
        />
      </Card>

      {/* 创建/编辑弹窗 */}
      <Modal
        title={editingKB ? '编辑知识库' : '创建知识库'}
        open={modalVisible}
        onCancel={() => setModalVisible(false)}
        onOk={() => form.submit()}
        width={800}
      >
        <Form form={form} layout="vertical" onFinish={handleSubmit}>
          <Row gutter={16}>
            <Col span={12}>
              <Form.Item
                name="name"
                label="名称"
                rules={[{ required: true, message: '请输入名称' }]}
              >
                <Input placeholder="如：产品FAQ" />
              </Form.Item>
            </Col>
            <Col span={12}>
              <Form.Item name="source_url" label="来源URL">
                <Input placeholder="可选，用于自动更新" />
              </Form.Item>
            </Col>
          </Row>

          <Form.Item name="description" label="描述">
            <Input placeholder="简短描述知识库内容" />
          </Form.Item>

          <Form.Item
            name="content"
            label="知识内容 (Markdown)"
            rules={[{ required: true, message: '请输入内容' }]}
          >
            <TextArea
              rows={15}
              placeholder={`# 产品FAQ

## 什么是我们的产品？
我们的产品是...

## 如何注册？
1. 访问官网
2. 点击注册
3. 填写信息

## 费用是多少？
基础版免费，高级版每月$99`}
            />
          </Form.Item>

          <Form.Item
            name="auto_update"
            label="自动更新"
            valuePropName="checked"
          >
            <Switch checkedChildren="开启" unCheckedChildren="关闭" />
          </Form.Item>
        </Form>
      </Modal>

      {/* 预览弹窗 */}
      <Modal
        title={`知识库详情: ${previewKB?.name}`}
        open={previewVisible}
        onCancel={() => setPreviewVisible(false)}
        footer={null}
        width={800}
      >
        {previewKB && (
          <Tabs
            items={[
              {
                key: 'content',
                label: '内容预览',
                children: (
                  <div>
                    <Paragraph>{previewKB.description}</Paragraph>
                    <pre style={{
                      background: '#f5f5f5',
                      padding: 16,
                      borderRadius: 4,
                      maxHeight: 400,
                      overflow: 'auto',
                      whiteSpace: 'pre-wrap'
                    }}>
                      {previewKB.content}
                    </pre>
                  </div>
                )
              },
              {
                key: 'campaigns',
                label: `关联战役 (${linkedCampaigns.length})`,
                children: (
                  <div>
                    <div style={{ marginBottom: 16 }}>
                      <Select
                        style={{ width: 200 }}
                        placeholder="选择战役关联"
                        onChange={(v) => handleLinkCampaign(previewKB.id, v)}
                      >
                        {campaigns
                          .filter(c => !linkedCampaigns.some(lc => lc.id === c.id))
                          .map(c => (
                            <Select.Option key={c.id} value={c.id}>{c.name}</Select.Option>
                          ))}
                      </Select>
                    </div>
                    <List
                      dataSource={linkedCampaigns}
                      renderItem={c => (
                        <List.Item
                          actions={[
                            <Button
                              type="link"
                              danger
                              onClick={() => handleUnlinkCampaign(previewKB.id, c.id)}
                            >
                              取消关联
                            </Button>
                          ]}
                        >
                          <List.Item.Meta
                            avatar={<LinkOutlined />}
                            title={c.name}
                            description={`状态: ${c.status}`}
                          />
                        </List.Item>
                      )}
                    />
                  </div>
                )
              }
            ]}
          />
        )}
      </Modal>
    </div>
  );
};

export default KnowledgeBasePage;
