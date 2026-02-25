import React, { useState, useEffect, useCallback, useRef } from 'react';
import { 
    Table, Button, Modal, Form, Input, Select, InputNumber, Tag, message, Card, 
    Steps, Row, Col, Statistic, Progress, Switch, Slider, Space, Tooltip, 
    Collapse, Badge, Divider, Alert, Tabs, List, Typography, Descriptions
} from 'antd';
import { 
    PlusOutlined, ReloadOutlined, PlayCircleOutlined, PauseCircleOutlined,
    DeleteOutlined, EyeOutlined, UserOutlined, RocketOutlined,
    SettingOutlined, FilterOutlined, TeamOutlined, ClockCircleOutlined,
    CheckCircleOutlined, CloseCircleOutlined, WarningOutlined, StopOutlined
} from '@ant-design/icons';
import api from '../services/api';

const { Option } = Select;
const { Text, Title } = Typography;
const { Panel } = Collapse;

// ==================== 类型定义 ====================

interface InviteTask {
    id: number;
    name: string;
    target_channel: string;
    status: string;
    total_count: number;
    success_count: number;
    fail_count: number;
    privacy_restricted_count: number;
    flood_wait_count: number;
    pending_count: number;
    min_delay: number;
    max_delay: number;
    max_invites_per_account: number;
    stop_on_flood: boolean;
    created_at: string;
    started_at?: string;
    completed_at?: string;
    last_error?: string;
    progress_percent?: number;
    estimated_remaining_minutes?: number;
}

interface InviteLog {
    id: number;
    account_id: number;
    account_username?: string;
    target_username?: string;
    target_telegram_id: number;
    status: string;
    error_code?: string;
    error_message?: string;
    created_at: string;
    duration_ms?: number;
}

interface InviteStats {
    total: number;
    success: number;
    failed: number;
    privacy_restricted: number;
    peer_flood: number;
    user_banned: number;
    other_errors: number;
    success_rate: number;
}

interface Account {
    id: number;
    phone_number: string;
    username?: string;
    combat_role?: string;
    tier?: string;
}

interface TargetUser {
    id: number;
    telegram_id: number;
    username?: string;
    first_name?: string;
    source_group?: string;
    ai_score?: number;
    funnel_stage?: string;
    invite_status?: string;
}

interface FilterPreview {
    count: number;
    targets: TargetUser[];
}

// ==================== 主组件 ====================

const InvitePage: React.FC = () => {
    // === 状态 ===
    const [tasks, setTasks] = useState<InviteTask[]>([]);
    const [loading, setLoading] = useState(false);
    const [isWizardVisible, setIsWizardVisible] = useState(false);
    const [currentStep, setCurrentStep] = useState(0);
    const [accounts, setAccounts] = useState<Account[]>([]);
    const [sourceGroups, setSourceGroups] = useState<string[]>([]);
    const [filterPreview, setFilterPreview] = useState<FilterPreview | null>(null);
    const [previewLoading, setPreviewLoading] = useState(false);
    
    // 任务详情
    const [detailTask, setDetailTask] = useState<InviteTask | null>(null);
    const [taskLogs, setTaskLogs] = useState<InviteLog[]>([]);
    const [taskStats, setTaskStats] = useState<InviteStats | null>(null);
    
    const [form] = Form.useForm();
    const tasksRef = useRef<InviteTask[]>([]); // 用于在 interval 中访问最新值

    // === 数据获取 ===
    const fetchTasks = useCallback(async () => {
        setLoading(true);
        try {
            const res = await api.get('/invites/tasks');
            const newTasks = res.data;
            setTasks(newTasks);
            tasksRef.current = newTasks; // 更新 ref
        } catch (error) {
            message.error('获取任务列表失败');
        } finally {
            setLoading(false);
        }
    }, []);

    const fetchAccounts = async () => {
        try {
            // API limit 最大值为 100，分两次获取
            const [res1, res2] = await Promise.all([
                api.get('/accounts/', { params: { status: 'active', skip: 0, limit: 100 } }),
                api.get('/accounts/', { params: { status: 'active', skip: 100, limit: 100 } })
            ]);
            setAccounts([...res1.data, ...res2.data]);
        } catch (error) {
            console.error('Failed to fetch accounts:', error);
            // 如果失败，尝试只获取前100个
            try {
                const res = await api.get('/accounts/', { params: { status: 'active', skip: 0, limit: 100 } });
                setAccounts(res.data);
            } catch (e) {
                message.error('获取账号列表失败');
            }
        }
    };

    const fetchSourceGroups = async () => {
        try {
            const res = await api.get('/source-groups/');
            const groups = res.data.map((g: any) => g.link || g.name);
            setSourceGroups(groups);
        } catch (error) {
            console.error('Failed to fetch source groups');
        }
    };

    const previewTargets = async () => {
        setPreviewLoading(true);
        try {
            const values = form.getFieldsValue();
            const res = await api.post('/invites/preview-targets', {
                filter_tags: values.filter_tags,
                filter_min_score: values.filter_min_score,
                filter_funnel_stages: values.filter_funnel_stages,
                filter_source_groups: values.filter_source_groups,
                exclude_invited: values.exclude_invited !== false,
                exclude_failed_recently: values.exclude_failed_recently !== false,
                failed_cooldown_hours: values.failed_cooldown_hours || 72,
                max_targets: values.max_targets || 100
            });
            setFilterPreview(res.data);
        } catch (error) {
            message.error('预览筛选结果失败');
        } finally {
            setPreviewLoading(false);
        }
    };

    const fetchTaskDetail = async (taskId: number) => {
        try {
            const [taskRes, logsRes, statsRes] = await Promise.all([
                api.get(`/invites/tasks/${taskId}`),
                api.get(`/invites/tasks/${taskId}/logs`, { params: { limit: 50 } }),
                api.get(`/invites/tasks/${taskId}/stats`)
            ]);
            setDetailTask(taskRes.data);
            setTaskLogs(logsRes.data);
            setTaskStats(statsRes.data);
        } catch (error) {
            message.error('获取任务详情失败');
        }
    };

    useEffect(() => {
        fetchTasks();
    }, [fetchTasks]); // 只在组件挂载时执行一次

    // 自动刷新运行中的任务
    useEffect(() => {
        const interval = setInterval(() => {
            // 使用 ref 访问最新的 tasks，避免依赖
            const hasRunning = tasksRef.current.some(t => t.status === 'running');
            if (hasRunning) {
                fetchTasks();
            }
        }, 5000);
        return () => clearInterval(interval);
    }, [fetchTasks]); // 只在挂载时创建一次 interval

    // === 操作处理 ===
    const handleOpenWizard = () => {
        fetchAccounts();
        fetchSourceGroups();
        form.resetFields();
        setCurrentStep(0);
        setFilterPreview(null);
        setIsWizardVisible(true);
    };

    const handleCreateTask = async () => {
        try {
            // 验证当前步骤的字段
            const fieldsToValidate: string[] = [];
            if (currentStep === 0) {
                fieldsToValidate.push('name', 'target_channel');
            } else if (currentStep === 1) {
                const accountMode = form.getFieldValue('account_mode');
                if (accountMode === 'group') {
                    fieldsToValidate.push('account_group');
                } else {
                    fieldsToValidate.push('account_ids');
                }
            } else if (currentStep === 3) {
                // 最后一步，验证所有字段
                await form.validateFields();
            }
            
            if (fieldsToValidate.length > 0) {
                await form.validateFields(fieldsToValidate);
            }
            
            const values = form.getFieldsValue();
            
            // 检查必填字段
            if (!values.name || !values.target_channel) {
                message.error('请填写任务名称和目标群链接');
                setCurrentStep(0);
                return;
            }
            
            const accountMode = values.account_mode || 'select';
            if (accountMode === 'group' && !values.account_group) {
                message.error('请选择账号组');
                setCurrentStep(1);
                return;
            } else if (accountMode === 'select' && (!values.account_ids || values.account_ids.length === 0)) {
                message.error('请至少选择一个账号');
                setCurrentStep(1);
                return;
            }
            
            const payload: any = {
                name: values.name,
                target_channel: values.target_channel,
                min_delay: values.min_delay || 30,
                max_delay: values.max_delay || 120,
                max_invites_per_account: values.max_invites_per_account || 20,
                max_invites_per_task: values.max_targets || 100,
                stop_on_flood: values.stop_on_flood !== false,
                exclude_invited: values.exclude_invited !== false,
                exclude_failed_recently: values.exclude_failed_recently !== false,
                failed_cooldown_hours: values.failed_cooldown_hours || 72
            };

            // 账号配置
            if (accountMode === 'group') {
                payload.account_group = values.account_group;
            } else {
                payload.account_ids = values.account_ids;
            }

            // 目标用户配置
            const targetMode = values.target_mode || 'filter';
            if (targetMode === 'filter') {
                if (values.filter_tags) payload.filter_tags = values.filter_tags;
                if (values.filter_min_score !== undefined && values.filter_min_score !== null) {
                    payload.filter_min_score = values.filter_min_score;
                }
                if (values.filter_funnel_stages) payload.filter_funnel_stages = values.filter_funnel_stages;
                if (values.filter_source_groups) payload.filter_source_groups = values.filter_source_groups;
                payload.max_targets = values.max_targets || 100;
            } else {
                if (!values.target_user_ids || values.target_user_ids.length === 0) {
                    message.error('请至少选择一个目标用户');
                    setCurrentStep(2);
                    return;
                }
                payload.target_user_ids = values.target_user_ids;
            }

            await api.post('/invites/tasks', payload);
            message.success('拉人任务创建成功');
            setIsWizardVisible(false);
            form.resetFields();
            fetchTasks();
        } catch (error: any) {
            const errorMsg = error.response?.data?.message || error.response?.data?.detail || error.message || '创建任务失败';
            message.error(errorMsg);
            console.error('Create task error:', error);
        }
    };

    const handlePauseResume = async (task: InviteTask) => {
        try {
            const newStatus = task.status === 'running' ? 'paused' : 'running';
            await api.patch(`/invites/tasks/${task.id}`, { status: newStatus });
            message.success(newStatus === 'paused' ? '任务已暂停' : '任务已恢复');
            fetchTasks();
        } catch (error) {
            message.error('操作失败');
        }
    };

    const handleDelete = async (taskId: number) => {
        try {
            await api.delete(`/invites/tasks/${taskId}`);
            message.success('任务已删除');
            fetchTasks();
        } catch (error: any) {
            const errorMsg = error.response?.data?.message || error.response?.data?.detail || error.message || '删除失败';
            message.error(errorMsg);
        }
    };

    // === 渲染 ===
    const statusColors: Record<string, string> = {
        pending: 'default',
        running: 'processing',
        paused: 'warning',
        completed: 'success',
        failed: 'error',
        cancelled: 'default'
    };

    const columns = [
        {
            title: '任务名称',
            dataIndex: 'name',
            key: 'name',
            render: (text: string, record: InviteTask) => (
                <a onClick={() => fetchTaskDetail(record.id)}>{text}</a>
            )
        },
        {
            title: '目标群',
            dataIndex: 'target_channel',
            key: 'target_channel',
            render: (text: string) => (
                <Tooltip title={text}>
                    <Text ellipsis style={{ maxWidth: 150 }}>{text}</Text>
                </Tooltip>
            )
        },
        {
            title: '状态',
            dataIndex: 'status',
            key: 'status',
            render: (status: string) => (
                <Badge status={statusColors[status] as any} text={status.toUpperCase()} />
            )
        },
        {
            title: '进度',
            key: 'progress',
            width: 200,
            render: (_: any, record: InviteTask) => {
                const percent = record.total_count > 0 
                    ? Math.round((record.success_count + record.fail_count) / record.total_count * 100)
                    : 0;
                return (
                    <div>
                        <Progress 
                            percent={percent} 
                            size="small" 
                            status={record.status === 'failed' ? 'exception' : undefined}
                        />
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            <span style={{ color: '#52c41a' }}>{record.success_count}</span>
                            {' / '}
                            <span style={{ color: '#ff4d4f' }}>{record.fail_count}</span>
                            {' / '}
                            {record.total_count}
                        </Text>
                    </div>
                );
            }
        },
        {
            title: '风控',
            key: 'flood',
            render: (_: any, record: InviteTask) => (
                record.flood_wait_count > 0 ? (
                    <Tag color="orange" icon={<WarningOutlined />}>
                        {record.flood_wait_count}
                    </Tag>
                ) : null
            )
        },
        {
            title: '创建时间',
            dataIndex: 'created_at',
            key: 'created_at',
            render: (text: string) => new Date(text).toLocaleString()
        },
        {
            title: '操作',
            key: 'actions',
            render: (_: any, record: InviteTask) => (
                <Space>
                    <Tooltip title="查看详情">
                        <Button 
                            icon={<EyeOutlined />} 
                            size="small"
                            onClick={() => fetchTaskDetail(record.id)}
                        />
                    </Tooltip>
                    {(record.status === 'running' || record.status === 'paused') && (
                        <Tooltip title={record.status === 'running' ? '暂停' : '恢复'}>
                            <Button
                                icon={record.status === 'running' ? <PauseCircleOutlined /> : <PlayCircleOutlined />}
                                size="small"
                                onClick={() => handlePauseResume(record)}
                            />
                        </Tooltip>
                    )}
                    {record.status !== 'running' && (
                        <Tooltip title="删除">
                            <Button
                                icon={<DeleteOutlined />}
                                size="small"
                                danger
                                onClick={() => handleDelete(record.id)}
                            />
                        </Tooltip>
                    )}
                </Space>
            )
        }
    ];

    // 向导步骤
    const wizardSteps = [
        { title: '基本信息', icon: <SettingOutlined /> },
        { title: '选择账号', icon: <UserOutlined /> },
        { title: '筛选用户', icon: <FilterOutlined /> },
        { title: '执行策略', icon: <RocketOutlined /> }
    ];

    return (
        <div style={{ padding: 24 }}>
            {/* 统计卡片 */}
            <Row gutter={16} style={{ marginBottom: 24 }}>
                <Col span={6}>
                    <Card>
                        <Statistic
                            title="运行中任务"
                            value={tasks.filter(t => t.status === 'running').length}
                            prefix={<PlayCircleOutlined />}
                            styles={{ content: { color: '#1890ff' } }}
                        />
                    </Card>
                </Col>
                <Col span={6}>
                    <Card>
                        <Statistic
                            title="今日成功拉入"
                            value={tasks.reduce((sum, t) => sum + t.success_count, 0)}
                            prefix={<CheckCircleOutlined />}
                            styles={{ content: { color: '#52c41a' } }}
                        />
                    </Card>
                </Col>
                <Col span={6}>
                    <Card>
                        <Statistic
                            title="隐私限制"
                            value={tasks.reduce((sum, t) => sum + t.privacy_restricted_count, 0)}
                            prefix={<StopOutlined />}
                            styles={{ content: { color: '#faad14' } }}
                        />
                    </Card>
                </Col>
                <Col span={6}>
                    <Card>
                        <Statistic
                            title="风控触发"
                            value={tasks.reduce((sum, t) => sum + t.flood_wait_count, 0)}
                            prefix={<WarningOutlined />}
                            styles={{ content: { color: '#ff4d4f' } }}
                        />
                    </Card>
                </Col>
            </Row>

            {/* 任务列表 */}
            <Card 
                title={<><TeamOutlined /> 批量拉人任务</>}
                extra={
                    <Space>
                        <Button icon={<ReloadOutlined />} onClick={fetchTasks}>刷新</Button>
                        <Button type="primary" icon={<PlusOutlined />} onClick={handleOpenWizard}>
                            创建任务
                        </Button>
                    </Space>
                }
            >
                <Table 
                    columns={columns} 
                    dataSource={tasks} 
                    rowKey="id" 
                    loading={loading}
                    pagination={{ pageSize: 10 }}
                />
            </Card>

            {/* 向导式创建 Modal */}
            <Modal
                title="创建拉人任务"
                open={isWizardVisible}
                onCancel={() => setIsWizardVisible(false)}
                width={800}
                footer={
                    <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                        <Button 
                            disabled={currentStep === 0}
                            onClick={() => setCurrentStep(currentStep - 1)}
                        >
                            上一步
                        </Button>
                        <Space>
                            <Button onClick={() => setIsWizardVisible(false)}>取消</Button>
                            {currentStep < 3 ? (
                                <Button type="primary" onClick={() => {
                                    if (currentStep === 2) previewTargets();
                                    setCurrentStep(currentStep + 1);
                                }}>
                                    下一步
                                </Button>
                            ) : (
                                <Button type="primary" onClick={handleCreateTask}>
                                    创建任务
                                </Button>
                            )}
                        </Space>
                    </div>
                }
            >
                <Steps current={currentStep} items={wizardSteps} style={{ marginBottom: 24 }} />
                
                <Form form={form} layout="vertical" initialValues={{
                    account_mode: 'select',
                    target_mode: 'filter',
                    min_delay: 30,
                    max_delay: 120,
                    max_invites_per_account: 20,
                    max_targets: 100,
                    stop_on_flood: true,
                    exclude_invited: true,
                    exclude_failed_recently: true,
                    failed_cooldown_hours: 72
                }}>
                    {/* Step 0: 基本信息 */}
                    {currentStep === 0 && (
                        <>
                            <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
                                <Input placeholder="例如：拉人到官方群 - 第一批" />
                            </Form.Item>
                            <Form.Item name="target_channel" label="目标群链接" rules={[{ required: true }]}>
                                <Input placeholder="https://t.me/your_group" />
                            </Form.Item>
                        </>
                    )}

                    {/* Step 1: 选择账号 */}
                    {currentStep === 1 && (
                        <>
                            <Form.Item name="account_mode" label="账号选择方式">
                                <Select>
                                    <Option value="select">手动选择账号</Option>
                                    <Option value="group">使用账号组（自动分配）</Option>
                                </Select>
                            </Form.Item>
                            
                            <Form.Item noStyle shouldUpdate={(prev, curr) => prev.account_mode !== curr.account_mode}>
                                {({ getFieldValue }) => 
                                    getFieldValue('account_mode') === 'group' ? (
                                        <Form.Item name="account_group" label="账号组">
                                            <Select placeholder="选择账号组">
                                                <Option value="cannon">炮灰号 (cannon)</Option>
                                                <Option value="scout">侦察号 (scout)</Option>
                                            </Select>
                                        </Form.Item>
                                    ) : (
                                        <Form.Item name="account_ids" label="选择账号" rules={[{ required: true }]}>
                                            <Select 
                                                mode="multiple" 
                                                placeholder="选择执行拉人的账号"
                                                optionFilterProp="children"
                                                maxTagCount={5}
                                            >
                                                {accounts.map(acc => (
                                                    <Option key={acc.id} value={acc.id}>
                                                        {acc.phone_number} {acc.username ? `@${acc.username}` : ''} 
                                                        ({acc.combat_role || acc.tier || 'unknown'})
                                                    </Option>
                                                ))}
                                            </Select>
                                        </Form.Item>
                                    )
                                }
                            </Form.Item>

                            <Form.Item name="max_invites_per_account" label="每账号每日最大拉人数">
                                <Slider min={1} max={50} marks={{ 5: '安全', 20: '推荐', 50: '激进' }} />
                            </Form.Item>
                        </>
                    )}

                    {/* Step 2: 筛选用户 */}
                    {currentStep === 2 && (
                        <>
                            <Form.Item name="target_mode" label="目标用户选择方式">
                                <Select>
                                    <Option value="filter">智能筛选</Option>
                                    <Option value="manual">手动选择（暂不支持）</Option>
                                </Select>
                            </Form.Item>

                            <Divider>筛选条件</Divider>

                            <Row gutter={16}>
                                <Col span={12}>
                                    <Form.Item name="filter_source_groups" label="来源群">
                                        <Select mode="multiple" placeholder="筛选来源群" allowClear>
                                            {sourceGroups.map(g => (
                                                <Option key={g} value={g}>{g}</Option>
                                            ))}
                                        </Select>
                                    </Form.Item>
                                </Col>
                                <Col span={12}>
                                    <Form.Item name="filter_funnel_stages" label="漏斗阶段">
                                        <Select mode="multiple" placeholder="筛选阶段" allowClear>
                                            <Option value="raw">原始 (raw)</Option>
                                            <Option value="qualified">合格 (qualified)</Option>
                                            <Option value="contacted">已触达 (contacted)</Option>
                                        </Select>
                                    </Form.Item>
                                </Col>
                            </Row>

                            <Row gutter={16}>
                                <Col span={12}>
                                    <Form.Item name="filter_min_score" label="最低AI评分">
                                        <InputNumber min={0} max={100} placeholder="不限" style={{ width: '100%' }} />
                                    </Form.Item>
                                </Col>
                                <Col span={12}>
                                    <Form.Item name="max_targets" label="最大拉人数">
                                        <InputNumber min={1} max={500} style={{ width: '100%' }} />
                                    </Form.Item>
                                </Col>
                            </Row>

                            <Divider>排除规则</Divider>

                            <Row gutter={16}>
                                <Col span={8}>
                                    <Form.Item name="exclude_invited" valuePropName="checked">
                                        <Switch checkedChildren="排除已拉入" unCheckedChildren="不排除" defaultChecked />
                                    </Form.Item>
                                </Col>
                                <Col span={8}>
                                    <Form.Item name="exclude_failed_recently" valuePropName="checked">
                                        <Switch checkedChildren="排除近期失败" unCheckedChildren="不排除" defaultChecked />
                                    </Form.Item>
                                </Col>
                                <Col span={8}>
                                    <Form.Item name="failed_cooldown_hours" label="失败冷却(小时)">
                                        <InputNumber min={1} max={720} />
                                    </Form.Item>
                                </Col>
                            </Row>

                            <Button onClick={previewTargets} loading={previewLoading}>预览筛选结果</Button>
                            
                            {filterPreview && (
                                <Alert 
                                    style={{ marginTop: 16 }}
                                    type="info"
                                    message={`找到 ${filterPreview.count} 个符合条件的用户`}
                                    description={
                                        <List
                                            size="small"
                                            dataSource={filterPreview.targets}
                                            renderItem={(item: TargetUser) => (
                                                <List.Item>
                                                    {item.first_name || item.username || item.telegram_id}
                                                    {item.ai_score && <Tag color="blue">AI:{item.ai_score}</Tag>}
                                                    <Tag>{item.invite_status}</Tag>
                                                </List.Item>
                                            )}
                                        />
                                    }
                                />
                            )}
                        </>
                    )}

                    {/* Step 3: 执行策略 */}
                    {currentStep === 3 && (
                        <>
                            <Alert
                                type="warning"
                                message="安全提示"
                                description="拉人是高风险操作，请确保使用炮灰号，并设置合理的延迟间隔。"
                                style={{ marginBottom: 16 }}
                            />

                            <Form.Item label="操作间隔（秒）">
                                <Row gutter={16}>
                                    <Col span={12}>
                                        <Form.Item name="min_delay" noStyle>
                                            <InputNumber addonBefore="最小" min={5} max={300} style={{ width: '100%' }} />
                                        </Form.Item>
                                    </Col>
                                    <Col span={12}>
                                        <Form.Item name="max_delay" noStyle>
                                            <InputNumber addonBefore="最大" min={10} max={600} style={{ width: '100%' }} />
                                        </Form.Item>
                                    </Col>
                                </Row>
                            </Form.Item>

                            <Form.Item name="stop_on_flood" valuePropName="checked" label="风控策略">
                                <Switch 
                                    checkedChildren="遇到风控立即停止" 
                                    unCheckedChildren="继续执行（危险）" 
                                    defaultChecked 
                                />
                            </Form.Item>

                            {filterPreview && (
                                <Descriptions bordered size="small" style={{ marginTop: 16 }}>
                                    <Descriptions.Item label="目标用户数">{filterPreview.count}</Descriptions.Item>
                                    <Descriptions.Item label="预计耗时">
                                        {Math.round(filterPreview.count * (form.getFieldValue('min_delay') + form.getFieldValue('max_delay')) / 2 / 60)} 分钟
                                    </Descriptions.Item>
                                </Descriptions>
                            )}
                        </>
                    )}
                </Form>
            </Modal>

            {/* 任务详情 Modal */}
            <Modal
                title={`任务详情: ${detailTask?.name}`}
                open={!!detailTask}
                onCancel={() => setDetailTask(null)}
                width={900}
                footer={null}
            >
                {detailTask && (
                    <Tabs items={[
                        {
                            key: 'overview',
                            label: '概览',
                            children: (
                                <>
                                    <Row gutter={16}>
                                        <Col span={6}>
                                            <Statistic title="成功" value={detailTask.success_count} 
                                                styles={{ content: { color: '#52c41a' } }} />
                                        </Col>
                                        <Col span={6}>
                                            <Statistic title="失败" value={detailTask.fail_count} 
                                                styles={{ content: { color: '#ff4d4f' } }} />
                                        </Col>
                                        <Col span={6}>
                                            <Statistic title="隐私限制" value={detailTask.privacy_restricted_count} />
                                        </Col>
                                        <Col span={6}>
                                            <Statistic title="待执行" value={detailTask.pending_count} />
                                        </Col>
                                    </Row>
                                    
                                    <Progress 
                                        percent={detailTask.progress_percent || 0} 
                                        status={detailTask.status === 'running' ? 'active' : undefined}
                                        style={{ marginTop: 24 }}
                                    />
                                    
                                    {taskStats && (
                                        <Descriptions bordered size="small" style={{ marginTop: 24 }}>
                                            <Descriptions.Item label="成功率">
                                                {taskStats.success_rate}%
                                            </Descriptions.Item>
                                            <Descriptions.Item label="隐私限制">
                                                {taskStats.privacy_restricted}
                                            </Descriptions.Item>
                                            <Descriptions.Item label="风控触发">
                                                {taskStats.peer_flood}
                                            </Descriptions.Item>
                                        </Descriptions>
                                    )}
                                </>
                            )
                        },
                        {
                            key: 'logs',
                            label: '执行日志',
                            children: (
                                <Table
                                    dataSource={taskLogs}
                                    rowKey="id"
                                    size="small"
                                    pagination={{ pageSize: 10 }}
                                    columns={[
                                        { title: '时间', dataIndex: 'created_at', key: 'time',
                                            render: (t: string) => new Date(t).toLocaleTimeString() },
                                        { title: '账号', dataIndex: 'account_username', key: 'account' },
                                        { title: '目标', dataIndex: 'target_username', key: 'target',
                                            render: (t: string, r: InviteLog) => t || r.target_telegram_id },
                                        { title: '状态', dataIndex: 'status', key: 'status',
                                            render: (s: string) => (
                                                <Tag color={s === 'success' ? 'green' : 'red'}>
                                                    {s === 'success' ? '成功' : '失败'}
                                                </Tag>
                                            )},
                                        { title: '错误', dataIndex: 'error_code', key: 'error' },
                                        { title: '耗时', dataIndex: 'duration_ms', key: 'duration',
                                            render: (ms: number) => ms ? `${ms}ms` : '-' }
                                    ]}
                                />
                            )
                        }
                    ]} />
                )}
            </Modal>
        </div>
    );
};

export default InvitePage;
