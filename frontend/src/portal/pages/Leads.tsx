import React from 'react';
import { Table, Tag, Typography, Empty } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { resourcesApi } from '../api';

const { Title, Text } = Typography;

const STATUS_COLOR: Record<string, string> = {
  new: 'blue', contacted: 'cyan', replied: 'gold',
  interested: 'orange', converted: 'green', closed: 'default',
};

const PortalLeads: React.FC = () => {
  const { data: leads = [], isLoading } = useQuery({
    queryKey: ['portal', 'leads'],
    queryFn: () => resourcesApi.leads(),
  });

  return (
    <div>
      <Title level={3}>Leads</Title>
      <Text type="secondary">
        Prospects captured by your AI from monitored groups and DMs.
        High-intent leads trigger real-time alerts.
      </Text>

      <Table
        style={{ marginTop: 24 }}
        loading={isLoading}
        dataSource={leads}
        rowKey="id"
        size="small"
        columns={[
          { title: 'ID', dataIndex: 'id', width: 60 },
          { title: 'TG Username', dataIndex: 'username',
            render: (v, r) => v || r.first_name || r.telegram_user_id },
          {
            title: 'Status', dataIndex: 'status',
            render: (s) => <Tag color={STATUS_COLOR[s] || 'default'}>{s}</Tag>,
          },
          { title: 'AI Active', dataIndex: 'ai_enabled',
            render: (v) => v ? <Tag color="blue">AI</Tag> : <Tag color="gold">Sales</Tag> },
          { title: 'Last Interaction', dataIndex: 'last_interaction_at',
            render: (v) => v ? new Date(v).toLocaleString() : '—' },
        ]}
        pagination={{ pageSize: 20 }}
        locale={{ emptyText: <Empty description="No leads captured yet — start your campaigns to begin acquiring." /> }}
      />
    </div>
  );
};

export default PortalLeads;
