import React, { useEffect, useState } from 'react';
import { Card, Table, Button, Modal, Form, Input, message, Row, Col, Typography, Alert, Space } from 'antd';
import { getSystemConfig, setSystemConfig, SystemConfig, changePassword, getCurrentUser, UserInfo } from '../services/api';
import { EditOutlined, PlusOutlined, LockOutlined, UserOutlined, SafetyCertificateOutlined } from '@ant-design/icons';

const { Text, Title } = Typography;

const SystemConfigPage: React.FC = () => {
    const [configs, setConfigs] = useState<SystemConfig[]>([]);
    const [loading, setLoading] = useState(false);
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [editingConfig, setEditingConfig] = useState<SystemConfig | null>(null);
    const [form] = Form.useForm();
    
    // 修改密码相关状态
    const [isPasswordModalVisible, setIsPasswordModalVisible] = useState(false);
    const [passwordLoading, setPasswordLoading] = useState(false);
    const [passwordForm] = Form.useForm();
    const [currentUser, setCurrentUser] = useState<UserInfo | null>(null);

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

    const fetchCurrentUser = async () => {
        try {
            const user = await getCurrentUser();
            setCurrentUser(user);
        } catch (e) {
            // 忽略错误
        }
    };

    useEffect(() => {
        fetchConfigs();
        fetchCurrentUser();
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

    // 修改密码处理
    const handlePasswordChange = async () => {
        try {
            const values = await passwordForm.validateFields();
            setPasswordLoading(true);
            
            await changePassword({
                current_password: values.current_password,
                new_password: values.new_password,
                confirm_password: values.confirm_password
            });
            
            message.success('密码修改成功，请使用新密码重新登录');
            setIsPasswordModalVisible(false);
            passwordForm.resetFields();
            
            // 清除token并跳转到登录页
            localStorage.removeItem('token');
            setTimeout(() => {
                window.location.href = '/login';
            }, 1500);
        } catch (e: any) {
            const errorMsg = e.response?.data?.detail || '密码修改失败';
            message.error(errorMsg);
        } finally {
            setPasswordLoading(false);
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
        <div>
            <Row gutter={[16, 16]}>
                {/* 账户安全卡片 */}
                <Col span={24}>
                    <Card 
                        title={
                            <Space>
                                <SafetyCertificateOutlined style={{ color: '#1890ff' }} />
                                <span>账户安全</span>
                            </Space>
                        }
                    >
                        <Row gutter={24} align="middle">
                            <Col span={16}>
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
                                    <Space>
                                        <UserOutlined />
                                        <Text strong>当前用户：</Text>
                                        <Text>{currentUser?.username || '-'}</Text>
                                        {currentUser?.is_superuser && (
                                            <Text type="warning" style={{ 
                                                background: '#fff7e6', 
                                                padding: '2px 8px', 
                                                borderRadius: 4,
                                                fontSize: 12 
                                            }}>
                                                超级管理员
                                            </Text>
                                        )}
                                    </Space>
                                    <Text type="secondary" style={{ fontSize: 12 }}>
                                        定期更换密码可以提高账户安全性。密码必须包含大写字母、小写字母和数字，长度至少8位。
                                    </Text>
                                </div>
                            </Col>
                            <Col span={8} style={{ textAlign: 'right' }}>
                                <Button 
                                    type="primary" 
                                    icon={<LockOutlined />}
                                    onClick={() => {
                                        passwordForm.resetFields();
                                        setIsPasswordModalVisible(true);
                                    }}
                                >
                                    修改密码
                                </Button>
                            </Col>
                        </Row>
                    </Card>
                </Col>

                {/* 系统配置卡片 */}
                <Col span={24}>
                    <Card 
                        title="系统配置" 
                        extra={
                            <Button type="primary" icon={<PlusOutlined />} onClick={handleAdd}>
                                新增配置
                            </Button>
                        }
                    >
                        <Table
                            dataSource={configs}
                            columns={columns}
                            rowKey="key"
                            loading={loading}
                            pagination={false}
                        />
                    </Card>
                </Col>
            </Row>
            
            {/* 配置编辑弹窗 */}
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

            {/* 修改密码弹窗 */}
            <Modal
                title={
                    <Space>
                        <LockOutlined style={{ color: '#1890ff' }} />
                        <span>修改密码</span>
                    </Space>
                }
                open={isPasswordModalVisible}
                onOk={handlePasswordChange}
                onCancel={() => {
                    setIsPasswordModalVisible(false);
                    passwordForm.resetFields();
                }}
                confirmLoading={passwordLoading}
                okText="确认修改"
                cancelText="取消"
                width={480}
            >
                <Alert
                    title="密码修改成功后需要重新登录"
                    type="info"
                    showIcon
                    style={{ marginBottom: 16 }}
                />
                
                <Form form={passwordForm} layout="vertical">
                    <Form.Item 
                        name="current_password" 
                        label="当前密码"
                        rules={[{ required: true, message: '请输入当前密码' }]}
                    >
                        <Input.Password 
                            prefix={<LockOutlined />}
                            placeholder="请输入当前密码" 
                        />
                    </Form.Item>
                    
                    <Form.Item 
                        name="new_password" 
                        label="新密码"
                        rules={[
                            { required: true, message: '请输入新密码' },
                            { min: 8, message: '密码长度至少8位' },
                            {
                                validator: (_, value) => {
                                    if (!value) return Promise.resolve();
                                    const hasUpper = /[A-Z]/.test(value);
                                    const hasLower = /[a-z]/.test(value);
                                    const hasDigit = /[0-9]/.test(value);
                                    if (hasUpper && hasLower && hasDigit) {
                                        return Promise.resolve();
                                    }
                                    return Promise.reject('密码必须包含大写字母、小写字母和数字');
                                }
                            }
                        ]}
                        extra={
                            <Text type="secondary" style={{ fontSize: 12 }}>
                                密码必须包含大写字母、小写字母和数字，长度至少8位
                            </Text>
                        }
                    >
                        <Input.Password 
                            prefix={<LockOutlined />}
                            placeholder="请输入新密码" 
                        />
                    </Form.Item>
                    
                    <Form.Item 
                        name="confirm_password" 
                        label="确认新密码"
                        dependencies={['new_password']}
                        rules={[
                            { required: true, message: '请确认新密码' },
                            ({ getFieldValue }) => ({
                                validator(_, value) {
                                    if (!value || getFieldValue('new_password') === value) {
                                        return Promise.resolve();
                                    }
                                    return Promise.reject('两次输入的密码不一致');
                                },
                            }),
                        ]}
                    >
                        <Input.Password 
                            prefix={<LockOutlined />}
                            placeholder="请再次输入新密码" 
                        />
                    </Form.Item>
                </Form>
            </Modal>
        </div>
    );
};

export default SystemConfigPage;
