import React, { useEffect, useState } from 'react';
import { Card, Table, Tag, Form, Select, Button, DatePicker } from 'antd';
import { getOperationLogs } from '../services/api';
import { ReloadOutlined } from '@ant-design/icons';

const { RangePicker } = DatePicker;
const { Option } = Select;

const LogsPage: React.FC = () => {
    const [logs, setLogs] = useState<any[]>([]);
    const [loading, setLoading] = useState(false);
    const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
    const [filters, setFilters] = useState<any>({});

    useEffect(() => {
        fetchLogs();
    }, [pagination.current, filters]);

    const fetchLogs = async () => {
        setLoading(true);
        try {
            const skip = (pagination.current - 1) * pagination.pageSize;
            const data = await getOperationLogs(skip, pagination.pageSize, filters.action);
            setLogs(data);
            // Assume 100 for now or implement count API
            setPagination(prev => ({ ...prev, total: 1000 })); 
        } catch (e) {
            // ignore
        } finally {
            setLoading(false);
        }
    };

    const columns = [
        { title: 'ID', dataIndex: 'id', width: 80 },
        { title: '时间', dataIndex: 'created_at', render: (t: string) => new Date(t).toLocaleString() },
        { title: '操作人', dataIndex: 'username' },
        { title: '动作', dataIndex: 'action', render: (t: string) => <Tag color="blue">{t}</Tag> },
        { title: '详情', dataIndex: 'details', ellipsis: true },
        { title: '状态', dataIndex: 'status', render: (t: string) => <Tag color={t === 'success' ? 'green' : 'red'}>{t}</Tag> },
        { title: 'IP', dataIndex: 'ip_address' },
    ];

    return (
        <Card title="审计日志" extra={<Button icon={<ReloadOutlined />} onClick={fetchLogs} />}>
            <div style={{ marginBottom: 16 }}>
                <Form layout="inline" onFinish={(v) => setFilters(v)}>
                    <Form.Item name="action" label="动作">
                        <Select style={{ width: 150 }} allowClear>
                            <Option value="login">登录</Option>
                            <Option value="create_account">创建账号</Option>
                            <Option value="send_message">发送消息</Option>
                        </Select>
                    </Form.Item>
                    <Form.Item>
                        <Button type="primary" htmlType="submit">查询</Button>
                    </Form.Item>
                </Form>
            </div>
            <Table
                dataSource={logs}
                columns={columns}
                rowKey="id"
                loading={loading}
                pagination={{
                    ...pagination,
                    onChange: (page) => setPagination(prev => ({ ...prev, current: page }))
                }}
            />
        </Card>
    );
};

export default LogsPage;
