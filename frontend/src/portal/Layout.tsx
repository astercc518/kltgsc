/**
 * Customer portal layout — top bar with TG1.AI brand + plan badge,
 * left sidebar with 5 main sections, content area.
 *
 * Deliberately not reusing src/App.tsx's MainLayout: customers should not
 * see the admin sidebar (which has 25+ sections that mean nothing to them).
 */
import React from 'react';
import { Layout, Menu, Tag, Avatar, Dropdown, Spin } from 'antd';
import {
  DashboardOutlined,
  CreditCardOutlined,
  TeamOutlined,
  MessageOutlined,
  BookOutlined,
  LogoutOutlined,
  UserOutlined,
  MobileOutlined,
  SettingOutlined,
  WalletOutlined,
  AppstoreOutlined,
  SendOutlined,
} from '@ant-design/icons';
import { Link, Outlet, useLocation, Navigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { authApi } from './api';
import { logoutCustomer, isCustomerAuthenticated } from './auth';

const { Header, Sider, Content } = Layout;

const PLAN_BADGE: Record<string, { color: string; label: string }> = {
  starter: { color: 'blue', label: 'Starter' },
  growth: { color: 'green', label: 'Growth' },
  pro: { color: 'gold', label: 'Pro' },
};

const STATUS_BADGE: Record<string, { color: string; label: string }> = {
  pending: { color: 'orange', label: 'Pending Payment' },
  active: { color: 'green', label: 'Active' },
  suspended: { color: 'red', label: 'Suspended' },
  canceled: { color: 'default', label: 'Canceled' },
};

const PortalLayout: React.FC = () => {
  const location = useLocation();

  if (!isCustomerAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  const { data: me, isLoading } = useQuery({
    queryKey: ['portal', 'me'],
    queryFn: authApi.me,
    retry: false,
  });

  const menuItems = [
    { key: '/portal/dashboard', icon: <DashboardOutlined />, label: <Link to="/portal/dashboard">Dashboard</Link> },
    { key: '/portal/billing', icon: <CreditCardOutlined />, label: <Link to="/portal/billing">Billing</Link> },
    { key: '/portal/wallet', icon: <WalletOutlined />, label: <Link to="/portal/wallet">Wallet</Link> },
    { key: '/portal/features', icon: <AppstoreOutlined />, label: <Link to="/portal/features">Feature Pack</Link> },
    { key: '/portal/bulk', icon: <SendOutlined />, label: <Link to="/portal/bulk">Bulk Send</Link> },
    { key: '/portal/accounts', icon: <TeamOutlined />, label: <Link to="/portal/accounts">TG Accounts</Link> },
    { key: '/portal/leads', icon: <MessageOutlined />, label: <Link to="/portal/leads">Leads</Link> },
    { key: '/portal/knowledge-bases', icon: <BookOutlined />, label: <Link to="/portal/knowledge-bases">Knowledge Base</Link> },
    { key: '/portal/main-account', icon: <MobileOutlined />, label: <Link to="/portal/main-account">My Telegram</Link> },
    { key: '/portal/settings', icon: <SettingOutlined />, label: <Link to="/portal/settings">Settings</Link> },
  ];

  const userMenu = {
    items: [
      { key: 'logout', icon: <LogoutOutlined />, label: 'Logout', danger: true, onClick: () => logoutCustomer() },
    ],
  };

  const planBadge = me?.plan ? PLAN_BADGE[me.plan] : null;
  const statusBadge = me?.status ? STATUS_BADGE[me.status] : null;

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider
        width={220}
        style={{ background: '#0F172A' }}
      >
        <div style={{
          height: 64,
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          color: '#fff',
          fontWeight: 800,
          fontSize: 22,
          letterSpacing: 1,
        }}>
          TG1<span style={{ color: '#0066FF' }}>.AI</span>
        </div>
        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[location.pathname]}
          items={menuItems}
          style={{ background: 'transparent', borderRight: 0 }}
        />
      </Sider>
      <Layout>
        <Header style={{
          background: '#fff',
          padding: '0 24px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          borderBottom: '1px solid #f0f0f0',
        }}>
          <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
            {planBadge && <Tag color={planBadge.color} style={{ fontSize: 13, padding: '2px 12px' }}>{planBadge.label} Plan</Tag>}
            {statusBadge && <Tag color={statusBadge.color}>{statusBadge.label}</Tag>}
          </div>
          <Dropdown menu={userMenu} placement="bottomRight">
            <div style={{ cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Avatar icon={<UserOutlined />} size="small" />
              <span style={{ color: '#475569' }}>{me?.email || '...'}</span>
            </div>
          </Dropdown>
        </Header>
        <Content style={{ margin: 24, padding: 24, background: '#fff', minHeight: 'calc(100vh - 64px - 48px)' }}>
          {isLoading ? <Spin /> : <Outlet />}
        </Content>
      </Layout>
    </Layout>
  );
};

export default PortalLayout;
