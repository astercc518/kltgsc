/**
 * GroupAILayout — sub-route container for /portal/group-ai/*
 *
 * Provides a secondary sidebar with 6 pages: icp / thresholds / cases /
 * personas / chitchat / stats. Outlet renders the selected page.
 */
import React from 'react';
import { Layout, Menu } from 'antd';
import {
  UserOutlined,
  SlidersFilled,
  BookOutlined,
  TeamOutlined,
  MessageOutlined,
  LineChartOutlined,
} from '@ant-design/icons';
import { Link, Outlet, useLocation, Navigate } from 'react-router-dom';

const { Sider, Content } = Layout;

const items = [
  { key: 'icp',        icon: <UserOutlined />,      label: <Link to="icp">ICP 画像</Link> },
  { key: 'thresholds', icon: <SlidersFilled />,     label: <Link to="thresholds">识别灵敏度</Link> },
  { key: 'cases',      icon: <BookOutlined />,      label: <Link to="cases">案例库</Link> },
  { key: 'personas',   icon: <TeamOutlined />,      label: <Link to="personas">账号人设</Link> },
  { key: 'chitchat',   icon: <MessageOutlined />,   label: <Link to="chitchat">闲聊话题</Link> },
  { key: 'stats',      icon: <LineChartOutlined />, label: <Link to="stats">实时统计</Link> },
];

export default function GroupAILayout() {
  const loc = useLocation();
  const selected = loc.pathname.split('/').pop() || 'icp';
  return (
    <Layout style={{ background: '#fff', minHeight: 'calc(100vh - 64px)' }}>
      <Sider width={180} style={{ background: '#fafafa' }}>
        <Menu
          mode="inline"
          selectedKeys={[selected]}
          items={items}
          style={{ borderRight: 0, paddingTop: 16 }}
        />
      </Sider>
      <Content style={{ padding: 24 }}>
        <Outlet />
      </Content>
    </Layout>
  );
}
