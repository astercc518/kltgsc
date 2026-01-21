import React, { useState, useEffect } from 'react';
import { Card, Form, Input, Button, Select, message, Tabs, Table, Tag, InputNumber, Row, Col } from 'antd';
import type { TabsProps } from 'antd';
import { SendOutlined } from '@ant-design/icons';
import { getAccounts, getTargetUsers, createSendTask, getMarketingTasks, Account, TargetUser } from '../services/api';

const { Option } = Select;
const { TextArea } = Input;

const Marketing: React.FC = () => {
    const [accounts, setAccounts] = useState<Account[]>([]);
    const [targetUsers, setTargetUsers] = useState<TargetUser[]>([]);
    const [tasks, setTasks] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    
    // Selection state
    const [selectedAccounts, setSelectedAccounts] = useState<number[]>([]);
    const [selectedUsers, setSelectedUsers] = useState<number[]>([]);

    useEffect(() => {
        loadData();
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
            message.success('任务创建成功');
            loadData(); // Refresh list
        } catch (e: any) {
            message.error(e.response?.data?.detail || '创建任务失败');
        } finally {
            setLoading(false);
        }
    };

    const taskColumns = [
        { title: 'ID', dataIndex: 'id', width: 60 },
        { title: '任务名称', dataIndex: 'name' },
        { title: '状态', dataIndex: 'status', render: (s: string) => <Tag color={s === 'completed' ? 'green' : s === 'running' ? 'blue' : 'default'}>{s}</Tag> },
        { title: '总数', dataIndex: 'total_count' },
        { title: '成功', dataIndex: 'success_count', render: (c: number) => <span style={{ color: 'green' }}>{c}</span> },
        { title: '失败', dataIndex: 'fail_count', render: (c: number) => <span style={{ color: 'red' }}>{c}</span> },
        { title: '创建时间', dataIndex: 'created_at', render: (t: string) => new Date(t).toLocaleString() },
    ];

    const tabItems: TabsProps['items'] = [
        {
            key: 'create',
            label: '创建群发任务',
            children: (
                <>
                    <Row gutter={24}>
                        <Col span={12}>
                            <Card title="1. 选择发送账号" style={{ marginBottom: 24, height: 300, overflow: 'auto' }}>
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
                                        { title: '状态', dataIndex: 'status', render: (s: string) => <Tag color="green">{s}</Tag> }
                                    ]}
                                />
                            </Card>
                        </Col>
                        <Col span={12}>
                            <Card title="2. 选择目标用户" style={{ marginBottom: 24, height: 300, overflow: 'auto' }}>
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
                                        { title: '来源', dataIndex: 'source_group' }
                                    ]}
                                />
                            </Card>
                        </Col>
                    </Row>
                    
                    <Card title="3. 任务配置">
                        <Form layout="vertical" onFinish={onCreateTask}>
                            <Row gutter={16}>
                                <Col span={8}>
                                    <Form.Item name="name" label="任务名称" rules={[{ required: true }]}>
                                        <Input placeholder="例如：新品推广-第一波" />
                                    </Form.Item>
                                </Col>
                                <Col span={4}>
                                    <Form.Item name="min_delay" label="最小延迟 (秒)" initialValue={10}>
                                        <InputNumber min={1} />
                                    </Form.Item>
                                </Col>
                                <Col span={4}>
                                    <Form.Item name="max_delay" label="最大延迟 (秒)" initialValue={60}>
                                        <InputNumber min={1} />
                                    </Form.Item>
                                </Col>
                            </Row>
                            <Form.Item name="message" label="消息内容" rules={[{ required: true }]}>
                                <TextArea rows={4} placeholder="支持文本消息..." />
                            </Form.Item>
                            <Form.Item>
                                <Button type="primary" htmlType="submit" icon={<SendOutlined />} loading={loading} block>
                                    提交任务 ({selectedAccounts.length} 账号 - {selectedUsers.length} 用户)
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
                <Table
                    dataSource={tasks}
                    columns={taskColumns}
                    rowKey="id"
                />
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
