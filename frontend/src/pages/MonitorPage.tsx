import React, { useState, useEffect } from 'react';
import { Table, Button, Modal, Form, Input, Select, Switch, Tag, Space, message, Tabs, Tooltip, InputNumber, Checkbox, Card, Row, Col, Slider, Alert, Spin } from 'antd';
import type { TabsProps } from 'antd';
import { PlusOutlined, EditOutlined, DeleteOutlined, RobotOutlined, MessageOutlined, BellOutlined, ReloadOutlined, ForwardOutlined, UserAddOutlined, FireOutlined, BulbOutlined, ThunderboltOutlined, EyeOutlined, SendOutlined } from '@ant-design/icons';
import { 
    KeywordMonitor, getKeywordMonitors, createKeywordMonitor, updateKeywordMonitor, deleteKeywordMonitor, 
    getKeywordHits, KeywordHit,
    getScripts, Script
} from '../services/api';
import api from '../services/api';

const { Option } = Select;
const { TextArea } = Input;

// AI 关键词联想 API
const suggestKeywords = async (seedKeyword?: string, scenarioDescription?: string): Promise<{ keywords: string[] }> => {
    const response = await api.post('/monitors/suggest-keywords', { 
        seed_keyword: seedKeyword, 
        scenario_description: scenarioDescription 
    });
    return response.data;
};

const MonitorPage: React.FC = () => {
    const [monitors, setMonitors] = useState<KeywordMonitor[]>([]);
    const [hits, setHits] = useState<KeywordHit[]>([]);
    const [scripts, setScripts] = useState<Script[]>([]);
    const [loading, setLoading] = useState(false);
    const [hitsLoading, setHitsLoading] = useState(false);
    const [isModalVisible, setIsModalVisible] = useState(false);
    const [editingMonitor, setEditingMonitor] = useState<KeywordMonitor | null>(null);
    const [form] = Form.useForm();
    
    // 表单状态
    const [actionType, setActionType] = useState<string>('notify');
    const [matchType, setMatchType] = useState<string>('partial');
    const [marketingMode, setMarketingMode] = useState<string>('passive');
    
    // AI 联想状态
    const [suggestLoading, setSuggestLoading] = useState(false);
    const [suggestions, setSuggestions] = useState<string[]>([]);

    const fetchData = async () => {
        setLoading(true);
        try {
            const [monitorsData, scriptsData] = await Promise.all([
                getKeywordMonitors(),
                getScripts()
            ]);
            setMonitors(monitorsData);
            setScripts(scriptsData);
        } catch (error) {
            message.error('加载数据失败');
        } finally {
            setLoading(false);
        }
    };

    const fetchHits = async () => {
        setHitsLoading(true);
        try {
            const data = await getKeywordHits();
            setHits(data);
        } catch (error) {
            message.error('加载命中记录失败');
        } finally {
            setHitsLoading(false);
        }
    };

    useEffect(() => {
        fetchData();
    }, []);

    const handleCreate = () => {
        setEditingMonitor(null);
        form.resetFields();
        setActionType('notify');
        setMatchType('partial');
        setMarketingMode('passive');
        setSuggestions([]);
        setIsModalVisible(true);
    };

    const handleEdit = (record: KeywordMonitor) => {
        setEditingMonitor(record);
        form.setFieldsValue(record);
        setActionType(record.action_type);
        setMatchType(record.match_type);
        setMarketingMode((record as any).marketing_mode || 'passive');
        setSuggestions([]);
        setIsModalVisible(true);
    };

    const handleDelete = async (id: number) => {
        try {
            await deleteKeywordMonitor(id);
            message.success('规则已删除');
            fetchData();
        } catch (error) {
            message.error('删除失败');
        }
    };

    const handleOk = async () => {
        try {
            const values = await form.validateFields();
            if (editingMonitor) {
                await updateKeywordMonitor(editingMonitor.id, values);
                message.success('规则已更新');
            } else {
                await createKeywordMonitor(values);
                message.success('规则已创建');
            }
            setIsModalVisible(false);
            fetchData();
        } catch (error) {
            message.error('操作失败');
        }
    };

    // AI 关键词联想
    const handleSuggest = async () => {
        const scenario = form.getFieldValue('scenario_description');
        const keyword = form.getFieldValue('keyword');
        
        if (!scenario && !keyword) {
            message.warning('请先输入业务场景描述或种子关键词');
            return;
        }
        
        setSuggestLoading(true);
        try {
            const res = await suggestKeywords(keyword, scenario);
            setSuggestions(res.keywords || []);
            message.success(`已生成 ${res.keywords?.length || 0} 个联想词`);
        } catch (e) {
            message.error('AI 联想失败');
        } finally {
            setSuggestLoading(false);
        }
    };

    const addSuggestionToKeywords = (word: string) => {
        const current = form.getFieldValue('keyword') || '';
        const newValue = current ? `${current}|${word}` : word;
        form.setFieldsValue({ keyword: newValue, match_type: 'regex' });
        setMatchType('regex');
        setSuggestions(suggestions.filter(s => s !== word));
    };

    const applyAllSuggestions = () => {
        if (suggestions.length === 0) return;
        const autoKeywords = JSON.stringify(suggestions);
        form.setFieldsValue({ auto_keywords: autoKeywords });
        message.success('已应用所有联想词到自动关键词库');
    };

    const getActionTag = (type: string) => {
        switch(type) {
            case 'notify': return <Tag icon={<BellOutlined />} color="gold">通知</Tag>;
            case 'trigger_script': return <Tag icon={<RobotOutlined />} color="purple">剧本</Tag>;
            case 'auto_reply': return <Tag icon={<MessageOutlined />} color="blue">AI回复</Tag>;
            default: return <Tag>{type}</Tag>;
        }
    };

    const getMarketingModeTag = (mode: string) => {
        if (mode === 'active') {
            return <Tag icon={<ThunderboltOutlined />} color="red">主动</Tag>;
        }
        return <Tag icon={<EyeOutlined />} color="blue">被动</Tag>;
    };

    const columns = [
        {
            title: '关键词/场景',
            dataIndex: 'keyword',
            key: 'keyword',
            render: (text: string, record: any) => (
                <div>
                    <Tag color="blue" style={{ fontSize: 13, fontWeight: 500 }}>{text}</Tag>
                    {record.match_type === 'semantic' && record.scenario_description && (
                        <div style={{ fontSize: 12, color: '#666', marginTop: 4 }}>
                            📋 {record.scenario_description.slice(0, 30)}...
                        </div>
                    )}
                </div>
            )
        },
        {
            title: '模式',
            key: 'mode',
            width: 100,
            render: (_: any, record: any) => (
                <Space direction="vertical" size={2}>
                    {getMarketingModeTag(record.marketing_mode || 'passive')}
                    <span style={{ fontSize: 11, color: '#999' }}>
                        {record.match_type === 'semantic' ? '语义' : 
                         record.match_type === 'regex' ? '正则' : 
                         record.match_type === 'exact' ? '精确' : '模糊'}
                    </span>
                </Space>
            )
        },
        {
            title: '响应',
            dataIndex: 'action_type',
            key: 'action_type',
            width: 80,
            render: (text: string) => getActionTag(text)
        },
        {
            title: '增强功能',
            key: 'features',
            render: (_: any, record: KeywordMonitor) => (
                <Space size={4} wrap>
                    {record.forward_target && <Tooltip title={`转发到: ${record.forward_target}`}><Tag icon={<ForwardOutlined />} color="cyan">转发</Tag></Tooltip>}
                    {record.auto_capture_lead && <Tag icon={<UserAddOutlined />} color="green">CRM</Tag>}
                    {record.score_weight && record.score_weight > 0 && (
                        <Tag icon={<FireOutlined />} color="orange">+{record.score_weight}</Tag>
                    )}
                    {(record as any).marketing_mode === 'active' && (
                        <Tag icon={<SendOutlined />} color="magenta">
                            {(record as any).reply_mode === 'private_dm' ? '私聊' : '群回'}
                        </Tag>
                    )}
                </Space>
            )
        },
        {
            title: '状态',
            dataIndex: 'is_active',
            key: 'is_active',
            width: 70,
            render: (active: boolean) => (
                <Tag color={active ? 'green' : 'red'}>{active ? '启用' : '禁用'}</Tag>
            )
        },
        {
            title: '操作',
            key: 'actions',
            width: 100,
            render: (_: any, record: KeywordMonitor) => (
                <Space>
                    <Button size="small" icon={<EditOutlined />} onClick={() => handleEdit(record)} />
                    <Button size="small" icon={<DeleteOutlined />} danger onClick={() => handleDelete(record.id)} />
                </Space>
            )
        }
    ];

    const hitColumns = [
        {
            title: '时间',
            dataIndex: 'detected_at',
            key: 'detected_at',
            width: 160,
            render: (text: string) => new Date(text).toLocaleString()
        },
        {
            title: '群组',
            key: 'group',
            render: (_: any, record: KeywordHit) => (
                <span>{record.source_group_name || record.source_group_id}</span>
            )
        },
        {
            title: '用户',
            key: 'user',
            render: (_: any, record: KeywordHit) => (
                <span>{record.source_user_name ? `@${record.source_user_name}` : record.source_user_id}</span>
            )
        },
        {
            title: '消息内容',
            dataIndex: 'message_content',
            key: 'message_content',
            width: 350,
            ellipsis: true
        },
        {
            title: '状态',
            dataIndex: 'status',
            key: 'status',
            width: 80,
            render: (status: string) => {
                const colors: Record<string, string> = {
                    handled: 'green', pending: 'gold', ignored: 'default', failed: 'red'
                };
                return <Tag color={colors[status] || 'default'}>{status}</Tag>;
            }
        }
    ];

    const tabItems: TabsProps['items'] = [
        {
            key: '1',
            label: '监控规则',
            children: (
                <>
                    <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between' }}>
                        <Button type="primary" icon={<PlusOutlined />} onClick={handleCreate}>
                            创建监控规则
                        </Button>
                        <Button icon={<ReloadOutlined />} onClick={fetchData}>刷新</Button>
                    </div>
                    <Table columns={columns} dataSource={monitors} rowKey="id" loading={loading} size="small" />
                </>
            ),
        },
        {
            key: '2',
            label: '命中记录',
            children: (
                <>
                    <div style={{ marginBottom: 16 }}>
                        <Button icon={<ReloadOutlined />} onClick={fetchHits}>刷新</Button>
                    </div>
                    <Table columns={hitColumns} dataSource={hits} rowKey="id" loading={hitsLoading} size="small" />
                </>
            ),
        },
    ];

    return (
        <div style={{ padding: 24 }}>
            <Tabs defaultActiveKey="1" items={tabItems} onChange={(key) => { if (key === '2') fetchHits(); }} />

            <Modal
                title={editingMonitor ? "编辑监控规则" : "创建监控规则"}
                open={isModalVisible}
                onOk={handleOk}
                onCancel={() => setIsModalVisible(false)}
                width={800}
                bodyStyle={{ maxHeight: '70vh', overflowY: 'auto' }}
            >
                <Form form={form} layout="vertical" initialValues={{ 
                    match_type: 'partial', 
                    marketing_mode: 'passive',
                    action_type: 'notify',
                    cooldown_seconds: 300,
                    score_weight: 10,
                    delay_min_seconds: 30,
                    delay_max_seconds: 180,
                    max_replies_per_day: 10,
                    similarity_threshold: 70,
                    ai_persona: 'helpful'
                }}>
                    
                    {/* ========== 营销模式选择 ========== */}
                    <Card size="small" title="🎯 营销模式" style={{ marginBottom: 16 }}>
                        <Form.Item name="marketing_mode" label="模式选择">
                            <Select onChange={(val) => setMarketingMode(val)}>
                                <Option value="passive">
                                    <EyeOutlined /> 被动式营销 - 只监听转发，不主动说话（安全）
                                </Option>
                                <Option value="active">
                                    <ThunderboltOutlined /> 主动式营销 - 直接在群里回复/私聊（高转化但有风险）
                                </Option>
                            </Select>
                        </Form.Item>
                        
                        {marketingMode === 'passive' && (
                            <Alert 
                                message="被动模式：监听账号不会在群里说话，只负责转发消息和录入线索。极度安全，适合长期潜伏。" 
                                type="info" 
                                showIcon 
                                style={{ marginTop: -8 }}
                            />
                        )}
                        {marketingMode === 'active' && (
                            <Alert 
                                message="主动模式：监听账号会直接回复用户或发起私聊。转化率高，但有被踢/封号风险，建议设置合理延迟。" 
                                type="warning" 
                                showIcon 
                                style={{ marginTop: -8 }}
                            />
                        )}
                    </Card>

                    {/* ========== 匹配规则 ========== */}
                    <Card size="small" title="🔍 匹配规则" style={{ marginBottom: 16 }}>
                        <Row gutter={16}>
                            <Col span={12}>
                                <Form.Item name="match_type" label="匹配方式">
                                    <Select onChange={(val) => setMatchType(val)}>
                                        <Option value="partial">模糊匹配 (包含即命中)</Option>
                                        <Option value="exact">精确匹配 (完全相等)</Option>
                                        <Option value="regex">正则表达式 (高级)</Option>
                                        <Option value="semantic">🧠 语义匹配 (AI两级过滤)</Option>
                                    </Select>
                                </Form.Item>
                            </Col>
                            <Col span={12}>
                                <Form.Item name="is_active" label="启用规则" valuePropName="checked" initialValue={true}>
                                    <Switch checkedChildren="启用" unCheckedChildren="禁用" />
                                </Form.Item>
                            </Col>
                        </Row>

                        {matchType !== 'semantic' && (
                            <Form.Item name="keyword" label="关键词" rules={[{ required: true, message: '请输入关键词' }]}>
                                <Input placeholder="输入关键词 (正则模式可用 | 分隔多个词，如: 价格|多少钱|费用)" />
                            </Form.Item>
                        )}

                        {matchType === 'semantic' && (
                            <>
                                <Form.Item 
                                    name="scenario_description" 
                                    label="业务场景描述" 
                                    rules={[{ required: true, message: '请描述业务场景' }]}
                                    tooltip="详细描述您想捕捉的用户需求场景，AI 会理解语义进行匹配"
                                >
                                    <TextArea 
                                        rows={3} 
                                        placeholder="例如：用户表现出购买加密货币的意向，正在询问价格、交易方式或寻找可靠的交易平台。" 
                                    />
                                </Form.Item>
                                
                                <Row gutter={16}>
                                    <Col span={16}>
                                        <Form.Item name="keyword" label="辅助关键词 (可选，用于Level1粗筛)">
                                            <Input placeholder="输入种子词，点击联想自动扩展" />
                                        </Form.Item>
                                    </Col>
                                    <Col span={8}>
                                        <Form.Item label=" ">
                                            <Button 
                                                icon={<BulbOutlined />} 
                                                loading={suggestLoading} 
                                                onClick={handleSuggest}
                                                block
                                            >
                                                AI 关键词联想
                                            </Button>
                                        </Form.Item>
                                    </Col>
                                </Row>

                                {suggestions.length > 0 && (
                                    <div style={{ marginBottom: 16, padding: 12, background: '#f5f5f5', borderRadius: 4 }}>
                                        <div style={{ marginBottom: 8, display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                            <span style={{ fontWeight: 500 }}>💡 AI 联想词 (点击添加):</span>
                                            <Button size="small" type="link" onClick={applyAllSuggestions}>
                                                全部应用到自动关键词库
                                            </Button>
                                        </div>
                                        <Space size={[4, 8]} wrap>
                                            {suggestions.map(s => (
                                                <Tag 
                                                    key={s} 
                                                    color="blue" 
                                                    style={{ cursor: 'pointer' }}
                                                    onClick={() => addSuggestionToKeywords(s)}
                                                >
                                                    {s} +
                                                </Tag>
                                            ))}
                                        </Space>
                                    </div>
                                )}

                                <Form.Item 
                                    name="auto_keywords" 
                                    label="自动关键词库 (JSON格式，用于Level1快速粗筛)" 
                                    tooltip="AI 联想生成的词会自动填入这里"
                                >
                                    <TextArea rows={2} placeholder='["价格","多少钱","购买","下单"]' />
                                </Form.Item>

                                <Form.Item name="similarity_threshold" label="语义相似度阈值 (Level2精判)">
                                    <Slider min={50} max={95} marks={{ 50: '宽松', 70: '标准', 90: '严格' }} />
                                </Form.Item>
                            </>
                        )}

                        <Form.Item name="target_groups" label="监控群组 (留空=所有群)">
                            <Input placeholder="@groupname, https://t.me/xxx, -100123456 (逗号分隔)" />
                        </Form.Item>
                    </Card>

                    {/* ========== 响应动作 ========== */}
                    <Card size="small" title="⚡ 响应动作" style={{ marginBottom: 16 }}>
                        <Form.Item name="action_type" label="触发动作">
                            <Select onChange={(val) => setActionType(val)}>
                                <Option value="notify">仅通知 (记录日志，不回复)</Option>
                                <Option value="auto_reply">AI 智能回复</Option>
                                <Option value="trigger_script">触发剧本</Option>
                            </Select>
                        </Form.Item>

                        {actionType === 'auto_reply' && (
                            <>
                                <Form.Item name="ai_persona" label="AI 人设预设">
                                    <Select>
                                        <Option value="helpful">🤝 热心群友 - 语气随意友善，简单分享经验</Option>
                                        <Option value="expert">🎓 行业老鸟 - 语气专业但不高傲，偶尔分享干货</Option>
                                        <Option value="curious">🤔 好奇新人 - 追问细节或附和别人观点</Option>
                                        <Option value="custom">✏️ 自定义 Prompt</Option>
                                    </Select>
                                </Form.Item>
                                
                                <Form.Item name="ai_reply_prompt" label="自定义 AI 提示词 (可选)">
                                    <TextArea rows={2} placeholder="覆盖预设人设，自定义 AI 回复风格..." />
                                </Form.Item>
                            </>
                        )}

                        {actionType === 'trigger_script' && (
                            <Form.Item name="reply_script_id" label="选择剧本" rules={[{ required: true }]}>
                                <Select placeholder="选择要执行的剧本">
                                    {scripts.map(s => (
                                        <Option key={s.id} value={s.id}>{s.name}</Option>
                                    ))}
                                </Select>
                            </Form.Item>
                        )}
                    </Card>

                    {/* ========== 主动营销配置 ========== */}
                    {marketingMode === 'active' && (
                        <Card size="small" title="🚀 主动营销设置" style={{ marginBottom: 16, borderColor: '#faad14' }}>
                            <Row gutter={16}>
                                <Col span={12}>
                                    <Form.Item name="reply_mode" label="回复方式">
                                        <Select>
                                            <Option value="group_reply">群内回复 (公开，截流效果好)</Option>
                                            <Option value="private_dm">私聊 (隐蔽，但易被举报)</Option>
                                        </Select>
                                    </Form.Item>
                                </Col>
                                <Col span={12}>
                                    <Form.Item name="max_replies_per_day" label="每日最大回复次数 (熔断)">
                                        <InputNumber min={1} max={100} style={{ width: '100%' }} />
                                    </Form.Item>
                                </Col>
                            </Row>
                            
                            <Form.Item label="随机延迟 (秒) - 模拟真人思考时间">
                                <Row gutter={16}>
                                    <Col span={12}>
                                        <Form.Item name="delay_min_seconds" noStyle>
                                            <InputNumber min={5} max={300} addonBefore="最小" style={{ width: '100%' }} />
                                        </Form.Item>
                                    </Col>
                                    <Col span={12}>
                                        <Form.Item name="delay_max_seconds" noStyle>
                                            <InputNumber min={10} max={600} addonBefore="最大" style={{ width: '100%' }} />
                                        </Form.Item>
                                    </Col>
                                </Row>
                            </Form.Item>

                            <Form.Item name="enable_account_rotation" valuePropName="checked">
                                <Checkbox>启用多账号轮询 (同群多号，随机选择一个回复)</Checkbox>
                            </Form.Item>
                        </Card>
                    )}

                    {/* ========== 被动功能 ========== */}
                    <Card size="small" title="📦 被动功能" style={{ marginBottom: 16 }}>
                        <Form.Item name="forward_target" label="消息转发目标">
                            <Input placeholder="https://t.me/my_channel 或 @admin_group" />
                        </Form.Item>
                        
                        <Row gutter={16}>
                            <Col span={12}>
                                <Form.Item name="auto_capture_lead" valuePropName="checked">
                                    <Checkbox>自动录入 CRM</Checkbox>
                                </Form.Item>
                            </Col>
                            <Col span={12}>
                                <Form.Item name="score_weight" label="评分权重">
                                    <InputNumber min={0} max={100} style={{ width: '100%' }} />
                                </Form.Item>
                            </Col>
                        </Row>
                        
                        <Form.Item name="cooldown_seconds" label="冷却时间 (秒)">
                            <InputNumber min={0} step={60} style={{ width: '100%' }} />
                        </Form.Item>
                    </Card>

                    <Form.Item name="description" label="备注">
                        <Input placeholder="规则说明 (可选)" />
                    </Form.Item>
                </Form>
            </Modal>
        </div>
    );
};

export default MonitorPage;
