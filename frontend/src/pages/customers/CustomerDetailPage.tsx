import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { useParams, useSearchParams, useNavigate } from 'react-router-dom';
import { Card, Tabs, Tag, Space, Button, Spin, Result, Descriptions } from 'antd';
import { ArrowLeftOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { getCustomerById, type Plan, type CustomerStatus } from '../../services/adminCustomers';
import OverviewTab from './tabs/OverviewTab';
import BillingTab from './tabs/BillingTab';
import AllocationTab from './tabs/AllocationTab';
import QuotaFeaturesTab from './tabs/QuotaFeaturesTab';
import UsageLogsTab from './tabs/UsageLogsTab';

const PLAN_COLOR: Record<Plan, string> = { starter: 'blue', growth: 'purple', pro: 'gold' };
const STATUS_COLOR: Record<CustomerStatus, string> = {
  pending: 'default',
  active: 'green',
  suspended: 'orange',
  canceled: 'red',
};

const CustomerDetailPage: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const [search, setSearch] = useSearchParams();
  const customerId = Number(id);

  const { data: customer, isLoading, error } = useQuery({
    queryKey: ['admin-customer', customerId],
    queryFn: () => getCustomerById(customerId),
    enabled: Number.isFinite(customerId),
  });

  if (isLoading) return <Spin tip="加载中..." style={{ display: 'block', padding: 48 }} />;
  if (error || !customer) {
    return (
      <Result
        status="404"
        title="未找到该客户"
        extra={<Button onClick={() => navigate('/customers')}>返回列表</Button>}
      />
    );
  }

  const activeTab = search.get('tab') ?? 'overview';
  const setTab = (k: string) => {
    search.set('tab', k);
    setSearch(search, { replace: true });
  };

  const renewalDays = customer.current_period_end
    ? dayjs(customer.current_period_end).diff(dayjs(), 'day')
    : null;

  return (
    <Card
      title={
        <Space>
          <Button icon={<ArrowLeftOutlined />} onClick={() => navigate('/customers')} />
          <span>{customer.name ?? customer.email}</span>
          {customer.plan && <Tag color={PLAN_COLOR[customer.plan]}>{customer.plan}</Tag>}
          <Tag color={STATUS_COLOR[customer.status]}>{customer.status}</Tag>
        </Space>
      }
    >
      <Descriptions size="small" column={4} style={{ marginBottom: 16 }}>
        <Descriptions.Item label="Email">{customer.email}</Descriptions.Item>
        <Descriptions.Item label="行业">{customer.industry ?? '—'}</Descriptions.Item>
        <Descriptions.Item label="续费倒计时">
          {renewalDays !== null ? (
            <span style={{ color: renewalDays < 7 ? '#cf1322' : undefined }}>{renewalDays} 天</span>
          ) : (
            '—'
          )}
        </Descriptions.Item>
        <Descriptions.Item label="创建时间">{dayjs(customer.created_at).format('YYYY-MM-DD')}</Descriptions.Item>
      </Descriptions>

      <Tabs
        activeKey={activeTab}
        onChange={setTab}
        items={[
          { key: 'overview', label: '概览', children: <OverviewTab customerId={customerId} /> },
          { key: 'billing', label: '订阅账单', children: <BillingTab customerId={customerId} /> },
          { key: 'allocation', label: '资源分配', children: <AllocationTab customerId={customerId} /> },
          { key: 'quota', label: '配额功能', children: <QuotaFeaturesTab customerId={customerId} /> },
          { key: 'usage', label: '用量日志', children: <UsageLogsTab customerId={customerId} /> },
        ]}
      />
    </Card>
  );
};

export default CustomerDetailPage;
