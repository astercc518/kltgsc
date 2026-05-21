/**
 * Sales workbench layout — minimal: brand bar + 3-item sidebar + content.
 *
 * Self-protecting: if no sales token, redirects to /login. JWT introspection
 * gives us role/email/customer_id for the header chip without a server call.
 */
import React from 'react';
import { Layout, Menu, Avatar, Dropdown, Tag, Typography } from 'antd';
import {
  InboxOutlined, WalletOutlined, SettingOutlined,
  LogoutOutlined, UserOutlined,
} from '@ant-design/icons';
import { Link, Outlet, useLocation, Navigate } from 'react-router-dom';
import { decodeJwtPayload } from './api';
import { isSalesAuthenticated, logoutSales } from './auth';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const SalesLayout: React.FC = () => {
  const location = useLocation();

  if (!isSalesAuthenticated()) {
    return <Navigate to="/login" replace />;
  }

  const profile = decodeJwtPayload();

  const menuItems = [
    { key: '/sales/inbox',    icon: <InboxOutlined />,    label: <Link to="/sales/inbox">Lead Inbox</Link> },
    { key: '/sales/wallet',   icon: <WalletOutlined />,   label: <Link to="/sales/wallet">My Wallet</Link> },
    { key: '/sales/settings', icon: <SettingOutlined />,  label: <Link to="/sales/settings">Settings</Link> },
  ];

  const userMenu = {
    items: [
      { key: 'logout', icon: <LogoutOutlined />, label: 'Logout', danger: true,
        onClick: () => logoutSales() },
    ],
  };

  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Header style={{
        display: 'flex', alignItems: 'center', justifyContent: 'space-between',
        background: '#001529', padding: '0 24px',
      }}>
        <div style={{ color: '#fff', fontSize: 18, fontWeight: 600 }}>
          TG1.AI · Sales
          {profile?.kind === 'platform' && (
            <Tag color="purple" style={{ marginLeft: 12 }}>PLATFORM</Tag>
          )}
          {profile?.kind === 'customer' && (
            <Tag color="cyan" style={{ marginLeft: 12 }}>TENANT</Tag>
          )}
        </div>
        <Dropdown menu={userMenu} placement="bottomRight">
          <div style={{ cursor: 'pointer', color: '#fff' }}>
            <Avatar icon={<UserOutlined />} style={{ background: '#1677ff' }} />
            <Text style={{ color: '#fff', marginLeft: 8 }}>{profile?.email || ''}</Text>
          </div>
        </Dropdown>
      </Header>
      <Layout>
        <Sider width={220} style={{ background: '#fff' }}>
          <Menu
            mode="inline"
            selectedKeys={[location.pathname]}
            items={menuItems}
            style={{ height: '100%', borderRight: 0, paddingTop: 16 }}
          />
        </Sider>
        <Content style={{ padding: 24, background: '#f5f5f5' }}>
          <div style={{ background: '#fff', padding: 24, minHeight: '80vh' }}>
            <Outlet />
          </div>
        </Content>
      </Layout>
    </Layout>
  );
};

export default SalesLayout;
