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
  LogoutOutlined,
  RadarChartOutlined,
  UserSwitchOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { getCurrentUser } from './services/api';
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
import CampaignPage from './pages/CampaignPage';
import SourceGroupPage from './pages/SourceGroupPage';
import PersonaPage from './pages/PersonaPage';
import FunnelGroupPage from './pages/FunnelGroupPage';
import KnowledgeBasePage from './pages/KnowledgeBasePage';
import AutoRegister from './pages/AutoRegister';
import MonitoringDashboard from './pages/MonitoringDashboard';
import BusinessOps from './pages/BusinessOps';
import UserManagement from './pages/UserManagement';
import FeaturePack from './pages/FeaturePack';
import ActivationCodes from './pages/billing/ActivationCodes';
import GroupAIInteractions from './pages/inbox/GroupAIInteractions';
import ExperimentList from './pages/ab/ExperimentList';
import ExperimentCreate from './pages/ab/ExperimentCreate';
import ExperimentReport from './pages/ab/ExperimentReport';

// ── TG1.AI Customer Portal (Epic 1.5) ─────────────────────────────
import PortalLayout from './portal/Layout';
import PortalLogin from './portal/pages/Login';
import PortalRegister from './portal/pages/Register';
import PortalDashboard from './portal/pages/Dashboard';
import PortalBilling from './portal/pages/Billing';
import PortalAccounts from './portal/pages/Accounts';
import PortalLeads from './portal/pages/Leads';
import PortalKnowledgeBases from './portal/pages/KnowledgeBases';
import PortalMainAccount from './portal/pages/MainAccount';
import PortalSettings from './portal/pages/Settings';
import PortalMonitors from './portal/pages/Monitors';
import PortalWallet from './portal/pages/Wallet';
import PortalFeatures from './portal/pages/Features';
import PortalBulk from './portal/pages/Bulk';
import PortalBulkNew from './portal/pages/BulkNew';
import PortalBulkDetail from './portal/pages/BulkDetail';
import PortalBulkInbox from './portal/pages/BulkInbox';
import PortalScrape from './portal/pages/Scrape';
import PortalInvite from './portal/pages/Invite';
import GroupAILayout from './portal/pages/GroupAI';
import IcpEditor from './portal/pages/GroupAI/IcpEditor';
import Thresholds from './portal/pages/GroupAI/Thresholds';
import CaseStudies from './portal/pages/GroupAI/CaseStudies';
import WorkerPersonas from './portal/pages/GroupAI/WorkerPersonas';
import ChitchatTopics from './portal/pages/GroupAI/ChitchatTopics';
import RealtimeStats from './portal/pages/GroupAI/RealtimeStats';
import SalesLayout from './sales/Layout';
import SalesInbox from './sales/pages/Inbox';
import SalesLeadDetail from './sales/pages/LeadDetail';
import SalesWalletPage from './sales/pages/Wallet';
import SalesSettings from './sales/pages/Settings';
import SalesMonitors from './sales/pages/Monitors';
import SalesAccounts from './sales/pages/Accounts';
import { isSalesAuthenticated } from './sales/auth';
import { isCustomerAuthenticated } from './portal/auth';
import { setSalesToken } from './sales/auth';

// Admin impersonation handoff: when a tab opens with
//   #impersonate=<jwt>&role=sales&to=/sales/inbox
// stash the token under the correct localStorage key BEFORE React reads it,
// clear the hash, and let normal routing take over.
// This runs once at module load so SPA routing sees the user as logged in.
(() => {
  const h = window.location.hash || '';
  if (!h.startsWith('#impersonate=')) return;
  try {
    const params = new URLSearchParams(h.slice(1));
    const token = params.get('impersonate');
    const role = params.get('role') || '';
    if (!token) return;
    if (role === 'sales') {
      setSalesToken(token);
    } else {
      localStorage.setItem('token', token);
    }
    // Clean the hash so refresh doesn't re-stash an old token.
    history.replaceState(null, '', window.location.pathname + window.location.search);
  } catch (_) {
    // Best-effort: leave the page in its original state on parse failure.
  }
})();

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

// admin-only 路由保护：sales 直接弹回 Dashboard
const AdminOnly: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const { data: me, isLoading } = useQuery({
    queryKey: ['me'], queryFn: getCurrentUser, retry: false,
  });
  if (isLoading) {
    return <div style={{ padding: 48, textAlign: 'center' }}><Spin tip="检查权限中..." /></div>;
  }
  if (me?.role !== 'admin' && !me?.is_superuser) {
    return <Navigate to="/dashboard" replace />;
  }
  return <>{children}</>;
};

const { Header, Content, Sider } = Layout;

// Menu items configuration (role-aware: admin-only items inserted conditionally)
const buildMenuItems = (role?: string, isSuperuser?: boolean): MenuProps['items'] => {
  const isAdmin = role === 'admin' || isSuperuser === true;
  const items: MenuProps['items'] = [
  {
    key: '1',
    icon: <DashboardOutlined />,
    label: <Link to="/dashboard">Dashboard</Link>,
  },
  {
    key: 'monitoring',
    icon: <RadarChartOutlined />,
    label: <Link to="/monitoring">实时监控</Link>,
  },
  {
    key: 'business-ops',
    icon: <DashboardOutlined />,
    label: <Link to="/business-ops">运营看板</Link>,
  },
  {
    key: 'resources',
    icon: <UserOutlined />,
    label: '资源中心',
    children: [
      {
        key: '2',
        label: <Link to="/accounts">账号管理</Link>,
      },
      {
        key: '3',
        label: <Link to="/proxies">代理管理</Link>,
      },
      {
        key: 'source-groups',
        label: <Link to="/source-groups">流量源管理</Link>,
      },
      {
        key: 'auto-register',
        label: <Link to="/auto-register">自动注册</Link>,
      },
    ]
  },
  {
    key: 'operations',
    icon: <RocketOutlined />,
    label: '作战中心',
    children: [
      {
        key: 'campaigns',
        label: <Link to="/campaigns">战役管理</Link>,
      },
      {
        key: '12',
        label: <Link to="/warmup">养号任务</Link>,
      },
      {
        key: '4',
        label: <Link to="/scraping">采集中心</Link>,
      },
      {
        key: '5',
        label: <Link to="/marketing">营销群发</Link>,
      },
      {
        key: '14',
        label: <Link to="/monitors">监控引流</Link>,
      },
      {
        key: '15',
        label: <Link to="/invites">批量拉人</Link>,
      },
      {
        key: 'funnel-groups',
        label: <Link to="/funnel-groups">营销群管理</Link>,
      },
    ]
  },
  {
    key: 'ai-hub',
    icon: <RobotOutlined />,
    label: 'AI 中心',
    children: [
      {
        key: '6',
        label: <Link to="/ai">AI 配置</Link>,
      },
      {
        key: 'personas',
        label: <Link to="/personas">AI 人设</Link>,
      },
      {
        key: 'knowledge-bases',
        label: <Link to="/knowledge-bases">知识库</Link>,
      },
      {
        key: '7',
        label: <Link to="/scripts">炒群脚本</Link>,
      },
    ]
  },
  {
    key: 'customer',
    icon: <TeamOutlined />,
    label: '客户中心',
    children: [
      {
        key: '13',
        label: <Link to="/crm">客户管理</Link>,
      },
      {
        key: '8',
        label: <Link to="/inbox">聚合聊天</Link>,
      },
      {
        key: 'group-ai-interactions',
        label: <Link to="/admin/group-ai-interactions">群内 AI 互动</Link>,
      },
      {
        key: 'ab-experiments',
        label: <Link to="/admin/ab/experiments">A/B 实验</Link>,
      },
    ]
  },
  ];

  // 账号中心 — 仅 admin 可见
  if (isAdmin) {
    items.push({
      key: 'accounts-hub',
      icon: <UserSwitchOutlined />,
      label: <Link to="/users">账号中心</Link>,
    });
    items.push({
      key: 'feature-pack',
      icon: <DashboardOutlined />,
      label: <Link to="/feature-pack">功能包</Link>,
    });
    items.push({
      key: 'activation-codes',
      icon: <FileTextOutlined />,
      label: <Link to="/activation-codes">激活码</Link>,
    });
  }

  items.push(
    {
      key: 'system',
      icon: <SettingOutlined />,
      label: '系统管理',
      children: [
        { key: '9', label: <Link to="/tasks">任务管理</Link> },
        { key: '10', label: <Link to="/logs">操作日志</Link> },
        { key: '11', label: <Link to="/system-config">系统配置</Link> },
      ],
    },
    { type: 'divider' },
    {
      key: 'logout',
      icon: <LogoutOutlined />,
      label: '退出登录',
      danger: true,
      onClick: handleLogout,
    },
  );

  return items;
};

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
        '/campaigns': '战役管理',
        '/source-groups': '流量源管理',
        '/personas': 'AI人设管理',
        '/funnel-groups': '营销群管理',
        '/knowledge-bases': '知识库',
        '/auto-register': '自动注册',
        '/monitoring': '实时监控',
        '/business-ops': '运营看板',
        '/activation-codes': '激活码管理',
    };

    const pathSnippets = location.pathname.split('/').filter(i => i);
    
    // Build breadcrumb items using the new items API
    const breadcrumbItems: BreadcrumbProps['items'] = [
        {
            key: 'home',
            title: <Link to="/dashboard">Home</Link>,
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
                    <Route path="/" element={<Navigate to="/dashboard" replace />} />
                    <Route path="/dashboard" element={<Dashboard />} />
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
                    <Route path="/campaigns" element={<CampaignPage />} />
                    <Route path="/source-groups" element={<SourceGroupPage />} />
                    <Route path="/personas" element={<PersonaPage />} />
                    <Route path="/funnel-groups" element={<FunnelGroupPage />} />
                    <Route path="/knowledge-bases" element={<KnowledgeBasePage />} />
                    <Route path="/auto-register" element={<AutoRegister />} />
                    <Route path="/monitoring" element={<MonitoringDashboard />} />
                    <Route path="/business-ops" element={<BusinessOps />} />
                    <Route path="/users" element={<AdminOnly><UserManagement /></AdminOnly>} />
                    <Route path="/feature-pack" element={<AdminOnly><FeaturePack /></AdminOnly>} />
                    <Route path="/activation-codes" element={<AdminOnly><ActivationCodes /></AdminOnly>} />
                    <Route path="/admin/group-ai-interactions" element={<GroupAIInteractions />} />
                    <Route path="/admin/ab/experiments" element={<ExperimentList />} />
                    <Route path="/admin/ab/experiments/new" element={<ExperimentCreate />} />
                    <Route path="/admin/ab/experiments/:id" element={<ExperimentReport />} />
                </Routes>
            </div>
        </Content>
    );
};

// 主应用布局（需要登录）
const MainLayout: React.FC = () => {
  const { data: me } = useQuery({
    queryKey: ['me'], queryFn: getCurrentUser, retry: false,
  });
  const menuItems = buildMenuItems(me?.role, me?.is_superuser);
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
        {/* ── Unified login ──────────────────────────────────────── */}
        {/* Single entry for customers (email), tenant-sub-user sales (email),
            platform sales (username), and admin (username). */}
        <Route path="/login" element={
          isAuthenticated()
            ? <Navigate to="/dashboard" replace />
            : isSalesAuthenticated()
              ? <Navigate to="/sales/inbox" replace />
              : isCustomerAuthenticated()
                ? <Navigate to="/portal/dashboard" replace />
                : <Login />
        } />
        {/* Legacy customer login URL → redirect to unified /login */}
        <Route path="/portal/login" element={
          isCustomerAuthenticated()
            ? <Navigate to="/portal/dashboard" replace />
            : <Navigate to="/login" replace />
        } />
        <Route path="/portal/register" element={
          isCustomerAuthenticated() ? <Navigate to="/portal/dashboard" replace /> : <PortalRegister />
        } />

        {/* ── TG1.AI Customer Portal (受保护，PortalLayout 内已鉴权) ── */}
        <Route path="/portal" element={<PortalLayout />}>
          <Route index element={<Navigate to="/portal/dashboard" replace />} />
          <Route path="dashboard" element={<PortalDashboard />} />
          <Route path="billing" element={<PortalBilling />} />
          <Route path="wallet" element={<PortalWallet />} />
          <Route path="features" element={<PortalFeatures />} />
          <Route path="bulk" element={<PortalBulk />} />
          <Route path="bulk/new" element={<PortalBulkNew />} />
          <Route path="bulk/inbox" element={<PortalBulkInbox />} />
          <Route path="bulk/:id" element={<PortalBulkDetail />} />
          <Route path="scrape" element={<PortalScrape />} />
          <Route path="invite" element={<PortalInvite />} />
          <Route path="accounts" element={<PortalAccounts />} />
          <Route path="leads" element={<PortalLeads />} />
          <Route path="monitors" element={<PortalMonitors />} />
          <Route path="knowledge-bases" element={<PortalKnowledgeBases />} />
          <Route path="main-account" element={<PortalMainAccount />} />
          <Route path="settings" element={<PortalSettings />} />
          <Route path="group-ai" element={<GroupAILayout />}>
            <Route index element={<Navigate to="icp" replace />} />
            <Route path="icp" element={<IcpEditor />} />
            <Route path="thresholds" element={<Thresholds />} />
            <Route path="cases" element={<CaseStudies />} />
            <Route path="personas" element={<WorkerPersonas />} />
            <Route path="chitchat" element={<ChitchatTopics />} />
            <Route path="stats" element={<RealtimeStats />} />
          </Route>
        </Route>

        {/* ── Sales workbench (Epic E) — customer_sales + platform_sales ── */}
        <Route path="/sales" element={<SalesLayout />}>
          <Route index element={<Navigate to="/sales/inbox" replace />} />
          <Route path="inbox" element={<SalesInbox />} />
          <Route path="leads/:id" element={<SalesLeadDetail />} />
          <Route path="monitors" element={<SalesMonitors />} />
          <Route path="accounts" element={<SalesAccounts />} />
          <Route path="wallet" element={<SalesWalletPage />} />
          <Route path="settings" element={<SalesSettings />} />
        </Route>

        {/* ── Admin: 所有其他页面需要内部登录 ──────────────────── */}
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
