import React, { useState, useEffect } from 'react';
import { Card, Form, Input, Button, Select, message, Tabs, Table, Tag, InputNumber, Row, Col, Statistic, Modal, Slider, Divider, Space, Tooltip, Progress } from 'antd';
import type { TabsProps } from 'antd';
import { SendOutlined, SettingOutlined, InfoCircleOutlined, ThunderboltOutlined, PauseCircleOutlined, StopOutlined } from '@ant-design/icons';
import api, { getAccounts, getTargetUsers, createSendTask, getMarketingTasks, Account, TargetUser } from '../services/api';

const { TextArea } = Input;

interface SafeSendConfig {
    max_daily_sends_new: number;
    max_daily_sends_normal: number;
    max_daily_sends_trusted: number;
    min_delay_seconds: number;
    max_delay_seconds: number;
    sends_before_rest: number;
    rest_duration_min: number;
    rest_duration_max: number;
    max_flood_wait_daily: number;
    cooldown_after_flood: number;
}

interface SendPlan {
    total_targets: number;
    total_capacity_today: number;
    can_complete_today: boolean;
    batches_needed: number;
    sends_today: number;
    sends_remaining: number;
    estimated_hours_today: number;
    estimated_days_total: number;
    accounts_available: number;
    avg_per_account: number;
    accounts_summary: any[];
}

const Marketing: React.FC = () => {
    const [accounts, setAccounts] = useState<Account[]>([]);
    const [targetUsers, setTargetUsers] = useState<TargetUser[]>([]);
    const [tasks, setTasks] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    
    // Selection state
    const [selectedAccounts, setSelectedAccounts] = useState<number[]>([]);
    const [selectedUsers, setSelectedUsers] = useState<number[]>([]);
    
    // Config modal
    const [configModalVisible, setConfigModalVisible] = useState(false);
    const [config, setConfig] = useState<SafeSendConfig | null>(null);
    const [configLoading, setConfigLoading] = useState(false);
    
    // Send plan
    const [sendPlan, setSendPlan] = useState<SendPlan | null>(null);
    const [planLoading, setPlanLoading] = useState(false);

    useEffect(() => {
        loadData();
        loadConfig();
    }, []);

    const loadData = async () => {
        try {
            const [accData, userData, taskData] = await Promise.all([
                getAccounts(0, 100, 'active'),
                getTargetUsers(0, 500),
                getMarketingTasks()
            ]);
            setAccounts(accData);
            setTargetUsers(userData);
            setTasks(taskData);
        } catch (e) {
            message.error('加载数据失败');
        }
    };

    const loadConfig = async () => {
        try {
            const res = await api.get('/marketing/config');
            setConfig(res.data);
        } catch (e) {
            console.error('Failed to load config');
        }
    };

    const saveConfig = async () => {
        if (!config) return;
        setConfigLoading(true);
        try {
            await api.post('/marketing/config', config);
            message.success('配置已保存');
            setConfigModalVisible(false);
        } catch (e) {
            message.error('保存失败');
        } finally {
            setConfigLoading(false);
        }
    };

    const loadSendPlan = async () => {
        if (selectedAccounts.length === 0 || selectedUsers.length === 0) {
            message.warning('请先选择账号和目标用户');
            return;
        }
        setPlanLoading(true);
        try {
            const res = await api.post('/marketing/plan', {
                account_ids: selectedAccounts,
                target_user_ids: selectedUsers
            });
            setSendPlan(res.data);
        } catch (e: any) {
            message.error(e.response?.data?.detail || '获取计划失败');
        } finally {
            setPlanLoading(false);
        }
    };

    const onCreateTask = async (values: any) => {
        if (selectedAccounts.length === 0 || selectedUsers.length === 0) {
            message.warning('请先选择发送账号和目标用户');
            return;
        }
        
        setLoading(true);
        try {
            const payload = {
                name: values.name,
                message_content: values.message,
                account_ids: selectedAccounts,
                target_user_ids: selectedUsers,
                min_delay: values.min_delay,
                max_delay: values.max_delay
            };
            await createSendTask(payload);
            message.success('任务创建成功，安全发送已启动');
            loadData();
            setSendPlan(null);
        } catch (e: any) {
            message.error(e.response?.data?.detail || '创建任务失败');
        } finally {
            setLoading(false);
        }
    };

    const pauseTask = async (taskId: number) => {
        try {
            await api.post(`/marketing/tasks/${taskId}/pause`);
            message.success('任务已暂停');
            loadData();
        } catch (e: any) {
            message.error(e.response?.data?.detail || '暂停失败');
        }
    };

    const cancelTask = async (taskId: number) => {
        try {
            await api.post(`/marketing/tasks/${taskId}/cancel`);
            message.success('任务已取消');
            loadData();
        } catch (e: any) {
            message.error(e.response?.data?.detail || '取消失败');
        }
    };

    const taskColumns = [
        { title: 'ID', dataIndex: 'id', width: 60 },
        { title: '任务名称', dataIndex: 'name' },
        { 
            title: '状态', 
            dataIndex: 'status', 
            render: (s: string) => {
                const colors: Record<string, string> = {
                    completed: 'green',
                    running: 'blue',
                    paused: 'orange',
                    cancelled: 'red',
                    failed: 'red',
                    pending: 'default'
                };
                return <Tag color={colors[s] || 'default'}>{s}</Tag>;
            }
        },
        { 
            title: '进度', 
            key: 'progress',
            width: 150,
            render: (r: any) => {
                const percent = r.total_count > 0 ? Math.round((r.success_count + r.fail_count) / r.total_count * 100) : 0;
                return <Progress percent={percent} size="small" />;
            }
        },
        { title: '成功', dataIndex: 'success_count', render: (c: number) => <span style={{ color: 'green' }}>{c}</span> },
        { title: '失败', dataIndex: 'fail_count', render: (c: number) => <span style={{ color: 'red' }}>{c}</span> },
        { title: '创建时间', dataIndex: 'created_at', render: (t: string) => new Date(t).toLocaleString() },
        {
            title: '操作',
            key: 'action',
            render: (r: any) => (
                <Space>
                    {r.status === 'running' && (
                        <Button size="small" icon={<PauseCircleOutlined />} onClick={() => pauseTask(r.id)}>暂停</Button>
                    )}
                    {['running', 'paused', 'pending'].includes(r.status) && (
                        <Button size="small" danger icon={<StopOutlined />} onClick={() => cancelTask(r.id)}>取消</Button>
                    )}
                </Space>
            )
        }
    ];

    const tabItems: TabsProps['items'] = [
        {
            key: 'create',
            label: '创建群发任务',
            children: (
                <>
                    <Row gutter={24}>
                        <Col span={12}>
                            <Card 
                                title="1. 选择发送账号" 
                                style={{ marginBottom: 24, height: 350, overflow: 'auto' }}
                                extra={<Tag color="blue">已选 {selectedAccounts.length}</Tag>}
                            >
                                <Table
                                    dataSource={accounts}
                                    rowKey="id"
                                    size="small"
                                    pagination={false}
                                    rowSelection={{
                                        type: 'checkbox',
                                        onChange: (keys: any) => setSelectedAccounts(keys)
                                    }}
                                    columns={[
                                        { title: '手机号', dataIndex: 'phone_number' },
                                        { title: 'Tier', dataIndex: 'tier', render: (t: string) => <Tag>{t || 'tier3'}</Tag> },
                                        { title: '状态', dataIndex: 'status', render: (s: string) => <Tag color="green">{s}</Tag> }
                                    ]}
                                />
                            </Card>
                        </Col>
                        <Col span={12}>
                            <Card 
                                title="2. 选择目标用户" 
                                style={{ marginBottom: 24, height: 350, overflow: 'auto' }}
                                extra={<Tag color="blue">已选 {selectedUsers.length}</Tag>}
                            >
                                <Table
                                    dataSource={targetUsers}
                                    rowKey="id"
                                    size="small"
                                    pagination={{ pageSize: 50 }}
                                    rowSelection={{
                                        type: 'checkbox',
                                        onChange: (keys: any) => setSelectedUsers(keys)
                                    }}
                                    columns={[
                                        { title: '用户名/ID', render: (r: any) => r.username || r.telegram_id },
                                        { title: '来源', dataIndex: 'source_group', ellipsis: true }
                                    ]}
                                />
                            </Card>
                        </Col>
                    </Row>
                    
                    {/* 发送计划预览 */}
                    <Card 
                        title={
                            <Space>
                                <ThunderboltOutlined />
                                发送计划预览
                                <Tooltip title="根据安全配置计算的发送计划，确保账号不被封禁">
                                    <InfoCircleOutlined style={{ color: '#999' }} />
                                </Tooltip>
                            </Space>
                        }
                        style={{ marginBottom: 24 }}
                        extra={
                            <Button onClick={loadSendPlan} loading={planLoading}>
                                计算发送计划
                            </Button>
                        }
                    >
                        {sendPlan ? (
                            <Row gutter={16}>
                                <Col span={4}>
                                    <Statistic title="目标用户" value={sendPlan.total_targets} />
                                </Col>
                                <Col span={4}>
                                    <Statistic title="今日可发" value={sendPlan.sends_today} styles={{ content: { color: '#3f8600' } }} />
                                </Col>
                                <Col span={4}>
                                    <Statistic title="剩余待发" value={sendPlan.sends_remaining} styles={{ content: { color: sendPlan.sends_remaining > 0 ? '#cf1322' : '#3f8600' } }} />
                                </Col>
                                <Col span={4}>
                                    <Statistic title="可用账号" value={sendPlan.accounts_available} suffix={`/ ${selectedAccounts.length}`} />
                                </Col>
                                <Col span={4}>
                                    <Statistic title="预计耗时" value={sendPlan.estimated_hours_today} suffix="小时" />
                                </Col>
                                <Col span={4}>
                                    <Statistic 
                                        title="完成天数" 
                                        value={sendPlan.batches_needed} 
                                        suffix="天"
                                        styles={{ content: { color: sendPlan.can_complete_today ? '#3f8600' : '#faad14' } }}
                                    />
                                </Col>
                            </Row>
                        ) : (
                            <div style={{ textAlign: 'center', color: '#999', padding: 20 }}>
                                选择账号和目标用户后，点击"计算发送计划"查看安全发送方案
                            </div>
                        )}
                    </Card>
                    
                    <Card title="3. 任务配置">
                        <Form layout="vertical" onFinish={onCreateTask} initialValues={{ min_delay: 60, max_delay: 180 }}>
                            <Row gutter={16}>
                                <Col span={8}>
                                    <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
                                        <Input placeholder="例如：新品推广-第一波" />
                                    </Form.Item>
                                </Col>
                                <Col span={4}>
                                    <Form.Item name="min_delay" label="最小延迟 (秒)">
                                        <InputNumber min={10} style={{ width: '100%' }} />
                                    </Form.Item>
                                </Col>
                                <Col span={4}>
                                    <Form.Item name="max_delay" label="最大延迟 (秒)">
                                        <InputNumber min={10} style={{ width: '100%' }} />
                                    </Form.Item>
                                </Col>
                            </Row>
                            <Form.Item name="message" label="消息内容" rules={[{ required: true }]}>
                                <TextArea rows={4} placeholder="支持文本消息..." />
                            </Form.Item>
                            <Form.Item>
                                <Button type="primary" htmlType="submit" icon={<SendOutlined />} loading={loading} block size="large">
                                    启动安全发送 ({selectedAccounts.length} 账号 → {selectedUsers.length} 用户)
                                </Button>
                            </Form.Item>
                        </Form>
                    </Card>
                </>
            ),
        },
        {
            key: 'list',
            label: '任务列表',
            children: (
                <Card extra={<Button onClick={loadData}>刷新</Button>}>
                    <Table
                        dataSource={tasks}
                        columns={taskColumns}
                        rowKey="id"
                    />
                </Card>
            ),
        },
        {
            key: 'config',
            label: (
                <span>
                    <SettingOutlined /> 安全配置
                </span>
            ),
            children: config ? (
                <Card title="安全发送配置" extra={<Button type="primary" onClick={saveConfig} loading={configLoading}>保存配置</Button>}>
                    <Row gutter={[24, 24]}>
                        <Col span={24}>
                            <Divider orientation="left">每日发送限额</Divider>
                        </Col>
                        <Col span={8}>
                            <Card size="small" title="新账号 (<7天)">
                                <Slider
                                    min={0}
                                    max={50}
                                    value={config.max_daily_sends_new}
                                    onChange={(v) => setConfig({ ...config, max_daily_sends_new: v })}
                                    marks={{ 0: '0', 15: '15', 30: '30', 50: '50' }}
                                />
                                <div style={{ textAlign: 'center', fontSize: 24, color: config.max_daily_sends_new === 0 ? '#999' : '#1890ff' }}>
                                    {config.max_daily_sends_new === 0 ? '禁用' : `${config.max_daily_sends_new} 条/天`}
                                </div>
                            </Card>
                        </Col>
                        <Col span={8}>
                            <Card size="small" title="普通账号 (7-30天)">
                                <Slider
                                    min={0}
                                    max={100}
                                    value={config.max_daily_sends_normal}
                                    onChange={(v) => setConfig({ ...config, max_daily_sends_normal: v })}
                                    marks={{ 0: '0', 30: '30', 60: '60', 100: '100' }}
                                />
                                <div style={{ textAlign: 'center', fontSize: 24, color: config.max_daily_sends_normal === 0 ? '#999' : '#1890ff' }}>
                                    {config.max_daily_sends_normal === 0 ? '禁用' : `${config.max_daily_sends_normal} 条/天`}
                                </div>
                            </Card>
                        </Col>
                        <Col span={8}>
                            <Card size="small" title="老账号 (>30天)">
                                <Slider
                                    min={0}
                                    max={150}
                                    value={config.max_daily_sends_trusted}
                                    onChange={(v) => setConfig({ ...config, max_daily_sends_trusted: v })}
                                    marks={{ 0: '0', 50: '50', 100: '100', 150: '150' }}
                                />
                                <div style={{ textAlign: 'center', fontSize: 24, color: config.max_daily_sends_trusted === 0 ? '#999' : '#1890ff' }}>
                                    {config.max_daily_sends_trusted === 0 ? '禁用' : `${config.max_daily_sends_trusted} 条/天`}
                                </div>
                            </Card>
                        </Col>

                        <Col span={24}>
                            <Divider orientation="left">发送间隔</Divider>
                        </Col>
                        <Col span={12}>
                            <Card size="small" title="最小间隔 (秒)">
                                <Slider
                                    min={10}
                                    max={300}
                                    value={config.min_delay_seconds}
                                    onChange={(v) => setConfig({ ...config, min_delay_seconds: v })}
                                    marks={{ 10: '10s', 60: '1分', 120: '2分', 300: '5分' }}
                                />
                                <div style={{ textAlign: 'center', fontSize: 20 }}>
                                    {config.min_delay_seconds} 秒
                                </div>
                            </Card>
                        </Col>
                        <Col span={12}>
                            <Card size="small" title="最大间隔 (秒)">
                                <Slider
                                    min={30}
                                    max={600}
                                    value={config.max_delay_seconds}
                                    onChange={(v) => setConfig({ ...config, max_delay_seconds: v })}
                                    marks={{ 30: '30s', 180: '3分', 300: '5分', 600: '10分' }}
                                />
                                <div style={{ textAlign: 'center', fontSize: 20 }}>
                                    {config.max_delay_seconds} 秒
                                </div>
                            </Card>
                        </Col>

                        <Col span={24}>
                            <Divider orientation="left">休息机制</Divider>
                        </Col>
                        <Col span={8}>
                            <Card size="small" title="连续发送后休息">
                                <InputNumber
                                    min={1}
                                    max={20}
                                    value={config.sends_before_rest}
                                    onChange={(v) => setConfig({ ...config, sends_before_rest: v || 5 })}
                                    addonAfter="条后休息"
                                    style={{ width: '100%' }}
                                />
                            </Card>
                        </Col>
                        <Col span={8}>
                            <Card size="small" title="最短休息时间 (秒)">
                                <InputNumber
                                    min={60}
                                    max={1800}
                                    step={60}
                                    value={config.rest_duration_min}
                                    onChange={(v) => setConfig({ ...config, rest_duration_min: v || 300 })}
                                    addonAfter="秒"
                                    style={{ width: '100%' }}
                                />
                                <div style={{ color: '#999', marginTop: 4 }}>
                                    ≈ {Math.round(config.rest_duration_min / 60)} 分钟
                                </div>
                            </Card>
                        </Col>
                        <Col span={8}>
                            <Card size="small" title="最长休息时间 (秒)">
                                <InputNumber
                                    min={120}
                                    max={3600}
                                    step={60}
                                    value={config.rest_duration_max}
                                    onChange={(v) => setConfig({ ...config, rest_duration_max: v || 900 })}
                                    addonAfter="秒"
                                    style={{ width: '100%' }}
                                />
                                <div style={{ color: '#999', marginTop: 4 }}>
                                    ≈ {Math.round(config.rest_duration_max / 60)} 分钟
                                </div>
                            </Card>
                        </Col>

                        <Col span={24}>
                            <Divider orientation="left">风险控制</Divider>
                        </Col>
                        <Col span={12}>
                            <Card size="small" title="每日 FloodWait 上限">
                                <InputNumber
                                    min={1}
                                    max={10}
                                    value={config.max_flood_wait_daily}
                                    onChange={(v) => setConfig({ ...config, max_flood_wait_daily: v || 2 })}
                                    addonAfter="次后停用"
                                    style={{ width: '100%' }}
                                />
                                <div style={{ color: '#999', marginTop: 4 }}>
                                    超过此次数后，账号当日停止发送
                                </div>
                            </Card>
                        </Col>
                        <Col span={12}>
                            <Card size="small" title="FloodWait 后冷却时间">
                                <InputNumber
                                    min={600}
                                    max={7200}
                                    step={300}
                                    value={config.cooldown_after_flood}
                                    onChange={(v) => setConfig({ ...config, cooldown_after_flood: v || 3600 })}
                                    addonAfter="秒"
                                    style={{ width: '100%' }}
                                />
                                <div style={{ color: '#999', marginTop: 4 }}>
                                    ≈ {Math.round(config.cooldown_after_flood / 60)} 分钟
                                </div>
                            </Card>
                        </Col>
                    </Row>
                </Card>
            ) : (
                <Card loading={true} />
            ),
        },
    ];

    return (
        <div style={{ padding: 24 }}>
            <Tabs defaultActiveKey="create" items={tabItems} />
        </div>
    );
};

export default Marketing;
