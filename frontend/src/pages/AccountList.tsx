import React, { useEffect, useState, useRef } from 'react';
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  message,
  Tag,
  Space,
  Upload,
  Tabs,
  UploadFile,
  Popconfirm,
  Card,
  Statistic,
  Row,
  Col,
  Select,
  Descriptions,
  Drawer,
  Checkbox,
  Radio,
  Progress,
  List,
  Typography,
  Switch
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  DeleteOutlined,
  UploadOutlined,
  SyncOutlined,
  EyeOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  ExclamationCircleOutlined,
  SwapOutlined,
  MessageOutlined,
  EditOutlined,
  RobotOutlined,
  CloudDownloadOutlined,
  LoadingOutlined,
  CoffeeOutlined,
} from '@ant-design/icons';
import {
  getAccounts,
  getAccountCount,
  getAccount,
  createAccount,
  deleteAccount,
  deleteAccountsBatch,
  uploadAccountSession,
  uploadAccountSessionsBatch,
  checkAccountStatus,
  checkAccountsBatch,
  updateAccountProxy,
  sendTestMessageBatch,
  updateAccountProfile,
  updateAccountUsername,
  updateAccount2FA,
  updateAccountPhoto,
  updateAccountPhotoRandom,
  autoUpdateAccount,
  updateAccountAIConfig,
  updateAccountsRoleBatch,
  getProxies,
  Account,
  AccountCreate,
  Proxy,
  startAutoRegistration,
  refreshProxiesFromIP2World,
  importMegaAccounts,
  getTasksBatch,
  TaskStatus,
  getWarmupTemplates,
  createWarmupTask,
  WarmupTemplate
} from '../services/api';

const { Option } = Select;
const { Text } = Typography;

interface ImportTask {
    taskId: string;
    url: string;
    status: string; // PENDING, STARTED, SUCCESS, FAILURE, PROGRESS
    progress?: {
        status: string;
        message: string;
        url: string;
    };
    result?: any;
    error?: string;
}

const AccountList: React.FC = () => {
  const [accounts, setAccounts] = useState<Account[]>([]);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState<number[]>([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [isDetailVisible, setIsDetailVisible] = useState(false);
  const [selectedAccount, setSelectedAccount] = useState<Account | null>(null);
  const [activeTab, setActiveTab] = useState('manual');
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [form] = Form.useForm();
  const [uploadForm] = Form.useForm();
  const [megaForm] = Form.useForm();
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [roleFilter, setRoleFilter] = useState<string | undefined>(undefined);
  const [tierFilter, setTierFilter] = useState<string | undefined>(undefined);
  const [stats, setStats] = useState({ total: 0, active: 0, init: 0, banned: 0 });
  const [visitedTabs, setVisitedTabs] = useState<Set<string>>(new Set(['manual']));
  
  // Role Modal State
  const [isRoleModalVisible, setIsRoleModalVisible] = useState(false);
  const [selectedRole, setSelectedRole] = useState<string>('worker');
  const [selectedTier, setSelectedTier] = useState<string>('tier3');
  const [selectedTags, setSelectedTags] = useState<string>('');
  const [roleModalLoading, setRoleModalLoading] = useState(false);
  
  // Import Progress State
  const [importTasks, setImportTasks] = useState<ImportTask[]>([]);
  const [isImportProgressVisible, setIsImportProgressVisible] = useState(false);
  const pollingInterval = useRef<NodeJS.Timeout | null>(null);
  
  // Proxy Modal State
  const [activeProxies, setActiveProxies] = useState<Proxy[]>([]);
  const [isProxyModalVisible, setIsProxyModalVisible] = useState(false);
  const [selectedProxyId, setSelectedProxyId] = useState<number | undefined>(undefined);
  const [proxyModalLoading, setProxyModalLoading] = useState(false);

  // Message Modal State
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  const [isMessageModalVisible, setIsMessageModalVisible] = useState(false);
  const [messageTarget, setMessageTarget] = useState('');
  const [messageContent, setMessageContent] = useState('Hello from [Phone Number]');
  const [sendingMessage, setSendingMessage] = useState(false);

  // Attribute Modal State
  const [isAttrModalVisible, setIsAttrModalVisible] = useState(false);
  const [attrModalTab, setAttrModalTab] = useState('profile');
  const [attrLoading, setAttrLoading] = useState(false);
  const [profileForm] = Form.useForm();
  const [useRandomProfile, setUseRandomProfile] = useState(false);
  const [usernameForm] = Form.useForm();
  const [twoFAForm] = Form.useForm();
  const [autoUpdateForm] = Form.useForm();
  const [photoFile, setPhotoFile] = useState<UploadFile | null>(null);
  
  // AI Modal State
  const [isAIModalVisible, setIsAIModalVisible] = useState(false);
  const [aiForm] = Form.useForm();
  const [aiLoading, setAiLoading] = useState(false);
  
  // Auto Reg State
  const [autoRegLoading, setAutoRegLoading] = useState(false);
  const [autoRegForm] = Form.useForm();
  
  // Quick Warmup State
  const [isWarmupModalVisible, setIsWarmupModalVisible] = useState(false);
  const [warmupTemplates, setWarmupTemplates] = useState<WarmupTemplate[]>([]);
  const [selectedWarmupTemplateId, setSelectedWarmupTemplateId] = useState<number | null>(null);
  const [warmupLoading, setWarmupLoading] = useState(false);

  // Use ref to always have the latest importTasks in the interval callback
  const importTasksRef = useRef(importTasks);
  useEffect(() => {
      importTasksRef.current = importTasks;
  }, [importTasks]);

  // Polling logic for import tasks - uses batch API to reduce request count
  useEffect(() => {
      const shouldPoll = importTasks.length > 0 && importTasks.some(t => ['PENDING', 'STARTED', 'PROGRESS'].includes(t.status));
      
      if (shouldPoll && !pollingInterval.current) {
          pollingInterval.current = setInterval(async () => {
              // Use ref to get latest tasks (avoid stale closure)
              const currentTasks = importTasksRef.current;
              
              // Get all pending task IDs for batch query
              const pendingTaskIds = currentTasks
                  .filter(t => ['PENDING', 'STARTED', 'PROGRESS'].includes(t.status))
                  .map(t => t.taskId);
              
              if (pendingTaskIds.length === 0) {
                  if (pollingInterval.current) {
                      clearInterval(pollingInterval.current);
                      pollingInterval.current = null;
                  }
                  return;
              }
              
              try {
                  // Single batch request instead of N individual requests
                  const batchResults = await getTasksBatch(pendingTaskIds);
                  
                  const updatedTasks = [...currentTasks];
                  let hasChanges = false;
                  
                  for (let i = 0; i < updatedTasks.length; i++) {
                      const task = updatedTasks[i];
                      const statusRes = batchResults[task.taskId];
                      
                      if (statusRes && (statusRes.status !== task.status || JSON.stringify(statusRes.result) !== JSON.stringify(task.result))) {
                          updatedTasks[i] = {
                              ...task,
                              status: statusRes.status,
                              result: statusRes.result,
                              // If state is PROGRESS, result contains the meta info
                              progress: statusRes.status === 'PROGRESS' ? statusRes.result : undefined,
                              error: statusRes.status === 'FAILURE' ? statusRes.result : undefined
                          };
                          hasChanges = true;
                      }
                  }
                  
                  if (hasChanges) {
                      setImportTasks(updatedTasks);
                      // Refresh accounts if any task completed successfully
                      if (updatedTasks.some(t => t.status === 'SUCCESS')) {
                          fetchAccounts(pagination.current, pagination.pageSize);
                          fetchStats();
                      }
                  }
                  
                  // Stop polling if all done
                  if (!updatedTasks.some(t => ['PENDING', 'STARTED', 'PROGRESS'].includes(t.status))) {
                      if (pollingInterval.current) {
                          clearInterval(pollingInterval.current);
                          pollingInterval.current = null;
                      }
                  }
              } catch (e) {
                  console.error('Failed to poll tasks batch', e);
              }
          }, 2000);
      }
      
      if (!shouldPoll && pollingInterval.current) {
          clearInterval(pollingInterval.current);
          pollingInterval.current = null;
      }
      
      return () => {
          // Don't clear on every render, only on unmount
      };
  }, [importTasks.length, importTasks.some(t => ['PENDING', 'STARTED', 'PROGRESS'].includes(t.status))]);

  // Quick Warmup handlers
  const fetchWarmupTemplates = async () => {
    try {
      const data = await getWarmupTemplates();
      setWarmupTemplates(data);
      // 自动选择默认模板
      const defaultTemplate = data.find(t => t.is_default);
      if (defaultTemplate) {
        setSelectedWarmupTemplateId(defaultTemplate.id);
      } else if (data.length > 0) {
        setSelectedWarmupTemplateId(data[0].id);
      }
    } catch (e) {
      console.error('Failed to fetch warmup templates:', e);
    }
  };

  const handleShowWarmupModal = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择要养号的账号');
      return;
    }
    // 只选择活跃账号
    const activeAccountIds = accounts
      .filter(a => selectedRowKeys.includes(a.id) && a.status === 'active')
      .map(a => a.id);
    
    if (activeAccountIds.length === 0) {
      message.warning('所选账号中没有活跃账号');
      return;
    }
    
    fetchWarmupTemplates();
    setIsWarmupModalVisible(true);
  };

  const handleQuickWarmup = async () => {
    if (!selectedWarmupTemplateId) {
      message.error('请选择一个养号模板');
      return;
    }
    
    const template = warmupTemplates.find(t => t.id === selectedWarmupTemplateId);
    if (!template) {
      message.error('模板不存在');
      return;
    }
    
    // 只选择活跃账号
    const activeAccountIds = accounts
      .filter(a => selectedRowKeys.includes(a.id) && a.status === 'active')
      .map(a => a.id);
    
    if (activeAccountIds.length === 0) {
      message.error('没有可用的活跃账号');
      return;
    }
    
    setWarmupLoading(true);
    try {
      await createWarmupTask({
        name: `${template.name} - ${new Date().toLocaleDateString()}`,
        account_ids: activeAccountIds,
        action_type: template.action_type,
        min_delay: template.min_delay,
        max_delay: template.max_delay,
        duration_minutes: template.duration_minutes,
        target_channels: template.target_channels
      });
      message.success(`养号任务已启动，${activeAccountIds.length} 个账号`);
      setIsWarmupModalVisible(false);
      setSelectedRowKeys([]);
    } catch (error: any) {
      message.error(`启动失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setWarmupLoading(false);
    }
  };

  const handleShowAIModal = () => {
    if (selectedRowKeys.length !== 1) {
        message.warning('请选择一个账号进行配置');
        return;
    }
    const account = accounts.find(a => a.id === selectedRowKeys[0]);
    if (account) {
        aiForm.setFieldsValue({
            auto_reply: account.auto_reply,
            persona_prompt: account.persona_prompt
        });
        setIsAIModalVisible(true);
    }
  };

  const handleUpdateAIConfig = async (values: any) => {
      setAiLoading(true);
      try {
          const accountId = selectedRowKeys[0] as number;
          await updateAccountAIConfig(accountId, values);
          message.success('AI 配置已更新');
          setIsAIModalVisible(false);
          fetchAccounts(pagination.current, pagination.pageSize);
      } catch (error: any) {
          message.error(`更新失败: ${error.response?.data?.detail || error.message}`);
      } finally {
          setAiLoading(false);
      }
  };

  const fetchAccounts = async (page: number = 1, pageSize: number = 20) => {
    setLoading(true);
    try {
      const skip = (page - 1) * pageSize;
      // Note: We might need to update getAccounts API signature to support tier filter
      const data = await getAccounts(skip, pageSize, statusFilter, roleFilter);
      // Client-side filtering for tier if API doesn't support it yet
      const filteredData = tierFilter 
        ? data.filter(acc => (acc.tier || 'tier3') === tierFilter)
        : data;
        
      setAccounts(filteredData);
      
      // 获取总数
      const count = await getAccountCount(statusFilter);
      setPagination(prev => ({ ...prev, current: page, pageSize, total: count.total }));
    } catch (error) {
      message.error('获取账号列表失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
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
  };

  useEffect(() => {
    fetchAccounts();
    fetchStats();
  }, [statusFilter, roleFilter, tierFilter]);

  const resetForms = () => {
    if (visitedTabs.has('manual')) form.resetFields();
    if (visitedTabs.has('upload')) uploadForm.resetFields();
    if (visitedTabs.has('mega')) megaForm.resetFields();
    if (visitedTabs.has('auto_reg')) autoRegForm.resetFields();
  };

  const handleCreate = async (values: any) => {
    try {
      if (activeTab === 'manual') {
        await createAccount(values);
        message.success('账号创建成功');
      } else if (activeTab === 'upload') {
        if (fileList.length === 0) {
          message.error('请选择文件');
            return;
        }
        // @ts-ignore
        await uploadAccountSession(fileList[0].originFileObj, values.phone_number);
        message.success('账号上传成功');
      } else if (activeTab === 'mega') {
        // Handle multiline MEGA URLs
        const urls = values.urls.split('\n').filter((url: string) => url.trim().length > 0);
        if (urls.length === 0) {
            message.warning('请输入至少一个有效的链接');
            return;
        }
        // 获取用户输入的目标频道
        const target_channels = values.target_channels;
        const auto_check = values.auto_check ?? false;
        const auto_warmup = values.auto_warmup ?? false;
        const res = await importMegaAccounts(urls, target_channels, auto_check, auto_warmup);
        message.success(`已提交 ${urls.length} 个 MEGA 导入任务`);
        
        // Add tasks to list
        const newTasks: ImportTask[] = res.task_ids.map((tid: string, index: number) => ({
            taskId: tid,
            url: res.urls[index],
            status: 'PENDING'
        }));
        
        setImportTasks(prev => [...newTasks, ...prev]);
        setIsImportProgressVisible(true);
        
      } else if (activeTab === 'auto_reg') {
          setAutoRegLoading(true);
          try {
              // 1. 先尝试刷新代理
              if (values.refresh_proxies) {
                  try {
                      const proxyRes = await refreshProxiesFromIP2World();
                      message.info(`已刷新代理池，新增 ${proxyRes.added_count} 个代理`);
                  } catch (e) {
                      message.warning('刷新代理失败，尝试使用现有代理');
                  }
              }
              
              // 2. 启动注册任务
              const res = await startAutoRegistration({
                  count: values.count,
                  country: values.country
              });
              message.success(res.message);
          } finally {
              setAutoRegLoading(false);
          }
      }
      setIsModalVisible(false);
      resetForms();
      setFileList([]);
      // fetchAccounts called inside useEffect or when tasks complete
    } catch (error: any) {
      message.error(`操作失败: ${error.response?.data?.detail || error.message}`);
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
      uploadForm.resetFields();
      fetchAccounts(pagination.current, pagination.pageSize);
      fetchStats();
    } catch (error: any) {
      message.error(`批量上传失败: ${error.response?.data?.detail || error.message}`);
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

  const handleCheckStatus = async (id: number) => {
    setChecking(prev => [...prev, id]);
    try {
      const result = await checkAccountStatus(id);
      message.info(`检查任务已提交，任务 ID: ${result.task_id}`);
      // 延迟后刷新（实际应该通过 WebSocket 或轮询获取结果）
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

  const handleViewDetail = async (id: number) => {
    try {
      const account = await getAccount(id);
      setSelectedAccount(account);
      setIsDetailVisible(true);
    } catch (error) {
      message.error('获取账号详情失败');
    }
  };

  const handleShowProxyModal = async (account: Account) => {
    setSelectedAccount(account);
    setSelectedProxyId(account.proxy_id);
    setIsProxyModalVisible(true);
    try {
      // 获取活跃代理列表
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

  const getStatusTag = (status: string) => {
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

  const onSelectChange = (newSelectedRowKeys: React.Key[]) => {
    setSelectedRowKeys(newSelectedRowKeys);
  };

  const rowSelection = {
    selectedRowKeys,
    onChange: onSelectChange,
  };

  const handleShowRoleModal = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择要设置角色的账号');
      return;
    }
    setIsRoleModalVisible(true);
  };

  const handleUpdateRole = async () => {
    setRoleModalLoading(true);
    try {
      const accountIds = selectedRowKeys as number[];
      // We are reusing updateAccountsRoleBatch but also need to update Tier
      // API needs to support tier update or we add a new param
      // For now, assume updateAccountsRoleBatch accepts extra params or we update API
      await updateAccountsRoleBatch(accountIds, selectedRole, selectedTags || undefined, selectedTier);
      message.success(`成功更新 ${accountIds.length} 个账号的角色/分级`);
      setIsRoleModalVisible(false);
      setSelectedRowKeys([]);
      fetchAccounts(pagination.current, pagination.pageSize);
    } catch (error: any) {
      message.error(`更新失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setRoleModalLoading(false);
    }
  };

  const getRoleTag = (role?: string) => {
    const roleConfig: Record<string, { color: string; text: string }> = {
      worker: { color: 'default', text: '临时号' },
      master: { color: 'gold', text: '主账号' },
      support: { color: 'blue', text: '客服号' },
      sales: { color: 'purple', text: '销售号' },
    };
    const config = roleConfig[role || 'worker'] || roleConfig.worker;
    return <Tag color={config.color}>{config.text}</Tag>;
  };

  const handleShowMessageModal = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择要发送消息的账号');
      return;
    }
    setIsMessageModalVisible(true);
  };

  const handleSendMessage = async () => {
    if (!messageTarget) {
      message.error('请输入接收目标');
      return;
    }
    if (!messageContent) {
      message.error('请输入消息内容');
      return;
    }

    setSendingMessage(true);
    try {
      const accountIds = selectedRowKeys as number[];
      const result = await sendTestMessageBatch(accountIds, messageTarget, messageContent);
      
      if (result.success_count > 0) {
        message.success(`发送完成: 成功 ${result.success_count}, 失败 ${result.fail_count}`);
      }
      
      if (result.fail_count > 0) {
        const errors = result.results
          .filter(r => r.status === 'error')
          .map(r => `ID ${r.id}: ${r.message}`)
          .join('; ');
        
        // 如果全部失败，使用 error 提示；如果有部分成功，使用 warning 提示
        if (result.success_count === 0) {
           message.error(`发送失败: ${errors}`);
        } else {
           message.warning(`部分失败: ${errors}`);
        }
        console.error("Failures:", result.results.filter(r => r.status === 'error'));
      }
      
      setIsMessageModalVisible(false);
      setSelectedRowKeys([]);
    } catch (error: any) {
      message.error(`发送失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setSendingMessage(false);
    }
  };

  const handleShowAttrModal = () => {
    if (selectedRowKeys.length === 0) {
      message.warning('请先选择账号');
      return;
    }
    setIsAttrModalVisible(true);
  };

  const handleUpdateProfile = async (values: any) => {
    setAttrLoading(true);
    try {
        const accountIds = selectedRowKeys as number[];
        let successCount = 0;
        let failCount = 0;
        
        // 串行执行，避免并发过高
        for (const id of accountIds) {
            try {
                await updateAccountProfile(id, values);
                successCount++;
            } catch (e) {
                failCount++;
            }
        }
        
        if (failCount > 0) {
            message.warning(`完成: 成功 ${successCount}, 失败 ${failCount}`);
        } else {
            message.success(`成功更新 ${successCount} 个账号`);
        }
        setIsAttrModalVisible(false);
    } finally {
        setAttrLoading(false);
    }
  };

  const handleUpdateUsername = async (values: any) => {
    if (selectedRowKeys.length > 1) {
        message.warning('批量修改用户名暂不支持（用户名必须唯一），请选择单个账号');
        return;
    }
    setAttrLoading(true);
    try {
        await updateAccountUsername(selectedRowKeys[0] as number, values.username);
        message.success('用户名更新成功');
        setIsAttrModalVisible(false);
    } catch (error: any) {
        message.error(`更新失败: ${error.response?.data?.detail || error.message}`);
    } finally {
        setAttrLoading(false);
    }
  };

  const handleUpdate2FA = async (values: any) => {
    setAttrLoading(true);
    try {
        const accountIds = selectedRowKeys as number[];
        let successCount = 0;
        let failCount = 0;
        
        for (const id of accountIds) {
            try {
                await updateAccount2FA(id, values);
                successCount++;
            } catch (e) {
                failCount++;
            }
        }
         if (failCount > 0) {
            message.warning(`完成: 成功 ${successCount}, 失败 ${failCount}`);
        } else {
            message.success(`成功更新 ${successCount} 个账号`);
        }
        setIsAttrModalVisible(false);
    } finally {
        setAttrLoading(false);
    }
  };

  const handleUpdatePhoto = async () => {
    if (!photoFile) {
        message.error('请先选择图片');
        return;
    }
    setAttrLoading(true);
    try {
        const accountIds = selectedRowKeys as number[];
        let successCount = 0;
        let failCount = 0;

        for (const id of accountIds) {
            try {
                // @ts-ignore
                await updateAccountPhoto(id, photoFile);
                successCount++;
            } catch (e) {
                failCount++;
            }
        }
        if (failCount > 0) {
            message.warning(`完成: 成功 ${successCount}, 失败 ${failCount}`);
        } else {
            message.success(`成功更新 ${successCount} 个账号`);
        }
        setIsAttrModalVisible(false);
        setPhotoFile(null);
    } finally {
        setAttrLoading(false);
    }
  };

  const handleUpdatePhotoRandom = async () => {
    setAttrLoading(true);
    try {
        const accountIds = selectedRowKeys as number[];
        let successCount = 0;
        let failCount = 0;

        for (const id of accountIds) {
            try {
                await updateAccountPhotoRandom(id);
                successCount++;
            } catch (e) {
                failCount++;
            }
        }
        if (failCount > 0) {
            message.warning(`完成: 成功 ${successCount}, 失败 ${failCount}`);
        } else {
            message.success(`成功更新 ${successCount} 个账号`);
        }
        setIsAttrModalVisible(false);
    } finally {
        setAttrLoading(false);
    }
  };

  const handleAutoUpdate = async (values: any) => {
    setAttrLoading(true);
    try {
        const accountIds = selectedRowKeys as number[];
        let successCount = 0;
        let failCount = 0;

        for (const id of accountIds) {
            try {
                await autoUpdateAccount(id, values);
                successCount++;
            } catch (e) {
                failCount++;
            }
        }
        
        if (failCount > 0) {
            message.warning(`完成: 成功 ${successCount}, 失败 ${failCount}`);
        } else {
            message.success(`成功自动更新 ${successCount} 个账号`);
        }
        setIsAttrModalVisible(false);
    } finally {
        setAttrLoading(false);
    }
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
      }
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
             const diff = Math.ceil((until.getTime() - now.getTime()) / 1000 / 60); // minutes
             if (diff > 0) {
                 return (
                     <Space orientation="vertical" size={0}>
                        {getStatusTag(status)}
                        <span style={{ fontSize: 12, color: '#cf1322' }}>{diff}分钟后恢复</span>
                     </Space>
                 )
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
            onClick={() => handleViewDetail(record.id)}
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

  const renderImportTaskItem = (task: ImportTask) => {
      let statusIcon;
      let statusColor;
      let statusText;
      
      switch(task.status) {
          case 'PENDING':
              statusIcon = <ClockCircleOutlined />;
              statusColor = 'default';
              statusText = '等待中';
              break;
          case 'STARTED':
          case 'PROGRESS':
              statusIcon = <LoadingOutlined />;
              statusColor = 'processing';
              statusText = task.progress?.message || '进行中';
              break;
          case 'SUCCESS':
              statusIcon = <CheckCircleOutlined />;
              statusColor = 'success';
              statusText = `成功导入 ${task.result?.imported_count || 0} 个账号 (100%)`;
              break;
          case 'FAILURE':
              statusIcon = <CloseCircleOutlined />;
              statusColor = 'error';
              statusText = '导入失败';
              break;
          default:
              statusIcon = <ClockCircleOutlined />;
              statusColor = 'default';
              statusText = task.status;
      }
      
      const getPercent = (status: string, progressStatus?: string) => {
          if (status === 'SUCCESS') return 100;
          if (status === 'FAILURE') return 100; // Show full red bar
          
          switch(progressStatus) {
              case 'downloading': return 10;
              case 'extracting': return 40; // Download complete (20-40 range)
              case 'converting': return 80; // Extraction complete (40-80 range)
              case 'saving': return 90; // Conversion complete
              default: return 0;
          }
      };
      
      return (
          <List.Item>
              <div style={{ width: '100%' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: 8 }}>
                      <Text ellipsis style={{ maxWidth: '60%' }}>{task.url}</Text>
                      <Tag icon={statusIcon} color={statusColor}>{statusText}</Tag>
                  </div>
                  {['STARTED', 'PROGRESS', 'SUCCESS', 'FAILURE'].includes(task.status) && (
                      <Progress 
                        percent={getPercent(task.status, task.progress?.status)} 
                        size="small" 
                        status={task.status === 'SUCCESS' ? 'success' : (task.status === 'FAILURE' ? 'exception' : 'active')} 
                        format={percent => `${percent}%`}
                      />
                  )}
                  {task.status === 'FAILURE' && (
                      <Text type="danger" style={{ fontSize: 12 }}>
                          {typeof task.error === 'string' 
                              ? task.error 
                              : task.error 
                                  ? JSON.stringify(task.error) 
                                  : task.result 
                                      ? (typeof task.result === 'string' ? task.result : JSON.stringify(task.result))
                                      : '未知错误'}
                      </Text>
                  )}
                  {task.status === 'SUCCESS' && task.result?.errors?.length > 0 && (
                      <div style={{ marginTop: 4 }}>
                          <Text type="warning" style={{ fontSize: 12 }}>存在 {task.result.errors.length} 个错误:</Text>
                          <ul style={{ fontSize: 12, color: '#faad14', paddingLeft: 20, margin: 0 }}>
                              {task.result.errors.slice(0, 3).map((e: any, i: number) => (
                                  <li key={i}>{typeof e === 'string' ? e : JSON.stringify(e)}</li>
                              ))}
                              {task.result.errors.length > 3 && <li>...</li>}
                          </ul>
                      </div>
                  )}
              </div>
          </List.Item>
      );
  };

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
            onClick={() => setIsModalVisible(true)}
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
              onClick={handleShowMessageModal}
              disabled={selectedRowKeys.length === 0}
            >
              发送消息
            </Button>
            <Button
              icon={<EditOutlined />}
              onClick={handleShowAttrModal}
              disabled={selectedRowKeys.length === 0}
            >
              属性管理
        </Button>
            <Button
              onClick={handleShowRoleModal}
              disabled={selectedRowKeys.length === 0}
            >
              设置角色
            </Button>
            <Button
              icon={<RobotOutlined />}
              onClick={handleShowAIModal}
              disabled={selectedRowKeys.length !== 1}
            >
              AI 配置
            </Button>
            <Button
              type="primary"
              icon={<CoffeeOutlined />}
              onClick={handleShowWarmupModal}
              disabled={selectedRowKeys.length === 0}
            >
              一键养号 {selectedRowKeys.length > 0 ? `(${selectedRowKeys.length})` : ''}
            </Button>
            <Button 
                icon={<CloudDownloadOutlined />} 
                onClick={() => setIsImportProgressVisible(true)}
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

      <Modal
        title="添加账号"
        open={isModalVisible}
        onCancel={() => {
          setIsModalVisible(false);
          resetForms();
          setFileList([]);
        }}
        footer={null}
        width={600}
        destroyOnHidden={true}
        afterClose={() => {
            setVisitedTabs(new Set(['manual']));
            setActiveTab('manual');
        }}
      >
        <Tabs
          activeKey={activeTab}
          onChange={(key) => {
              setActiveTab(key);
              setVisitedTabs(prev => new Set(prev).add(key));
          }}
          items={[
            {
                key: 'manual',
              label: '手动输入',
                children: (
                    <Form form={form} onFinish={handleCreate} layout="vertical">
                      <Form.Item
                        name="phone_number"
                    label="手机号"
                    rules={[{ required: true, message: '请输入手机号' }]}
                      >
                        <Input placeholder="+1234567890" />
                      </Form.Item>
                  <Form.Item
                    name="api_id"
                    label="API ID（可选）"
                  >
                    <Input type="number" placeholder="从 my.telegram.org 获取" />
                  </Form.Item>
                  <Form.Item
                    name="api_hash"
                    label="API Hash（可选）"
                  >
                    <Input placeholder="从 my.telegram.org 获取" />
                  </Form.Item>
                      <Form.Item
                        name="session_string"
                    label="Session String（可选）"
                      >
                        <Input.TextArea rows={4} placeholder="Pyrogram Session String" />
                      </Form.Item>
                      <Form.Item>
                        <Button type="primary" htmlType="submit" block>
                      创建
                        </Button>
                      </Form.Item>
                    </Form>
              ),
            },
            {
                key: 'upload',
              label: '上传 Session 文件',
                children: (
                    <Form form={uploadForm} onFinish={handleCreate} layout="vertical">
                        <Form.Item
                            name="phone_number"
                    label="手机号（可选，将从文件名自动解析）"
                        >
                    <Input placeholder="+1234567890（如果不提供，将从文件名解析）" />
                        </Form.Item>
                  <Form.Item label="Session 文件">
                            <Upload 
                      beforeUpload={() => false}
                                fileList={fileList}
                      onChange={({ fileList }) => setFileList(fileList)}
                                maxCount={1}
                      accept=".session"
                            >
                      <Button icon={<UploadOutlined />}>选择 .session 文件</Button>
                            </Upload>
                    <div style={{ marginTop: 8, color: '#999', fontSize: '12px' }}>
                      支持 Pyrogram 格式的 .session 文件，文件名应包含手机号（如：+1234567890.session）
                    </div>
                        </Form.Item>
                        <Form.Item>
                            <Button type="primary" htmlType="submit" block>
                      上传并创建
                            </Button>
                        </Form.Item>
                    </Form>
              ),
            },
            {
                key: 'mega',
                label: 'MEGA 批量导入',
                children: (
                    <Form form={megaForm} onFinish={handleCreate} layout="vertical">
                        <Form.Item
                            name="urls"
                            label="MEGA 分享链接 (一行一个)"
                            rules={[{ required: true, message: '请输入至少一个 MEGA 链接' }]}
                            help="支持批量输入，每行一个链接。格式如：https://mega.nz/file/..."
                        >
                            <Input.TextArea rows={6} placeholder="https://mega.nz/file/...\nhttps://mega.nz/file/..." />
                        </Form.Item>
                        <Form.Item
                            name="target_channels"
                            label="养号目标频道 (可选)"
                            initialValue="kltgsc"
                            help="导入后将在这些频道进行随机浏览和互动，用逗号分隔频道用户名"
                        >
                            <Input placeholder="kltgsc,telegram,news" />
                        </Form.Item>
                        <Form.Item
                            name="auto_check"
                            label="导入后自动验活"
                            initialValue={false}
                            valuePropName="checked"
                            help="开启后会在导入完成后自动进行低风险验活（仅连接测试，不发消息/不搜索）"
                        >
                            <Switch />
                        </Form.Item>
                        <Form.Item
                            name="auto_warmup"
                            label="导入后自动养号/热身"
                            initialValue={false}
                            valuePropName="checked"
                            help="建议新号先关闭。开启后会自动加入频道/浏览/互动，容易触发风控"
                        >
                            <Switch />
                        </Form.Item>
                        <Form.Item>
                            <Button type="primary" htmlType="submit" block icon={<CloudDownloadOutlined />}>
                                开始批量后台导入
                            </Button>
                        </Form.Item>
                    </Form>
              ),
            },
          ]}
        />
      </Modal>

      <Modal
        title="MEGA 导入进度"
        open={isImportProgressVisible}
        onCancel={() => setIsImportProgressVisible(false)}
        footer={null}
        width={600}
      >
          {importTasks.length > 0 ? (
              <List
                  itemLayout="horizontal"
                  dataSource={importTasks}
                  renderItem={renderImportTaskItem}
                  pagination={{ pageSize: 5 }}
              />
          ) : (
              <div style={{ textAlign: 'center', padding: 20, color: '#999' }}>暂无导入任务</div>
          )}
      </Modal>

      <Drawer
        title="账号详情"
        placement="right"
        onClose={() => setIsDetailVisible(false)}
        open={isDetailVisible}
        size="large"
      >
        {selectedAccount && (
          <Descriptions column={1} bordered>
            <Descriptions.Item label="ID">{selectedAccount.id}</Descriptions.Item>
            <Descriptions.Item label="手机号">{selectedAccount.phone_number}</Descriptions.Item>
            <Descriptions.Item label="状态">{getStatusTag(selectedAccount.status)}</Descriptions.Item>
            <Descriptions.Item label="API ID">{selectedAccount.api_id || '-'}</Descriptions.Item>
            <Descriptions.Item label="API Hash">{selectedAccount.api_hash ? '***' : '-'}</Descriptions.Item>
            <Descriptions.Item label="Session 文件路径">
              {selectedAccount.session_file_path || '-'}
            </Descriptions.Item>
            <Descriptions.Item label="绑定代理">
              {selectedAccount.proxy ? (
                `${selectedAccount.proxy.ip}:${selectedAccount.proxy.port} (${selectedAccount.proxy.protocol})`
              ) : (
                '未绑定'
              )}
            </Descriptions.Item>
            <Descriptions.Item label="设备型号">{selectedAccount.device_model || '-'}</Descriptions.Item>
            <Descriptions.Item label="系统版本">{selectedAccount.system_version || '-'}</Descriptions.Item>
            <Descriptions.Item label="应用版本">{selectedAccount.app_version || '-'}</Descriptions.Item>
            <Descriptions.Item label="最后活跃">
              {selectedAccount.last_active ? new Date(selectedAccount.last_active).toLocaleString() : '-'}
            </Descriptions.Item>
            <Descriptions.Item label="创建时间">
              {new Date(selectedAccount.created_at).toLocaleString()}
            </Descriptions.Item>
          </Descriptions>
        )}
      </Drawer>

      <Modal
        title="更换代理"
        open={isProxyModalVisible}
        onOk={handleUpdateProxy}
        onCancel={() => setIsProxyModalVisible(false)}
        confirmLoading={proxyModalLoading}
      >
        <p>为账号 {selectedAccount?.phone_number} 选择新的代理：</p>
        <Select
          style={{ width: '100%' }}
          placeholder="选择代理"
          value={selectedProxyId}
          onChange={(value) => setSelectedProxyId(value)}
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

      <Modal
        title="发送测试消息"
        open={isMessageModalVisible}
        onOk={handleSendMessage}
        onCancel={() => setIsMessageModalVisible(false)}
        confirmLoading={sendingMessage}
      >
        <Form layout="vertical">
          <Form.Item label="接收目标 (用户名或手机号)" required>
            <Input
              placeholder="@username"
              value={messageTarget}
              onChange={(e) => setMessageTarget(e.target.value)}
            />
          </Form.Item>
          <Form.Item label="消息内容" required>
            <Input.TextArea
              rows={4}
              value={messageContent}
              onChange={(e) => setMessageContent(e.target.value)}
              placeholder="Hello..."
            />
            <div style={{ marginTop: 8, color: '#999', fontSize: '12px' }}>
              提示: 消息中的 [Phone Number] 会被自动替换为发送账号的手机号。
            </div>
          </Form.Item>
        </Form>
      </Modal>

      <Modal
        title="账号属性管理"
        open={isAttrModalVisible}
        onCancel={() => setIsAttrModalVisible(false)}
        footer={null}
        width={600}
      >
        <Tabs
          activeKey={attrModalTab}
          onChange={setAttrModalTab}
          items={[
            {
              key: 'auto',
              label: '一键全自动',
              children: (
                 <Form form={autoUpdateForm} onFinish={handleAutoUpdate} layout="vertical" initialValues={{
                     update_profile: true,
                     update_photo: true,
                     update_2fa: false,
                     update_username: false
                 }}>
                  <div style={{ marginBottom: 16, background: '#e6f7ff', padding: '10px', borderRadius: '4px', border: '1px solid #91d5ff' }}>
                     <p>全自动模式将为选中账号随机生成并设置以下属性。</p>
                  </div>
                  <Form.Item name="update_profile" valuePropName="checked">
                    <Checkbox>随机资料 (姓名 + 简介)</Checkbox>
                  </Form.Item>
                  <Form.Item name="update_photo" valuePropName="checked">
                    <Checkbox>随机头像 (AI 人脸)</Checkbox>
                  </Form.Item>
                  <Form.Item name="update_2fa" valuePropName="checked">
                    <Checkbox>设置随机 2FA 密码 (仅适用于无密码的新号)</Checkbox>
                  </Form.Item>
                   <Form.Item name="update_username" valuePropName="checked">
                    <Checkbox>设置随机用户名 (基于英文名)</Checkbox>
                  </Form.Item>
                  
                  <Form.Item
                    noStyle
                    shouldUpdate={(prev, current) => prev.update_2fa !== current.update_2fa}
                  >
                    {({ getFieldValue }) => 
                      getFieldValue('update_2fa') ? (
                        <Form.Item name="password_2fa" label="指定 2FA 密码 (可选)">
                          <Input.Password placeholder="留空则随机生成" />
                        </Form.Item>
                      ) : null
                    }
                  </Form.Item>

                  <Button type="primary" htmlType="submit" loading={attrLoading} block>
                    一键执行
                  </Button>
                </Form>
              ),
            },
            {
              key: 'profile',
              label: '基本资料',
              children: (
                <Form form={profileForm} onFinish={handleUpdateProfile} layout="vertical">
                   <Form.Item name="random" valuePropName="checked">
                    <Checkbox onChange={(e) => setUseRandomProfile(e.target.checked)}>
                      随机生成姓名和简介
                    </Checkbox>
                  </Form.Item>
                  <Form.Item name="first_name" label="名 (First Name)">
                    <Input placeholder="如果不填则不修改" disabled={useRandomProfile} />
                  </Form.Item>
                  <Form.Item name="last_name" label="姓 (Last Name)">
                    <Input placeholder="如果不填则不修改" disabled={useRandomProfile} />
                  </Form.Item>
                  <Form.Item name="about" label="简介 (About)">
                    <Input.TextArea placeholder="如果不填则不修改" rows={3} disabled={useRandomProfile} />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" loading={attrLoading} block>
                    批量更新
                  </Button>
                </Form>
              ),
            },
            {
              key: 'avatar',
              label: '头像',
              children: (
                <div style={{ textAlign: 'center' }}>
                  <Upload
                    beforeUpload={(file) => {
                      setPhotoFile(file);
                      return false;
                    }}
                    fileList={photoFile ? [photoFile] : []}
                    onRemove={() => setPhotoFile(null)}
                    accept="image/*"
                    maxCount={1}
                  >
                    <Button icon={<UploadOutlined />}>选择图片</Button>
                  </Upload>
                  <div style={{ margin: '16px 0' }}>
                    <Button type="primary" onClick={handleUpdatePhoto} loading={attrLoading} disabled={!photoFile} block>
                      批量上传并设置头像 (使用选中图片)
                    </Button>
                    <div style={{ margin: '8px 0', textAlign: 'center', color: '#999' }}>—— 或 ——</div>
                    <Button onClick={handleUpdatePhotoRandom} loading={attrLoading} block>
                      批量随机生成头像 (AI 人脸/随机图)
                    </Button>
                  </div>
                </div>
              ),
            },
            {
              key: '2fa',
              label: '2FA 密码',
              children: (
                <Form form={twoFAForm} onFinish={handleUpdate2FA} layout="vertical">
                  <Form.Item name="password" label="新密码" rules={[{ required: true }]}>
                    <Input.Password />
                  </Form.Item>
                  <Form.Item name="current_password" label="当前密码 (如果已开启)">
                    <Input.Password placeholder="如果是首次设置，留空即可" />
                  </Form.Item>
                  <Form.Item name="hint" label="密码提示">
                    <Input />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" loading={attrLoading} block>
                    批量设置
                  </Button>
                </Form>
              ),
            },
            {
              key: 'username',
              label: '用户名',
              disabled: selectedRowKeys.length > 1,
              children: (
                 <Form form={usernameForm} onFinish={handleUpdateUsername} layout="vertical">
                  <div style={{ marginBottom: 16, color: '#faad14' }}>
                     注意：用户名必须全局唯一，仅支持单个账号修改。
                  </div>
                  <Form.Item name="username" label="用户名 (不带 @)" rules={[{ required: true }]}>
                    <Input prefix="@" />
                  </Form.Item>
                  <Button type="primary" htmlType="submit" loading={attrLoading} block>
                    更新用户名
                  </Button>
                </Form>
              ),
            },
          ]}
        />
      </Modal>

      <Modal
        title="AI 智能配置"
        open={isAIModalVisible}
        onCancel={() => setIsAIModalVisible(false)}
        footer={null}
      >
        <Form form={aiForm} onFinish={handleUpdateAIConfig} layout="vertical">
            <Form.Item name="auto_reply" valuePropName="checked">
                <Checkbox>开启自动回复</Checkbox>
            </Form.Item>
            <Form.Item 
                name="persona_prompt" 
                label="人设提示词 (System Prompt)" 
                help="例如：你是一个热情的客服，名字叫 Alice，负责解答关于加密货币的问题。"
            >
                <Input.TextArea rows={6} placeholder="You are a helpful assistant..." />
            </Form.Item>
            <Button type="primary" htmlType="submit" loading={aiLoading} block>
                保存配置
            </Button>
        </Form>
      </Modal>

      <Modal
        title="设置账号角色"
        open={isRoleModalVisible}
        onOk={handleUpdateRole}
        onCancel={() => setIsRoleModalVisible(false)}
        confirmLoading={roleModalLoading}
      >
        <div style={{ marginBottom: 16 }}>
          <p>已选择 <strong>{selectedRowKeys.length}</strong> 个账号</p>
        </div>
        <Form layout="vertical">
          <Form.Item label="账号分级 (Tier)" required>
            <Select value={selectedTier} onChange={setSelectedTier} style={{ width: '100%' }}>
              <Option value="tier3">Tier 3 (Worker) - 消耗品，用于批量任务</Option>
              <Option value="tier2">Tier 2 (Support) - 辅助号，受限批量操作</Option>
              <Option value="tier1">Tier 1 (Premium) - 精品号，禁止批量操作</Option>
            </Select>
          </Form.Item>
          <Form.Item label="账号角色" required>
            <Select value={selectedRole} onChange={setSelectedRole} style={{ width: '100%' }}>
              <Option value="worker">临时号 - 用于采集、群发等高风险操作</Option>
              <Option value="master">主账号 - 核心资产，用于管理群组</Option>
              <Option value="support">客服号 - 接待客户咨询</Option>
              <Option value="sales">销售号 - 销售人员专用</Option>
            </Select>
          </Form.Item>
          <Form.Item label="标签 (Tags)" help="用逗号分隔多个标签，如：US,Crypto,VIP">
            <Input 
              value={selectedTags} 
              onChange={(e) => setSelectedTags(e.target.value)}
              placeholder="US,Crypto,VIP"
            />
          </Form.Item>
        </Form>
      </Modal>

      {/* Quick Warmup Modal */}
      <Modal
        title={<span><CoffeeOutlined /> 一键养号</span>}
        open={isWarmupModalVisible}
        onCancel={() => setIsWarmupModalVisible(false)}
        onOk={handleQuickWarmup}
        confirmLoading={warmupLoading}
        okText="启动养号"
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <p>已选择 <strong>{selectedRowKeys.length}</strong> 个账号</p>
          <p style={{ color: '#888', fontSize: 12 }}>
            仅活跃状态的账号会参与养号
          </p>
        </div>
        
        {warmupTemplates.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <p style={{ color: '#999' }}>暂无养号模板</p>
            <p style={{ fontSize: 12, color: '#bbb' }}>
              请先到「养号管理」页面创建模板
            </p>
          </div>
        ) : (
          <div>
            <p style={{ marginBottom: 8 }}>选择养号模板：</p>
            <Select
              style={{ width: '100%' }}
              value={selectedWarmupTemplateId}
              onChange={setSelectedWarmupTemplateId}
              placeholder="选择模板"
            >
              {warmupTemplates.map(t => (
                <Option key={t.id} value={t.id}>
                  {t.is_default && '⭐ '}{t.name} - {t.duration_minutes}分钟
                </Option>
              ))}
            </Select>
            {selectedWarmupTemplateId && (
              <div style={{ marginTop: 16, padding: 12, background: '#f5f5f5', borderRadius: 4 }}>
                {(() => {
                  const t = warmupTemplates.find(t => t.id === selectedWarmupTemplateId);
                  if (!t) return null;
                  return (
                    <>
                      <p><strong>目标频道：</strong>{t.target_channels || '无'}</p>
                      <p><strong>操作类型：</strong>{t.action_type === 'mixed' ? '混合模式' : '仅浏览'}</p>
                      <p><strong>持续时长：</strong>{t.duration_minutes} 分钟</p>
                      <p><strong>操作延迟：</strong>{t.min_delay}-{t.max_delay} 秒</p>
                    </>
                  );
                })()}
              </div>
            )}
          </div>
        )}
      </Modal>
    </div>
  );
};

export default AccountList;
