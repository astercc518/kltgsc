import React, { useEffect, useState } from 'react';
import { Card, Typography, Space, Spin, Alert, Button, Row, Col, Statistic, Table, Tag, Progress, Tabs } from 'antd';
import { 
    CheckCircleOutlined, 
    CloseCircleOutlined, 
    ReloadOutlined,
    UserOutlined,
    MessageOutlined,
    TeamOutlined,
    ClockCircleOutlined,
    ThunderboltOutlined,
    AimOutlined,
    RocketOutlined,
    RadarChartOutlined
} from '@ant-design/icons';
import api from '../services/api';
import { 
    BarChart, 
    Bar, 
    XAxis, 
    YAxis, 
    CartesianGrid, 
    Tooltip, 
    Legend, 
    ResponsiveContainer,
    LineChart,
    Line
} from 'recharts';
import { useQueryClient } from '@tanstack/react-query';
import { 
    useHealthCheck, 
    useOverviewStats, 
    useDailyTrend, 
    useOperationLogs,
    OverviewStats,
    DailyTrendData
} from '../hooks';
import { queryKeys } from '../lib/queryClient';

const { Title, Paragraph, Text } = Typography;

const Dashboard: React.FC = () => {
  const queryClient = useQueryClient();
  
  // 战略数据状态
  const [roleStats, setRoleStats] = useState<any>({});
  const [campaignStats, setCampaignStats] = useState<any[]>([]);
  const [sourceGroupStats, setSourceGroupStats] = useState<any>(null);
  
  // 使用 React Query hooks
  const { 
    data: healthStatus, 
    isLoading: healthLoading,
    refetch: refetchHealth 
  } = useHealthCheck();
  
  const { 
    data: stats, 
    isLoading: statsLoading,
    refetch: refetchStats 
  } = useOverviewStats();
  
  const { 
    data: trendData = [], 
    isLoading: trendLoading,
    refetch: refetchTrend 
  } = useDailyTrend(7);
  
  const { 
    data: logs = [], 
    isLoading: logsLoading,
    refetch: refetchLogs 
  } = useOperationLogs(0, 10);
  
  const loading = healthLoading || statsLoading || trendLoading || logsLoading;
  const error = !healthStatus && !healthLoading ? '无法连接到后端服务' : null;

  // 获取战略数据
  const fetchStrategicData = async () => {
    try {
      const [rolesRes, campaignsRes, sourceRes] = await Promise.all([
        api.get('/workflow/roles/stats').catch(() => ({ data: {} })),
        api.get('/campaigns/', { params: { limit: 5 } }).catch(() => ({ data: [] })),
        api.get('/source-groups/stats/summary').catch(() => ({ data: null }))
      ]);
      setRoleStats(rolesRes.data);
      setCampaignStats(campaignsRes.data);
      setSourceGroupStats(sourceRes.data);
    } catch (e) {
      console.error('获取战略数据失败');
    }
  };

  useEffect(() => {
    fetchStrategicData();
  }, []);

  const handleRefresh = () => {
    refetchHealth();
    refetchStats();
    refetchTrend();
    refetchLogs();
    fetchStrategicData();
  };

  // 战斗角色颜色
  const roleColors: Record<string, string> = {
    cannon: '#ff4d4f',
    scout: '#1890ff',
    actor: '#722ed1',
    sniper: '#faad14'
  };

  const roleNames: Record<string, string> = {
    cannon: '炮灰组',
    scout: '侦察组',
    actor: '演员组',
    sniper: '狙击组'
  };

  const logColumns = [
      { title: '时间', dataIndex: 'created_at', key: 'time', render: (t: string) => new Date(t).toLocaleString() },
      { title: '操作', dataIndex: 'action', key: 'action', render: (t: string) => <Tag color="blue">{t}</Tag> },
      { title: '用户', dataIndex: 'username', key: 'user' },
      { title: '状态', dataIndex: 'status', key: 'status', render: (t: string) => <Tag color={t === 'success' ? 'green' : 'red'}>{t}</Tag> },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 20 }}>
          <Title level={2} style={{ margin: 0 }}>Dashboard</Title>
          <Button icon={<ReloadOutlined />} onClick={handleRefresh} loading={loading}>刷新</Button>
      </div>

      {/* KPI Cards */}
      {stats && (
          <Row gutter={16} style={{ marginBottom: 24 }}>
              <Col span={6}>
                  <Card>
                      <Statistic 
                        title="活跃账号" 
                        value={stats.accounts.active} 
                        suffix={`/ ${stats.accounts.total}`} 
                        prefix={<UserOutlined />}
                        styles={{ content: { color: '#3f8600' } }}
                      />
                      <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
                          存活率: {stats.accounts.survival_rate}%
                      </div>
                  </Card>
              </Col>
              <Col span={6}>
                  <Card>
                      <Statistic 
                        title="今日发送" 
                        value={stats.messages.today_sent} 
                        prefix={<MessageOutlined />}
                        styles={{ content: { color: '#1890ff' } }}
                      />
                  </Card>
              </Col>
              <Col span={6}>
                  <Card>
                      <Statistic 
                        title="总线索数" 
                        value={stats.leads.total} 
                        prefix={<TeamOutlined />}
                      />
                      <div style={{ marginTop: 8, fontSize: 12, color: '#999' }}>
                          今日新增: +{stats.leads.new_today}
                      </div>
                  </Card>
              </Col>
              <Col span={6}>
                  <Card>
                      <Statistic 
                        title="系统状态" 
                        value={healthStatus?.status === 'ok' ? '正常' : '异常'} 
                        prefix={<CheckCircleOutlined />}
                        styles={{ content: { color: healthStatus?.status === 'ok' ? '#3f8600' : '#cf1322' } }}
                      />
                  </Card>
              </Col>
          </Row>
      )}

      <Row gutter={24}>
          {/* Chart */}
          <Col span={16}>
              <Card title="近7天发送趋势" style={{ minHeight: 400 }}>
                  <div style={{ height: 300 }}>
                      <ResponsiveContainer width="100%" height="100%">
                          <BarChart data={trendData}>
                              <CartesianGrid strokeDasharray="3 3" />
                              <XAxis dataKey="date" />
                              <YAxis />
                              <Tooltip />
                              <Legend />
                              <Bar dataKey="success" name="成功" fill="#3f8600" stackId="a" />
                              <Bar dataKey="failed" name="失败" fill="#cf1322" stackId="a" />
                          </BarChart>
                      </ResponsiveContainer>
                  </div>
              </Card>
          </Col>
          
          {/* Quick Actions & System Info */}
          <Col span={8}>
              <Card title="系统信息" style={{ marginBottom: 24 }}>
                  <p><Text strong>版本:</Text> v1.0.0 (Stage 8)</p>
                  <p><Text strong>后端:</Text> FastAPI + SQLModel</p>
                  <p><Text strong>前端:</Text> React + Ant Design</p>
                  <Alert 
                    title={healthStatus?.message || "Checking..."} 
                    type={healthStatus?.status === 'ok' ? 'success' : 'warning'} 
                    showIcon 
                  />
              </Card>
              <Card title="快速入口">
                  <Space wrap>
                      <Button href="/accounts">账号管理</Button>
                      <Button href="/marketing">创建群发</Button>
                      <Button href="/inbox">查看私信</Button>
                      <Button href="/logs">审计日志</Button>
                  </Space>
              </Card>
          </Col>
      </Row>

      {/* 战略大屏 */}
      <Row gutter={24} style={{ marginTop: 24 }}>
        {/* 战斗角色统计 */}
        <Col span={12}>
          <Card title={<><ThunderboltOutlined /> 战斗角色分布</>}>
            <Row gutter={16}>
              {Object.entries(roleStats).map(([role, data]: [string, any]) => (
                <Col span={6} key={role}>
                  <div style={{ textAlign: 'center', padding: 8 }}>
                    <div style={{ 
                      fontSize: 24, 
                      fontWeight: 'bold', 
                      color: roleColors[role] 
                    }}>
                      {data?.active || 0}
                    </div>
                    <div style={{ fontSize: 12, color: '#999' }}>
                      / {data?.total || 0}
                    </div>
                    <Tag color={roleColors[role]}>{roleNames[role] || role}</Tag>
                    {data?.available !== undefined && (
                      <div style={{ fontSize: 11, color: '#52c41a', marginTop: 4 }}>
                        可用: {data.available}
                      </div>
                    )}
                  </div>
                </Col>
              ))}
            </Row>
          </Card>
        </Col>

        {/* 流量源统计 */}
        <Col span={12}>
          <Card title={<><RadarChartOutlined /> 流量源概览</>}>
            {sourceGroupStats && (
              <Row gutter={16}>
                <Col span={6}>
                  <Statistic 
                    title="总流量源" 
                    value={sourceGroupStats.total_groups || 0} 
                  />
                </Col>
                <Col span={6}>
                  <Statistic 
                    title="竞品群" 
                    value={sourceGroupStats.by_type?.competitor?.count || 0}
                    styles={{ content: { color: '#cf1322' } }}
                  />
                </Col>
                <Col span={6}>
                  <Statistic 
                    title="行业群" 
                    value={sourceGroupStats.by_type?.industry?.count || 0}
                    styles={{ content: { color: '#1890ff' } }}
                  />
                </Col>
                <Col span={6}>
                  <Statistic 
                    title="泛流量" 
                    value={sourceGroupStats.by_type?.traffic?.count || 0}
                    styles={{ content: { color: '#52c41a' } }}
                  />
                </Col>
              </Row>
            )}
          </Card>
        </Col>
      </Row>

      {/* 战役概览 */}
      {campaignStats.length > 0 && (
        <Card title={<><RocketOutlined /> 活跃战役</>} style={{ marginTop: 24 }}>
          <Table
            dataSource={campaignStats}
            rowKey="id"
            pagination={false}
            size="small"
            columns={[
              { 
                title: '战役名称', 
                dataIndex: 'name', 
                key: 'name',
                render: (text: string) => <a href="/campaigns">{text}</a>
              },
              { 
                title: '状态', 
                dataIndex: 'status', 
                key: 'status',
                render: (s: string) => (
                  <Tag color={s === 'active' ? 'green' : s === 'paused' ? 'orange' : 'default'}>
                    {s === 'active' ? '进行中' : s === 'paused' ? '已暂停' : '已完成'}
                  </Tag>
                )
              },
              { 
                title: '发送/回复/转化', 
                key: 'stats',
                render: (_: any, r: any) => (
                  <Space>
                    <span>{r.total_messages_sent || 0}</span>
                    <span>/</span>
                    <span style={{ color: '#52c41a' }}>{r.total_replies_received || 0}</span>
                    <span>/</span>
                    <span style={{ color: '#faad14' }}>{r.total_conversions || 0}</span>
                  </Space>
                )
              },
              { 
                title: '回复率', 
                key: 'reply_rate',
                render: (_: any, r: any) => {
                  const rate = r.total_messages_sent > 0 
                    ? Math.round(r.total_replies_received / r.total_messages_sent * 100) 
                    : 0;
                  return <Progress percent={rate} size="small" style={{ width: 100 }} />;
                }
              }
            ]}
          />
        </Card>
      )}

      {/* Recent Logs */}
      <Card title="最近操作日志" style={{ marginTop: 24 }}>
          <Table 
            dataSource={logs} 
            columns={logColumns} 
            rowKey="id" 
            pagination={false} 
            size="small"
          />
      </Card>
    </div>
  );
};

export default Dashboard;
