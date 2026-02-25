import React, { useState, useEffect, useRef } from 'react';
import {
  Modal,
  Form,
  Input,
  Button,
  Upload,
  Tabs,
  UploadFile,
  Switch,
  message,
  List,
  Tag,
  Progress,
  Typography,
} from 'antd';
import {
  UploadOutlined,
  CloudDownloadOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  ClockCircleOutlined,
  LoadingOutlined,
} from '@ant-design/icons';
import {
  createAccount,
  uploadAccountSession,
  importMegaAccounts,
  startAutoRegistration,
  refreshProxiesFromIP2World,
  getTasksBatch,
} from '../../services/api';
import { ImportTask, PaginationState } from './types';

const { Text } = Typography;

interface AccountUploaderProps {
  visible: boolean;
  onClose: () => void;
  importTasks: ImportTask[];
  setImportTasks: React.Dispatch<React.SetStateAction<ImportTask[]>>;
  isImportProgressVisible: boolean;
  setIsImportProgressVisible: React.Dispatch<React.SetStateAction<boolean>>;
  fetchAccounts: (page?: number, pageSize?: number) => Promise<void>;
  fetchStats: () => Promise<void>;
  pagination: PaginationState;
}

const AccountUploader: React.FC<AccountUploaderProps> = ({
  visible,
  onClose,
  importTasks,
  setImportTasks,
  isImportProgressVisible,
  setIsImportProgressVisible,
  fetchAccounts,
  fetchStats,
  pagination,
}) => {
  const [activeTab, setActiveTab] = useState('manual');
  const [fileList, setFileList] = useState<UploadFile[]>([]);
  const [visitedTabs, setVisitedTabs] = useState<Set<string>>(new Set(['manual']));
  const [autoRegLoading, setAutoRegLoading] = useState(false);

  const [form] = Form.useForm();
  const [uploadForm] = Form.useForm();
  const [megaForm] = Form.useForm();
  const [autoRegForm] = Form.useForm();

  const pollingInterval = useRef<NodeJS.Timeout | null>(null);
  const importTasksRef = useRef(importTasks);

  useEffect(() => {
    importTasksRef.current = importTasks;
  }, [importTasks]);

  // Polling logic for import tasks - uses batch API to reduce request count
  useEffect(() => {
    const shouldPoll = importTasks.length > 0 && importTasks.some(t => ['PENDING', 'STARTED', 'PROGRESS'].includes(t.status));

    if (shouldPoll && !pollingInterval.current) {
      pollingInterval.current = setInterval(async () => {
        const currentTasks = importTasksRef.current;

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
                progress: statusRes.status === 'PROGRESS' ? statusRes.result : undefined,
                error: statusRes.status === 'FAILURE' ? statusRes.result : undefined,
              };
              hasChanges = true;
            }
          }

          if (hasChanges) {
            setImportTasks(updatedTasks);
            if (updatedTasks.some(t => t.status === 'SUCCESS')) {
              fetchAccounts(pagination.current, pagination.pageSize);
              fetchStats();
            }
          }

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
        const urls = values.urls.split('\n').filter((url: string) => url.trim().length > 0);
        if (urls.length === 0) {
          message.warning('请输入至少一个有效的链接');
          return;
        }
        const target_channels = values.target_channels;
        const auto_check = values.auto_check ?? false;
        const auto_warmup = values.auto_warmup ?? false;
        const res = await importMegaAccounts(urls, target_channels, auto_check, auto_warmup);
        message.success(`已提交 ${urls.length} 个 MEGA 导入任务`);

        const newTasks: ImportTask[] = res.task_ids.map((tid: string, index: number) => ({
          taskId: tid,
          url: res.urls[index],
          status: 'PENDING',
        }));

        setImportTasks(prev => [...newTasks, ...prev]);
        setIsImportProgressVisible(true);
      } else if (activeTab === 'auto_reg') {
        setAutoRegLoading(true);
        try {
          if (values.refresh_proxies) {
            try {
              const proxyRes = await refreshProxiesFromIP2World();
              message.info(`已刷新代理池，新增 ${proxyRes.added_count} 个代理`);
            } catch (e) {
              message.warning('刷新代理失败，尝试使用现有代理');
            }
          }
          const res = await startAutoRegistration({
            count: values.count,
            country: values.country,
          });
          message.success(res.message);
        } finally {
          setAutoRegLoading(false);
        }
      }
      onClose();
      resetForms();
      setFileList([]);
    } catch (error: any) {
      message.error(`操作失败: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleCloseModal = () => {
    onClose();
    resetForms();
    setFileList([]);
  };

  const renderImportTaskItem = (task: ImportTask) => {
    let statusIcon;
    let statusColor;
    let statusText;

    switch (task.status) {
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
      if (status === 'FAILURE') return 100;
      switch (progressStatus) {
        case 'downloading': return 10;
        case 'extracting': return 40;
        case 'converting': return 80;
        case 'saving': return 90;
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
    <>
      <Modal
        title="添加账号"
        open={visible}
        onCancel={handleCloseModal}
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
                  <Form.Item name="api_id" label="API ID（可选）">
                    <Input type="number" placeholder="从 my.telegram.org 获取" />
                  </Form.Item>
                  <Form.Item name="api_hash" label="API Hash（可选）">
                    <Input placeholder="从 my.telegram.org 获取" />
                  </Form.Item>
                  <Form.Item name="session_string" label="Session String（可选）">
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
                  <Form.Item name="phone_number" label="手机号（可选，将从文件名自动解析）">
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

      {/* Import Progress Modal */}
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
    </>
  );
};

export default AccountUploader;
