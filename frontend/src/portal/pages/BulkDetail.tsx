import React, { useState } from 'react';
import {
  Card, Tag, Space, Typography, Row, Col, Statistic, Table, Progress, Divider,
  Button, Empty, Alert, message, Popconfirm, Input, InputNumber,
} from 'antd';
import {
  ArrowLeftOutlined, DeleteOutlined, PlayCircleOutlined, PauseCircleOutlined,
  EditOutlined, PlusOutlined, CheckOutlined, CloseOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, useParams } from 'react-router-dom';
import { bulkApi, BulkBatchDetail, BulkVariant } from '../api';

const { TextArea } = Input;
const { Title, Text, Paragraph } = Typography;

const STATUS_COLOR: Record<string, string> = {
  draft: 'default', pending: 'orange', running: 'processing',
  paused: 'gold', completed: 'green', failed: 'red', canceled: 'default',
};

const TARGET_COLOR: Record<string, string> = {
  pending: 'default', sending: 'processing', sent: 'blue',
  delivered: 'cyan', failed: 'red', replied: 'green',
  opted_out: 'orange', skipped: 'default',
};

const formatUsd = (cents: number) => `$${(cents / 100).toFixed(2)}`;

const VARIANT_EDITABLE_STATUSES = new Set(['draft', 'paused']);

// ── Inline variant editor row ────────────────────────────────────────

const VariantRow: React.FC<{
  variant: BulkVariant;
  index: number;
  canEdit: boolean;
  onChanged: () => void;
}> = ({ variant, index, canEdit, onChanged }) => {
  const [editing, setEditing] = useState(false);
  const [content, setContent] = useState(variant.content);
  const [weight, setWeight] = useState(variant.weight);

  const saveMut = useMutation({
    mutationFn: () => bulkApi.updateVariant(variant.id, { content, weight }),
    onSuccess: () => { message.success('Variant updated'); setEditing(false); onChanged(); },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Update failed'),
  });

  const deleteMut = useMutation({
    mutationFn: () => bulkApi.deleteVariant(variant.id),
    onSuccess: () => { message.success('Variant deleted'); onChanged(); },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Delete failed'),
  });

  return (
    <Card
      size="small" type="inner"
      title={
        <Space>
          <span>Variant {index + 1}</span>
          <Tag>weight {variant.weight}</Tag>
          <Tag color="blue">used {variant.use_count}×</Tag>
        </Space>
      }
      extra={
        canEdit && (
          editing ? (
            <Space>
              <Button size="small" icon={<CheckOutlined />} type="primary" loading={saveMut.isPending} onClick={() => saveMut.mutate()}>
                Save
              </Button>
              <Button size="small" icon={<CloseOutlined />} onClick={() => {
                setEditing(false);
                setContent(variant.content);
                setWeight(variant.weight);
              }}>
                Cancel
              </Button>
            </Space>
          ) : (
            <Space>
              <Button size="small" icon={<EditOutlined />} onClick={() => setEditing(true)}>Edit</Button>
              <Popconfirm title="Delete this variant?" onConfirm={() => deleteMut.mutate()}>
                <Button size="small" danger icon={<DeleteOutlined />} />
              </Popconfirm>
            </Space>
          )
        )
      }
    >
      {editing ? (
        <Space direction="vertical" style={{ width: '100%' }}>
          <TextArea rows={3} value={content} onChange={e => setContent(e.target.value)} />
          <Space>
            <span style={{ fontSize: 12, color: '#475569' }}>Weight:</span>
            <InputNumber min={1} max={100} value={weight} onChange={v => setWeight(Number(v) || 1)} />
          </Space>
        </Space>
      ) : (
        <Paragraph style={{ marginBottom: 0, whiteSpace: 'pre-wrap' }}>{variant.content}</Paragraph>
      )}
    </Card>
  );
};

// ── Add-new variant inline form ──────────────────────────────────────

const VariantAdder: React.FC<{ batchId: number; onAdded: () => void }> = ({ batchId, onAdded }) => {
  const [open, setOpen] = useState(false);
  const [content, setContent] = useState('');
  const [weight, setWeight] = useState(1);

  const addMut = useMutation({
    mutationFn: () => bulkApi.addVariant(batchId, content.trim(), weight),
    onSuccess: () => {
      message.success('Variant added');
      setContent('');
      setWeight(1);
      setOpen(false);
      onAdded();
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Add failed'),
  });

  if (!open) {
    return (
      <Button type="dashed" block icon={<PlusOutlined />} onClick={() => setOpen(true)}>
        Add a variant
      </Button>
    );
  }

  return (
    <Card size="small" type="inner" title="New variant">
      <Space direction="vertical" style={{ width: '100%' }}>
        <TextArea
          rows={3}
          value={content}
          onChange={e => setContent(e.target.value)}
          placeholder="Hey {{name}}, exclusive offer for you today."
        />
        <Space>
          <span style={{ fontSize: 12, color: '#475569' }}>Weight:</span>
          <InputNumber min={1} max={100} value={weight} onChange={v => setWeight(Number(v) || 1)} />
          <Button
            type="primary"
            icon={<CheckOutlined />}
            loading={addMut.isPending}
            disabled={!content.trim()}
            onClick={() => addMut.mutate()}
          >
            Add
          </Button>
          <Button onClick={() => { setOpen(false); setContent(''); setWeight(1); }}>Cancel</Button>
        </Space>
      </Space>
    </Card>
  );
};

// ── Page ──────────────────────────────────────────────────────────────

const BulkDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const batchId = Number(id);
  const nav = useNavigate();
  const qc = useQueryClient();

  const { data: batch, isLoading } = useQuery({
    queryKey: ['portal', 'bulk', 'batch', batchId],
    queryFn: () => bulkApi.getBatch(batchId),
    enabled: !!batchId,
    refetchInterval: 10000,
  });

  const invalidate = () =>
    qc.invalidateQueries({ queryKey: ['portal', 'bulk', 'batch', batchId] });

  const cancelMut = useMutation({
    mutationFn: () => bulkApi.cancelBatch(batchId),
    onSuccess: () => {
      message.success('Draft canceled');
      qc.invalidateQueries({ queryKey: ['portal', 'bulk'] });
      nav('/portal/bulk');
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Cancel failed'),
  });

  const startMut = useMutation({
    mutationFn: () => bulkApi.startBatch(batchId),
    onSuccess: () => {
      message.success('Batch armed — dispatcher will pick it up shortly.');
      qc.invalidateQueries({ queryKey: ['portal', 'bulk'] });
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Start failed'),
  });

  const pauseMut = useMutation({
    mutationFn: () => bulkApi.pauseBatch(batchId),
    onSuccess: () => {
      message.success('Pause requested — running workers will exit on next iteration.');
      qc.invalidateQueries({ queryKey: ['portal', 'bulk'] });
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Pause failed'),
  });

  const resumeMut = useMutation({
    mutationFn: () => bulkApi.resumeBatch(batchId),
    onSuccess: () => {
      message.success('Resume requested.');
      qc.invalidateQueries({ queryKey: ['portal', 'bulk'] });
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Resume failed'),
  });

  if (isLoading) return <Card loading />;
  if (!batch) return <Empty description="Batch not found" />;

  const sentPct = batch.total_targets > 0
    ? Math.round((batch.sent_count / batch.total_targets) * 100) : 0;
  const failedPct = batch.total_targets > 0
    ? Math.round((batch.failed_count / batch.total_targets) * 100) : 0;

  const canEditVariants = VARIANT_EDITABLE_STATUSES.has(batch.status);

  const targetCols = [
    { title: 'ID', dataIndex: 'id', key: 'id', width: 60 },
    { title: 'phone', dataIndex: 'phone', key: 'phone' },
    { title: 'username', dataIndex: 'tg_username', key: 'tg_username' },
    { title: 'tg_user_id', dataIndex: 'tg_user_id', key: 'tg_user_id' },
    { title: 'name', dataIndex: 'display_name', key: 'display_name' },
    { title: 'country', dataIndex: 'country', key: 'country', width: 80 },
    {
      title: 'status', dataIndex: 'status', key: 'status', width: 100,
      render: (s: string) => <Tag color={TARGET_COLOR[s] || 'default'}>{s}</Tag>,
    },
    {
      title: 'reason', dataIndex: 'failed_reason', key: 'failed_reason',
      render: (r: string | null) => r ? <Text type="secondary" style={{ fontSize: 12 }}>{r}</Text> : '',
    },
  ];

  return (
    <div>
      <Button type="link" icon={<ArrowLeftOutlined />} onClick={() => nav('/portal/bulk')} style={{ padding: 0, marginBottom: 8 }}>
        Back to Bulk Send
      </Button>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <Space>
            <Title level={3} style={{ margin: 0 }}>{batch.name}</Title>
            <Tag color={STATUS_COLOR[batch.status]} style={{ fontSize: 14 }}>{batch.status}</Tag>
          </Space>
          <div>
            <Text type="secondary">Batch #{batch.id} · created {new Date(batch.created_at).toLocaleString()}</Text>
          </div>
        </div>
        <Space>
          {(batch.status === 'draft' || batch.status === 'pending') && (
            <Popconfirm title="Delete this draft batch?" onConfirm={() => cancelMut.mutate()}>
              <Button danger icon={<DeleteOutlined />}>Delete draft</Button>
            </Popconfirm>
          )}
          {batch.status === 'draft' && (
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              loading={startMut.isPending}
              onClick={() => startMut.mutate()}
            >
              Start sending
            </Button>
          )}
          {(batch.status === 'pending' || batch.status === 'running') && (
            <Button
              icon={<PauseCircleOutlined />}
              loading={pauseMut.isPending}
              onClick={() => pauseMut.mutate()}
            >
              Pause
            </Button>
          )}
          {batch.status === 'paused' && (
            <Button
              type="primary"
              icon={<PlayCircleOutlined />}
              loading={resumeMut.isPending}
              onClick={() => resumeMut.mutate()}
            >
              Resume
            </Button>
          )}
        </Space>
      </div>

      <Divider />

      <Row gutter={16}>
        <Col span={6}><Card><Statistic title="Targets" value={batch.total_targets} /></Card></Col>
        <Col span={6}><Card><Statistic title="Sent" value={batch.sent_count} suffix={`/ ${batch.total_targets}`} /></Card></Col>
        <Col span={6}><Card><Statistic title="Failed" value={batch.failed_count} valueStyle={{ color: batch.failed_count ? '#ef4444' : undefined }} /></Card></Col>
        <Col span={6}><Card><Statistic title="Replied" value={batch.replied_count} valueStyle={{ color: '#22c55e' }} /></Card></Col>
      </Row>

      <Card style={{ marginTop: 16 }}>
        <Progress percent={sentPct} success={{ percent: sentPct - failedPct }} format={() => `${batch.sent_count}/${batch.total_targets}`} />
      </Card>

      <Row gutter={16} style={{ marginTop: 16 }}>
        <Col span={12}>
          <Card title="Estimated cost">
            <Statistic title="Total" value={formatUsd(batch.estimated_total_cents)} />
            <Text type="secondary">Unit at creation: ¢{batch.estimated_unit_price_cents}/msg</Text>
          </Card>
        </Col>
        <Col span={12}>
          <Card title="Send schedule">
            <Text>Random delay between {batch.min_delay_sec}–{batch.max_delay_sec} seconds.</Text>
            {batch.paused_at && (
              <Alert type="warning" message={`Paused: ${batch.pause_reason || 'unknown reason'}`} style={{ marginTop: 8 }} />
            )}
          </Card>
        </Col>
      </Row>

      <Card
        title={`Message variants (${batch.variants.length})`}
        style={{ marginTop: 16 }}
        extra={
          !canEditVariants && (
            <Text type="secondary" style={{ fontSize: 12 }}>
              Pause this batch to edit variants
            </Text>
          )
        }
      >
        <Space direction="vertical" style={{ width: '100%' }}>
          {batch.variants.length === 0 ? (
            <Empty description="No variants. At least 5 are needed to start sending." />
          ) : (
            batch.variants.map((v, idx) => (
              <VariantRow
                key={v.id}
                variant={v}
                index={idx}
                canEdit={canEditVariants}
                onChanged={invalidate}
              />
            ))
          )}
          {canEditVariants && (
            <VariantAdder batchId={batchId} onAdded={invalidate} />
          )}
        </Space>
      </Card>

      <Card title={`Targets preview (first ${batch.targets_preview.length} of ${batch.total_targets})`} style={{ marginTop: 16 }}>
        {batch.targets_preview.length === 0 ? (
          <Empty description="No targets" />
        ) : (
          <Table
            rowKey="id"
            size="small"
            dataSource={batch.targets_preview}
            columns={targetCols as any}
            pagination={false}
          />
        )}
      </Card>
    </div>
  );
};

export default BulkDetailPage;
