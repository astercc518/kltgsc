import React, { useState, useEffect, useRef } from 'react';
import {
  Card, Table, Button, Modal, Form, Input, Select, Tag, Space,
  Tabs, Statistic, Row, Col, message, Popconfirm, Switch, List, Typography,
  Upload
} from 'antd';
import type { UploadFile } from 'antd/es/upload/interface';
import {
  PlusOutlined, EditOutlined, DeleteOutlined, BookOutlined,
  LinkOutlined, SearchOutlined, RobotOutlined, CloudDownloadOutlined,
  ThunderboltOutlined, ReloadOutlined, InboxOutlined, FilePdfOutlined
} from '@ant-design/icons';
import api, {
  triggerScrapeAccountGroups, getScrapeStatus, getScrapedMessagesStats,
  triggerExtractQA, ScrapeStatus, ChatMessageStat,
  importKnowledgeFile, getKnowledgeImportStatus, KnowledgeImportStatus
} from '../services/api';

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
  const [generating, setGenerating] = useState(false);
  const [form] = Form.useForm();

  // ── 群组采集 / Q&A 抽取 ──
  const [scrapeModalVisible, setScrapeModalVisible] = useState(false);
  const [scrapeForm] = Form.useForm();
  const [accounts, setAccounts] = useState<{ id: number; phone_number: string; status: string }[]>([]);
  const [scrapeStatus, setScrapeStatus] = useState<ScrapeStatus | null>(null);
  const [scrapeStatusId, setScrapeStatusId] = useState<number | null>(null);
  const [chatStats, setChatStats] = useState<ChatMessageStat[]>([]);

  // ── 文档批量导入 ──
  const [importFileList, setImportFileList] = useState<UploadFile[]>([]);
  const [importCategory, setImportCategory] = useState<string>('');
  const [importing, setImporting] = useState(false);
  const [importJobs, setImportJobs] = useState<Record<string, KnowledgeImportStatus & { filename: string }>>({});
  const importPollRef = useRef<number | null>(null);

  useEffect(() => {
    api.get('/accounts/').then(r => {
      setAccounts((r.data || []).filter((a: any) => a.status === 'active'));
    }).catch(() => {});
    refreshChatStats();
  }, []);

  // 轮询采集进度
  useEffect(() => {
    if (!scrapeStatusId) return;
    const tick = async () => {
      try {
        const s = await getScrapeStatus(scrapeStatusId);
        setScrapeStatus(s);
        if (s.status === 'completed' || s.status === 'failed') {
          refreshChatStats();
          if (s.status === 'completed') {
            message.success(`任务完成：处理 ${s.progress.processed_chats || s.progress.windows_processed || 0} 项`);
          } else {
            message.error(`任务失败：${s.error_message}`);
          }
          setScrapeStatusId(null);
        }
      } catch (e) {
        // ignore
      }
    };
    const id = setInterval(tick, 3000);
    tick();
    return () => clearInterval(id);
  }, [scrapeStatusId]);

  // 轮询导入任务进度（活动中的任务才轮询）
  useEffect(() => {
    const activeJobs = Object.values(importJobs).filter(j => !j.ready);
    if (activeJobs.length === 0) {
      if (importPollRef.current) {
        clearInterval(importPollRef.current);
        importPollRef.current = null;
      }
      return;
    }
    if (importPollRef.current) return;
    importPollRef.current = window.setInterval(async () => {
      const pending = Object.values(importJobs).filter(j => !j.ready);
      for (const job of pending) {
        try {
          const status = await getKnowledgeImportStatus(job.task_id);
          setImportJobs(prev => ({
            ...prev,
            [job.task_id]: { ...status, filename: job.filename },
          }));
          if (status.ready) {
            const res = status.result || {};
            if (res.ok) {
              message.success(`${job.filename} 导入完成，共写入 ${res.chunks} 个 chunk`);
              fetchKnowledgeBases();
            } else if (res.error) {
              message.error(`${job.filename} 导入失败：${res.error}${res.hint ? '（' + res.hint + '）' : ''}`);
            }
          }
        } catch (e) {
          // ignore single tick error
        }
      }
    }, 3000);
    return () => {
      if (importPollRef.current) {
        clearInterval(importPollRef.current);
        importPollRef.current = null;
      }
    };
  }, [importJobs]);

  const handleImportSubmit = async () => {
    if (importFileList.length === 0) {
      message.warning('请先选择 PDF 文件');
      return;
    }
    setImporting(true);
    try {
      for (const fileWrapper of importFileList) {
        const file = fileWrapper.originFileObj as File | undefined;
        if (!file) continue;
        try {
          const res = await importKnowledgeFile(file, importCategory || undefined);
          setImportJobs(prev => ({
            ...prev,
            [res.task_id]: {
              task_id: res.task_id,
              state: 'PENDING',
              ready: false,
              filename: res.filename,
            },
          }));
          message.success(`已提交：${res.filename}（task=${res.task_id.slice(0, 8)}...）`);
        } catch (e: any) {
          message.error(`${file.name} 提交失败：${e?.response?.data?.detail || e.message}`);
        }
      }
      setImportFileList([]);
    } finally {
      setImporting(false);
    }
  };

  const refreshChatStats = async () => {
    try {
      const stats = await getScrapedMessagesStats();
      setChatStats(stats);
    } catch (e) {
      // ignore
    }
  };

  const handleScrapeSubmit = async (values: any) => {
    try {
      const res = await triggerScrapeAccountGroups(values.account_id, {
        include_private: values.include_private,
        limit_per_chat: values.limit_per_chat || null,
        chat_sleep_sec: values.chat_sleep_sec || 2.0,
      });
      message.success(`采集任务已启动（ID: ${res.scraping_task_id}）`);
      setScrapeStatusId(res.scraping_task_id);
      setScrapeModalVisible(false);
    } catch (e: any) {
      message.error(`启动失败：${e?.response?.data?.detail || e.message}`);
    }
  };

  const handleExtractQA = async () => {
    try {
      const res = await triggerExtractQA({ window_size: 50, concurrency: 3 });
      message.success(`Q&A 抽取任务已启动（ID: ${res.scraping_task_id}）`);
      setScrapeStatusId(res.scraping_task_id);
    } catch (e: any) {
      message.error(`启动失败：${e?.response?.data?.detail || e.message}`);
    }
  };

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
      const { reference_material, ...payload } = values;
      if (editingKB) {
        await api.put(`/knowledge-bases/${editingKB.id}`, payload);
        message.success('更新成功');
      } else {
        await api.post('/knowledge-bases/', payload);
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

  const handleGenerateContent = async () => {
    const name = form.getFieldValue('name');
    const description = form.getFieldValue('description');
    if (!name || !description) {
      message.warning('请先填写名称和描述');
      return;
    }
    setGenerating(true);
    try {
      const res = await api.post('/knowledge-bases/generate-content', {
        name,
        description,
        reference_material: form.getFieldValue('reference_material') || undefined,
      });
      form.setFieldsValue({ content: res.data.content });
      message.success('内容生成成功');
    } catch (e) {
      message.error('AI 生成内容失败');
    } finally {
      setGenerating(false);
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

      {/* ── 群组采集 + Q&A 抽取 ── */}
      <Card
        title="📥 群组消息采集 → Q&A 抽取（喂养 AI 知识库）"
        style={{ marginBottom: 16 }}
        extra={
          <Space>
            <Button icon={<CloudDownloadOutlined />} onClick={() => setScrapeModalVisible(true)}>
              采集群组消息
            </Button>
            <Button type="primary" icon={<ThunderboltOutlined />} onClick={handleExtractQA}>
              抽取 Q&A 入库
            </Button>
            <Button icon={<ReloadOutlined />} onClick={refreshChatStats} />
          </Space>
        }
      >
        {scrapeStatus && scrapeStatus.status === 'running' && (
          <div style={{ marginBottom: 12, padding: 8, background: '#e6f4ff', borderRadius: 4 }}>
            <Text strong>任务运行中：</Text>{' '}
            {scrapeStatus.progress.processed_chats !== undefined ? (
              <>
                进度 {scrapeStatus.progress.processed_chats}/{scrapeStatus.progress.total_chats} 个 chat，
                已采集 {scrapeStatus.progress.total_messages} 条消息
                {scrapeStatus.progress.current_chat && (
                  <>，当前：<Text code>{scrapeStatus.progress.current_chat}</Text></>
                )}
              </>
            ) : (
              <>
                抽取窗口 {scrapeStatus.progress.windows_processed || 0}，已生成 Q&A {scrapeStatus.progress.qa_extracted || 0} 条
              </>
            )}
          </div>
        )}
        <Row gutter={16}>
          <Col span={6}>
            <Statistic title="已采群/聊数" value={chatStats.length} />
          </Col>
          <Col span={6}>
            <Statistic title="总消息数" value={chatStats.reduce((s, c) => s + c.message_count, 0)} />
          </Col>
          <Col span={6}>
            <Statistic title="已抽 Q&A 消息" value={chatStats.reduce((s, c) => s + c.qa_extracted, 0)} />
          </Col>
          <Col span={6}>
            <Statistic
              title="待抽消息"
              value={chatStats.reduce((s, c) => s + (c.message_count - c.qa_extracted), 0)}
              valueStyle={{ color: '#fa8c16' }}
            />
          </Col>
        </Row>
        {chatStats.length > 0 && (
          <Table
            size="small"
            style={{ marginTop: 12 }}
            dataSource={chatStats}
            rowKey="chat_id"
            pagination={{ pageSize: 8 }}
            columns={[
              { title: '群/聊名称', dataIndex: 'chat_title', ellipsis: true },
              { title: '类型', dataIndex: 'chat_type', width: 100, render: (t: string) => (
                <Tag color={t === 'private' ? 'blue' : t === 'supergroup' ? 'green' : 'default'}>{t}</Tag>
              ) },
              { title: '消息数', dataIndex: 'message_count', width: 100, sorter: (a: any, b: any) => a.message_count - b.message_count },
              { title: '已抽 Q&A', dataIndex: 'qa_extracted', width: 100 },
            ]}
          />
        )}
      </Card>

      {/* ── 文档批量导入 (PDF) ── */}
      <Card
        title="📄 文档批量导入（PDF）"
        style={{ marginBottom: 16 }}
      >
        <Row gutter={16}>
          <Col span={14}>
            <Upload.Dragger
              fileList={importFileList}
              beforeUpload={() => false}
              onChange={({ fileList }) => setImportFileList(fileList)}
              multiple
              accept=".pdf"
              disabled={importing}
            >
              <p className="ant-upload-drag-icon"><InboxOutlined /></p>
              <p className="ant-upload-text">点击或拖拽 PDF 文件到此处上传</p>
              <p className="ant-upload-hint">
                每个文件单独成一份文档；后端按段落切片、向量化后写入知识库。单文件最大 50 MB。
              </p>
            </Upload.Dragger>
          </Col>
          <Col span={10}>
            <div style={{ padding: '8px 16px' }}>
              <Form layout="vertical">
                <Form.Item label="分类标签（可选）">
                  <Input
                    placeholder="如：产品手册 / 报价单 / FAQ"
                    value={importCategory}
                    onChange={e => setImportCategory(e.target.value)}
                  />
                </Form.Item>
                <Button
                  type="primary"
                  icon={<FilePdfOutlined />}
                  onClick={handleImportSubmit}
                  loading={importing}
                  disabled={importFileList.length === 0}
                  block
                >
                  开始导入（{importFileList.length} 个文件）
                </Button>
                <div style={{ marginTop: 12, fontSize: 12, color: '#888' }}>
                  导入后端用 Gemini text-embedding-004（768 维）做向量化。MVP 不支持 OCR；扫描件需先 OCR 转可选文本 PDF。
                </div>
              </Form>
            </div>
          </Col>
        </Row>

        {Object.keys(importJobs).length > 0 && (
          <div style={{ marginTop: 16 }}>
            <Typography.Text strong>导入任务：</Typography.Text>
            <List
              size="small"
              dataSource={Object.values(importJobs).sort((a, b) => a.task_id.localeCompare(b.task_id))}
              renderItem={(job) => {
                const res = job.result || {};
                let status: string;
                let color: 'default' | 'processing' | 'success' | 'error' = 'default';
                if (!job.ready) {
                  status = job.state || 'PENDING';
                  color = 'processing';
                } else if (res.ok) {
                  status = `完成 · ${res.chunks} chunks`;
                  color = 'success';
                } else {
                  status = `失败 · ${res.error || job.error || 'unknown'}`;
                  color = 'error';
                }
                return (
                  <List.Item>
                    <Space>
                      <FilePdfOutlined />
                      <Typography.Text>{job.filename}</Typography.Text>
                      <Tag color={color}>{status}</Tag>
                      <Typography.Text type="secondary" style={{ fontSize: 12 }}>
                        {job.task_id.slice(0, 8)}...
                      </Typography.Text>
                    </Space>
                  </List.Item>
                );
              }}
            />
          </div>
        )}
      </Card>

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

          <Form.Item
            name="description"
            label="描述"
            rules={[{ required: true, message: '请输入描述' }]}
          >
            <Input placeholder="简短描述知识库内容" />
          </Form.Item>

          <Form.Item name="reference_material" label="参考资料（可选）">
            <TextArea
              rows={4}
              placeholder="可粘贴网页内容、产品文档、FAQ 等参考资料，AI 将基于这些资料生成结构化内容"
            />
          </Form.Item>

          <Form.Item
            name="content"
            label={
              <Space>
                <span>知识内容 (Markdown)</span>
                <Button
                  type="primary"
                  ghost
                  size="small"
                  icon={<RobotOutlined />}
                  loading={generating}
                  onClick={handleGenerateContent}
                >
                  AI 生成内容
                </Button>
              </Space>
            }
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

      {/* 群组采集弹窗 */}
      <Modal
        title="📥 采集账号下所有群组/私聊消息"
        open={scrapeModalVisible}
        onCancel={() => setScrapeModalVisible(false)}
        onOk={() => scrapeForm.submit()}
        width={560}
      >
        <Form
          form={scrapeForm}
          layout="vertical"
          onFinish={handleScrapeSubmit}
          initialValues={{ include_private: true, limit_per_chat: null, chat_sleep_sec: 2.0 }}
        >
          <Form.Item
            name="account_id"
            label="使用哪个账号采集"
            rules={[{ required: true, message: '请选择账号' }]}
          >
            <Select
              placeholder="选择活跃账号"
              showSearch
              optionFilterProp="label"
              options={accounts.map(a => ({
                value: a.id,
                label: `${a.phone_number}（ID:${a.id}）`,
              }))}
            />
          </Form.Item>
          <Form.Item name="include_private" label="包含私聊" valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="limit_per_chat" label="每个 chat 最多采多少条（留空 = 全量历史）">
            <Input type="number" placeholder="留空采全部" />
          </Form.Item>
          <Form.Item name="chat_sleep_sec" label="chat 之间停顿秒数（防 FloodWait）">
            <Input type="number" step="0.5" />
          </Form.Item>
          <div style={{ background: '#fff7e6', padding: 8, borderRadius: 4 }}>
            <Text type="warning">
              ⚠ 全量采集 50-300 群预计耗时 4-12 小时。任务支持断点续采（重复触发只采新消息）。
            </Text>
          </div>
        </Form>
      </Modal>
    </div>
  );
};

export default KnowledgeBasePage;
