import React, { useEffect, useState } from 'react';
import { Card, Table, Button, Modal, Form, Input, message } from 'antd';
import { getSystemConfig, setSystemConfig, SystemConfig } from '../services/api';
import { EditOutlined, PlusOutlined } from '@ant-design/icons';

const SystemConfigPage: React.FC = () => {
    const [configs, setConfigs] = useState<SystemConfig[]>([]);
    const [loading, setLoading] = useState(false);
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [editingConfig, setEditingConfig] = useState<SystemConfig | null>(null);
    const [form] = Form.useForm();

    const fetchConfigs = async () => {
        setLoading(true);
        try {
            const data = await getSystemConfig();
            setConfigs(data);
        } catch (e) {
            message.error('加载配置失败');
        } finally {
            setLoading(false);
        }
    };

    useEffect(() => {
        fetchConfigs();
    }, []);

    const handleEdit = (record: SystemConfig) => {
        setEditingConfig(record);
        form.setFieldsValue(record);
        setIsModalVisible(true);
    };

    const handleAdd = () => {
        setEditingConfig(null);
        form.resetFields();
        setIsModalVisible(true);
    };

    const handleSave = async () => {
        try {
            const values = await form.validateFields();
            await setSystemConfig(values.key, values.value, values.description);
            message.success('保存成功');
            setIsModalVisible(false);
            fetchConfigs();
        } catch (e) {
            message.error('保存失败');
        }
    };

    const columns = [
        { title: '键 (Key)', dataIndex: 'key', width: 200 },
        { title: '值 (Value)', dataIndex: 'value', ellipsis: true },
        { title: '描述', dataIndex: 'description' },
        { title: '更新时间', dataIndex: 'updated_at', render: (t: string) => new Date(t).toLocaleString(), width: 180 },
        {
            title: '操作',
            key: 'action',
            width: 100,
            render: (_: any, record: SystemConfig) => (
                <Button type="link" icon={<EditOutlined />} onClick={() => handleEdit(record)}>
                    编辑
                </Button>
            )
        }
    ];

    return (
        <Card title="系统配置" extra={<Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>新增配置</Button>}>
            <Table
                dataSource={configs}
                columns={columns}
                rowKey="key"
                loading={loading}
                pagination={false}
            />
            
            <Modal
                title={editingConfig ? "编辑配置" : "新增配置"}
                open={isModalVisible}
                onOk={handleSave}
                onCancel={() => setIsModalVisible(false)}
            >
                <Form form={form} layout="vertical">
                    <Form.Item name="key" label="键 (Key)" rules={[{ required: true }]}>
                        <Input disabled={!!editingConfig} />
                    </Form.Item>
                    <Form.Item name="value" label="值 (Value)" rules={[{ required: true }]}>
                        <Input.TextArea rows={4} />
                    </Form.Item>
                    <Form.Item name="description" label="描述">
                        <Input />
                    </Form.Item>
                </Form>
            </Modal>
        </Card>
    );
};

export default SystemConfigPage;
