import React, { useState } from 'react';
import {
  Card, Input, Button, Space, Typography, Alert, Row, Col, Statistic,
  Upload, message, Form, InputNumber, Divider, Tag, Tooltip,
} from 'antd';
import { UploadOutlined, SendOutlined, EyeOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import type { UploadProps } from 'antd';
import { useMutation, useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { bulkApi, walletApi } from '../api';

const { Title, Text, Paragraph } = Typography;
const { TextArea } = Input;

const formatUsd = (cents: number) => `$${(cents / 100).toFixed(2)}`;

const BulkNewPage: React.FC = () => {
  const nav = useNavigate();
  const [form] = Form.useForm();
  const [csvText, setCsvText] = useState('');
  const [previewCount, setPreviewCount] = useState<number | null>(null);
  const [variants, setVariants] = useState<string[]>(['', '', '', '', '']);

  // Count parsed lines client-side (rough)
  React.useEffect(() => {
    const lines = csvText.split(/\r?\n/).filter(l => l.trim());
    setPreviewCount(lines.length);
  }, [csvText]);

  const { data: wallet } = useQuery({
    queryKey: ['portal', 'wallet'],
    queryFn: walletApi.get,
  });

  const previewMut = useMutation({
    mutationFn: (count: number) => bulkApi.previewCost(count),
  });

  // Auto-preview when count changes (debounced)
  React.useEffect(() => {
    if (!previewCount || previewCount < 1) return;
    const t = setTimeout(() => {
      previewMut.mutate(previewCount);
    }, 400);
    return () => clearTimeout(t);
  }, [previewCount]);

  const createMut = useMutation({
    mutationFn: bulkApi.createBatch,
    onSuccess: (b) => {
      message.success(`Draft batch #${b.id} created with ${b.total_targets} targets`);
      nav(`/portal/bulk/${b.id}`);
    },
    onError: (e: any) => message.error(e?.response?.data?.detail || 'Create failed'),
  });

  const uploadProps: UploadProps = {
    accept: '.csv,.txt',
    maxCount: 1,
    showUploadList: false,
    beforeUpload: (file) => {
      const reader = new FileReader();
      reader.onload = e => setCsvText(String(e.target?.result || ''));
      reader.readAsText(file);
      return false;
    },
  };

  const handleSubmit = (values: any) => {
    const cleanVariants = variants.map(v => v.trim()).filter(Boolean);
    createMut.mutate({
      name: values.name,
      message_template: values.message_template,
      csv_text: csvText,
      variants: cleanVariants,
      min_delay_sec: values.min_delay_sec,
      max_delay_sec: values.max_delay_sec,
    });
  };

  const cost = previewMut.data;
  const balanceShort = cost && !cost.balance_sufficient;

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      <Button type="link" icon={<ArrowLeftOutlined />} onClick={() => nav('/portal/bulk')} style={{ padding: 0, marginBottom: 8 }}>
        Back to Bulk Send
      </Button>
      <Title level={3}>Create New Batch</Title>
      <Paragraph type="secondary">
        Upload your targets (CSV with phone / username / user_id columns), write a message template,
        and add 5+ variants. A draft batch is created instantly with a cost estimate — sending starts
        only when you press <Text strong>Start</Text> on the batch detail page (W3).
      </Paragraph>

      <Form form={form} layout="vertical" onFinish={handleSubmit} initialValues={{
        name: '',
        message_template: '',
        min_delay_sec: 30,
        max_delay_sec: 180,
      }}>
        <Row gutter={24}>
          <Col span={16}>
            <Card title="1) Batch details" style={{ marginBottom: 16 }}>
              <Form.Item name="name" label="Batch name" rules={[{ required: true, message: 'Give this batch a name' }]}>
                <Input placeholder="e.g. US BC promo 2026-05-20" />
              </Form.Item>
              <Form.Item name="message_template" label="Primary message" rules={[{ required: true, min: 1 }]}>
                <TextArea rows={3} placeholder="Hi! We saw your interest and want to share an offer..." />
              </Form.Item>
              <Row gutter={16}>
                <Col span={12}>
                  <Form.Item name="min_delay_sec" label="Min delay (sec)" rules={[{ required: true }]}>
                    <InputNumber min={10} max={600} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
                <Col span={12}>
                  <Form.Item name="max_delay_sec" label="Max delay (sec)" rules={[{ required: true }]}>
                    <InputNumber min={30} max={1800} style={{ width: '100%' }} />
                  </Form.Item>
                </Col>
              </Row>
              <Alert
                type="info" showIcon
                message="Random delay between sends — keeps the account healthy."
                description="30–180s is safe for most cases. Lower numbers raise spam-flag risk."
              />
            </Card>

            <Card title="2) Targets (CSV)" style={{ marginBottom: 16 }}>
              <Space direction="vertical" style={{ width: '100%' }}>
                <Space>
                  <Upload {...uploadProps}>
                    <Button icon={<UploadOutlined />}>Upload CSV/TXT file</Button>
                  </Upload>
                  <Text type="secondary">
                    or paste below • {previewCount ?? 0} non-empty lines detected
                  </Text>
                </Space>
                <TextArea
                  rows={8}
                  value={csvText}
                  onChange={e => setCsvText(e.target.value)}
                  placeholder={`Examples (one of):

phone,name,country
+12025551234,Alice,US
+12025555678,Bob,US

# or username-only
@cooluser
@anotheruser

# or numeric user_id
12345678
98765432`}
                />
                <Alert
                  type="info" showIcon
                  message="Recognised columns: phone | tg_username | tg_user_id | name | country"
                  description="With a header row, columns are mapped by name. Without a header, each line is auto-detected as phone, username, or user_id."
                />
              </Space>
            </Card>

            <Card title={
              <Space>
                <span>3) Message variants (5+ recommended)</span>
                <Tag color={variants.filter(v => v.trim()).length >= 5 ? 'green' : 'orange'}>
                  {variants.filter(v => v.trim()).length}/5+
                </Tag>
              </Space>
            }>
              <Paragraph type="secondary" style={{ fontSize: 12 }}>
                Anti-spam: TG flags identical messages from multiple accounts. Each message is
                randomly picked from your variant pool. <strong>≥ 5 variants are required at
                send time (W3)</strong>.
              </Paragraph>
              {variants.map((v, idx) => (
                <TextArea
                  key={idx}
                  rows={2}
                  style={{ marginBottom: 8 }}
                  placeholder={`Variant ${idx + 1}`}
                  value={v}
                  onChange={e => {
                    const next = [...variants];
                    next[idx] = e.target.value;
                    setVariants(next);
                  }}
                />
              ))}
              <Button type="dashed" block onClick={() => setVariants([...variants, ''])}>
                + Add another variant
              </Button>
            </Card>
          </Col>

          <Col span={8}>
            <Card title="Cost preview" style={{ position: 'sticky', top: 16 }}>
              <Statistic title="Targets" value={previewCount ?? 0} />
              <Divider />
              {cost ? (
                <>
                  <Statistic
                    title="Estimated total"
                    value={formatUsd(cost.total_cost_cents)}
                    valueStyle={{ color: balanceShort ? '#ef4444' : '#0066FF' }}
                  />
                  <Text type="secondary" style={{ fontSize: 12 }}>
                    Current tier unit: ¢{cost.current_tier_unit_cents}/msg
                  </Text>
                  {cost.breakdown.length > 1 && (
                    <>
                      <Divider style={{ margin: '12px 0' }} />
                      <Text strong>Tier breakdown:</Text>
                      {cost.breakdown.map((b, i) => (
                        <div key={i} style={{ fontSize: 12, color: '#475569' }}>
                          {b.count.toLocaleString()} × ¢{b.unit_cents} = {formatUsd(b.subtotal_cents)}
                        </div>
                      ))}
                    </>
                  )}
                  <Divider style={{ margin: '12px 0' }} />
                  <Statistic
                    title="Wallet balance"
                    value={formatUsd(cost.balance_cents)}
                    valueStyle={{ fontSize: 18 }}
                  />
                  {balanceShort && (
                    <Alert
                      type="warning" showIcon style={{ marginTop: 8 }}
                      message={`Short by ${formatUsd(cost.shortfall_cents)}`}
                      description={
                        <Button type="link" size="small" onClick={() => nav('/portal/wallet')} style={{ padding: 0 }}>
                          Top up wallet →
                        </Button>
                      }
                    />
                  )}
                </>
              ) : (
                <Text type="secondary">Add targets to see the cost.</Text>
              )}
              <Divider />
              <Button
                type="primary"
                block
                size="large"
                icon={<EyeOutlined />}
                loading={createMut.isPending}
                onClick={() => form.submit()}
                disabled={!previewCount || previewCount < 1}
              >
                Create Draft
              </Button>
              <Paragraph type="secondary" style={{ marginTop: 8, fontSize: 12 }}>
                Draft is reviewable; no charges yet. Start sending from the batch detail page.
              </Paragraph>
            </Card>
          </Col>
        </Row>
      </Form>
    </div>
  );
};

export default BulkNewPage;
