import React, { useEffect, useState } from 'react';
import { Card, Typography, Space, Spin, Alert, Button, Row, Col, Statistic, Table, Tag } from 'antd';
import { 
    CheckCircleOutlined, 
    CloseCircleOutlined, 
    ReloadOutlined,
    UserOutlined,
    MessageOutlined,
    TeamOutlined,
    ClockCircleOutlined
} from '@ant-design/icons';
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
import { 
    checkHealth, 
    HealthStatus, 
    getOverviewStats, 
    getDailyTrend, 
    getOperationLogs 
} from '../services/api';

const { Title, Paragraph, Text } = Typography;

const Dashboard: React.FC = () => {
  const [healthStatus, setHealthStatus] = useState<HealthStatus | null>(null);
  const [loading, setLoading] = useState(true);
  const [stats, setStats] = useState<any>(null);
  const [trendData, setTrendData] = useState<any[]>([]);
  const [logs, setLogs] = useState<any[]>([]);
  const [error, setError] = useState<string | null>(null);

  const fetchData = async () => {
    setLoading(true);
    setError(null);
    try {
      const results = await Promise.allSettled([
          checkHealth(),
          getOverviewStats(),
          getDailyTrend(7),
          getOperationLogs(0, 10)
      ]);
      
      // Extract values from settled promises
      if (results[0].status === 'fulfilled') setHealthStatus(results[0].value);
      if (results[1].status === 'fulfilled') setStats(results[1].value);
      if (results[2].status === 'fulfilled') setTrendData(results[2].value);
      if (results[3].status === 'fulfilled') setLogs(results[3].value);
      
      // Check if any essential request failed
      if (results[0].status === 'rejected') {
        setError('无法连接到后端服务');
      }
    } catch (err: any) {
      setError(err.message || 'Error fetching dashboard data');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 30000);
    return () => clearInterval(interval);
  }, []);

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
          <Button icon={<ReloadOutlined />} onClick={fetchData} loading={loading}>刷新</Button>
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
