import React, { useState, useRef, useCallback } from 'react';
import {
  Modal,
  Form,
  Input,
  Button,
  Select,
  Checkbox,
  Tabs,
  Upload,
  UploadFile,
  message,
  Progress,
  Radio,
  Alert,
  Typography,
} from 'antd';
import { UploadOutlined, PictureOutlined } from '@ant-design/icons';
import {
  sendTestMessageBatch,
  updateAccountProfile,
  updateAccountUsername,
  updateAccount2FA,
  updateAccountPhoto,
  updateAccountAIConfig,
  updateAccountsRoleBatch,
  batchUpdatePhotoRandom,
  batchAutoUpdate,
  getBatchTaskStatus,
  Account,
} from '../../services/api';
import { PaginationState } from './types';

const { Text } = Typography;

const { Option } = Select;

interface AccountActionsProps {
  accounts: Account[];
  selectedRowKeys: React.Key[];
  setSelectedRowKeys: React.Dispatch<React.SetStateAction<React.Key[]>>;
  fetchAccounts: (page?: number, pageSize?: number) => Promise<void>;
  pagination: PaginationState;

  // Message modal
  isMessageModalVisible: boolean;
  setIsMessageModalVisible: React.Dispatch<React.SetStateAction<boolean>>;

  // Attribute modal
  isAttrModalVisible: boolean;
  setIsAttrModalVisible: React.Dispatch<React.SetStateAction<boolean>>;

  // AI modal
  isAIModalVisible: boolean;
  setIsAIModalVisible: React.Dispatch<React.SetStateAction<boolean>>;

  // Role modal
  isRoleModalVisible: boolean;
  setIsRoleModalVisible: React.Dispatch<React.SetStateAction<boolean>>;
}

const AccountActions: React.FC<AccountActionsProps> = ({
  accounts,
  selectedRowKeys,
  setSelectedRowKeys,
  fetchAccounts,
  pagination,
  isMessageModalVisible,
  setIsMessageModalVisible,
  isAttrModalVisible,
  setIsAttrModalVisible,
  isAIModalVisible,
  setIsAIModalVisible,
  isRoleModalVisible,
  setIsRoleModalVisible,
}) => {
  // Message state
  const [messageTarget, setMessageTarget] = useState('');
  const [messageContent, setMessageContent] = useState('Hello from [Phone Number]');
  const [sendingMessage, setSendingMessage] = useState(false);

  // Attribute modal state
  const [attrModalTab, setAttrModalTab] = useState('profile');
  const [attrLoading, setAttrLoading] = useState(false);
  const [profileForm] = Form.useForm();
  const [useRandomProfile, setUseRandomProfile] = useState(false);
  const [usernameForm] = Form.useForm();
  const [twoFAForm] = Form.useForm();
  const [autoUpdateForm] = Form.useForm();
  const [photoFile, setPhotoFile] = useState<UploadFile | null>(null);

  // Avatar batch state
  const [avatarStyle, setAvatarStyle] = useState<string>('face');
  const [batchTaskId, setBatchTaskId] = useState<string | null>(null);
  const [batchProgress, setBatchProgress] = useState<{ current: number; total: number; success: number; fail: number } | null>(null);
  const pollRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // AI state
  const [aiForm] = Form.useForm();
  const [aiLoading, setAiLoading] = useState(false);

  // Role state
  const [selectedRole, setSelectedRole] = useState<string>('worker');
  const [selectedTier, setSelectedTier] = useState<string>('tier3');
  const [selectedTags, setSelectedTags] = useState<string>('');
  const [roleModalLoading, setRoleModalLoading] = useState(false);

  // --- Message Handlers ---
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
          .filter((r: any) => r.status === 'error')
          .map((r: any) => `ID ${r.account_id}: ${r.message}`)
          .join('; ');

        if (result.success_count === 0) {
          message.error(`发送失败: ${errors}`);
        } else {
          message.warning(`部分失败: ${errors}`);
        }
        console.error('Failures:', result.results.filter((r: any) => r.status === 'error'));
      }

      setIsMessageModalVisible(false);
      setSelectedRowKeys([]);
    } catch (error: any) {
      message.error(`发送失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setSendingMessage(false);
    }
  };

  // --- Profile Handlers ---
  const handleUpdateProfile = async (values: any) => {
    setAttrLoading(true);
    try {
      const accountIds = selectedRowKeys as number[];
      let successCount = 0;
      let failCount = 0;

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

  // 轮询任务进度
  const startPolling = useCallback((taskId: string) => {
    if (pollRef.current) clearInterval(pollRef.current);
    pollRef.current = setInterval(async () => {
      try {
        const res = await getBatchTaskStatus(taskId);
        if (res.status === 'running' && res.progress) {
          setBatchProgress(res.progress);
        } else if (res.status === 'completed') {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setBatchTaskId(null);
          const r = res.result;
          setBatchProgress(null);
          setAttrLoading(false);
          if (r.fail_count > 0) {
            message.warning(`完成: 成功 ${r.success_count}, 失败 ${r.fail_count}`);
          } else {
            message.success(`成功更新 ${r.success_count} 个账号`);
          }
          fetchAccounts(pagination.current, pagination.pageSize);
        } else if (res.status === 'failed') {
          if (pollRef.current) clearInterval(pollRef.current);
          pollRef.current = null;
          setBatchTaskId(null);
          setBatchProgress(null);
          setAttrLoading(false);
          message.error(`任务失败: ${res.error || '未知错误'}`);
        }
      } catch {
        // ignore poll errors
      }
    }, 2000);
  }, [fetchAccounts, pagination]);

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
        message.success(`已提交 ${successCount} 个头像更新任务`);
      }
      setPhotoFile(null);
    } finally {
      setAttrLoading(false);
    }
  };

  const handleUpdatePhotoRandom = async () => {
    setAttrLoading(true);
    setBatchProgress(null);
    try {
      const accountIds = selectedRowKeys as number[];
      const res = await batchUpdatePhotoRandom(accountIds, avatarStyle);
      if (res.task_id) {
        setBatchTaskId(res.task_id);
        message.info(`批量头像任务已提交，共 ${accountIds.length} 个账号`);
        startPolling(res.task_id);
      }
    } catch (error: any) {
      message.error(`提交失败: ${error.response?.data?.detail || error.message}`);
      setAttrLoading(false);
    }
  };

  const handleAutoUpdate = async (values: any) => {
    setAttrLoading(true);
    setBatchProgress(null);
    try {
      const accountIds = selectedRowKeys as number[];
      const res = await batchAutoUpdate(accountIds, { ...values, avatar_style: avatarStyle });
      if (res.task_id) {
        setBatchTaskId(res.task_id);
        message.info(`批量更新任务已提交，共 ${accountIds.length} 个账号`);
        startPolling(res.task_id);
      }
    } catch (error: any) {
      message.error(`提交失败: ${error.response?.data?.detail || error.message}`);
      setAttrLoading(false);
    }
  };

  // --- AI Handler ---
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

  // --- Role Handler ---
  const handleUpdateRole = async () => {
    setRoleModalLoading(true);
    try {
      const accountIds = selectedRowKeys as number[];
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

  // Populate AI form when modal opens
  React.useEffect(() => {
    if (isAIModalVisible && selectedRowKeys.length === 1) {
      const account = accounts.find(a => a.id === selectedRowKeys[0]);
      if (account) {
        aiForm.setFieldsValue({
          auto_reply: account.auto_reply,
          persona_prompt: account.persona_prompt,
        });
      }
    }
  }, [isAIModalVisible]);

  return (
    <>
      {/* Message Modal */}
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

      {/* Attribute Modal */}
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
                  update_username: false,
                }}>
                  <Alert
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                    message={`全自动模式将为选中的 ${selectedRowKeys.length} 个账号批量执行以下操作`}
                  />

                  {/* 进度条 */}
                  {batchProgress && (
                    <div style={{ marginBottom: 16 }}>
                      <Progress
                        percent={Math.round((batchProgress.current / batchProgress.total) * 100)}
                        format={() => `${batchProgress.current}/${batchProgress.total}`}
                        status="active"
                      />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        成功: {batchProgress.success} | 失败: {batchProgress.fail}
                      </Text>
                    </div>
                  )}

                  <Form.Item name="update_profile" valuePropName="checked">
                    <Checkbox>随机资料 (姓名 + 简介)</Checkbox>
                  </Form.Item>
                  <Form.Item name="update_photo" valuePropName="checked">
                    <Checkbox>随机头像</Checkbox>
                  </Form.Item>

                  <Form.Item
                    noStyle
                    shouldUpdate={(prev, current) => prev.update_photo !== current.update_photo}
                  >
                    {({ getFieldValue }) =>
                      getFieldValue('update_photo') ? (
                        <Form.Item label="头像风格" style={{ marginLeft: 24 }}>
                          <Radio.Group value={avatarStyle} onChange={(e) => setAvatarStyle(e.target.value)} size="small">
                            <Radio.Button value="face">AI 人脸</Radio.Button>
                            <Radio.Button value="portrait">肖像</Radio.Button>
                            <Radio.Button value="illustration">插画</Radio.Button>
                            <Radio.Button value="abstract">抽象</Radio.Button>
                          </Radio.Group>
                        </Form.Item>
                      ) : null
                    }
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

                  <Button type="primary" htmlType="submit" loading={attrLoading} disabled={!!batchTaskId} block>
                    一键执行 ({selectedRowKeys.length} 个账号)
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
                <div>
                  {/* 进度条 */}
                  {batchProgress && (
                    <div style={{ marginBottom: 16 }}>
                      <Progress
                        percent={Math.round((batchProgress.current / batchProgress.total) * 100)}
                        format={() => `${batchProgress.current}/${batchProgress.total}`}
                        status="active"
                      />
                      <Text type="secondary" style={{ fontSize: 12 }}>
                        成功: {batchProgress.success} | 失败: {batchProgress.fail}
                      </Text>
                    </div>
                  )}

                  {/* 方式一：上传自定义图片 */}
                  <div style={{ marginBottom: 16, padding: '12px', background: '#fafafa', borderRadius: 6 }}>
                    <Text strong style={{ display: 'block', marginBottom: 8 }}>方式一：上传自定义图片</Text>
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
                    <Button
                      type="primary"
                      onClick={handleUpdatePhoto}
                      loading={attrLoading && !batchTaskId}
                      disabled={!photoFile || !!batchTaskId}
                      block
                      style={{ marginTop: 8 }}
                    >
                      批量上传并设置 (所有选中账号使用同一图片)
                    </Button>
                  </div>

                  {/* 方式二：随机生成 */}
                  <div style={{ padding: '12px', background: '#fafafa', borderRadius: 6 }}>
                    <Text strong style={{ display: 'block', marginBottom: 8 }}>方式二：批量随机生成 (每个账号不同)</Text>
                    <div style={{ marginBottom: 12 }}>
                      <Text type="secondary" style={{ display: 'block', marginBottom: 4, fontSize: 12 }}>选择头像风格:</Text>
                      <Radio.Group value={avatarStyle} onChange={(e) => setAvatarStyle(e.target.value)}>
                        <Radio.Button value="face">
                          <PictureOutlined /> AI 人脸
                        </Radio.Button>
                        <Radio.Button value="portrait">肖像照片</Radio.Button>
                        <Radio.Button value="illustration">插画风格</Radio.Button>
                        <Radio.Button value="abstract">抽象图案</Radio.Button>
                      </Radio.Group>
                    </div>
                    <Button
                      type="primary"
                      onClick={handleUpdatePhotoRandom}
                      loading={attrLoading && !!batchTaskId}
                      disabled={!!batchTaskId && !attrLoading}
                      block
                      icon={<PictureOutlined />}
                    >
                      批量随机生成头像 ({selectedRowKeys.length} 个账号)
                    </Button>
                    {avatarStyle === 'face' && (
                      <Alert
                        type="info"
                        showIcon
                        style={{ marginTop: 8 }}
                        message="AI 人脸由 thispersondoesnotexist.com 生成，每张独一无二"
                      />
                    )}
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

      {/* AI Modal */}
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

      {/* Role Modal */}
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
    </>
  );
};

export default AccountActions;
