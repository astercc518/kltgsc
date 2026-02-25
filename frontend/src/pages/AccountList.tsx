import React, { useEffect, useState, useCallback } from 'react';
import { message } from 'antd';
import {
  getAccounts,
  getAccountCount,
  getAccount,
  Account,
} from '../services/api';
import {
  AccountTable,
  AccountUploader,
  AccountActions,
  AccountDetailDrawer,
  CombatRoleManager,
} from './accounts';
import type { ImportTask, AccountStats, PaginationState } from './accounts';

const AccountList: React.FC = () => {
  // Core shared state
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(false);
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [pagination, setPagination] = useState<PaginationState>({ current: 1, pageSize: 20, total: 0 });
  const [stats, setStats] = useState<AccountStats>({ total: 0, active: 0, init: 0, banned: 0 });

  // Filters
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [roleFilter, setRoleFilter] = useState<string | undefined>(undefined);
  const [tierFilter, setTierFilter] = useState<string | undefined>(undefined);

  // Modal visibility states
  const [isUploadModalVisible, setIsUploadModalVisible] = useState(false);
  const [isMessageModalVisible, setIsMessageModalVisible] = useState(false);
  const [isAttrModalVisible, setIsAttrModalVisible] = useState(false);
  const [isAIModalVisible, setIsAIModalVisible] = useState(false);
  const [isRoleModalVisible, setIsRoleModalVisible] = useState(false);
  const [isCombatRoleModalVisible, setIsCombatRoleModalVisible] = useState(false);
  const [isWarmupModalVisible, setIsWarmupModalVisible] = useState(false);

  // Detail drawer
  const [isDetailVisible, setIsDetailVisible] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null);

  // Import tasks (shared between uploader and table)
  const [importTasks, setImportTasks] = useState<ImportTask[]>([]);
  const [isImportProgressVisible, setIsImportProgressVisible] = useState(false);

  // --- Data fetching ---
  const fetchAccounts = useCallback(async (page: number = 1, pageSize: number = 20) => {
    setLoading(true);
    try {
      const skip = (page - 1) * pageSize;
      const data = await getAccounts(skip, pageSize, statusFilter, roleFilter);
      const filteredData = tierFilter
        ? data.filter(acc => (acc.tier || 'tier3') === tierFilter)
        : data;
      setAccounts(filteredData);

      const count = await getAccountCount(statusFilter);
      setPagination(prev => ({ ...prev, current: page, pageSize, total: count.total }));
    } catch (error) {
      message.error('获取账号列表失败');
    } finally {
      setLoading(false);
    }
  }, [statusFilter, roleFilter, tierFilter]);

  const fetchStats = useCallback(async () => {
    try {
      const [totalRes, activeRes, initRes, bannedRes] = await Promise.all([
        getAccountCount(),
        getAccountCount('active'),
        getAccountCount('init'),
        getAccountCount('banned'),
      ]);
      setStats({
        total: totalRes.total,
        active: activeRes.total,
        init: initRes.total,
        banned: bannedRes.total,
      });
    } catch (error) {
      console.error('获取统计信息失败', error);
    }
  }, []);

  useEffect(() => {
    fetchAccounts();
    fetchStats();
  }, [statusFilter, roleFilter, tierFilter]);

  // --- Modal show helpers with validation ---
  const handleShowMessageModal = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择要发送消息的账号');
      return;
    }
    setIsMessageModalVisible(true);
  };

  const handleShowAttrModal = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择账号');
      return;
    }
    setIsAttrModalVisible(true);
  };

  const handleShowRoleModal = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择要设置角色的账号');
      return;
    }
    setIsRoleModalVisible(true);
  };

  const handleShowAIModal = () => {
    if (selectedRowKeys.length !== 1) {
      message.warning('请选择一个账号进行配置');
      return;
    }
    setIsAIModalVisible(true);
  };

  const handleShowWarmupModal = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择要养号的账号');
      return;
    }
    const activeAccountIds = accounts
      .filter(a => selectedRowKeys.includes(a.id) && a.status === 'active')
      .map(a => a.id);
    if (activeAccountIds.length === 0) {
      message.warning('所选账号中没有活跃账号');
      return;
    }
    setIsWarmupModalVisible(true);
  };

  const handleViewDetail = async (id: number) => {
    try {
      const account = await getAccount(id);
      setSelectedAccount(account);
      setIsDetailVisible(true);
    } catch (error) {
      message.error('获取账号详情失败');
    }
  };

  return (
    <div>
      <AccountTable
        accounts={accounts}
        loading={loading}
        selectedRowKeys={selectedRowKeys}
        setSelectedRowKeys={setSelectedRowKeys}
        pagination={pagination}
        setPagination={setPagination}
        stats={stats}
        fetchAccounts={fetchAccounts}
        fetchStats={fetchStats}
        onShowUploadModal={() => setIsUploadModalVisible(true)}
        onShowMessageModal={handleShowMessageModal}
        onShowAttrModal={handleShowAttrModal}
        onShowRoleModal={handleShowRoleModal}
        onShowCombatRoleModal={() => setIsCombatRoleModalVisible(true)}
        onShowAIModal={handleShowAIModal}
        onShowWarmupModal={handleShowWarmupModal}
        onShowImportProgress={() => setIsImportProgressVisible(true)}
        onViewDetail={handleViewDetail}
        importTasks={importTasks}
        statusFilter={statusFilter}
        setStatusFilter={setStatusFilter}
        roleFilter={roleFilter}
        setRoleFilter={setRoleFilter}
        tierFilter={tierFilter}
        setTierFilter={setTierFilter}
      />

      <AccountUploader
        visible={isUploadModalVisible}
        onClose={() => setIsUploadModalVisible(false)}
        importTasks={importTasks}
        setImportTasks={setImportTasks}
        isImportProgressVisible={isImportProgressVisible}
        setIsImportProgressVisible={setIsImportProgressVisible}
        fetchAccounts={fetchAccounts}
        fetchStats={fetchStats}
        pagination={pagination}
      />

      <AccountActions
        accounts={accounts}
        selectedRowKeys={selectedRowKeys}
        setSelectedRowKeys={setSelectedRowKeys}
        fetchAccounts={fetchAccounts}
        pagination={pagination}
        isMessageModalVisible={isMessageModalVisible}
        setIsMessageModalVisible={setIsMessageModalVisible}
        isAttrModalVisible={isAttrModalVisible}
        setIsAttrModalVisible={setIsAttrModalVisible}
        isAIModalVisible={isAIModalVisible}
        setIsAIModalVisible={setIsAIModalVisible}
        isRoleModalVisible={isRoleModalVisible}
        setIsRoleModalVisible={setIsRoleModalVisible}
      />

      <AccountDetailDrawer
        visible={isDetailVisible}
        onClose={() => setIsDetailVisible(false)}
        account={selectedAccount}
      />

      <CombatRoleManager
        accounts={accounts}
        selectedRowKeys={selectedRowKeys}
        setSelectedRowKeys={setSelectedRowKeys}
        fetchAccounts={fetchAccounts}
        pagination={pagination}
        isCombatRoleModalVisible={isCombatRoleModalVisible}
        setIsCombatRoleModalVisible={setIsCombatRoleModalVisible}
        isWarmupModalVisible={isWarmupModalVisible}
        setIsWarmupModalVisible={setIsWarmupModalVisible}
      />
    </div>
  );
};

export default AccountList;
