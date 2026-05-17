import React, { useEffect, useState, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
    Layout, Input, Button, Tag, Avatar, Badge, Empty, message, Spin,
    Typography, notification, Switch, Space, Card
} from 'antd';
import {
    UserOutlined, SendOutlined, FireOutlined, RobotOutlined,
    ThunderboltOutlined, ReloadOutlined, CloseOutlined
} from '@ant-design/icons';
import {
    getLeads, getLead, sendLeadMessage, connectWebSocket,
    setLeadAiEnabled, regenerateLeadDraft, releaseLead,
    Lead, LeadInteraction
} from '../services/api';

const { Sider, Content } = Layout;
const { Search, TextArea } = Input;
const { Text } = Typography;

const Inbox: React.FC = () => {
    const [searchParams] = useSearchParams();
    const [leads, setLeads] = useState<Lead[]>([]);
    const [selectedLead, setSelectedLead] = useState<Lead | null>(null);
    const [messages, setMessages] = useState<LeadInteraction[]>([]);
    const [loading, setLoading] = useState(false);
    const [sending, setSending] = useState(false);
    const [inputText, setInputText] = useState('');
    const [draft, setDraft] = useState<string>('');
    const [regenerating, setRegenerating] = useState(false);
    const ws = useRef<WebSocket | null>(null);
    const messagesEndRef = useRef<HTMLDivElement>(null);
    const selectedLeadRef = useRef<Lead | null>(null);
    const wsConnectedRef = useRef<boolean>(false); // 防止 StrictMode 重复连接

    // 保持 selectedLead 的最新引用
    useEffect(() => {
        selectedLeadRef.current = selectedLead;
    }, [selectedLead]);

    const fetchLeads = useCallback(async () => {
        try {
            const data = await getLeads();
            setLeads(data);
        } catch (e) {
            // ignore
        }
    }, []);

    // WebSocket 连接只在组件挂载时建立一次
    useEffect(() => {
        fetchLeads();
        
        // 防止 StrictMode 下重复创建 WebSocket
        if (wsConnectedRef.current) {
            return;
        }
        wsConnectedRef.current = true;
        
        // Connect WS
        ws.current = connectWebSocket((data) => {
            if (data.type === 'new_message') {
                const currentLead = selectedLeadRef.current;
                if (currentLead && data.lead_id === currentLead.id) {
                    setMessages(prev => [...prev, data.message]);
                    scrollToBottom();
                }
                fetchLeads();
            } else if (data.type === 'high_intent_alert') {
                notification.open({
                    message: 'High Intent Alert!',
                    description: `User ${data.data.lead_name} shows ${data.data.intent} intent!`,
                    icon: <FireOutlined style={{ color: '#ff4d4f' }} />,
                    duration: 0,
                    onClick: () => {
                        console.log('Alert clicked', data.data);
                    }
                });
                fetchLeads();
            } else if (data.type === 'ai_draft') {
                // AI 副驾驶推送新草稿
                const currentLead = selectedLeadRef.current;
                if (currentLead && data.lead_id === currentLead.id) {
                    setDraft(data.draft || '');
                }
                fetchLeads();
            } else if (data.type === 'lead_claimed' || data.type === 'lead_released' || data.type === 'lead_ai_config') {
                fetchLeads();
                // 同步当前 selected 的最新状态
                const currentLead = selectedLeadRef.current;
                if (currentLead && data.lead_id === currentLead.id) {
                    getLead(currentLead.id).then(setSelectedLead).catch(() => {});
                }
            }
        });

        return () => {
            // 只有真正有连接时才关闭
            if (ws.current && ws.current.readyState !== WebSocket.CONNECTING) {
                ws.current.close();
            }
        };
        // eslint-disable-next-line react-hooks-exhaustive-deps
    }, []);

    useEffect(() => {
        if (selectedLead) {
            fetchMessages(selectedLead.id);
            setDraft(selectedLead.ai_draft || '');
        } else {
            setDraft('');
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedLead?.id]);

    // 通过 URL 参数 ?leadId=xxx 自动选中（从 CRM 跳过来）
    useEffect(() => {
        const leadIdParam = searchParams.get('leadId');
        if (!leadIdParam) return;
        const leadId = parseInt(leadIdParam, 10);
        if (isNaN(leadId)) return;
        if (selectedLead?.id === leadId) return;
        // 优先用列表里的，否则单独拉
        const inList = leads.find(l => l.id === leadId);
        if (inList) {
            setSelectedLead(inList);
        } else {
            getLead(leadId).then(setSelectedLead).catch(() => {});
        }
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [searchParams, leads.length]);

    const fetchMessages = async (leadId: number) => {
        setLoading(true);
        try {
            const lead = await getLead(leadId);
            setMessages(lead.interactions || []);
            // 同步最新的 lead 元数据（接管状态/草稿）
            setSelectedLead(prev => prev ? { ...prev, ...lead } : lead);
            setDraft(lead.ai_draft || '');
            scrollToBottom();
        } catch (e) {
            message.error('加载消息失败');
        } finally {
            setLoading(false);
        }
    };

    const handleToggleAI = async (enabled: boolean) => {
        if (!selectedLead) return;
        try {
            const updated = await setLeadAiEnabled(selectedLead.id, enabled);
            setSelectedLead(prev => prev ? { ...prev, ...updated } : prev);
            message.success(`AI ${enabled ? '已开启' : '已关闭'}`);
        } catch (e: any) {
            message.error(e?.response?.data?.detail || '切换失败');
        }
    };

    const handleRegenerateDraft = async () => {
        if (!selectedLead) return;
        setRegenerating(true);
        try {
            const updated = await regenerateLeadDraft(selectedLead.id);
            setSelectedLead(prev => prev ? { ...prev, ...updated } : prev);
            setDraft(updated.ai_draft || '');
            message.success('已重新生成草稿');
        } catch (e: any) {
            message.error(e?.response?.data?.detail || '生成失败');
        } finally {
            setRegenerating(false);
        }
    };

    const handleUseDraft = () => {
        if (!draft) return;
        setInputText(draft);
    };

    const handleDismissDraft = () => {
        setDraft('');
    };

    const handleRelease = async () => {
        if (!selectedLead) return;
        try {
            const updated = await releaseLead(selectedLead.id);
            setSelectedLead(prev => prev ? { ...prev, ...updated } : prev);
            message.success('已释放线索，AI 恢复自动回复');
        } catch (e: any) {
            message.error(e?.response?.data?.detail || '释放失败');
        }
    };

    const handleSend = async () => {
        if (!selectedLead || !inputText.trim()) return;
        setSending(true);
        try {
            await sendLeadMessage(selectedLead.id, inputText);
            setInputText('');
            // Optimistically append or wait for WS? 
            // Better to wait or refetch, but for UX append local
            const tempMsg: any = {
                id: Date.now(),
                direction: 'outbound',
                content: inputText,
                created_at: new Date().toISOString(),
                message_type: 'text'
            };
            setMessages(prev => [...prev, tempMsg]);
            scrollToBottom();
        } catch (e) {
            message.error('发送失败');
        } finally {
            setSending(false);
        }
    };

    const scrollToBottom = () => {
        setTimeout(() => {
            messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
        }, 100);
    };

    return (
        <Layout style={{ height: 'calc(100vh - 64px)', background: '#fff' }}>
            <Sider width={300} theme="light" style={{ borderRight: '1px solid #f0f0f0' }}>
                <div style={{ padding: 16, borderBottom: '1px solid #f0f0f0' }}>
                    <Search placeholder="搜索联系人..." />
                </div>
                <div style={{ height: 'calc(100% - 65px)', overflow: 'auto' }}>
                    {leads.map(item => (
                        <div 
                            key={item.id}
                            style={{ 
                                padding: 16, 
                                cursor: 'pointer', 
                                background: selectedLead?.id === item.id ? '#e6f7ff' : 'transparent',
                                borderBottom: '1px solid #f0f0f0',
                                display: 'flex',
                                alignItems: 'flex-start',
                                gap: 12
                            }}
                            onClick={() => setSelectedLead(item)}
                        >
                            <Avatar icon={<UserOutlined />} />
                            <div style={{ flex: 1, minWidth: 0 }}>
                                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                                    <Text ellipsis style={{ maxWidth: 120 }}>
                                        {item.first_name || item.username || `User ${item.telegram_user_id}`}
                                    </Text>
                                    <Text type="secondary" style={{ fontSize: 12 }}>
                                        {new Date(item.last_interaction_at).toLocaleTimeString([], {hour: '2-digit', minute:'2-digit'})}
                                    </Text>
                                </div>
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                                    <Text ellipsis type="secondary" style={{ maxWidth: 180 }}>
                                        {item.notes || "点击查看消息"}
                                    </Text>
                                    <div style={{ display: 'flex', gap: 4 }}>
                                        {item.tags_json && JSON.parse(item.tags_json).some((t: string) => t.includes('intent:inquiry') || t.includes('intent:purchase')) && (
                                            <FireOutlined style={{ color: '#ff4d4f' }} />
                                        )}
                                        <Badge status={item.status === 'new' ? 'processing' : 'default'} />
                                    </div>
                                </div>
                            </div>
                        </div>
                    ))}
                </div>
            </Sider>
            <Content style={{ display: 'flex', flexDirection: 'column' }}>
                {selectedLead ? (
                    <>
                        {/* Header */}
                        <div style={{ padding: '16px 24px', borderBottom: '1px solid #f0f0f0', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                            <div>
                                <Text strong style={{ fontSize: 16 }}>
                                    {selectedLead.first_name || selectedLead.username || selectedLead.telegram_user_id}
                                </Text>
                                <div>
                                    <Tag color="blue">{selectedLead.status}</Tag>
                                    {JSON.parse(selectedLead.tags_json || '[]').map((tag: string) => (
                                        <Tag key={tag}>{tag}</Tag>
                                    ))}
                                    {selectedLead.assigned_to_user_id != null && (
                                        <Tag color="processing">接管中</Tag>
                                    )}
                                </div>
                            </div>
                            <Space>
                                <Space size={4}>
                                    <RobotOutlined />
                                    <Text type="secondary">AI 副驾驶</Text>
                                    <Switch
                                        size="small"
                                        checked={selectedLead.ai_enabled ?? true}
                                        onChange={handleToggleAI}
                                    />
                                </Space>
                                {selectedLead.assigned_to_user_id != null && (
                                    <Button size="small" onClick={handleRelease}>
                                        释放线索
                                    </Button>
                                )}
                            </Space>
                        </div>

                        {/* Messages Area */}
                        <div style={{ flex: 1, padding: 24, overflow: 'auto', background: '#f5f5f5' }}>
                            {loading ? <Spin /> : (
                                <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
                                    {messages.map(msg => {
                                        const isMe = msg.direction === 'outbound';
                                        return (
                                            <div key={msg.id} style={{ alignSelf: isMe ? 'flex-end' : 'flex-start', maxWidth: '70%' }}>
                                                <div style={{ 
                                                    background: isMe ? '#1890ff' : '#fff', 
                                                    color: isMe ? '#fff' : '#000',
                                                    padding: '8px 12px',
                                                    borderRadius: 8,
                                                    boxShadow: '0 1px 2px rgba(0,0,0,0.1)'
                                                }}>
                                                    {msg.content}
                                                </div>
                                                <div style={{ fontSize: 12, color: '#999', marginTop: 4, textAlign: isMe ? 'right' : 'left' }}>
                                                    {new Date(msg.created_at).toLocaleString()}
                                                </div>
                                            </div>
                                        );
                                    })}
                                    <div ref={messagesEndRef} />
                                </div>
                            )}
                        </div>

                        {/* AI 副驾驶建议草稿 */}
                        {draft && (
                            <Card
                                size="small"
                                style={{
                                    margin: '8px 16px 0',
                                    background: '#f0f5ff',
                                    border: '1px solid #adc6ff',
                                }}
                                bodyStyle={{ padding: '8px 12px' }}
                            >
                                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', gap: 8 }}>
                                    <div style={{ flex: 1 }}>
                                        <Space size={4} style={{ marginBottom: 4 }}>
                                            <RobotOutlined style={{ color: '#1677ff' }} />
                                            <Text strong style={{ color: '#1677ff' }}>AI 建议草稿</Text>
                                        </Space>
                                        <div style={{ whiteSpace: 'pre-wrap', color: '#262626' }}>{draft}</div>
                                    </div>
                                    <Space direction="vertical" size={4}>
                                        <Button size="small" type="primary" icon={<ThunderboltOutlined />} onClick={handleUseDraft}>
                                            使用
                                        </Button>
                                        <Button size="small" icon={<ReloadOutlined />} loading={regenerating} onClick={handleRegenerateDraft}>
                                            改写
                                        </Button>
                                        <Button size="small" icon={<CloseOutlined />} onClick={handleDismissDraft}>
                                            忽略
                                        </Button>
                                    </Space>
                                </div>
                            </Card>
                        )}

                        {/* Input Area */}
                        <div style={{ padding: 16, background: '#fff', borderTop: '1px solid #f0f0f0' }}>
                            <div style={{ display: 'flex', gap: 16 }}>
                                <TextArea
                                    rows={3}
                                    value={inputText}
                                    onChange={e => setInputText(e.target.value)}
                                    placeholder="输入消息..."
                                    onPressEnter={(e) => {
                                        if (!e.shiftKey) {
                                            e.preventDefault();
                                            handleSend();
                                        }
                                    }}
                                />
                                <Button
                                    type="primary"
                                    icon={<SendOutlined />}
                                    style={{ height: 'auto' }}
                                    onClick={handleSend}
                                    loading={sending}
                                >
                                    发送
                                </Button>
                            </div>
                        </div>
                    </>
                ) : (
                    <Empty description="选择一个联系人开始聊天" style={{ marginTop: 100 }} />
                )}
            </Content>
        </Layout>
    );
};

export default Inbox;
