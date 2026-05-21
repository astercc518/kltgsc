import React from 'react';
import { Table, Tag, Typography, Empty, Button, Space, Alert } from 'antd';
import { CustomerServiceOutlined } from '@ant-design/icons';
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
      <Space style={{ justifyContent: 'space-between', width: '100%', alignItems: 'flex-start' }}>
        <div>
          <Title level={3} style={{ marginBottom: 0 }}>Leads</Title>
          <Text type="secondary">
            Prospects captured by your AI from monitored groups and DMs.
            High-intent leads trigger real-time alerts.
          </Text>
        </div>
        <Button
          type="primary"
          icon={<CustomerServiceOutlined />}
          onClick={() => window.open('/sales/inbox', '_blank')}
        >
          打开销售工作台
        </Button>
      </Space>

      <Alert
        type="info"
        showIcon
        style={{ marginTop: 16, marginBottom: 8 }}
        message="销售坐席接管"
        description="要私聊回复某个 lead，请到「销售工作台 → Inbox」由销售人员手动接管。此页只读，便于客户管理者查看全量线索。"
      />

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
