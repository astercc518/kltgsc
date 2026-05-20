import React, { useState } from 'react';
import {
  Table, Tag, Typography, Empty, Button, Space, Modal, Form, Input, Select,
  Upload, message, Popconfirm, Tooltip, Card, Slider, Checkbox,
  Progress, Alert,
} from 'antd';
import {
  PlusOutlined, UploadOutlined, EditOutlined, DeleteOutlined, EyeOutlined,
  CloudDownloadOutlined, MobileOutlined,
} from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { kbApi, KBEntry, resourcesApi, importApi, mainAccountApi } from '../api';
import dayjs from 'dayjs';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const CATEGORY_OPTIONS = [
  { value: 'custom', label: 'Custom' },
  { value: 'industry_overview', label: 'Industry Overview' },
  { value: 'pain_points', label: 'Customer Pain Points' },
  { value: 'sales_qa', label: 'Sales Q&A' },
  { value: 'opening_lines', label: 'Opening Lines' },
  { value: 'product', label: 'Product Info' },
  { value: 'pricing', label: 'Pricing' },
  { value: 'uploaded', label: 'Uploaded' },
];

const CATEGORY_COLOR: Record<string, string> = {
  industry_overview: 'blue', pain_points: 'orange', sales_qa: 'green',
  opening_lines: 'purple', product: 'cyan', pricing: 'gold',
  uploaded: 'magenta', custom: 'default',
};

const SOURCE_LABEL: Record<string, { color: string; text: string }> = {
  manual: { color: 'default', text: 'Manual' },
  industry_template: { color: 'blue', text: 'Auto' },
  file_import: { color: 'magenta', text: 'Upload' },
  qa_extracted: { color: 'cyan', text: 'Q&A' },
  scraped: { color: 'purple', text: 'Scraped' },
};

interface EditorState {
  open: boolean;
  initial: Partial<KBEntry> | null;   // null = create mode
}

const KBEditor: React.FC<{
  state: EditorState;
  onClose: () => void;
}> = ({ state, onClose }) => {
  const qc = useQueryClient();
  const [form] = Form.useForm();
  const isEdit = !!state.initial?.id;

  React.useEffect(() => {
    if (state.open) {
      form.setFieldsValue({
        name: state.initial?.name,
        category: state.initial?.category || 'custom',
        language: state.initial?.language,
        description: state.initial?.description,
        content: state.initial?.content,
      });
    }
  }, [state.open, state.initial?.id]);

  const mutation = useMutation({
    mutationFn: async (values: any) => {
      if (isEdit) {
        return kbApi.update(state.initial!.id!, values);
      }
      return kbApi.create(values);
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['portal', 'knowledge-bases'] });
      message.success(isEdit ? 'Updated' : 'Created');
      onClose();
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.detail || 'Save failed');
    },
  });

  return (
    <Modal
      open={state.open}
      onCancel={onClose}
      onOk={() => form.submit()}
      okText={isEdit ? 'Save' : 'Create'}
      confirmLoading={mutation.isPending}
      title={isEdit ? `Edit KB #${state.initial?.id}` : 'New KB Entry'}
      width={680}
    >
      <Form form={form} layout="vertical" onFinish={(v) => mutation.mutate(v)}>
        <Form.Item name="name" label="Name" rules={[{ required: true }]}>
          <Input placeholder="Short identifier, e.g. 'Pricing 2026'" />
        </Form.Item>
        <Space style={{ width: '100%' }}>
          <Form.Item name="category" label="Category" style={{ flex: 1, minWidth: 180 }}>
            <Select options={CATEGORY_OPTIONS} />
          </Form.Item>
          <Form.Item name="language" label="Language" style={{ minWidth: 120 }}>
            <Input placeholder="en / zh / ..." />
          </Form.Item>
        </Space>
        <Form.Item name="description" label="Description">
          <Input placeholder="Optional — what this entry is about" />
        </Form.Item>
        <Form.Item
          name="content"
          label={
            <Space>
              <span>Content</span>
              <Text type="secondary" style={{ fontSize: 12 }}>
                (will be auto-embedded for RAG retrieval)
              </Text>
            </Space>
          }
          rules={[{ required: true, message: 'Content is required' }]}
        >
          <TextArea rows={10} placeholder="The text the AI will retrieve from." />
        </Form.Item>
      </Form>
    </Modal>
  );
};

const ViewerModal: React.FC<{ entry: KBEntry | null; onClose: () => void }> = ({ entry, onClose }) => {
  if (!entry) return null;
  return (
    <Modal open={true} footer={null} onCancel={onClose} width={760} title={entry.name}>
      <Space wrap style={{ marginBottom: 12 }}>
        {entry.category && <Tag color={CATEGORY_COLOR[entry.category] || 'default'}>{entry.category}</Tag>}
        {entry.language && <Tag>{entry.language}</Tag>}
        <Tag color={SOURCE_LABEL[entry.source_type]?.color}>{SOURCE_LABEL[entry.source_type]?.text || entry.source_type}</Tag>
        {entry.source_filename && <Text type="secondary">from {entry.source_filename}</Text>}
      </Space>
      {entry.description && (
        <Paragraph type="secondary">{entry.description}</Paragraph>
      )}
      <pre style={{
        background: '#f8fafc', padding: 16, borderRadius: 6,
        whiteSpace: 'pre-wrap', fontFamily: 'inherit', maxHeight: 480, overflowY: 'auto',
      }}>{entry.content}</pre>
    </Modal>
  );
};

// ── Epic 5.1 — Import-from-Telegram modal ──────────────────────────────

const ImportModal: React.FC<{ open: boolean; onClose: () => void }> = ({ open, onClose }) => {
  const qc = useQueryClient();
  const [sinceDays, setSinceDays] = useState(30);
  const [maxMessages, setMaxMessages] = useState(500);
  const [costCap, setCostCap] = useState(5);
  const [dialogTypes, setDialogTypes] = useState<string[]>(['private', 'supergroup', 'group']);
  const [taskId, setTaskId] = useState<number | null>(null);

  const { data: mainAccount } = useQuery({
    queryKey: ['portal', 'main-account'],
    queryFn: mainAccountApi.current,
  });

  const startMut = useMutation({
    mutationFn: () => {
      const since = dayjs().subtract(sinceDays, 'day').toISOString();
      return importApi.start({
        since,
        dialog_types: dialogTypes,
        max_messages_per_chat: maxMessages,
        cost_cap_usd: costCap,
      });
    },
    onSuccess: (data) => {
      setTaskId(data.scraping_task_id);
      message.success(`Import queued (task #${data.scraping_task_id})`);
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.detail || 'Failed to start import');
    },
  });

  const { data: status } = useQuery({
    queryKey: ['portal', 'import-status', taskId],
    queryFn: () => importApi.status(taskId!),
    enabled: !!taskId,
    refetchInterval: (q) => {
      const s = q.state.data;
      if (!s || s.status === 'running' || s.status === 'pending') return 3000;
      return false;
    },
    refetchOnWindowFocus: false,
  });

  React.useEffect(() => {
    if (status?.status === 'completed') {
      qc.invalidateQueries({ queryKey: ['portal', 'knowledge-bases'] });
      message.success('Import completed!');
    }
  }, [status?.status, qc]);

  const noMainAccount = !mainAccount?.connected;
  const progressPct = status?.progress?.total_chats
    ? Math.round((status.progress.processed_chats || 0) / status.progress.total_chats * 100)
    : 0;

  return (
    <Modal
      open={open}
      onCancel={() => { onClose(); setTaskId(null); }}
      footer={null}
      title={<><CloudDownloadOutlined /> Import from My Telegram</>}
      width={620}
    >
      {noMainAccount ? (
        <Alert
          type="warning"
          showIcon
          message="No main account connected"
          description={<>Connect your main TG account first via <a href="/portal/main-account">My Telegram</a>.</>}
        />
      ) : (
        <>
          <Form layout="vertical">
            <Form.Item label={`How far back? (last ${sinceDays} days)`}>
              <Slider
                min={1} max={365} value={sinceDays}
                onChange={setSinceDays}
                marks={{ 1: '1d', 30: '30d', 90: '90d', 365: '1y' }}
              />
            </Form.Item>
            <Form.Item label={`Max messages per chat (${maxMessages})`}>
              <Slider
                min={50} max={5000} step={50} value={maxMessages}
                onChange={setMaxMessages}
                marks={{ 50: '50', 500: '500', 2000: '2k', 5000: '5k' }}
              />
            </Form.Item>
            <Form.Item label={`Hard cost cap ($${costCap} USD)`}>
              <Slider
                min={1} max={50} value={costCap}
                onChange={setCostCap}
                marks={{ 1: '$1', 5: '$5', 20: '$20', 50: '$50' }}
              />
            </Form.Item>
            <Form.Item label="Dialog types">
              <Checkbox.Group
                value={dialogTypes}
                onChange={(v) => setDialogTypes(v as string[])}
                options={[
                  { label: 'Private DMs', value: 'private' },
                  { label: 'Supergroups', value: 'supergroup' },
                  { label: 'Small groups', value: 'group' },
                ]}
              />
            </Form.Item>
            <Button
              type="primary" block size="large" icon={<MobileOutlined />}
              onClick={() => startMut.mutate()}
              loading={startMut.isPending}
              disabled={!!taskId && status?.status !== 'completed' && status?.status !== 'failed'}
              style={{ background: '#0066FF', borderColor: '#0066FF' }}
            >
              {taskId ? 'Import In Progress' : 'Start Import'}
            </Button>
          </Form>

          {taskId && status && (
            <Card size="small" style={{ marginTop: 16 }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Typography.Text strong>Status: {status.status}</Typography.Text>
                {status.progress?.total_chats && (
                  <>
                    <Progress percent={progressPct} />
                    <Typography.Text type="secondary">
                      {status.progress.processed_chats || 0} / {status.progress.total_chats} chats ·
                      {' '}{status.progress.total_messages || 0} messages scraped
                    </Typography.Text>
                  </>
                )}
                <Typography.Text>KB entries extracted: <strong>{status.kb_extracted_total}</strong></Typography.Text>
                {status.error && <Alert type="error" message={status.error} showIcon />}
              </Space>
            </Card>
          )}
        </>
      )}
    </Modal>
  );
};


const PortalKnowledgeBases: React.FC = () => {
  const qc = useQueryClient();
  const [editorState, setEditorState] = useState<EditorState>({ open: false, initial: null });
  const [viewing, setViewing] = useState<KBEntry | null>(null);
  const [importOpen, setImportOpen] = useState(false);

  const { data: kbs = [], isLoading } = useQuery({
    queryKey: ['portal', 'knowledge-bases'],
    queryFn: () => resourcesApi.knowledgeBases() as Promise<KBEntry[]>,
  });

  const deleteMut = useMutation({
    mutationFn: (id: number) => kbApi.delete(id),
    onSuccess: () => {
      message.success('Deleted');
      qc.invalidateQueries({ queryKey: ['portal', 'knowledge-bases'] });
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.detail || 'Delete failed');
    },
  });

  const uploadProps: UploadProps = {
    accept: '.pdf,.docx,.txt,.md,.markdown',
    multiple: false,
    showUploadList: false,
    customRequest: async ({ file, onSuccess, onError }) => {
      try {
        const f = file as File;
        const hide = message.loading(`Uploading ${f.name}…`, 0);
        const res = await kbApi.upload(f);
        hide();
        message.success(`${res.name}: ${res.total_chunks} chunks (${res.embedded_chunks} embedded)`);
        qc.invalidateQueries({ queryKey: ['portal', 'knowledge-bases'] });
        onSuccess?.(res);
      } catch (e: any) {
        const detail = e?.response?.data?.detail || e?.message || 'Upload failed';
        message.error(detail);
        onError?.(e);
      }
    },
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', flexWrap: 'wrap' }}>
        <div>
          <Title level={3} style={{ marginBottom: 4 }}>Knowledge Base</Title>
          <Text type="secondary">
            Industry-specific knowledge your AI retrieves from when handling leads.
            Auto-generated entries are seeded at activation; you can add custom entries or upload documents.
          </Text>
        </div>
        <Space style={{ marginTop: 8 }}>
          <Button icon={<CloudDownloadOutlined />} onClick={() => setImportOpen(true)}>
            Import from My Telegram
          </Button>
          <Upload {...uploadProps}>
            <Button icon={<UploadOutlined />}>Upload document</Button>
          </Upload>
          <Button
            type="primary"
            icon={<PlusOutlined />}
            onClick={() => setEditorState({ open: true, initial: null })}
            style={{ background: '#0066FF', borderColor: '#0066FF' }}
          >
            New KB entry
          </Button>
        </Space>
      </div>

      <Table
        style={{ marginTop: 24 }}
        loading={isLoading}
        dataSource={kbs}
        rowKey="id"
        size="small"
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          {
            title: 'Name',
            dataIndex: 'name',
            render: (v, r) => (
              <Tooltip title={r.description}>
                <span>{v}</span>
              </Tooltip>
            ),
          },
          {
            title: 'Category', dataIndex: 'category', width: 140,
            render: (c) => c ? <Tag color={CATEGORY_COLOR[c] || 'default'}>{c}</Tag> : '—',
          },
          {
            title: 'Source', dataIndex: 'source_type', width: 100,
            render: (s) => {
              const m = SOURCE_LABEL[s];
              return m ? <Tag color={m.color}>{m.text}</Tag> : <Tag>{s}</Tag>;
            },
          },
          {
            title: 'Updated', dataIndex: 'updated_at', width: 160,
            render: (v) => v ? new Date(v).toLocaleString() : '—',
          },
          {
            title: '',
            width: 140,
            render: (_, r) => (
              <Space>
                <Tooltip title="View"><Button size="small" icon={<EyeOutlined />} onClick={() => setViewing(r)} /></Tooltip>
                <Tooltip title="Edit"><Button size="small" icon={<EditOutlined />} onClick={() => setEditorState({ open: true, initial: r })} /></Tooltip>
                <Popconfirm
                  title="Delete this KB entry?"
                  description="The AI will stop retrieving from this immediately."
                  okType="danger"
                  onConfirm={() => deleteMut.mutate(r.id)}
                >
                  <Tooltip title="Delete"><Button size="small" danger icon={<DeleteOutlined />} /></Tooltip>
                </Popconfirm>
              </Space>
            ),
          },
        ]}
        pagination={{ pageSize: 20 }}
        locale={{ emptyText: <Empty description="No KB entries yet. Subscribe to a plan to auto-generate industry KB, or click 'New KB entry'." /> }}
      />

      <KBEditor state={editorState} onClose={() => setEditorState({ open: false, initial: null })} />
      <ViewerModal entry={viewing} onClose={() => setViewing(null)} />
      <ImportModal open={importOpen} onClose={() => setImportOpen(false)} />
    </div>
  );
};

export default PortalKnowledgeBases;
