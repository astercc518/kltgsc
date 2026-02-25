import React, { useState } from 'react';
import {
  Table,
  Button,
  Modal,
  Tag,
  Space,
  Upload,
  UploadFile,
  Popconfirm,
  Card,
  Statistic,
  Row,
  Col,
  Select,
  message,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  DeleteOutlined,
  UploadOutlined,
  SyncOutlined,
  EyeOutlined,
  SwapOutlined,
  MessageOutlined,
  EditOutlined,
  RobotOutlined,
  CloudDownloadOutlined,
  LoadingOutlined,
  CoffeeOutlined,
} from '@ant-design/icons';
import {
  deleteAccount,
  deleteAccountsBatch,
  uploadAccountSessionsBatch,
  checkAccountStatus,
  checkAccountsBatch,
  getProxies,
  updateAccountProxy,
  Account,
  Proxy,
} from '../../services/api';
import { getStatusTag, getRoleTag } from './helpers';
import { AccountStats, PaginationState, ImportTask } from './types';

const { Option } = Select;

interface AccountTableProps {
  accounts: Account[];
  loading: boolean;
  selectedRowKeys: React.Key[];
  setSelectedRowKeys: React.Dispatch<React.SetStateAction<React.Key[]>>;
  pagination: PaginationState;
  setPagination: React.Dispatch<React.SetStateAction<PaginationState>>;
  stats: AccountStats;
  fetchAccounts: (page?: number, pageSize?: number) => Promise<void>;
  fetchStats: () => Promise<void>;
  onShowUploadModal: () => void;
  onShowMessageModal: () => void;
  onShowAttrModal: () => void;
  onShowRoleModal: () => void;
  onShowCombatRoleModal: () => void;
  onShowAIModal: () => void;
  onShowWarmupModal: () => void;
  onShowImportProgress: () => void;
  onViewDetail: (id: number) => void;
  importTasks: ImportTask[];
  statusFilter: string | undefined;
  setStatusFilter: React.Dispatch<React.SetStateAction<string | undefined>>;
  roleFilter: string | undefined;
  setRoleFilter: React.Dispatch<React.SetStateAction<string | undefined>>;
  tierFilter: string | undefined;
  setTierFilter: React.Dispatch<React.SetStateAction<string | undefined>>;
}

const AccountTable: React.FC<AccountTableProps> = ({
  accounts,
  loading,
  selectedRowKeys,
  setSelectedRowKeys,
  pagination,
  setPagination,
  stats,
  fetchAccounts,
  fetchStats,
  onShowUploadModal,
  onShowMessageModal,
  onShowAttrModal,
  onShowRoleModal,
  onShowCombatRoleModal,
  onShowAIModal,
  onShowWarmupModal,
  onShowImportProgress,
  onViewDetail,
  importTasks,
  statusFilter,
  setStatusFilter,
  roleFilter,
  setRoleFilter,
  tierFilter,
  setTierFilter,
}) => {
  const [checking, setChecking] = useState<number[]>([]);
  const [fileList, setFileList] = useState<UploadFile[]>([]);

  // Proxy modal state (inline in table for the "swap proxy" button)
  const [isProxyModalVisible, setIsProxyModalVisible] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null);
  const [activeProxies, setActiveProxies] = useState<Proxy[]>([]);
  const [selectedProxyId, setSelectedProxyId] = useState<number | undefined>(undefined);
  const [proxyModalLoading, setProxyModalLoading] = useState(false);

  const handleCheckStatus = async (id: number) => {
    setChecking(prev => [...prev, id]);
    try {
      const result = await checkAccountStatus(id);
      message.info(`检查任务已提交，任务 ID: ${result.task_id}`);
      setTimeout(() => {
        fetchAccounts(pagination.current, pagination.pageSize);
        fetchStats();
        setChecking(prev => prev.filter(aid => aid !== id));
      }, 3000);
    } catch (error) {
      message.error('启动检查任务失败');
      setChecking(prev => prev.filter(aid => aid !== id));
    }
  };

  const handleBatchCheck = async () => {
    if (accounts.length === 0) {
      message.warning('没有可检查的账号');
      return;
    }
    const accountIds = accounts.map(a => a.id);
    setChecking(accountIds);
    try {
      const result = await checkAccountsBatch(accountIds);
      message.info(`批量检查任务已提交，共 ${result.account_count} 个账号`);
      setTimeout(() => {
        fetchAccounts(pagination.current, pagination.pageSize);
        fetchStats();
        setChecking([]);
      }, 5000);
    } catch (error) {
      message.error('批量检查失败');
      setChecking([]);
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteAccount(id);
      message.success('账号删除成功');
      fetchAccounts(pagination.current, pagination.pageSize);
      fetchStats();
    } catch (error) {
      message.error('删除账号失败');
    }
  };

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择要删除的账号');
      return;
    }
    try {
      const result = await deleteAccountsBatch(selectedRowKeys as number[]);
      message.success(result.message);
      setSelectedRowKeys([]);
      fetchAccounts(pagination.current, pagination.pageSize);
      fetchStats();
    } catch (error) {
      message.error('批量删除失败');
    }
  };

  const handleBatchUpload = async () => {
    if (fileList.length === 0) {
      message.error('请选择文件');
      return;
    }
    try {
      const files = fileList.map(item => item.originFileObj).filter(Boolean) as File[];
      const result = await uploadAccountSessionsBatch(files);
      message.success(`批量上传完成：创建 ${result.created} 个，更新 ${result.updated} 个，跳过 ${result.skipped} 个`);
      if (result.errors.length > 0) {
        message.warning(`有 ${result.errors.length} 个错误，请查看控制台`);
        console.error('上传错误:', result.errors);
      }
      setFileList([]);
      fetchAccounts(pagination.current, pagination.pageSize);
      fetchStats();
    } catch (error: any) {
      message.error(`批量上传失败: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleShowProxyModal = async (account: Account) => {
    setSelectedAccount(account);
    setSelectedProxyId(account.proxy_id);
    setIsProxyModalVisible(true);
    try {
      const proxies = await getProxies(0, 100, 'active');
      setActiveProxies(proxies);
    } catch (error) {
      message.error('获取代理列表失败');
    }
  };

  const handleUpdateProxy = async () => {
    if (!selectedAccount || !selectedProxyId) {
      message.warning('请选择代理');
      return;
    }
    setProxyModalLoading(true);
    try {
      await updateAccountProxy(selectedAccount.id, selectedProxyId);
      message.success('代理已更新');
      setIsProxyModalVisible(false);
      fetchAccounts();
    } catch (error) {
      message.error('更新代理失败');
    } finally {
      setProxyModalLoading(false);
    }
  };

  const onSelectChange = (newSelectedRowKeys: React.Key[]) => {
    setSelectedRowKeys(newSelectedRowKeys);
  };

  const rowSelection = {
    selectedRowKeys,
    onChange: onSelectChange,
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 80,
    },
    {
      title: '手机号',
      dataIndex: 'phone_number',
      key: 'phone_number',
    },
    {
      title: '角色',
      dataIndex: 'role',
      key: 'role',
      width: 100,
      render: (role: string) => getRoleTag(role),
    },
    {
      title: '分级',
      dataIndex: 'tier',
      key: 'tier',
      width: 100,
      render: (tier: string) => {
        const color = tier === 'tier1' ? 'gold' : (tier === 'tier2' ? 'blue' : 'default');
        return <Tag color={color}>{tier ? tier.toUpperCase() : 'TIER3'}</Tag>;
      },
    },
    {
      title: '战斗角色',
      dataIndex: 'combat_role',
      key: 'combat_role',
      width: 100,
      filters: [
        { text: '炮灰', value: 'cannon' },
        { text: '侦察', value: 'scout' },
        { text: '演员', value: 'actor' },
        { text: '狙击', value: 'sniper' },
      ],
      onFilter: (value: any, record: Account) => record.combat_role === value,
      render: (role: string) => {
        const config: Record<string, { color: string; label: string }> = {
          cannon: { color: 'red', label: '炮灰' },
          scout: { color: 'blue', label: '侦察' },
          actor: { color: 'purple', label: '演员' },
          sniper: { color: 'gold', label: '狙击' },
        };
        const c = config[role] || { color: 'default', label: role || 'cannon' };
        return <Tag color={c.color}>{c.label}</Tag>;
      },
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 150,
      render: (status: string, record: Account) => {
        if (status === 'flood_wait' && record.cooldown_until) {
          const until = new Date(record.cooldown_until);
          const now = new Date();
          const diff = Math.ceil((until.getTime() - now.getTime()) / 1000 / 60);
          if (diff > 0) {
            return (
              <Space direction="vertical" size={0}>
                {getStatusTag(status)}
                <span style={{ fontSize: 12, color: '#cf1322' }}>{diff}分钟后恢复</span>
              </Space>
            );
          }
        }
        return getStatusTag(status);
      },
    },
    {
      title: '绑定代理',
      key: 'proxy',
      width: 150,
      render: (_: any, record: Account) => {
        if (record.proxy) {
          return `${record.proxy.ip}:${record.proxy.port}`;
        }
        return <Tag color="default">未绑定</Tag>;
      },
    },
    {
      title: '最后活跃',
      dataIndex: 'last_active',
      key: 'last_active',
      width: 180,
      render: (text: string) => text ? new Date(text).toLocaleString() : '-',
    },
    {
      title: '创建时间',
      dataIndex: 'created_at',
      key: 'created_at',
      width: 180,
      render: (text: string) => new Date(text).toLocaleString(),
    },
    {
      title: '操作',
      key: 'action',
      width: 200,
      render: (_: any, record: Account) => (
        <Space>
          <Button
            size="small"
            icon={<EyeOutlined />}
            onClick={() => onViewDetail(record.id)}
          >
            详情
          </Button>
          <Button
            size="small"
            icon={<SyncOutlined />}
            loading={checking.includes(record.id)}
            onClick={() => handleCheckStatus(record.id)}
          >
            检查
          </Button>
          <Button
            size="small"
            icon={<SwapOutlined />}
            onClick={() => handleShowProxyModal(record)}
          >
            换代理
          </Button>
          <Popconfirm
            title="确定要删除这个账号吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={6}>
            <Statistic title="总账号数" value={stats.total} />
          </Col>
          <Col span={6}>
            <Statistic title="活跃账号" value={stats.active} styles={{ content: { color: '#3f8600' } }} />
          </Col>
          <Col span={6}>
            <Statistic title="初始化" value={stats.init} styles={{ content: { color: '#1890ff' } }} />
          </Col>
          <Col span={6}>
            <Statistic title="已封禁" value={stats.banned} styles={{ content: { color: '#cf1322' } }} />
          </Col>
        </Row>
      </Card>

      <Card>
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <Space>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={onShowUploadModal}
            >
              添加账号
            </Button>
            <Upload
              fileList={fileList}
              beforeUpload={() => false}
              onChange={({ fileList }) => setFileList(fileList)}
              accept=".session,.json"
              multiple
            >
              <Button icon={<UploadOutlined />}>批量上传 Session/JSON</Button>
            </Upload>
            {fileList.length > 0 && (
              <Button type="primary" onClick={handleBatchUpload}>
                导入 {fileList.length} 个文件
              </Button>
            )}
            <Button
              icon={<SyncOutlined />}
              onClick={handleBatchCheck}
              loading={checking.length > 0}
            >
              批量检查
            </Button>
            <Popconfirm
              title="确认删除"
              description={`确定要删除选中的 ${selectedRowKeys.length} 个账号吗？此操作不可恢复。`}
              onConfirm={handleBatchDelete}
              okText="确认删除"
              cancelText="取消"
              okButtonProps={{ danger: true }}
            >
              <Button
                icon={<DeleteOutlined />}
                danger
                disabled={selectedRowKeys.length === 0}
              >
                批量删除 {selectedRowKeys.length > 0 ? `(${selectedRowKeys.length})` : ''}
              </Button>
            </Popconfirm>
            <Button
              icon={<MessageOutlined />}
              onClick={onShowMessageModal}
              disabled={selectedRowKeys.length === 0}
            >
              发送消息
            </Button>
            <Button
              icon={<EditOutlined />}
              onClick={onShowAttrModal}
              disabled={selectedRowKeys.length === 0}
            >
              属性管理
            </Button>
            <Button
              onClick={onShowRoleModal}
              disabled={selectedRowKeys.length === 0}
            >
              设置角色
            </Button>
            <Button
              onClick={onShowCombatRoleModal}
              disabled={selectedRowKeys.length === 0}
              style={{ backgroundColor: '#722ed1', borderColor: '#722ed1', color: '#fff' }}
            >
              战斗角色
            </Button>
            <Button
              icon={<RobotOutlined />}
              onClick={onShowAIModal}
              disabled={selectedRowKeys.length !== 1}
            >
              AI 配置
            </Button>
            <Button
              type="primary"
              icon={<CoffeeOutlined />}
              onClick={onShowWarmupModal}
              disabled={selectedRowKeys.length === 0}
            >
              一键养号 {selectedRowKeys.length > 0 ? `(${selectedRowKeys.length})` : ''}
            </Button>
            <Button
              icon={<CloudDownloadOutlined />}
              onClick={onShowImportProgress}
              disabled={importTasks.length === 0}
            >
              导入进度 {importTasks.some(t => ['STARTED', 'PROGRESS'].includes(t.status)) && <LoadingOutlined />}
            </Button>
            <Button icon={<ReloadOutlined />} onClick={() => fetchAccounts(pagination.current, pagination.pageSize)}>
              刷新
            </Button>
          </Space>
          <Space>
            <Select
              style={{ width: 120 }}
              placeholder="筛选分级"
              allowClear
              value={tierFilter}
              onChange={(value) => {
                setTierFilter(value);
                setPagination(prev => ({ ...prev, current: 1 }));
              }}
            >
              <Option value="tier1">Tier 1 (Premium)</Option>
              <Option value="tier2">Tier 2 (Support)</Option>
              <Option value="tier3">Tier 3 (Worker)</Option>
            </Select>
            <Select
              style={{ width: 120 }}
              placeholder="筛选角色"
              allowClear
              value={roleFilter}
              onChange={(value) => {
                setRoleFilter(value);
                setPagination(prev => ({ ...prev, current: 1 }));
              }}
            >
              <Option value="worker">临时号</Option>
              <Option value="master">主账号</Option>
              <Option value="support">客服号</Option>
              <Option value="sales">销售号</Option>
            </Select>
            <Select
              style={{ width: 150 }}
              placeholder="筛选状态"
              allowClear
              value={statusFilter}
              onChange={(value) => {
                setStatusFilter(value);
                setPagination(prev => ({ ...prev, current: 1 }));
              }}
            >
              <Option value="init">初始化</Option>
              <Option value="active">活跃</Option>
              <Option value="uploaded">已上传</Option>
              <Option value="banned">已封禁</Option>
              <Option value="spam_block">限制</Option>
            </Select>
          </Space>
        </div>

        <Table
          rowSelection={rowSelection}
          columns={columns}
          dataSource={accounts}
          rowKey="id"
          loading={loading}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: pagination.total,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) => {
              setPagination(prev => ({ ...prev, current: page, pageSize }));
              fetchAccounts(page, pageSize);
            },
          }}
        />
      </Card>

      {/* Proxy Modal (inline, part of table actions) */}
      {isProxyModalVisible && (
        <ProxyModal
          visible={isProxyModalVisible}
          account={selectedAccount}
          activeProxies={activeProxies}
          selectedProxyId={selectedProxyId}
          loading={proxyModalLoading}
          onSelectProxy={setSelectedProxyId}
          onOk={handleUpdateProxy}
          onCancel={() => setIsProxyModalVisible(false)}
        />
      )}
    </div>
  );
};

// Inline proxy modal sub-component
interface ProxyModalProps {
  visible: boolean;
  account: Account | null;
  activeProxies: Proxy[];
  selectedProxyId: number | undefined;
  loading: boolean;
  onSelectProxy: (id: number) => void;
  onOk: () => void;
  onCancel: () => void;
}

const ProxyModal: React.FC<ProxyModalProps> = ({
  visible,
  account,
  activeProxies,
  selectedProxyId,
  loading,
  onSelectProxy,
  onOk,
  onCancel,
}) => (
  <Modal
    title="更换代理"
    open={visible}
    onOk={onOk}
    onCancel={onCancel}
    confirmLoading={loading}
  >
    <p>为账号 {account?.phone_number} 选择新的代理：</p>
    <Select
      style={{ width: '100%' }}
      placeholder="选择代理"
      value={selectedProxyId}
      onChange={(value) => onSelectProxy(value)}
      showSearch
      optionFilterProp="children"
    >
      <Option value={0} key="none">不绑定（直接连接）</Option>
      {activeProxies.map((proxy) => (
        <Option key={proxy.id} value={proxy.id}>
          {proxy.ip}:{proxy.port} ({proxy.protocol})
        </Option>
      ))}
    </Select>
  </Modal>
);

export default AccountTable;
