import React from 'react';
import { Table, Tag, Typography, Empty, Alert } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { resourcesApi } from '../api';

const { Title, Text } = Typography;

const STATUS_COLOR: Record<string, string> = {
  init: 'default', active: 'green', banned: 'red',
  spam_block: 'orange', flood_wait: 'orange',
};

const ROLE_LABEL: Record<string, string> = {
  cannon: 'Cannon', scout: 'Scout', actor: 'Actor', sniper: 'Sniper',
};

const PortalAccounts: React.FC = () => {
  const { data: accounts = [], isLoading } = useQuery({
    queryKey: ['portal', 'accounts'],
    queryFn: resourcesApi.accounts,
  });

  return (
    <div>
      <Title level={3}>My TG Accounts</Title>
      <Text type="secondary">
        TG accounts allocated to your subscription. Industry-customized, pre-warmed, and
        auto-replaced on ban.
      </Text>

      {accounts.length === 0 && !isLoading && (
        <Alert
          type="info"
          showIcon
          style={{ margin: '24px 0' }}
          message="No accounts allocated yet"
          description={
            <span>
              Accounts will be assigned automatically once your subscription is active.
              If you've just paid, please allow a few minutes for ops to confirm and
              allocate from the pool. <Link to="/portal/billing">Check billing status</Link>.
            </span>
          }
        />
      )}

      <Table
        loading={isLoading}
        dataSource={accounts}
        rowKey="id"
        size="small"
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: 'Phone', dataIndex: 'phone_number' },
          {
            title: 'Status', dataIndex: 'status',
            render: (s) => <Tag color={STATUS_COLOR[s] || 'default'}>{s}</Tag>,
          },
          {
            title: 'Role', dataIndex: 'combat_role',
            render: (r) => ROLE_LABEL[r] || r,
          },
          {
            title: 'Health', dataIndex: 'health_score',
            render: (h) => `${h}/100`,
          },
          {
            title: 'Last Active', dataIndex: 'last_active',
            render: (v) => v ? new Date(v).toLocaleString() : '—',
          },
        ]}
        pagination={{ pageSize: 20 }}
        locale={{ emptyText: <Empty description="No accounts yet" /> }}
      />
    </div>
  );
};

export default PortalAccounts;
