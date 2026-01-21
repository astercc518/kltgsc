import React, { useEffect, useState } from 'react';
import { BrowserRouter as Router, Routes, Route, Link, useLocation, Navigate } from 'react-router-dom';
import { Layout, Menu, Breadcrumb, Spin } from 'antd';
import type { MenuProps, BreadcrumbProps } from 'antd';
import {
  DashboardOutlined,
  UserOutlined,
  GlobalOutlined,
  RocketOutlined,
  RobotOutlined,
  MessageOutlined,
  SettingOutlined,
  FileTextOutlined,
  ScheduleOutlined,
  CoffeeOutlined,
  TeamOutlined,
  LogoutOutlined
} from '@ant-design/icons';
import Dashboard from './pages/Dashboard';
import AccountList from './pages/AccountList';
import ProxyList from './pages/ProxyList';
import AIPage from './pages/AIPage';
import ScriptPage from './pages/ScriptPage';
import Inbox from './pages/Inbox';
import LogsPage from './pages/LogsPage';
import SystemConfigPage from './pages/SystemConfigPage';
import TasksPage from './pages/TasksPage';
import Scraping from './pages/Scraping';
import Marketing from './pages/Marketing';
import Warmup from './pages/Warmup';
import CRM from './pages/CRM';
import Login from './pages/Login';
import MonitorPage from './pages/MonitorPage';
import InvitePage from './pages/InvitePage';

// 检查用户是否已登录
const isAuthenticated = (): boolean => {
  const token = localStorage.getItem('token');
  return !!token;
};

// 登出函数
const handleLogout = () => {
  localStorage.removeItem('token');
  window.location.href = '/login';
};

// 路由保护组件
const ProtectedRoute: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  if (!isAuthenticated()) {
    return <Navigate to="/login" replace />;
  }
  return <>{children}</>;
};

const { Header, Content, Sider } = Layout;

// Menu items configuration
const menuItems: MenuProps['items'] = [
  {
    key: '1',
    icon: <DashboardOutlined />,
    label: <Link to="/">Dashboard</Link>,
  },
  {
    key: '2',
    icon: <UserOutlined />,
    label: <Link to="/accounts">账号管理</Link>,
  },
  {
    key: '3',
    icon: <GlobalOutlined />,
    label: <Link to="/proxies">代理管理</Link>,
  },
  {
    key: '12',
    icon: <CoffeeOutlined />,
    label: <Link to="/warmup">养号任务</Link>,
  },
  {
    key: '4',
    icon: <RocketOutlined />,
    label: <Link to="/scraping">采集中心</Link>,
  },
  {
    key: '5',
    icon: <MessageOutlined />,
    label: <Link to="/marketing">营销群发</Link>,
  },
  {
    key: '13',
    icon: <TeamOutlined />,
    label: <Link to="/crm">客户管理</Link>,
  },
  {
    key: '14',
    icon: <RocketOutlined />,
    label: <Link to="/monitors">监控引流</Link>,
  },
  {
    key: '15',
    icon: <TeamOutlined />,
    label: <Link to="/invites">批量拉人</Link>,
  },
  {
    key: '6',
    icon: <RobotOutlined />,
    label: <Link to="/ai">AI 配置</Link>,
  },
  {
    key: '7',
    icon: <FileTextOutlined />,
    label: <Link to="/scripts">炒群脚本</Link>,
  },
  {
    key: '8',
    icon: <MessageOutlined />,
    label: <Link to="/inbox">聚合聊天</Link>,
  },
  {
    key: '9',
    icon: <ScheduleOutlined />,
    label: <Link to="/tasks">任务管理</Link>,
  },
  {
    key: '10',
    icon: <FileTextOutlined />,
    label: <Link to="/logs">操作日志</Link>,
  },
  {
    key: '11',
    icon: <SettingOutlined />,
    label: <Link to="/system-config">系统配置</Link>,
  },
  {
    type: 'divider',
  },
  {
    key: 'logout',
    icon: <LogoutOutlined />,
    label: '退出登录',
    danger: true,
    onClick: handleLogout,
  },
];

const AppContent: React.FC = () => {
    const location = useLocation();
    
    // Map path to breadcrumb name
    const breadcrumbNameMap: Record<string, string> = {
        '/': 'Dashboard',
        '/accounts': '账号管理',
        '/proxies': '代理管理',
        '/ai': 'AI 配置',
        '/scripts': '炒群脚本',
        '/inbox': '聚合聊天',
        '/scraping': '采集中心',
        '/marketing': '营销群发',
        '/logs': '操作日志',
        '/system-config': '系统配置',
        '/tasks': '任务管理',
        '/warmup': '养号任务',
        '/crm': '客户管理',
        '/monitors': '监控引流',
        '/invites': '批量拉人',
    };

    const pathSnippets = location.pathname.split('/').filter(i => i);
    
    // Build breadcrumb items using the new items API
    const breadcrumbItems: BreadcrumbProps['items'] = [
        {
            key: 'home',
            title: <Link to="/">Home</Link>,
        },
        ...pathSnippets.map((_, index) => {
            const url = `/${pathSnippets.slice(0, index + 1).join('/')}`;
            return {
                key: url,
                title: <Link to={url}>{breadcrumbNameMap[url] || url}</Link>,
            };
        }),
    ];

    return (
        <Content style={{ margin: '0 16px' }}>
            <Breadcrumb style={{ margin: '16px 0' }} items={breadcrumbItems} />
            <div style={{ padding: 24, minHeight: 360, background: '#fff' }}>
                <Routes>
                    <Route path="/" element={<Dashboard />} />
                    <Route path="/accounts" element={<AccountList />} />
                    <Route path="/proxies" element={<ProxyList />} />
                    <Route path="/ai" element={<AIPage />} />
                    <Route path="/scripts" element={<ScriptPage />} />
                    <Route path="/inbox" element={<Inbox />} />
                    <Route path="/scraping" element={<Scraping />} />
                    <Route path="/marketing" element={<Marketing />} />
                    <Route path="/logs" element={<LogsPage />} />
                    <Route path="/system-config" element={<SystemConfigPage />} />
                    <Route path="/tasks" element={<TasksPage />} />
                    <Route path="/warmup" element={<Warmup />} />
                    <Route path="/crm" element={<CRM />} />
                    <Route path="/monitors" element={<MonitorPage />} />
                    <Route path="/invites" element={<InvitePage />} />
                </Routes>
            </div>
        </Content>
    );
};

// 主应用布局（需要登录）
const MainLayout: React.FC = () => {
  return (
    <Layout style={{ minHeight: '100vh' }}>
      <Sider collapsible>
        <div style={{ height: 32, margin: 16, background: 'rgba(255, 255, 255, 0.2)', textAlign: 'center', color: '#fff', lineHeight: '32px' }}>
          TGSC
        </div>
        <Menu 
          theme="dark" 
          defaultSelectedKeys={['1']} 
          mode="inline"
          items={menuItems}
        />
      </Sider>
      <Layout className="site-layout">
        <Header className="site-layout-background" style={{ padding: 0, background: '#fff' }} />
        <AppContent />
      </Layout>
    </Layout>
  );
};

const App: React.FC = () => {
  return (
    <Router future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        {/* 登录页面 - 不需要认证 */}
        <Route path="/login" element={
          isAuthenticated() ? <Navigate to="/" replace /> : <Login />
        } />
        
        {/* 所有其他页面 - 需要认证 */}
        <Route path="/*" element={
          <ProtectedRoute>
            <MainLayout />
          </ProtectedRoute>
        } />
      </Routes>
    </Router>
  );
};

export default App;
