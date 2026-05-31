import React, { useState } from 'react';
import {
  Alert, Button, Drawer, Empty, List, Skeleton, Space, Table, Tag, Typography,
} from 'antd';
import { CustomerServiceOutlined, BranchesOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { resourcesApi } from '../api';

const { Title, Text, Paragraph } = Typography;

const STATUS_COLOR: Record<string, string> = {
  new: 'blue', contacted: 'cyan', replied: 'gold',
  interested: 'orange', converted: 'green', closed: 'default',
};

const PortalLeads: React.FC = () => {
  const { data: leads = [], isLoading } = useQuery({
    queryKey: ['portal', 'leads'],
    queryFn: () => resourcesApi.leads(),
  });

  const [attrLeadId, setAttrLeadId] = useState<number | null>(null);

  const attrQuery = useQuery({
    queryKey: ['portal', 'leads', attrLeadId, 'attribution'],
    queryFn: () => resourcesApi.leadAttribution(attrLeadId as number),
    enabled: attrLeadId !== null,
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
          {
            title: '来源', key: 'attribution', width: 88,
            render: (_, r: any) => (
              <Button
                size="small"
                type="link"
                icon={<BranchesOutlined />}
                onClick={() => setAttrLeadId(r.id)}
              >
                追溯
              </Button>
            ),
          },
        ]}
        pagination={{ pageSize: 20 }}
        locale={{ emptyText: <Empty description="No leads captured yet — start your campaigns to begin acquiring." /> }}
      />

      <Drawer
        title={attrLeadId ? `Lead #${attrLeadId} 来源追溯` : '来源追溯'}
        placement="right"
        width={520}
        open={attrLeadId !== null}
        onClose={() => setAttrLeadId(null)}
      >
        {attrQuery.isLoading && <Skeleton active />}
        {attrQuery.isError && (
          <Alert type="error" showIcon message="加载失败，请重试" />
        )}
        {attrQuery.data && attrQuery.data.entries.length === 0 && (
          <Empty description="尚未匹配到触发此 lead 的群内 AI 回复。后台会自动回填，30 分钟后重试。" />
        )}
        {attrQuery.data && attrQuery.data.entries.length > 0 && (
          <>
            <Paragraph type="secondary" style={{ marginBottom: 12 }}>
              共 {attrQuery.data.entries.length} 条群内 AI 回复在 24h 内归因到此 lead。
            </Paragraph>
            <List
              size="small"
              itemLayout="vertical"
              dataSource={attrQuery.data.entries}
              renderItem={(e) => (
                <List.Item key={e.pending_reply_id}>
                  <Space direction="vertical" size={4} style={{ width: '100%' }}>
                    <Space wrap>
                      <Tag color="blue">reply #{e.pending_reply_id}</Tag>
                      {e.monitor_id !== null && <Tag>monitor {e.monitor_id}</Tag>}
                      {e.chat_id !== null && <Tag color="cyan">chat {e.chat_id}</Tag>}
                      {e.layer3_score !== null && (
                        <Tag color="purple">L3 {e.layer3_score}</Tag>
                      )}
                      {e.experiment_tag && (
                        <Tag color="magenta">{e.experiment_tag}</Tag>
                      )}
                      {e.sent_at && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                          {new Date(e.sent_at).toLocaleString()}
                        </Text>
                      )}
                    </Space>
                    {e.source_text && (
                      <Paragraph style={{ marginBottom: 0 }}>
                        <Text strong>群消息：</Text>
                        <Text>{e.source_text}</Text>
                      </Paragraph>
                    )}
                    {e.reply_text && (
                      <Paragraph style={{ marginBottom: 0 }}>
                        <Text strong>AI 回复：</Text>
                        <Text type="secondary">{e.reply_text}</Text>
                      </Paragraph>
                    )}
                  </Space>
                </List.Item>
              )}
            />
          </>
        )}
      </Drawer>
    </div>
  );
};

export default PortalLeads;
