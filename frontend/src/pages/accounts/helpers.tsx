import React from 'react';
import { Tag } from 'antd';
import {
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  UploadOutlined,
  SyncOutlined,
} from '@ant-design/icons';

export const getStatusTag = (status: string) => {
  const statusConfig: Record<string, { color: string; icon: React.ReactNode; text: string }> = {
    active: { color: 'green', icon: <CheckCircleOutlined />, text: '活跃' },
    init: { color: 'blue', icon: <ClockCircleOutlined />, text: '未验活' },
    uploaded: { color: 'cyan', icon: <UploadOutlined />, text: '已上传' },
    banned: { color: 'red', icon: <CloseCircleOutlined />, text: '已封禁' },
    spam_block: { color: 'orange', icon: <ExclamationCircleOutlined />, text: '限制' },
    flood_wait: { color: 'volcano', icon: <ClockCircleOutlined />, text: '冷却中' },
    warmup: { color: 'gold', icon: <ClockCircleOutlined />, text: '养号中' },
    error: { color: 'red', icon: <CloseCircleOutlined />, text: '错误' },
    pending: { color: 'default', icon: <ClockCircleOutlined />, text: '待处理' },
    checking: { color: 'processing', icon: <SyncOutlined spin />, text: '检测中' },
  };

  const config = statusConfig[status] || { color: 'default', icon: null, text: status };
  return (
    <Tag color={config.color} icon={config.icon}>
      {config.text}
    </Tag>
  );
};

export const getRoleTag = (role?: string) => {
  const roleConfig: Record<string, { color: string; text: string }> = {
    worker: { color: 'default', text: '临时号' },
    master: { color: 'gold', text: '主账号' },
    support: { color: 'blue', text: '客服号' },
    sales: { color: 'purple', text: '销售号' },
  };
  const config = roleConfig[role || 'worker'] || roleConfig.worker;
  return <Tag color={config.color}>{config.text}</Tag>;
};

export const getCombatRoleName = (role: string) => {
  const names: Record<string, string> = {
    cannon: '炮灰组',
    scout: '侦察组',
    actor: '演员组',
    sniper: '狙击组',
  };
  return names[role] || role;
};
