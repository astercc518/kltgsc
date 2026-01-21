import React, { useEffect, useState } from 'react';
import { Card, Form, Input, Button, Table, Space, message, Modal, List, Tag, Select, Steps, Divider } from 'antd';
import { PlayCircleOutlined, PlusOutlined, RobotOutlined, UserOutlined } from '@ant-design/icons';
import { 
    createScript, 
    getScripts, 
    generateScriptLines, 
    createScriptTask, 
    getScriptTasks, 
    getAccounts,
    Script, 
    ScriptTask, 
    Account,
    Line
} from '../services/api';

const { TextArea } = Input;
const { Option } = Select;

const ScriptPage: React.FC = () => {
    const [scripts, setScripts] = useState<Script[]>([]);
    const [tasks, setTasks] = useState<ScriptTask[]>([]);
    const [accounts, setAccounts] = useState<Account[]>([]);
    const [loading, setLoading] = useState(false);
    
    // Create Script Modal
    const [isCreateModalVisible, setIsCreateModalVisible] = useState(false);
    const [createForm] = Form.useForm();
    const [roles, setRoles] = useState<{name: string, prompt: string}[]>([{name: 'A', prompt: ''}, {name: 'B', prompt: ''}]);

    // Generate Content Modal
    const [generatingScriptId, setGeneratingScriptId] = useState<number | null>(null);
    const [generatedLines, setGeneratedLines] = useState<Line[]>([]);
    const [isGenerateModalVisible, setIsGenerateModalVisible] = useState(false);

    // Create Task Modal
    const [isTaskModalVisible, setIsTaskModalVisible] = useState(false);
    const [selectedScript, setSelectedScript] = useState<Script | null>(null);
    const [taskForm] = Form.useForm();

    useEffect(() => {
        fetchScripts();
        fetchTasks();
        fetchAccounts();
    }, []);

    const fetchScripts = async () => {
        try {
            const data = await getScripts();
            setScripts(data);
        } catch (e) {
            // ignore
        }
    };

    const fetchTasks = async () => {
        try {
            const data = await getScriptTasks();
            setTasks(data);
        } catch (e) {
            // ignore
        }
    };

    const fetchAccounts = async () => {
        try {
            const data = await getAccounts(0, 100, 'active');
            setAccounts(data);
        } catch (e) {
            // ignore
        }
    };

    const handleCreateScript = async (values: any) => {
        setLoading(true);
        try {
            const rolesList = roles.filter(r => r.name.trim() !== '');
            await createScript({
                name: values.name,
                description: values.description,
                topic: values.topic,
                roles_json: JSON.stringify(rolesList)
            });
            message.success('剧本创建成功');
            setIsCreateModalVisible(false);
            createForm.resetFields();
            fetchScripts();
        } catch (error: any) {
            message.error('创建失败');
        } finally {
            setLoading(false);
        }
    };

    const handleGenerate = async (script: Script) => {
        setGeneratingScriptId(script.id);
        setLoading(true);
        try {
            const res = await generateScriptLines(script.id);
            setGeneratedLines(res.lines);
            message.success('内容生成成功');
            fetchScripts(); // refresh to get updated lines_json if needed
            setIsGenerateModalVisible(true);
        } catch (error: any) {
            message.error('生成失败: ' + error.response?.data?.detail);
        } finally {
            setLoading(false);
            setGeneratingScriptId(null);
        }
    };

    const handleShowTaskModal = (script: Script) => {
        if (!script.lines_json) {
            message.warning('请先生成对话内容');
            return;
        }
        setSelectedScript(script);
        setIsTaskModalVisible(true);
    };

    const handleCreateTask = async (values: any) => {
        if (!selectedScript) return;
        setLoading(true);
        try {
            // values contains mapping like: "role_A": 123, "role_B": 456
            const accountMapping: Record<string, number> = {};
            const roles = JSON.parse(selectedScript.roles_json);
            
            roles.forEach((r: any) => {
                if (values[`role_${r.name}`]) {
                    accountMapping[r.name] = values[`role_${r.name}`];
                }
            });

            await createScriptTask({
                script_id: selectedScript.id,
                target_group: values.target_group,
                account_mapping_json: JSON.stringify(accountMapping),
                min_delay: values.min_delay,
                max_delay: values.max_delay
            });
            message.success('任务启动成功');
            setIsTaskModalVisible(false);
            taskForm.resetFields();
            fetchTasks();
        } catch (error: any) {
            message.error('启动失败');
        } finally {
            setLoading(false);
        }
    };

    const scriptColumns = [
        { title: 'ID', dataIndex: 'id', width: 50 },
        { title: '名称', dataIndex: 'name' },
        { title: '主题', dataIndex: 'topic' },
        { 
            title: '角色', 
            dataIndex: 'roles_json', 
            render: (text: string) => {
                const roles = JSON.parse(text || '[]');
                return roles.map((r: any) => <Tag key={r.name}>{r.name}</Tag>);
            }
        },
        { 
            title: '状态', 
            key: 'status',
            render: (_: any, record: Script) => record.lines_json ? <Tag color="success">已生成</Tag> : <Tag color="default">未生成</Tag>
        },
        {
            title: '操作',
            key: 'action',
            render: (_: any, record: Script) => (
                <Space>
                    <Button 
                        size="small" 
                        icon={<RobotOutlined />} 
                        onClick={() => handleGenerate(record)}
                        loading={generatingScriptId === record.id}
                    >
                        生成内容
                    </Button>
                    <Button 
                        size="small" 
                        type="primary" 
                        icon={<PlayCircleOutlined />} 
                        onClick={() => handleShowTaskModal(record)}
                        disabled={!record.lines_json}
                    >
                        执行任务
                    </Button>
                </Space>
            )
        }
    ];

    const taskColumns = [
        { title: 'ID', dataIndex: 'id', width: 50 },
        { title: '剧本ID', dataIndex: 'script_id' },
        { title: '目标群组', dataIndex: 'target_group' },
        { 
            title: '进度', 
            dataIndex: 'current_step', 
            render: (step: number) => `第 ${step} 步`
        },
        { 
            title: '状态', 
            dataIndex: 'status', 
            render: (status: string) => {
                const colors: any = { running: 'processing', completed: 'success', failed: 'error' };
                return <Tag color={colors[status] || 'default'}>{status}</Tag>;
            }
        },
        { title: '创建时间', dataIndex: 'created_at', render: (t: string) => new Date(t).toLocaleString() }
    ];

    return (
        <div style={{ padding: 20 }}>
            <Card 
                title="炒群脚本管理" 
                extra={<Button type="primary" icon={<PlusOutlined />} onClick={() => setIsCreateModalVisible(true)}>新建剧本</Button>}
                style={{ marginBottom: 20 }}
            >
                <Table 
                    dataSource={scripts} 
                    columns={scriptColumns} 
                    rowKey="id" 
                    pagination={{ pageSize: 5 }}
                />
            </Card>

            <Card title="执行任务列表">
                <Table 
                    dataSource={tasks} 
                    columns={taskColumns} 
                    rowKey="id" 
                    pagination={{ pageSize: 5 }}
                />
            </Card>

            {/* Create Script Modal */}
            <Modal
                title="新建剧本"
                open={isCreateModalVisible}
                onCancel={() => setIsCreateModalVisible(false)}
                footer={null}
                width={600}
            >
                <Form form={createForm} layout="vertical" onFinish={handleCreateScript}>
                    <Form.Item name="name" label="剧本名称" rules={[{ required: true }]}>
                        <Input />
                    </Form.Item>
                    <Form.Item name="description" label="描述">
                        <Input />
                    </Form.Item>
                    <Form.Item name="topic" label="对话主题" rules={[{ required: true }]} help="LLM 将根据此主题生成对话">
                        <TextArea rows={3} placeholder="例如：讨论 Web3 游戏的未来发展，UserA 比较乐观，UserB 持怀疑态度。" />
                    </Form.Item>
                    
                    <Divider orientation="left">角色设定</Divider>
                    {roles.map((role, index) => (
                        <Space key={index} style={{ display: 'flex', marginBottom: 8 }} align="baseline">
                            <Input 
                                placeholder="角色名 (UserA)" 
                                value={role.name} 
                                onChange={e => {
                                    const newRoles = [...roles];
                                    newRoles[index].name = e.target.value;
                                    setRoles(newRoles);
                                }}
                            />
                            <Input 
                                placeholder="人设 (Prompt)" 
                                value={role.prompt}
                                style={{ width: 300 }}
                                onChange={e => {
                                    const newRoles = [...roles];
                                    newRoles[index].prompt = e.target.value;
                                    setRoles(newRoles);
                                }}
                            />
                            {index > 1 && (
                                <Button danger shape="circle" icon={<MinusOutlined />} onClick={() => {
                                    setRoles(roles.filter((_, i) => i !== index));
                                }} />
                            )}
                        </Space>
                    ))}
                    <Button type="dashed" onClick={() => setRoles([...roles, {name: '', prompt: ''}])} block icon={<PlusOutlined />}>
                        添加角色
                    </Button>

                    <Form.Item style={{ marginTop: 20 }}>
                        <Button type="primary" htmlType="submit" block loading={loading}>创建</Button>
                    </Form.Item>
                </Form>
            </Modal>

            {/* Generate Result Modal */}
            <Modal
                title="生成的对话预览"
                open={isGenerateModalVisible}
                onCancel={() => setIsGenerateModalVisible(false)}
                footer={[<Button key="ok" type="primary" onClick={() => setIsGenerateModalVisible(false)}>确定</Button>]}
            >
                <List
                    dataSource={generatedLines}
                    renderItem={item => (
                        <List.Item>
                            <List.Item.Meta
                                avatar={<Tag color="blue">{item.role}</Tag>}
                                description={item.content}
                            />
                        </List.Item>
                    )}
                />
            </Modal>

            {/* Create Task Modal */}
            <Modal
                title="启动炒群任务"
                open={isTaskModalVisible}
                onCancel={() => setIsTaskModalVisible(false)}
                footer={null}
            >
                {selectedScript && (
                    <Form form={taskForm} layout="vertical" onFinish={handleCreateTask} initialValues={{ min_delay: 5, max_delay: 15 }}>
                        <Form.Item name="target_group" label="目标群组链接/用户名" rules={[{ required: true }]}>
                            <Input placeholder="@target_group" />
                        </Form.Item>
                        
                        <Divider orientation="left">账号分配</Divider>
                        {JSON.parse(selectedScript.roles_json).map((role: any) => (
                            <Form.Item 
                                key={role.name} 
                                name={`role_${role.name}`} 
                                label={`角色: ${role.name}`} 
                                rules={[{ required: true, message: '请分配账号' }]}
                            >
                                <Select placeholder="选择账号" showSearch optionFilterProp="children">
                                    {accounts.map(acc => (
                                        <Option key={acc.id} value={acc.id}>
                                            {acc.phone_number} ({acc.status})
                                        </Option>
                                    ))}
                                </Select>
                            </Form.Item>
                        ))}

                        <Space>
                            <Form.Item name="min_delay" label="最小延迟(秒)">
                                <Input type="number" />
                            </Form.Item>
                            <Form.Item name="max_delay" label="最大延迟(秒)">
                                <Input type="number" />
                            </Form.Item>
                        </Space>

                        <Button type="primary" htmlType="submit" block loading={loading}>
                            开始执行
                        </Button>
                    </Form>
                )}
            </Modal>
        </div>
    );
};

// Missing MinusOutlined import fix
import { MinusOutlined } from '@ant-design/icons';

export default ScriptPage;
