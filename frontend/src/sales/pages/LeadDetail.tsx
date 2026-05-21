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
import { useT } from '../i18n';

const { Title, Text, Paragraph } = Typography;


const LeadDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const nav = useNavigate();
  const t = useT();

  // Opening this route triggers the charge by calling /sales/leads/{id}/view
  const { data, isLoading, isError, error } = useQuery({
    queryKey: ['sales', 'lead', id, 'view'],
    queryFn: () => leadsApi.view(Number(id)),
    retry: false,
  });

  if (isLoading) return <Spin tip={t('detail.charging')} />;

  if (isError) {
    const errAny = error as any;
    const status = errAny?.response?.status;
    const detail = errAny?.response?.data?.detail || 'Failed to load lead';
    if (status === 402) {
      return (
        <Result
          status="warning"
          title={t('detail.insufficientTitle')}
          subTitle={`${detail}. ${t('detail.insufficientHint')}`}
          extra={[
            <Button type="primary" key="topup" onClick={() => nav('/sales/wallet')}>
              {t('detail.topupBtn')}
            </Button>,
            <Button key="back" onClick={() => nav(-1)}>{t('common.back')}</Button>,
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
        <Button icon={<ArrowLeftOutlined />} onClick={() => nav(-1)}>{t('common.back')}</Button>
      </Space>

      {charge_skipped ? (
        <Alert
          type="info" showIcon
          icon={<CheckCircleOutlined />}
          message={t('detail.freeReopen')}
          description={`${t('detail.freeReopenDesc')}: $${(balance_after_cents/100).toFixed(2)}`}
          style={{ marginBottom: 16 }}
        />
      ) : (
        <Alert
          type="success" showIcon
          icon={<DollarOutlined />}
          message={`${t('detail.chargedTitle')} $${(charged_cents/100).toFixed(2)}`}
          description={`${t('detail.chargedDesc')}: $${(balance_after_cents/100).toFixed(2)} · ${t('detail.freeRest')}`}
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
          <Text type="secondary">{t('detail.viewed')} {lead.view_count}×</Text>
        </Space>

        <Descriptions bordered column={2} style={{ marginTop: 24 }} size="middle">
          <Descriptions.Item label={t('detail.tgId')} span={2}>
            <Space>
              <code>{lead.telegram_user_id}</code>
              <Button
                size="small" type="text"
                onClick={() => {
                  navigator.clipboard.writeText(String(lead.telegram_user_id));
                  message.success(t('common.copied'));
                }}
              >{t('common.copy')}</Button>
            </Space>
          </Descriptions.Item>
          <Descriptions.Item label={<><MailOutlined /> {t('detail.username')}</>}>
            {lead.username ? `@${lead.username}` : '—'}
          </Descriptions.Item>
          <Descriptions.Item label={<><PhoneOutlined /> {t('detail.phone')}</>}>
            {lead.phone ? (
              <Space>
                <code>{lead.phone}</code>
                <Button size="small" type="text" onClick={() => {
                  navigator.clipboard.writeText(lead.phone!);
                  message.success(t('common.copied'));
                }}>{t('common.copy')}</Button>
              </Space>
            ) : '—'}
          </Descriptions.Item>
          <Descriptions.Item label={t('detail.tags')}>
            {lead.tags.length ? lead.tags.map(tg => <Tag key={tg}>{tg}</Tag>) : '—'}
          </Descriptions.Item>
          <Descriptions.Item label={t('detail.notes')}>
            {lead.notes || <Text type="secondary">{t('detail.noNotes')}</Text>}
          </Descriptions.Item>
          <Descriptions.Item label={t('detail.bulkBatch')}>
            {lead.bulk_batch_id ?? '—'}
          </Descriptions.Item>
          <Descriptions.Item label={t('detail.accountId')}>
            {lead.account_id}
          </Descriptions.Item>
          <Descriptions.Item label={t('detail.created')}>
            {new Date(lead.created_at).toLocaleString()}
          </Descriptions.Item>
          <Descriptions.Item label={t('detail.lastInteraction')}>
            {new Date(lead.last_interaction_at).toLocaleString()}
          </Descriptions.Item>
        </Descriptions>

        <Alert
          type="info" showIcon
          icon={<MessageOutlined />}
          style={{ marginTop: 24 }}
          message={t('detail.dmHint')}
          description={
            <span>
              {t('detail.dmDesc')} (id {lead.account_id}):{' '}
              <code>@{lead.username || lead.telegram_user_id}</code>. {t('detail.dmComing')}
            </span>
          }
        />

        {lead.interactions.length > 0 && (
          <>
            <Title level={5} style={{ marginTop: 24 }}>{t('detail.interactions')}</Title>
            <Timeline
              items={lead.interactions.map(i => ({
                color: i.direction === 'inbound' ? 'blue' : 'green',
                children: (
                  <>
                    <Text strong>{i.direction === 'inbound' ? t('detail.them') : t('detail.us')}</Text>{' '}
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
