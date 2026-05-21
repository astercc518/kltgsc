/**
 * Sales workbench layout — minimal: brand bar + 3-item sidebar + content.
 *
 * Self-protecting: if no sales token, redirects to /login. JWT introspection
 * gives us role/email/customer_id for the header chip without a server call.
 */
import React from 'react';
import { Layout, Menu, Avatar, Dropdown, Tag, Typography, Segmented } from 'antd';
import {
  InboxOutlined, WalletOutlined, SettingOutlined,
  LogoutOutlined, UserOutlined, GlobalOutlined,
  ThunderboltOutlined, PhoneOutlined,
} from '@ant-design/icons';
import { Link, Outlet, useLocation, Navigate } from 'react-router-dom';
import { decodeJwtPayload } from './api';
import { isSalesAuthenticated, logoutSales } from './auth';
import { SalesI18nProvider, useLang, useT } from './i18n';

const { Header, Sider, Content } = Layout;
const { Text } = Typography;

const SalesShell: React.FC = () => {
  const location = useLocation();
  const t = useT();
  const { lang, setLang } = useLang();

  const profile = decodeJwtPayload();

  const menuItems = [
    { key: '/sales/inbox',    icon: <InboxOutlined />,    label: <Link to="/sales/inbox">{t('nav.inbox')}</Link> },
    { key: '/sales/monitors', icon: <ThunderboltOutlined />, label: <Link to="/sales/monitors">{t('nav.monitors')}</Link> },
    { key: '/sales/accounts', icon: <PhoneOutlined />,    label: <Link to="/sales/accounts">{t('nav.accounts')}</Link> },
    { key: '/sales/wallet',   icon: <WalletOutlined />,   label: <Link to="/sales/wallet">{t('nav.wallet')}</Link> },
    { key: '/sales/settings', icon: <SettingOutlined />,  label: <Link to="/sales/settings">{t('nav.settings')}</Link> },
  ];

  const userMenu = {
    items: [
      { key: 'logout', icon: <LogoutOutlined />, label: t('common.logout'), danger: true,
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
          {t('app.brand')}
          {profile?.kind === 'platform' && (
            <Tag color="purple" style={{ marginLeft: 12 }}>{t('app.platform')}</Tag>
          )}
          {profile?.kind === 'customer' && (
            <Tag color="cyan" style={{ marginLeft: 12 }}>{t('app.tenant')}</Tag>
          )}
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}>
          <Segmented
            size="small"
            value={lang}
            onChange={(v) => setLang(v as any)}
            options={[
              { value: 'zh-CN', label: <><GlobalOutlined /> 中文</> },
              { value: 'en',    label: <><GlobalOutlined /> EN</> },
            ]}
          />
          <Dropdown menu={userMenu} placement="bottomRight">
            <div style={{ cursor: 'pointer', color: '#fff' }}>
              <Avatar icon={<UserOutlined />} style={{ background: '#1677ff' }} />
              <Text style={{ color: '#fff', marginLeft: 8 }}>{profile?.email || ''}</Text>
            </div>
          </Dropdown>
        </div>
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

const SalesLayout: React.FC = () => {
  if (!isSalesAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  // Provider wraps the entire sales subtree so every page can call useT().
  return (
    <SalesI18nProvider>
      <SalesShell />
    </SalesI18nProvider>
  );
};

export default SalesLayout;
