/**
 * Portal-wide low-balance banner.
 *
 * Mounted in PortalLayout so every customer page shows the warning when
 * wallet balance drops below LOW_BALANCE_THRESHOLD_CENTS. Hidden on
 * /portal/wallet itself (where the in-page Statistic card already shows
 * the same warning).
 */
import React from 'react';
import { Alert, Button } from 'antd';
import { WalletOutlined } from '@ant-design/icons';
import { Link, useLocation } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { walletApi } from '../api';

const LOW_BALANCE_THRESHOLD_CENTS = 2000; // $20

const LowBalanceBanner: React.FC = () => {
  const location = useLocation();

  const { data: wallet } = useQuery({
    queryKey: ['portal', 'wallet', 'balance'],
    queryFn: walletApi.get,
    refetchInterval: 60_000,
    retry: false,
  });

  if (!wallet) return null;
  if (location.pathname.startsWith('/portal/wallet')) return null;
  if (wallet.balance_cents >= LOW_BALANCE_THRESHOLD_CENTS) return null;

  const dollars = (wallet.balance_cents / 100).toFixed(2);
  const isEmpty = wallet.balance_cents <= 0;

  return (
    <Alert
      type={isEmpty ? 'error' : 'warning'}
      showIcon
      banner
      message={
        isEmpty
          ? `钱包余额已归零 — 进行中的群发 / 群拉 / 采集会自动暂停 (paused_no_funds)`
          : `钱包余额仅剩 $${dollars} — 低于 $20 阈值，建议立即充值以避免任务中断`
      }
      action={
        <Link to="/portal/wallet">
          <Button size="small" type="primary" icon={<WalletOutlined />}>
            立即充值
          </Button>
        </Link>
      }
      style={{ marginBottom: 16 }}
    />
  );
};

export default LowBalanceBanner;
