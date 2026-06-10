import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Card, Table, Empty, Tag } from 'antd';
import dayjs from 'dayjs';
import { listCustomerUsage, type AdminFeatureUsageSummary } from '../../../services/adminCustomers';

const UsageLogsTab: React.FC<{ customerId: number }> = ({ customerId }) => {
  const { data, isLoading } = useQuery({
    queryKey: ['admin-customer-usage', customerId],
    queryFn: () => listCustomerUsage(customerId),
  });

  const columns = [
    { title: '功能', dataIndex: 'name_zh', key: 'name_zh' },
    { title: 'Slug', dataIndex: 'feature_slug', key: 'feature_slug', render: (s: string) => <Tag>{s}</Tag> },
    {
      title: '本月用量',
      dataIndex: 'units_consumed',
      key: 'units_consumed',
      sorter: (a: AdminFeatureUsageSummary, b: AdminFeatureUsageSummary) =>
        a.units_consumed - b.units_consumed,
      defaultSortOrder: 'descend' as const,
    },
    {
      title: '本月计费',
      dataIndex: 'total_charged_cents',
      key: 'total_charged_cents',
      render: (cents: number) => `$${(cents / 100).toFixed(2)}`,
    },
    {
      title: '最近一次',
      dataIndex: 'last_charged_at',
      key: 'last_charged_at',
      render: (t: string | null) => (t ? dayjs(t).format('YYYY-MM-DD HH:mm') : '—'),
    },
  ];

  return (
    <Card title="功能用量摘要">
      <Table<AdminFeatureUsageSummary>
        rowKey="feature_slug"
        dataSource={data ?? []}
        columns={columns}
        loading={isLoading}
        pagination={{ pageSize: 20 }}
        size="small"
        locale={{ emptyText: <Empty description="暂无用量数据" /> }}
      />
    </Card>
  );
};

export default UsageLogsTab;
