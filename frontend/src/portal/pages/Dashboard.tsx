import React from 'react';
import { Card, Row, Col, Progress, Statistic, Typography, Alert, Button, Empty } from 'antd';
import { TeamOutlined, MessageOutlined, BookOutlined, RocketOutlined, CrownOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { resourcesApi, authApi } from '../api';

const { Title, Text } = Typography;

function pct(used: number, limit: number): number {
  if (!limit) return 0;
  return Math.min(100, Math.round((used / limit) * 100));
}

function daysUntil(iso: string | null): number | null {
  if (!iso) return null;
  const ms = new Date(iso).getTime() - Date.now();
  return Math.max(0, Math.ceil(ms / (1000 * 60 * 60 * 24)));
}

const QuotaMeter: React.FC<{ icon: React.ReactNode; label: string; used: number; limit: number; suffix?: string }> = ({
  icon, label, used, limit, suffix = '',
}) => (
  <Card size="small">
    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 8, color: '#475569' }}>
      {icon}
      <Text strong>{label}</Text>
    </div>
    <Statistic value={used} suffix={`/ ${limit.toLocaleString()}${suffix}`} valueStyle={{ fontSize: 24 }} />
    <Progress
      percent={pct(used, limit)}
      strokeColor={limit && used / limit > 0.85 ? '#ef4444' : '#0066FF'}
      showInfo={false}
      style={{ marginTop: 8 }}
    />
  </Card>
);

const PortalDashboard: React.FC = () => {
  const { data: quota } = useQuery({
    queryKey: ['portal', 'quota'],
    queryFn: resourcesApi.quota,
    refetchInterval: 15000,
  });
  const { data: me } = useQuery({
    queryKey: ['portal', 'me'],
    queryFn: authApi.me,
  });

  const daysLeft = daysUntil(quota?.current_period_end ?? null);
  const isActive = quota?.status === 'active';
  const isPending = quota?.status === 'pending';

  return (
    <div>
      <Title level={3} style={{ marginBottom: 4 }}>Welcome back{me?.name ? `, ${me.name}` : ''}</Title>
      <Text type="secondary">
        {me?.company ? `${me.company} · ` : ''}
        {me?.industry ? me.industry.toUpperCase() : 'Set your industry to unlock auto-generated KB'}
      </Text>

      {isPending && (
        <Alert
          type="warning"
          showIcon
          style={{ marginTop: 24 }}
          message="Your account is pending — pick a plan to activate"
          description="Subscribe to a plan and complete the USDT payment to start using TG accounts and AI lead generation."
          action={<Link to="/portal/billing"><Button type="primary" size="small">Choose a plan</Button></Link>}
        />
      )}

      {isActive && (
        <Alert
          type="success"
          showIcon
          style={{ marginTop: 24 }}
          message={
            <span>
              <CrownOutlined /> {quota?.plan?.toUpperCase()} plan active
              {daysLeft != null && ` — renews in ${daysLeft} day${daysLeft === 1 ? '' : 's'}`}
            </span>
          }
        />
      )}

      <Title level={5} style={{ marginTop: 32, marginBottom: 16 }}>Quota Usage</Title>
      {quota ? (
        <Row gutter={16}>
          <Col xs={24} sm={12} lg={6}>
            <QuotaMeter
              icon={<TeamOutlined />}
              label="TG Accounts"
              used={quota.usage.accounts}
              limit={quota.limits.account_quota}
            />
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <QuotaMeter
              icon={<RocketOutlined />}
              label="AI Target Groups"
              used={0 /* group_used not yet wired */}
              limit={quota.limits.group_quota}
            />
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <QuotaMeter
              icon={<MessageOutlined />}
              label="Leads Captured"
              used={quota.usage.leads}
              limit={quota.limits.account_quota * 200 /* soft cap, no real limit */}
            />
          </Col>
          <Col xs={24} sm={12} lg={6}>
            <QuotaMeter
              icon={<BookOutlined />}
              label="AI Tokens"
              used={quota.usage.tokens}
              limit={quota.limits.token_quota}
              suffix=" tok"
            />
          </Col>
        </Row>
      ) : (
        <Empty description="Loading quota…" />
      )}
    </div>
  );
};

export default PortalDashboard;
