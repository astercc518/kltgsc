import React from 'react';
import {
  Card, Descriptions, Tag, Button, Space, Typography, Alert, Spin, Result,
  Timeline, message,
} from 'antd';
import {
  ArrowLeftOutlined, MessageOutlined, MailOutlined, PhoneOutlined,
  CheckCircleOutlined, DollarOutlined,
} from '@ant-design/icons';
import { useNavigate, useParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { leadsApi } from '../api';

const { Title, Text, Paragraph } = Typography;


const LeadDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();

  // Opening this route triggers the charge by calling /sales/leads/{id}/view
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['sales', 'lead', id, 'view'],
    queryFn: () => leadsApi.view(Number(id)),
    retry: false,
  });

  if (isLoading) return <Spin tip="Charging wallet and unlocking lead..." />;

  if (isError) {
    const errAny = error as any;
    const status = errAny?.response?.status;
    const detail = errAny?.response?.data?.detail || 'Failed to load lead';
    if (status === 402) {
      return (
        <Result
          status="warning"
          title="Insufficient balance"
          subTitle={`${detail}. Top up your wallet to view this lead.`}
          extra={[
            <Button type="primary" key="topup" onClick={() => nav('/sales/wallet')}>
              Topup wallet
            </Button>,
            <Button key="back" onClick={() => nav(-1)}>Back</Button>,
          ]}
        />
      );
    }
    return <Alert type="error" message={detail} />;
  }

  if (!data) return null;
  const { lead, charged_cents, balance_after_cents, charge_skipped } = data;

  return (
    <div>
      <Space style={{ marginBottom: 16 }}>
        <Button icon={<ArrowLeftOutlined />} onClick={() => nav(-1)}>Back</Button>
      </Space>

      {charge_skipped ? (
        <Alert
          type="info" showIcon
          icon={<CheckCircleOutlined />}
          message="Free re-open"
          description={`You've already paid to view this lead today. Balance: $${(balance_after_cents/100).toFixed(2)}`}
          style={{ marginBottom: 16 }}
        />
      ) : (
        <Alert
          type="success" showIcon
          icon={<DollarOutlined />}
          message={`Charged $${(charged_cents/100).toFixed(2)} from your wallet`}
          description={`Remaining balance: $${(balance_after_cents/100).toFixed(2)} · This lead is free to re-open today.`}
          style={{ marginBottom: 16 }}
        />
      )}

      <Card>
        <Title level={3} style={{ margin: 0 }}>
          {lead.first_name || ''} {lead.last_name || ''}
          {lead.username && (
            <Text type="secondary" style={{ marginLeft: 12, fontSize: 16 }}>
              @{lead.username}
            </Text>
          )}
        </Title>
        <Space style={{ marginTop: 8 }}>
          {lead.industry && <Tag color="cyan">{lead.industry}</Tag>}
          {lead.category && <Tag color="purple">{lead.category}</Tag>}
          <Tag>{lead.source}</Tag>
          <Tag color="green">{lead.status}</Tag>
          <Text type="secondary">viewed {lead.view_count}×</Text>
        </Space>

        <Descriptions bordered column={2} style={{ marginTop: 24 }} size="middle">
          <Descriptions.Item label="Telegram ID" span={2}>
            <Space>
              <code>{lead.telegram_user_id}</code>
              <Button
                size="small" type="text"
                onClick={() => {
                  navigator.clipboard.writeText(String(lead.telegram_user_id));
                  message.success('Copied');
                }}
              >Copy</Button>
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label={<><MailOutlined /> Username</>}>
            {lead.username ? `@${lead.username}` : '—'}
          </Descriptions.Item>
          <Descriptions.Item label={<><PhoneOutlined /> Phone</>}>
            {lead.phone ? (
              <Space>
                <code>{lead.phone}</code>
                <Button size="small" type="text" onClick={() => {
                  navigator.clipboard.writeText(lead.phone!);
                  message.success('Copied');
                }}>Copy</Button>
              </Space>
            ) : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Tags">
            {lead.tags.length ? lead.tags.map(t => <Tag key={t}>{t}</Tag>) : '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Notes">
            {lead.notes || <Text type="secondary">none</Text>}
          </Descriptions.Item>
          <Descriptions.Item label="Bulk batch">
            {lead.bulk_batch_id ?? '—'}
          </Descriptions.Item>
          <Descriptions.Item label="Account ID">
            {lead.account_id}
          </Descriptions.Item>
          <Descriptions.Item label="Created">
            {new Date(lead.created_at).toLocaleString()}
          </Descriptions.Item>
          <Descriptions.Item label="Last interaction">
            {new Date(lead.last_interaction_at).toLocaleString()}
          </Descriptions.Item>
        </Descriptions>

        <Alert
          type="info" showIcon
          icon={<MessageOutlined />}
          style={{ marginTop: 24 }}
          message="To message this lead"
          description={
            <span>
              Use the TG account linked to this lead (id {lead.account_id}) and DM{' '}
              <code>@{lead.username || lead.telegram_user_id}</code>. Direct in-app
              messaging is coming in a follow-up.
            </span>
          }
        />

        {lead.interactions.length > 0 && (
          <>
            <Title level={5} style={{ marginTop: 24 }}>Recent interactions</Title>
            <Timeline
              items={lead.interactions.map(i => ({
                color: i.direction === 'inbound' ? 'blue' : 'green',
                children: (
                  <>
                    <Text strong>{i.direction === 'inbound' ? 'They' : 'Us'}</Text>{' '}
                    <Text type="secondary" style={{ fontSize: 12 }}>
                      {new Date(i.created_at).toLocaleString()}
                    </Text>
                    <Paragraph>{i.content}</Paragraph>
                  </>
                ),
              }))}
            />
          </>
        )}
      </Card>
    </div>
  );
};

export default LeadDetail;
