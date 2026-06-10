import React, { useMemo, useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { Card, Table, Input, Select, Tag, Button, Space, Empty } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import dayjs from 'dayjs';
import { listCustomers, type Customer, type Plan, type CustomerStatus } from '../../services/adminCustomers';

const PLAN_COLOR: Record<Plan, string> = {
  starter: 'blue',
  growth: 'purple',
  pro: 'gold',
};
const STATUS_COLOR: Record<CustomerStatus, string> = {
  pending: 'default',
  active: 'green',
  suspended: 'orange',
  canceled: 'red',
};

const CustomerListPage: React.FC = () => {
  const navigate = useNavigate();
  const [search, setSearch] = useState('');
  const [planFilter, setPlanFilter] = useState<Plan[]>([]);
  const [statusFilter, setStatusFilter] = useState<CustomerStatus[]>([]);

  const { data, isLoading } = useQuery({
    queryKey: ['admin-customers'],
    queryFn: () => listCustomers({ limit: 500 }),
  });

  const filtered = useMemo(() => {
    let rows = data ?? [];
    if (search.trim()) {
      const s = search.trim().toLowerCase();
      rows = rows.filter((r) => r.email.toLowerCase().includes(s) || (r.name ?? '').toLowerCase().includes(s));
    }
    if (planFilter.length > 0) rows = rows.filter((r) => r.plan && planFilter.includes(r.plan));
    if (statusFilter.length > 0) rows = rows.filter((r) => statusFilter.includes(r.status));
    return rows;
  }, [data, search, planFilter, statusFilter]);

  const columns = [
    { title: 'Email', dataIndex: 'email', key: 'email' },
    { title: '姓名', dataIndex: 'name', key: 'name', render: (v: string | null) => v ?? '—' },
    {
      title: '套餐',
      dataIndex: 'plan',
      key: 'plan',
      render: (p: Plan | null) => (p ? <Tag color={PLAN_COLOR[p]}>{p}</Tag> : <Tag>无</Tag>),
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      render: (s: CustomerStatus) => <Tag color={STATUS_COLOR[s]}>{s}</Tag>,
    },
    {
      title: '续费倒计时',
      dataIndex: 'current_period_end',
      key: 'renewal',
      render: (end: string | null) => {
        if (!end) return '—';
        const days = dayjs(end).diff(dayjs(), 'day');
        const color = days < 7 ? '#cf1322' : undefined;
        return <span style={{ color }}>{days} 天</span>;
      },
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      render: (t: string) => dayjs(t).format('YYYY-MM-DD'),
    },
    {
      title: '操作',
      key: 'action',
      render: (_: unknown, r: Customer) => (
        <Button type="link" onClick={() => navigate(`/customers/${r.id}`)}>详情</Button>
      ),
    },
  ];

  return (
    <Card
      title="客户运营 / 客户列表"
      extra={
        <Button type="primary" icon={<PlusOutlined />} onClick={() => navigate('/customers/new')}>
          新建客户
        </Button>
      }
    >
      <Space style={{ marginBottom: 16 }}>
        <Input.Search
          placeholder="搜索邮箱或姓名"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          style={{ width: 280 }}
          allowClear
        />
        <Select
          mode="multiple"
          placeholder="套餐"
          value={planFilter}
          onChange={setPlanFilter}
          style={{ width: 200 }}
          options={[
            { value: 'starter', label: 'Starter' },
            { value: 'growth', label: 'Growth' },
            { value: 'pro', label: 'Pro' },
          ]}
        />
        <Select
          mode="multiple"
          placeholder="状态"
          value={statusFilter}
          onChange={setStatusFilter}
          style={{ width: 200 }}
          options={[
            { value: 'pending', label: 'Pending' },
            { value: 'active', label: 'Active' },
            { value: 'suspended', label: 'Suspended' },
            { value: 'canceled', label: 'Canceled' },
          ]}
        />
      </Space>
      <Table
        rowKey="id"
        loading={isLoading}
        columns={columns}
        dataSource={filtered}
        pagination={{ pageSize: 20, showSizeChanger: true }}
        locale={{
          emptyText: (
            <Empty
              description={data && data.length === 0 ? '还没有客户' : '没有匹配结果'}
            >
              {data && data.length === 0 && (
                <Button type="primary" onClick={() => navigate('/customers/new')}>
                  立即开户第一个客户
                </Button>
              )}
            </Empty>
          ),
        }}
      />
    </Card>
  );
};

export default CustomerListPage;
