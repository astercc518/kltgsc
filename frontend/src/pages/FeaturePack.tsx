import React, { useState } from 'react';
import {
  Tabs, Card, Row, Col, Table, Button, Input, InputNumber, Switch, Tag,
  Modal, Form, Select, message, Typography, Statistic, Space,
  Popconfirm, Empty,
} from 'antd';
import {
  AppstoreOutlined, UserOutlined, EditOutlined, ReloadOutlined,
  DollarOutlined,
} from '@ant-design/icons';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import api, {
  FeatureRegistry, CustomerFeature, FeatureUsage,
  adminListFeatures, adminUpdateFeature,
  adminListCustomerFeatures, adminSetCustomerFeature,
  adminRemoveCustomerFeature, adminGetCustomerUsage,
} from '../services/api';

const { Title, Text } = Typography;

const CATEGORY_LABEL: Record<string, { color: string; text: string }> = {
  marketing: { color: 'magenta', text: '营销' },
  scraping: { color: 'cyan', text: '采集' },
  ai: { color: 'purple', text: 'AI' },
  kb: { color: 'green', text: '知识库' },
  account: { color: 'orange', text: '账号' },
};

const formatCents = (c: number) => `$${(c / 100).toFixed(2)}`;

// ─── Tab 1: Global Pricing ──────────────────────────────────────────────

const GlobalPricingTab: React.FC = () => {
  const qc = useQueryClient();
  const [editForm] = Form.useForm();
  const [editing, setEditing] = useState<FeatureRegistry | null>(null);

  const { data: features = [], isLoading } = useQuery({
    queryKey: ['admin', 'features'],
    queryFn: adminListFeatures,
  });

  const updateMut = useMutation({
    mutationFn: ({ slug, body }: { slug: string; body: any }) =>
      adminUpdateFeature(slug, body),
    onSuccess: () => {
      message.success('已更新');
      qc.invalidateQueries({ queryKey: ['admin', 'features'] });
      setEditing(null);
    },
    onError: (e: any) =>
      message.error(e.response?.data?.message || e.response?.data?.detail || '更新失败'),
  });

  const handleSubmit = async () => {
    const v = await editForm.validateFields();
    updateMut.mutate({ slug: editing!.slug, body: v });
  };

  const columns = [
    { title: 'Slug', dataIndex: 'slug', key: 'slug', width: 200,
      render: (s: string) => <Text code>{s}</Text> },
    { title: '中文名', dataIndex: 'name_zh', key: 'name_zh', width: 130 },
    { title: '类别', dataIndex: 'category', key: 'category', width: 90,
      render: (c: string) => {
        const info = CATEGORY_LABEL[c] || { color: 'default', text: c };
        return <Tag color={info.color}>{info.text}</Tag>;
      },
    },
    { title: '计费单元', dataIndex: 'billing_unit', key: 'billing_unit', width: 100,
      render: (u: string) => <Tag>{u}</Tag> },
    { title: '默认价', dataIndex: 'default_price_cents', key: 'default_price_cents', width: 120,
      render: (c: number, row: FeatureRegistry) => (
        <Space>
          <Text strong>{formatCents(c)}</Text>
          <Text type="secondary">/ {row.billing_unit}</Text>
        </Space>
      ),
    },
    { title: '默认开通', dataIndex: 'enabled_by_default', key: 'enabled_by_default', width: 100,
      render: (v: boolean) => v ? <Tag color="green">是</Tag> : <Tag>否</Tag>,
    },
    { title: '激活', dataIndex: 'is_active', key: 'is_active', width: 80,
      render: (v: boolean) => v ? <Tag color="green">✓</Tag> : <Tag color="red">已下架</Tag>,
    },
    { title: '描述', dataIndex: 'description', key: 'description', ellipsis: true },
    { title: '操作', key: 'actions', width: 80, fixed: 'right' as const,
      render: (_: any, row: FeatureRegistry) => (
        <Button size="small" icon={<EditOutlined />}
          onClick={() => {
            setEditing(row);
            editForm.setFieldsValue({
              default_price_cents: row.default_price_cents,
              enabled_by_default: row.enabled_by_default,
              is_active: row.is_active,
              description: row.description,
            });
          }}
        >
          编辑
        </Button>
      ),
    },
  ];

  return (
    <>
      <Card title="全局功能定价（feature_registry）" extra={
        <Button icon={<ReloadOutlined />}
          onClick={() => qc.invalidateQueries({ queryKey: ['admin', 'features'] })}
        >刷新</Button>
      }>
        <Text type="secondary">
          所有客户的默认价格。已设置 custom_price_cents 的客户单价不受此处影响。
          slug / billing_unit / category 不可修改（与历史用量记录绑定）。
        </Text>
        <Table
          style={{ marginTop: 16 }}
          rowKey="slug" dataSource={features} columns={columns}
          loading={isLoading} pagination={false}
          scroll={{ x: 1100 }}
        />
      </Card>

      <Modal
        open={!!editing} title={`编辑：${editing?.name_zh}`}
        onCancel={() => setEditing(null)} onOk={handleSubmit}
        okText="保存" confirmLoading={updateMut.isPending}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="default_price_cents" label="默认单价（cents）"
            rules={[{ required: true, type: 'integer', min: 0 }]}
            extra={`$ = cents/100  ·  当前 billing_unit = ${editing?.billing_unit}`}
          >
            <InputNumber min={0} style={{ width: '100%' }} />
          </Form.Item>
          <Form.Item name="enabled_by_default" label="新客户默认开通"
            valuePropName="checked">
            <Switch />
          </Form.Item>
          <Form.Item name="is_active" label="功能激活" valuePropName="checked"
            extra="关闭后所有客户该功能 charge 都会拒绝">
            <Switch />
          </Form.Item>
          <Form.Item name="description" label="描述">
            <Input.TextArea rows={2} maxLength={500} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

// ─── Tab 2: Per-Customer Customization ─────────────────────────────────

interface CustomerOpt { id: number; email: string; name: string | null; plan: string | null; }

const PerCustomerTab: React.FC = () => {
  const qc = useQueryClient();
  const [editForm] = Form.useForm();
  const [selectedCid, setSelectedCid] = useState<number | null>(null);
  const [editing, setEditing] = useState<CustomerFeature | null>(null);

  // 客户列表（复用 admin dashboard endpoint）
  const { data: customerList = [] } = useQuery({
    queryKey: ['admin', 'customers-for-features'],
    queryFn: async () => {
      const r = await api.get('/admin/dashboard/customers?limit=200');
      return r.data as Array<CustomerOpt & Record<string, any>>;
    },
  });

  const { data: features = [], isLoading: featuresLoading } = useQuery({
    queryKey: ['admin', 'customer-features', selectedCid],
    queryFn: () => adminListCustomerFeatures(selectedCid!),
    enabled: selectedCid != null,
  });

  const { data: usage = [] } = useQuery({
    queryKey: ['admin', 'customer-usage', selectedCid],
    queryFn: () => adminGetCustomerUsage(selectedCid!, 30),
    enabled: selectedCid != null,
  });

  const usageMap = new Map<string, FeatureUsage>(
    usage.map(u => [u.feature_slug, u])
  );

  const upsertMut = useMutation({
    mutationFn: ({ cid, slug, body }: { cid: number; slug: string; body: any }) =>
      adminSetCustomerFeature(cid, slug, body),
    onSuccess: () => {
      message.success('已保存');
      qc.invalidateQueries({ queryKey: ['admin', 'customer-features', selectedCid] });
      setEditing(null);
    },
    onError: (e: any) =>
      message.error(e.response?.data?.message || e.response?.data?.detail || '保存失败'),
  });

  const removeMut = useMutation({
    mutationFn: ({ cid, slug }: { cid: number; slug: string }) =>
      adminRemoveCustomerFeature(cid, slug),
    onSuccess: () => {
      message.success('已回退到默认');
      qc.invalidateQueries({ queryKey: ['admin', 'customer-features', selectedCid] });
    },
    onError: (e: any) =>
      message.error(e.response?.data?.message || e.response?.data?.detail || '回退失败'),
  });

  const handleToggleEnabled = (row: CustomerFeature, checked: boolean) => {
    upsertMut.mutate({
      cid: selectedCid!, slug: row.feature_slug,
      body: {
        enabled: checked,
        custom_price_cents: row.is_custom_price ? row.unit_price_cents : null,
        notes: row.notes,
      },
    });
  };

  const handleSubmitEdit = async () => {
    const v = await editForm.validateFields();
    upsertMut.mutate({
      cid: selectedCid!, slug: editing!.feature_slug,
      body: {
        enabled: v.enabled,
        custom_price_cents: v.use_custom ? v.custom_price_cents : null,
        notes: v.notes || '',
      },
    });
  };

  const columns = [
    { title: '功能', dataIndex: 'name_zh', key: 'name_zh', width: 180,
      render: (n: string, row: CustomerFeature) => (
        <Space direction="vertical" size={0}>
          <Text strong>{n}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{row.feature_slug}</Text>
        </Space>
      ),
    },
    { title: '类别', dataIndex: 'category', key: 'category', width: 80,
      render: (c: string) => {
        const info = CATEGORY_LABEL[c] || { color: 'default', text: c };
        return <Tag color={info.color}>{info.text}</Tag>;
      },
    },
    { title: '启用', dataIndex: 'enabled', key: 'enabled', width: 100,
      render: (e: boolean, row: CustomerFeature) => (
        <Switch checked={e}
          checkedChildren="开通" unCheckedChildren="关闭"
          loading={upsertMut.isPending && upsertMut.variables?.slug === row.feature_slug}
          onChange={(v) => handleToggleEnabled(row, v)}
        />
      ),
    },
    { title: '单价', key: 'price', width: 130,
      render: (_: any, row: CustomerFeature) => (
        <Space direction="vertical" size={0}>
          <Text strong>{formatCents(row.unit_price_cents)}</Text>
          {row.is_custom_price
            ? <Tag color="gold" style={{ fontSize: 10 }}>覆盖</Tag>
            : <Tag style={{ fontSize: 10 }}>默认</Tag>}
        </Space>
      ),
    },
    { title: '本月用量', key: 'usage', width: 150,
      render: (_: any, row: CustomerFeature) => {
        const u = usageMap.get(row.feature_slug);
        if (!u || u.units_consumed === 0) return <Text type="secondary">—</Text>;
        return (
          <Space direction="vertical" size={0}>
            <Text>{u.units_consumed.toLocaleString()} {row.billing_unit}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              花费 {formatCents(u.total_charged_cents)}
            </Text>
          </Space>
        );
      },
    },
    { title: '备注', dataIndex: 'notes', key: 'notes', ellipsis: true },
    { title: '操作', key: 'actions', width: 180, fixed: 'right' as const,
      render: (_: any, row: CustomerFeature) => (
        <Space>
          <Button size="small" icon={<EditOutlined />}
            onClick={() => {
              setEditing(row);
              editForm.setFieldsValue({
                enabled: row.enabled,
                use_custom: row.is_custom_price,
                custom_price_cents: row.unit_price_cents,
                notes: row.notes,
              });
            }}
          >编辑</Button>
          {row.is_custom_price && (
            <Popconfirm title="回退到默认配置？"
              description="将删除本客户的 override，使用全局默认价"
              onConfirm={() => removeMut.mutate({ cid: selectedCid!, slug: row.feature_slug })}
            >
              <Button size="small" type="text">回退默认</Button>
            </Popconfirm>
          )}
        </Space>
      ),
    },
  ];

  const selectedCustomer = customerList.find(c => c.id === selectedCid);
  const totalSpend = usage.reduce((s, u) => s + u.total_charged_cents, 0);

  return (
    <>
      <Card title="选择客户" style={{ marginBottom: 16 }}>
        <Select
          showSearch placeholder="按邮箱/姓名搜索客户"
          style={{ width: '100%', maxWidth: 500 }}
          value={selectedCid}
          onChange={setSelectedCid}
          filterOption={(input, option) =>
            (option?.label ?? '').toString().toLowerCase().includes(input.toLowerCase())
          }
          options={customerList.map(c => ({
            value: c.id,
            label: `${c.email}${c.name ? ` (${c.name})` : ''}${c.plan ? ` · ${c.plan.toUpperCase()}` : ''}`,
          }))}
        />
        {selectedCustomer && (
          <Row gutter={16} style={{ marginTop: 16 }}>
            <Col span={6}>
              <Statistic title="客户 ID" value={selectedCustomer.id} />
            </Col>
            <Col span={6}>
              <Statistic title="套餐"
                value={selectedCustomer.plan ? selectedCustomer.plan.toUpperCase() : '未订阅'}
              />
            </Col>
            <Col span={6}>
              <Statistic title="已开通功能数"
                value={features.filter(f => f.enabled).length}
                suffix={`/ ${features.length}`}
              />
            </Col>
            <Col span={6}>
              <Statistic title="近 30 天 feature 花费"
                value={(totalSpend / 100).toFixed(2)}
                prefix={<DollarOutlined />}
              />
            </Col>
          </Row>
        )}
      </Card>

      {selectedCid ? (
        <Card title={`功能列表（${features.length}）`}>
          <Table
            rowKey="feature_slug" dataSource={features} columns={columns}
            loading={featuresLoading} pagination={false}
            scroll={{ x: 1100 }}
          />
        </Card>
      ) : (
        <Card>
          <Empty description="请先选择一个客户查看其功能权限" />
        </Card>
      )}

      <Modal
        open={!!editing} title={`编辑：${editing?.name_zh}（${selectedCustomer?.email}）`}
        onCancel={() => setEditing(null)} onOk={handleSubmitEdit}
        okText="保存" confirmLoading={upsertMut.isPending}
        destroyOnClose
      >
        <Form form={editForm} layout="vertical">
          <Form.Item name="enabled" label="启用" valuePropName="checked">
            <Switch checkedChildren="开通" unCheckedChildren="关闭" />
          </Form.Item>
          <Form.Item name="use_custom" label="使用自定义单价" valuePropName="checked"
            extra="关闭则使用全局默认价">
            <Switch />
          </Form.Item>
          <Form.Item
            noStyle
            shouldUpdate={(prev, cur) => prev.use_custom !== cur.use_custom}
          >
            {({ getFieldValue }) =>
              getFieldValue('use_custom') ? (
                <Form.Item name="custom_price_cents" label="自定义单价 (cents)"
                  rules={[{ required: true, type: 'integer', min: 0 }]}>
                  <InputNumber min={0} style={{ width: '100%' }} />
                </Form.Item>
              ) : null
            }
          </Form.Item>
          <Form.Item name="notes" label="备注（如 VIP 八折）">
            <Input.TextArea rows={2} maxLength={500} />
          </Form.Item>
        </Form>
      </Modal>
    </>
  );
};

// ─── Main page ──────────────────────────────────────────────────────────

const FeaturePack: React.FC = () => {
  return (
    <div style={{ padding: 24 }}>
      <Title level={3}><AppstoreOutlined /> 功能包管理</Title>
      <Text type="secondary">
        在套餐订阅之外，按功能模块独立定价 + 给客户定制开通。功能消费走客户钱包扣费。
      </Text>
      <Tabs
        style={{ marginTop: 16 }}
        items={[
          {
            key: 'global',
            label: <span><DollarOutlined /> 全局定价</span>,
            children: <GlobalPricingTab />,
          },
          {
            key: 'customer',
            label: <span><UserOutlined /> 客户功能定制</span>,
            children: <PerCustomerTab />,
          },
        ]}
      />
    </div>
  );
};

export default FeaturePack;
