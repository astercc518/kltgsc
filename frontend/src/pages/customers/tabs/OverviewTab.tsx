import React, { useEffect, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Row, Col, Card, Progress, Statistic, Space } from 'antd';
import { getCustomerById } from '../../../services/adminCustomers';

interface MeterProps {
  title: string;
  used: number;
  total: number;
}

const QuotaMeter: React.FC<MeterProps> = ({ title, used, total }) => {
  const pct = total > 0 ? Math.min(100, Math.round((used / total) * 100)) : 0;
  return (
    <Card size="small">
      <Statistic title={title} value={used} suffix={`/ ${total}`} />
      <Progress percent={pct} size="small" status={pct >= 90 ? 'exception' : 'active'} />
    </Card>
  );
};

const OverviewTab: React.FC<{ customerId: number }> = ({ customerId }) => {
  const [pollCount, setPollCount] = useState(0);
  const polling = pollCount < 6;

  const { data } = useQuery({
    queryKey: ['admin-customer', customerId],
    queryFn: () => getCustomerById(customerId),
    refetchInterval: polling ? 5000 : false,
  });

  useEffect(() => {
    setPollCount(0);
  }, [customerId]);

  useEffect(() => {
    if (!polling) return;
    const t = setInterval(() => setPollCount((n) => n + 1), 5000);
    return () => clearInterval(t);
  }, [polling]);

  if (!data) return null;

  return (
    <Space direction="vertical" size="large" style={{ width: '100%' }}>
      <Row gutter={16}>
        <Col span={6}>
          <QuotaMeter title="TG 账号" used={data.account_used} total={data.account_quota} />
        </Col>
        <Col span={6}>
          <QuotaMeter title="AI 获客群" used={data.group_used} total={data.group_quota} />
        </Col>
        <Col span={6}>
          <QuotaMeter title="Token" used={data.token_used} total={data.token_quota} />
        </Col>
        <Col span={6}>
          <QuotaMeter title="销售席位" used={data.seat_used} total={data.seat_quota} />
        </Col>
      </Row>
      {polling && (
        <Card size="small" type="inner" title="资源分配进度">
          每 5 秒刷新一次，已刷新 {pollCount}/6 次。完成后停止。
        </Card>
      )}
    </Space>
  );
};

export default OverviewTab;
