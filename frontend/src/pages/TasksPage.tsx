import React, { useEffect, useState } from 'react';
import { Card, Table, Tag, Button, Tabs, message, Popconfirm } from 'antd';
import type { TabsProps } from 'antd';
import { ReloadOutlined, StopOutlined } from '@ant-design/icons';
import { getActiveTasks, revokeTask } from '../services/api';

const TasksPage: React.FC = () => {
    const [loading, setLoading] = useState(false);
    const [data, setData] = useState<any>({ active: {}, reserved: {}, scheduled: {} });

    const fetchData = async () => {
        setLoading(true);
        try {
            const res = await getActiveTasks();
            setData(res);
        } catch (error) {
            message.error('Failed to fetch tasks');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
        const interval = setInterval(fetchData, 5000);
        return () => clearInterval(interval);
    }, []);

    const handleRevoke = async (taskId: string) => {
        try {
            await revokeTask(taskId);
            message.success('Task revoked');
            fetchData();
        } catch (e) {
            message.error('Failed to revoke task');
        }
    };

    // Flatten data from workers
    const flattenTasks = (workerData: any) => {
        const tasks: any[] = [];
        if (!workerData) return tasks;
        
        Object.keys(workerData).forEach(workerName => {
            const workerTasks = workerData[workerName];
            if (Array.isArray(workerTasks)) {
                workerTasks.forEach(t => {
                    tasks.push({ ...t, worker: workerName });
                });
            }
        });
        return tasks;
    };

    const columns = [
        { 
            title: 'Task ID', 
            dataIndex: 'id', 
            key: 'id',
            width: 300,
        },
        { 
            title: 'Name', 
            dataIndex: 'name', 
            key: 'name',
            render: (text: string) => <Tag color="blue">{text}</Tag>
        },
        { 
            title: 'Args', 
            dataIndex: 'args', 
            key: 'args',
            render: (args: any) => JSON.stringify(args)
        },
        { 
            title: 'Started', 
            dataIndex: 'time_start', 
            key: 'time_start',
            render: (ts: number) => ts ? new Date(ts * 1000).toLocaleString() : '-'
        },
        { 
            title: 'Worker', 
            dataIndex: 'worker', 
            key: 'worker' 
        },
        {
            title: 'Action',
            key: 'action',
            render: (_: any, record: any) => (
                <Popconfirm title="Terminate this task?" onConfirm={() => handleRevoke(record.id)}>
                    <Button type="link" danger icon={<StopOutlined />}>Stop</Button>
                </Popconfirm>
            )
        }
    ];

    const tabItems: TabsProps['items'] = [
        {
            key: 'active',
            label: `Active (${flattenTasks(data.active).length})`,
            children: (
                <Table 
                    dataSource={flattenTasks(data.active)} 
                    columns={columns} 
                    rowKey="id" 
                    pagination={false}
                />
            ),
        },
        {
            key: 'reserved',
            label: `Reserved (${flattenTasks(data.reserved).length})`,
            children: (
                <Table 
                    dataSource={flattenTasks(data.reserved)} 
                    columns={columns} 
                    rowKey="id" 
                    pagination={false}
                />
            ),
        },
        {
            key: 'scheduled',
            label: `Scheduled (${flattenTasks(data.scheduled).length})`,
            children: (
                <Table 
                    dataSource={flattenTasks(data.scheduled)} 
                    columns={columns} 
                    rowKey="id" 
                    pagination={false}
                />
            ),
        },
    ];

    return (
        <div style={{ padding: 24 }}>
            <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
                <h2>Background Tasks</h2>
                <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>Refresh</Button>
            </div>

            <Tabs defaultActiveKey="active" items={tabItems} />
        </div>
    );
};

export default TasksPage;
