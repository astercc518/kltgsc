import React, { useEffect, useState } from 'react';
import {
    Card, Row, Col, Statistic, Segmented, Select, Table, Tag, Spin, Alert, Space, Typography,
} from 'antd';
import {
    DollarCircleOutlined, ThunderboltOutlined, ApiOutlined,
} from '@ant-design/icons';
import {
    ResponsiveContainer, LineChart, Line, XAxis, YAxis, Tooltip as RTooltip, CartesianGrid,
    PieChart, Pie, Cell, Legend,
} from 'recharts';
import {
    getUsageSummary, getUsageTimeline, getUsageTop,
    UsageSummary, UsageTimelinePoint, UsageTopItem,
} from '../../services/api';

const { Text } = Typography;

const PIE_COLORS = [
    '#1677ff', '#52c41a', '#faad14', '#eb2f96', '#722ed1',
    '#13c2c2', '#fa541c', '#a0d911', '#2f54eb', '#fa8c16',
];

const SOURCE_LABEL: Record<string, string> = {
    chat_reply: '私聊回复',
    intent_analyze: '意图识别',
    qa_extract: 'QA 抽取',
    embedding_backfill: 'KB 向量回填',
    embedding_runtime: 'KB 实时检索',
    embedding_import: '文档导入向量',
    shill_dispatch: '群推话术',
    shill_free_chat: '群推闲聊',
    director_reactive: 'Director 被动回复',
    director_proactive: 'Director 主动发言',
    intercept_reply: '关键词拦截回复',
    keyword_match_judge: '关键词意图判别',
    keyword_expand: '关键词扩充',
    semantic_match: '语义匹配',
    user_analysis: '用户画像',
    group_analysis: '群组分析',
    opener: '开场白生成',
    smart_reply: '智能回复',
    script_generation: '剧本生成',
    content_rewrite: '内容改写',
    kb_generation: '知识库生成',
    risk_detection: '风险检测',
    smoke_test: '冒烟测试',
    unknown: '未分类',
};

const fmtUsd = (n: number) =>
    n < 0.01 && n > 0 ? `$${n.toExponential(2)}` : `$${n.toFixed(4)}`;

const UsageDashboard: React.FC = () => {
    const [days, setDays] = useState<number>(30);
    const [summary, setSummary] = useState<UsageSummary | null>(null);
    const [timeline, setTimeline] = useState<UsageTimelinePoint[]>([]);
    const [topDim, setTopDim] = useState<'account' | 'persona' | 'chat'>('account');
    const [topItems, setTopItems] = useState<UsageTopItem[]>([]);
    const [loading, setLoading] = useState(false);
    const [topLoading, setTopLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const loadCore = async () => {
        setLoading(true);
        setError(null);
        try {
            const [s, t] = await Promise.all([
                getUsageSummary(days),
                getUsageTimeline(days, 'day'),
            ]);
            setSummary(s);
            setTimeline(t.points);
        } catch (e: any) {
            setError(e?.response?.data?.detail || e?.message || '加载失败');
        } finally {
            setLoading(false);
        }
    };

    const loadTop = async () => {
        setTopLoading(true);
        try {
            const r = await getUsageTop(topDim, Math.min(days, 30), 10);
            setTopItems(r.items);
        } catch (e) {
            setTopItems([]);
        } finally {
            setTopLoading(false);
        }
    };

    useEffect(() => { loadCore(); }, [days]);
    useEffect(() => { loadTop(); }, [topDim, days]);

    const timelineData = timeline.map((p) => ({
        date: p.ts ? p.ts.slice(5, 10) : '',
        cost: Number(p.cost_usd.toFixed(6)),
        calls: p.calls,
    }));

    const sourcePieData = (summary?.by_source || []).map((b) => ({
        name: SOURCE_LABEL[b.source || ''] || b.source || '未知',
        value: Number(b.cost_usd.toFixed(6)),
    }));
    const modelPieData = (summary?.by_model || []).map((b) => ({
        name: b.model || '未知',
        value: Number(b.cost_usd.toFixed(6)),
    }));

    const topColumns = [
        {
            title: topDim === 'account' ? '账号' : topDim === 'persona' ? 'Persona' : '群组/对话',
            dataIndex: 'name',
            key: 'name',
            render: (v: string | null, r: UsageTopItem) => v || (r.id ? `#${r.id}` : '-'),
        },
        {
            title: '费用 (USD)',
            dataIndex: 'cost_usd',
            key: 'cost_usd',
            render: (v: number) => <Text strong>{fmtUsd(v)}</Text>,
            sorter: (a: UsageTopItem, b: UsageTopItem) => a.cost_usd - b.cost_usd,
        },
        { title: '调用次数', dataIndex: 'calls', key: 'calls' },
        { title: '输入 tokens', dataIndex: 'input_tokens', key: 'input_tokens' },
        { title: '输出 tokens', dataIndex: 'output_tokens', key: 'output_tokens' },
    ];

    return (
        <Spin spinning={loading}>
            {error && (
                <Alert
                    type="error"
                    message="加载费用数据失败"
                    description={error}
                    showIcon
                    style={{ marginBottom: 16 }}
                    closable
                />
            )}

            <Card
                size="small"
                style={{ marginBottom: 16 }}
                extra={
                    <Space>
                        <span>统计窗口：</span>
                        <Segmented
                            value={days}
                            onChange={(v) => setDays(Number(v))}
                            options={[
                                { label: '7 天', value: 7 },
                                { label: '30 天', value: 30 },
                                { label: '90 天', value: 90 },
                            ]}
                        />
                    </Space>
                }
            >
                <Row gutter={16}>
                    <Col xs={12} md={6}>
                        <Statistic
                            title="今日费用"
                            value={summary?.today_cost_usd || 0}
                            precision={4}
                            prefix={<DollarCircleOutlined />}
                            suffix="USD"
                        />
                    </Col>
                    <Col xs={12} md={6}>
                        <Statistic
                            title={`近 ${days} 天费用`}
                            value={summary?.total_cost_usd || 0}
                            precision={4}
                            prefix={<DollarCircleOutlined />}
                            suffix="USD"
                        />
                    </Col>
                    <Col xs={12} md={6}>
                        <Statistic
                            title={`近 ${days} 天调用`}
                            value={summary?.total_calls || 0}
                            prefix={<ApiOutlined />}
                            suffix="次"
                        />
                    </Col>
                    <Col xs={12} md={6}>
                        <Statistic
                            title="累计费用"
                            value={summary?.all_time_cost_usd || 0}
                            precision={4}
                            prefix={<DollarCircleOutlined />}
                            suffix="USD"
                        />
                    </Col>
                </Row>
                <div style={{ marginTop: 12, color: '#999', fontSize: 12 }}>
                    输入 tokens: {summary?.total_input_tokens?.toLocaleString() || 0} ·
                    输出 tokens: {summary?.total_output_tokens?.toLocaleString() || 0} ·
                    费用按本地价格表（pricing.py）按 token 估算，可能与 GCP 真实账单有 ±5% 误差
                </div>
            </Card>

            <Card title="费用趋势" size="small" style={{ marginBottom: 16 }}>
                <div style={{ width: '100%', height: 260 }}>
                    <ResponsiveContainer>
                        <LineChart data={timelineData} margin={{ top: 10, right: 20, left: 0, bottom: 0 }}>
                            <CartesianGrid strokeDasharray="3 3" />
                            <XAxis dataKey="date" />
                            <YAxis />
                            <RTooltip />
                            <Legend />
                            <Line type="monotone" dataKey="cost" name="费用 (USD)" stroke="#1677ff" strokeWidth={2} dot={false} />
                            <Line type="monotone" dataKey="calls" name="调用次数" stroke="#52c41a" strokeWidth={1} dot={false} yAxisId={0} />
                        </LineChart>
                    </ResponsiveContainer>
                </div>
            </Card>

            <Row gutter={16}>
                <Col xs={24} md={12}>
                    <Card title="按调用来源" size="small" style={{ marginBottom: 16 }}>
                        <div style={{ width: '100%', height: 280 }}>
                            <ResponsiveContainer>
                                <PieChart>
                                    <Pie
                                        data={sourcePieData}
                                        dataKey="value"
                                        nameKey="name"
                                        outerRadius={90}
                                        label={(e: any) => e.name}
                                    >
                                        {sourcePieData.map((_, i) => (
                                            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                                        ))}
                                    </Pie>
                                    <RTooltip formatter={(v: any) => fmtUsd(Number(v))} />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    </Card>
                </Col>
                <Col xs={24} md={12}>
                    <Card title="按模型" size="small" style={{ marginBottom: 16 }}>
                        <div style={{ width: '100%', height: 280 }}>
                            <ResponsiveContainer>
                                <PieChart>
                                    <Pie
                                        data={modelPieData}
                                        dataKey="value"
                                        nameKey="name"
                                        outerRadius={90}
                                        label={(e: any) => e.name}
                                    >
                                        {modelPieData.map((_, i) => (
                                            <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                                        ))}
                                    </Pie>
                                    <RTooltip formatter={(v: any) => fmtUsd(Number(v))} />
                                </PieChart>
                            </ResponsiveContainer>
                        </div>
                    </Card>
                </Col>
            </Row>

            <Card
                title="消耗 Top 10"
                size="small"
                extra={
                    <Select
                        value={topDim}
                        onChange={(v) => setTopDim(v as any)}
                        style={{ width: 120 }}
                        options={[
                            { label: '按账号', value: 'account' },
                            { label: '按 Persona', value: 'persona' },
                            { label: '按群组', value: 'chat' },
                        ]}
                    />
                }
            >
                <Table
                    columns={topColumns}
                    dataSource={topItems}
                    rowKey={(r) => String(r.id ?? Math.random())}
                    loading={topLoading}
                    pagination={false}
                    size="small"
                />
            </Card>
        </Spin>
    );
};

export default UsageDashboard;
