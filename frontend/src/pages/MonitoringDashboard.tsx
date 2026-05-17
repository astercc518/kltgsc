import React, { useEffect, useRef, useState } from 'react';
import {
    Alert,
    Badge,
    Button,
    Card,
    Col,
    Progress,
    Row,
    Statistic,
    Table,
    Tag,
    Tooltip,
    Typography,
} from 'antd';
import {
    CheckCircleOutlined,
    CloseCircleOutlined,
    ExclamationCircleOutlined,
    GlobalOutlined,
    ReloadOutlined,
    RobotOutlined,
    SafetyOutlined,
    UserOutlined,
    WarningOutlined,
} from '@ant-design/icons';
import { getMonitoringStats, triggerManualCheck, MonitoringStats } from '../services/api';

const { Title, Text } = Typography;

const REFRESH_INTERVAL = 30_000; // 30 秒自动刷新

const statusColor: Record<string, string> = {
    active: '#52c41a',
    banned: '#ff4d4f',
    spam_block: '#fa8c16',
    stale: '#d9d9d9',
    error: '#ff4d4f',
};

const MonitoringDashboard: React.FC = () => {
    const [stats, setStats] = useState<MonitoringStats | null>(null);
    const [loading, setLoading] = useState(false);
    const [triggering, setTriggering] = useState(false);
    const [lastRefresh, setLastRefresh] = useState<Date | null>(null);
    const [countdown, setCountdown] = useState(REFRESH_INTERVAL / 1000);
    const timerRef = useRef<number | null>(null);
    const countdownRef = useRef<number | null>(null);

    const fetchStats = async () => {
        setLoading(true);
        try {
            const data = await getMonitoringStats();
            setStats(data);
            setLastRefresh(new Date());
            setCountdown(REFRESH_INTERVAL / 1000);
        } catch (e) {
            console.error('Failed to fetch monitoring stats', e);
        } finally {
            setLoading(false);
        }
    };

    const handleTrigger = async () => {
        setTriggering(true);
        try {
            await triggerManualCheck();
            // 5 秒后刷新，让任务有时间跑
            setTimeout(fetchStats, 5000);
        } finally {
            setTriggering(false);
        }
    };

    useEffect(() => {
        fetchStats();
        timerRef.current = window.setInterval(fetchStats, REFRESH_INTERVAL);
        countdownRef.current = window.setInterval(() => {
            setCountdown(c => (c <= 1 ? REFRESH_INTERVAL / 1000 : c - 1));
        }, 1000);
        return () => {
            if (timerRef.current) clearInterval(timerRef.current);
            if (countdownRef.current) clearInterval(countdownRef.current);
        };
    }, []);

    if (!stats) {
        return (
            <div style={{ textAlign: 'center', padding: 40 }}>
                <ReloadOutlined spin style={{ fontSize: 32 }} />
                <div style={{ marginTop: 8 }}>加载监控数据...</div>
            </div>
        );
    }

    const { accounts, proxies, roles, warmup, alerts } = stats;
    const proxyHealthColor =
        proxies.active_rate >= 80 ? '#52c41a' : proxies.active_rate >= 50 ? '#fa8c16' : '#ff4d4f';

    // 账号状态饼图数据（用进度条代替）
    const acctRows = [
        { key: 'active', label: '正常', count: accounts.active, color: '#52c41a' },
        { key: 'stale', label: '失活', count: accounts.stale, color: '#d9d9d9' },
        { key: 'spam_block', label: '受限', count: accounts.spam_block, color: '#fa8c16' },
        { key: 'banned', label: '封号', count: accounts.banned, color: '#ff4d4f' },
        { key: 'error', label: '错误', count: accounts.error, color: '#ff7a45' },
    ].filter(r => r.count > 0);

    const countryColumns = [
        { title: '国家', dataIndex: 'country', key: 'country', render: (v: string) => <><GlobalOutlined style={{ marginRight: 4 }} />{v}</> },
        { title: '可用代理', dataIndex: 'count', key: 'count', render: (v: number) => <Badge count={v} color="#1677ff" showZero /> },
    ];

    return (
        <div style={{ padding: '0 4px' }}>
            {/* 头部 */}
            <Row align="middle" justify="space-between" style={{ marginBottom: 16 }}>
                <Col>
                    <Title level={4} style={{ margin: 0 }}>
                        <SafetyOutlined style={{ marginRight: 8, color: '#1677ff' }} />
                        实时监控看板
                    </Title>
                    {lastRefresh && (
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            上次刷新 {lastRefresh.toLocaleTimeString()}，{countdown}s 后自动刷新
                        </Text>
                    )}
                </Col>
                <Col>
                    <Button
                        icon={<ReloadOutlined />}
                        loading={loading}
                        onClick={fetchStats}
                        style={{ marginRight: 8 }}
                    >
                        刷新
                    </Button>
                    <Button
                        type="primary"
                        icon={<CheckCircleOutlined />}
                        loading={triggering}
                        onClick={handleTrigger}
                    >
                        立即检测
                    </Button>
                </Col>
            </Row>

            {/* 告警横幅 */}
            {alerts.length > 0 && (
                <div style={{ marginBottom: 16 }}>
                    {alerts.map((a, i) => (
                        <Alert
                            key={i}
                            type={a.level === 'critical' ? 'error' : 'warning'}
                            message={a.msg}
                            showIcon
                            style={{ marginBottom: 6 }}
                            icon={a.level === 'critical' ? <CloseCircleOutlined /> : <WarningOutlined />}
                        />
                    ))}
                </div>
            )}

            {/* 核心指标卡片 */}
            <Row gutter={16} style={{ marginBottom: 16 }}>
                <Col xs={12} sm={6}>
                    <Card size="small">
                        <Statistic
                            title="代理存活率"
                            value={proxies.active_rate}
                            suffix="%"
                            precision={1}
                            valueStyle={{ color: proxyHealthColor }}
                            prefix={proxies.active_rate >= 80
                                ? <CheckCircleOutlined />
                                : <ExclamationCircleOutlined />}
                        />
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            {proxies.active} / {proxies.total} 可用
                        </Text>
                    </Card>
                </Col>
                <Col xs={12} sm={6}>
                    <Card size="small">
                        <Statistic
                            title="账号总数"
                            value={accounts.total}
                            prefix={<UserOutlined />}
                            valueStyle={{ color: '#1677ff' }}
                        />
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            活跃 {accounts.active} · 封号 {accounts.banned}
                        </Text>
                    </Card>
                </Col>
                <Col xs={12} sm={6}>
                    <Card size="small">
                        <Statistic
                            title="近1h封号/限制"
                            value={accounts.banned_1h}
                            valueStyle={{ color: accounts.banned_1h >= 5 ? '#ff4d4f' : '#52c41a' }}
                            prefix={accounts.banned_1h >= 5 ? <WarningOutlined /> : <CheckCircleOutlined />}
                        />
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            spam_block {accounts.spam_block}
                        </Text>
                    </Card>
                </Col>
                <Col xs={12} sm={6}>
                    <Card size="small">
                        <Statistic
                            title="养号任务运行"
                            value={warmup.running}
                            prefix={<RobotOutlined />}
                            valueStyle={{ color: warmup.running > 0 ? '#52c41a' : '#d9d9d9' }}
                        />
                        <Text type="secondary" style={{ fontSize: 12 }}>
                            {warmup.running > 0 ? '有任务进行中' : '当前无养号任务'}
                        </Text>
                    </Card>
                </Col>
            </Row>

            <Row gutter={16}>
                {/* 账号状态分布 */}
                <Col xs={24} sm={12} lg={8}>
                    <Card title="账号状态分布" size="small" style={{ marginBottom: 16 }}>
                        {acctRows.map(r => (
                            <div key={r.key} style={{ marginBottom: 10 }}>
                                <Row justify="space-between" style={{ marginBottom: 2 }}>
                                    <Text style={{ fontSize: 12 }}>
                                        <span style={{
                                            display: 'inline-block', width: 8, height: 8,
                                            borderRadius: '50%', background: r.color, marginRight: 6
                                        }} />
                                        {r.label}
                                    </Text>
                                    <Text style={{ fontSize: 12 }}>{r.count}</Text>
                                </Row>
                                <Progress
                                    percent={Math.round(r.count / accounts.total * 100)}
                                    strokeColor={r.color}
                                    showInfo={false}
                                    size="small"
                                />
                            </div>
                        ))}
                        {accounts.total === 0 && <Text type="secondary">暂无账号</Text>}
                    </Card>
                </Col>

                {/* 代理健康 */}
                <Col xs={24} sm={12} lg={8}>
                    <Card title="代理健康" size="small" style={{ marginBottom: 16 }}>
                        <div style={{ textAlign: 'center', marginBottom: 12 }}>
                            <Progress
                                type="circle"
                                percent={proxies.active_rate}
                                strokeColor={proxyHealthColor}
                                size={100}
                                format={p => <span style={{ fontSize: 16, fontWeight: 600 }}>{p}%</span>}
                            />
                        </div>
                        <Row gutter={8}>
                            <Col span={12} style={{ textAlign: 'center' }}>
                                <Tag color="success" style={{ fontSize: 13, padding: '2px 8px' }}>
                                    活跃 {proxies.active}
                                </Tag>
                            </Col>
                            <Col span={12} style={{ textAlign: 'center' }}>
                                <Tag color="error" style={{ fontSize: 13, padding: '2px 8px' }}>
                                    死亡 {proxies.dead}
                                </Tag>
                            </Col>
                        </Row>
                    </Card>
                </Col>

                {/* 战斗角色分布 */}
                <Col xs={24} sm={12} lg={8}>
                    <Card title="战斗角色分布" size="small" style={{ marginBottom: 16 }}>
                        {[
                            { key: 'listener', label: 'Listener (侦察)', count: roles.listener, color: '#1677ff', warn: roles.listener === 0 },
                            { key: 'actor', label: 'Actor (演员)', count: roles.actor, color: '#52c41a', warn: roles.actor < 3 },
                            { key: 'cannon', label: 'Cannon (炮灰)', count: roles.cannon, color: '#8c8c8c', warn: false },
                            { key: 'sniper', label: 'Sniper (狙击)', count: roles.sniper, color: '#722ed1', warn: false },
                        ].map(r => (
                            <Row key={r.key} justify="space-between" style={{ marginBottom: 8 }}>
                                <Text style={{ fontSize: 13 }}>
                                    <span style={{
                                        display: 'inline-block', width: 8, height: 8,
                                        borderRadius: '50%', background: r.color, marginRight: 6
                                    }} />
                                    {r.label}
                                </Text>
                                <Tooltip title={r.warn ? '数量不足，建议补充' : undefined}>
                                    <Badge
                                        count={r.count}
                                        showZero
                                        color={r.warn ? '#ff4d4f' : r.color}
                                    />
                                </Tooltip>
                            </Row>
                        ))}
                    </Card>
                </Col>

                {/* 代理国家分布 */}
                {proxies.top_countries.length > 0 && (
                    <Col xs={24} sm={12} lg={12}>
                        <Card title="活跃代理国家分布 Top 5" size="small">
                            <Table
                                dataSource={proxies.top_countries}
                                columns={countryColumns}
                                pagination={false}
                                size="small"
                                rowKey="country"
                            />
                        </Card>
                    </Col>
                )}
            </Row>
        </div>
    );
};

export default MonitoringDashboard;
