import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Card, Descriptions, Tooltip, InputNumber, Table, Switch, Space, message, Tag } from 'antd';
import {
  getCustomerById,
  listFeatureRegistry,
  listCustomerFeatures,
  upsertCustomerFeature,
  AdminApiError,
  type AdminFeatureEntry,
  type AdminCustomerFeature,
} from '../../../services/adminCustomers';

const QuotaFeaturesTab: React.FC<{ customerId: number }> = ({ customerId }) => {
  const queryClient = useQueryClient();

  const { data: customer } = useQuery({
    queryKey: ['admin-customer', customerId],
    queryFn: () => getCustomerById(customerId),
  });
  const { data: registry } = useQuery({
    queryKey: ['admin-feature-registry'],
    queryFn: listFeatureRegistry,
  });
  const { data: customerFeatures } = useQuery({
    queryKey: ['admin-customer-features', customerId],
    queryFn: () => listCustomerFeatures(customerId),
  });

  const toggleMutation = useMutation({
    mutationFn: ({ slug, enabled }: { slug: string; enabled: boolean }) =>
      upsertCustomerFeature(customerId, slug, { enabled }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-customer-features', customerId] });
      message.success('已更新');
    },
    onError: (err: unknown) =>
      message.error(err instanceof AdminApiError ? err.message : '更新失败'),
  });

  const enabledMap = new Map(
    (customerFeatures ?? []).map((f: AdminCustomerFeature) => [f.feature_slug, f.enabled]),
  );

  const featureColumns = [
    { title: '功能', dataIndex: 'name_zh', key: 'name_zh' },
    { title: 'Slug', dataIndex: 'slug', key: 'slug', render: (s: string) => <Tag>{s}</Tag> },
    { title: '说明', dataIndex: 'description', key: 'description', render: (d: string) => d || '—' },
    {
      title: '已启用',
      key: 'enabled',
      render: (_: unknown, r: AdminFeatureEntry) => {
        const enabled = enabledMap.get(r.slug) ?? r.enabled_by_default;
        return (
          <Switch
            checked={enabled}
            loading={toggleMutation.isPending && toggleMutation.variables?.slug === r.slug}
            onChange={(next) => toggleMutation.mutate({ slug: r.slug, enabled: next })}
          />
        );
      },
    },
  ];

  const readOnlyTip = '暂不支持后台调整，需联系开发';

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Card title="配额上限 (只读)">
        <Descriptions size="small" column={2}>
          <Descriptions.Item label="TG 账号">
            <Tooltip title={readOnlyTip}>
              <InputNumber disabled value={customer?.account_quota} addonAfter={`已用 ${customer?.account_used ?? 0}`} />
            </Tooltip>
          </Descriptions.Item>
          <Descriptions.Item label="AI 获客群">
            <Tooltip title={readOnlyTip}>
              <InputNumber disabled value={customer?.group_quota} addonAfter={`已用 ${customer?.group_used ?? 0}`} />
            </Tooltip>
          </Descriptions.Item>
          <Descriptions.Item label="Token">
            <Tooltip title={readOnlyTip}>
              <InputNumber disabled value={customer?.token_quota} addonAfter={`已用 ${customer?.token_used ?? 0}`} />
            </Tooltip>
          </Descriptions.Item>
          <Descriptions.Item label="销售席位">
            <Tooltip title={readOnlyTip}>
              <InputNumber disabled value={customer?.seat_quota} addonAfter={`已用 ${customer?.seat_used ?? 0}`} />
            </Tooltip>
          </Descriptions.Item>
        </Descriptions>
      </Card>

      <Card title="功能开关">
        <Table<AdminFeatureEntry>
          rowKey="slug"
          dataSource={registry ?? []}
          columns={featureColumns}
          pagination={false}
          size="small"
        />
      </Card>
    </Space>
  );
};

export default QuotaFeaturesTab;
