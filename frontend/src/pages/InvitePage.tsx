import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, Select, InputNumber, Tag, message, Card } from 'antd';
import { PlusOutlined, ReloadOutlined } from '@ant-design/icons';
import { 
    InviteTask, getInviteTasks, createInviteTask, 
    getAccounts, Account, 
    getTargetUsers, TargetUser 
} from '../services/api';

const { Option } = Select;

const InvitePage: React.FC = () => {
    const [tasks, setTasks] = useState<InviteTask[]>([]);
    const [loading, setLoading] = useState(false);
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [accounts, setAccounts] = useState<Account[]>([]);
    const [targetUsers, setTargetUsers] = useState<TargetUser[]>([]);
    const [form] = Form.useForm();

    const fetchTasks = async () => {
        setLoading(true);
        try {
            const data = await getInviteTasks();
            setTasks(data);
        } catch (error) {
            message.error('Failed to fetch invite tasks');
        } finally {
            setLoading(false);
        }
    };

    const fetchResources = async () => {
        try {
            const accs = await getAccounts(0, 100, 'active');
            setAccounts(accs);
            // Fetch users (this might be large, in real app use async search)
            const users = await getTargetUsers(0, 100); 
            setTargetUsers(users);
        } catch (error) {
            message.error('Failed to fetch resources');
        }
    };

    useEffect(() => {
        fetchTasks();
    }, []);

    const handleCreate = () => {
        fetchResources();
        setIsModalVisible(true);
    };

    const handleOk = async () => {
        try {
            const values = await form.validateFields();
            await createInviteTask(values);
            message.success('Invite task created');
            setIsModalVisible(false);
            fetchTasks();
        } catch (error) {
            message.error('Failed to create task');
        }
    };

    const columns = [
        {
            title: 'Name',
            dataIndex: 'name',
            key: 'name',
        },
        {
            title: 'Target Channel',
            dataIndex: 'target_channel',
            key: 'target_channel',
            render: (text: string) => <a href={text} target="_blank" rel="noreferrer">{text}</a>
        },
        {
            title: 'Status',
            dataIndex: 'status',
            key: 'status',
            render: (status: string) => {
                let color = 'default';
                if (status === 'completed') color = 'green';
                if (status === 'running') color = 'blue';
                if (status === 'failed') color = 'red';
                return <Tag color={color}>{status.toUpperCase()}</Tag>;
            }
        },
        {
            title: 'Progress',
            key: 'progress',
            render: (_: any, record: InviteTask) => (
                <span>
                    <span style={{ color: 'green' }}>{record.success_count} OK</span> / 
                    <span style={{ color: 'red', marginLeft: 8 }}>{record.fail_count} Fail</span>
                </span>
            )
        },
        {
            title: 'Created At',
            dataIndex: 'created_at',
            key: 'created_at',
            render: (text: string) => new Date(text).toLocaleString()
        }
    ];

    return (
        <div style={{ padding: 24 }}>
            <Card title="Invite Tasks (Build Your Private Traffic)" extra={
                <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
                    Create Task
                </Button>
            }>
                <div style={{ marginBottom: 16 }}>
                    <Button icon={<ReloadOutlined />} onClick={fetchTasks}>Refresh</Button>
                </div>
                <Table columns={columns} dataSource={tasks} rowKey="id" loading={loading} />
            </Card>

            <Modal
                title="Create Invite Task"
                open={isModalVisible}
                onOk={handleOk}
                onCancel={() => setIsModalVisible(false)}
                width={700}
            >
                <Form form={form} layout="vertical">
                    <Form.Item name="name" label="Task Name" rules={[{ required: true }]}>
                        <Input placeholder="e.g. Invite to Official Group" />
                    </Form.Item>
                    
                    <Form.Item name="target_channel" label="Target Channel Link" rules={[{ required: true }]}>
                        <Input placeholder="https://t.me/your_channel" />
                    </Form.Item>
                    
                    <Form.Item name="account_ids" label="Select Worker Accounts" rules={[{ required: true }]}>
                        <Select mode="multiple" placeholder="Select accounts to perform invites" maxTagCount="responsive">
                            {accounts.map(acc => (
                                <Option key={acc.id} value={acc.id}>
                                    {acc.phone_number} ({acc.tier || 'tier3'})
                                </Option>
                            ))}
                        </Select>
                    </Form.Item>
                    
                    <Form.Item name="target_user_ids" label="Select Users to Invite" rules={[{ required: true }]}>
                        <Select mode="multiple" placeholder="Select collected users" maxTagCount="responsive">
                            {targetUsers.map(user => (
                                <Option key={user.id} value={user.id}>
                                    {user.first_name} {user.last_name} (@{user.username || 'no_user'})
                                </Option>
                            ))}
                        </Select>
                    </Form.Item>
                    
                    <Form.Item name="max_invites_per_account" label="Max Invites Per Account (Safety Limit)" initialValue={5}>
                        <InputNumber min={1} max={50} />
                    </Form.Item>
                </Form>
            </Modal>
        </div>
    );
};

export default InvitePage;
