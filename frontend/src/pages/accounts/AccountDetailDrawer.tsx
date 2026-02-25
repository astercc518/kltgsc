import React from 'react';
import { Drawer, Descriptions } from 'antd';
import { Account } from '../../services/api';
import { getStatusTag } from './helpers';

interface AccountDetailDrawerProps {
  visible: boolean;
  onClose: () => void;
  account: Account | null;
}

const AccountDetailDrawer: React.FC<AccountDetailDrawerProps> = ({
  visible,
  onClose,
  account,
}) => {
  return (
    <Drawer
      title="账号详情"
      placement="right"
      onClose={onClose}
      open={visible}
      size="large"
    >
      {account && (
        <Descriptions column={1} bordered>
          <Descriptions.Item label="ID">{account.id}</Descriptions.Item>
          <Descriptions.Item label="手机号">{account.phone_number}</Descriptions.Item>
          <Descriptions.Item label="状态">{getStatusTag(account.status)}</Descriptions.Item>
          <Descriptions.Item label="API ID">{account.api_id || '-'}</Descriptions.Item>
          <Descriptions.Item label="API Hash">{account.api_hash ? '***' : '-'}</Descriptions.Item>
          <Descriptions.Item label="Session 文件路径">
            {account.session_file_path || '-'}
          </Descriptions.Item>
          <Descriptions.Item label="绑定代理">
            {account.proxy ? (
              `${account.proxy.ip}:${account.proxy.port} (${account.proxy.protocol})`
            ) : (
              '未绑定'
            )}
          </Descriptions.Item>
          <Descriptions.Item label="设备型号">{account.device_model || '-'}</Descriptions.Item>
          <Descriptions.Item label="系统版本">{account.system_version || '-'}</Descriptions.Item>
          <Descriptions.Item label="应用版本">{account.app_version || '-'}</Descriptions.Item>
          <Descriptions.Item label="最后活跃">
            {account.last_active ? new Date(account.last_active).toLocaleString() : '-'}
          </Descriptions.Item>
          <Descriptions.Item label="创建时间">
            {new Date(account.created_at).toLocaleString()}
          </Descriptions.Item>
        </Descriptions>
      )}
    </Drawer>
  );
};

export default AccountDetailDrawer;
