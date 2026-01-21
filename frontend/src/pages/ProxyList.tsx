import React, { useEffect, useState } from 'react';
import {
  Table,
  Button,
  Modal,
  Form,
  Input,
  InputNumber,
  message,
  Tag,
  Space,
  Upload,
  Select,
  Popconfirm,
  Card,
  Statistic,
  Row,
  Col,
  Radio,
} from 'antd';
import {
  PlusOutlined,
  ReloadOutlined,
  DeleteOutlined,
  UploadOutlined,
  SyncOutlined,
  CheckCircleOutlined,
  CloseCircleOutlined,
  CloudSyncOutlined,
} from '@ant-design/icons';
import {
  getProxies,
  getProxyCount,
  createProxy,
  deleteProxy,
  uploadProxies,
  checkProxy,
  checkProxiesBatch,
  deleteProxiesBatch,
  syncIP2World,
  Proxy,
  ProxyCreate,
} from '../services/api';

const { Option } = Select;

const ProxyList: React.FC = () => {
  const [proxies, setProxies] = useState<Proxy[]>([]);
  const [loading, setLoading] = useState(false);
  const [checking, setChecking] = useState<number[]>([]);
  const [isModalVisible, setIsModalVisible] = useState(false);
  const [form] = Form.useForm();
  const [uploadForm] = Form.useForm();
  const [fileList, setFileList] = useState<any[]>([]);
  const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
  const [statusFilter, setStatusFilter] = useState<string | undefined>(undefined);
  const [categoryFilter, setCategoryFilter] = useState<string | undefined>(undefined);
  const [stats, setStats] = useState({ total: 0, active: 0, dead: 0 });
  const [selectedRowKeys, setSelectedRowKeys] = useState<React.Key[]>([]);
  
  // Upload Category
  const [uploadCategory, setUploadCategory] = useState<string>('static');
  const [uploadProviderType, setUploadProviderType] = useState<string>('datacenter');

  // IP2World Sync
  const [isIP2WorldModalVisible, setIsIP2WorldModalVisible] = useState(false);
  const [ip2worldApiUrl, setIp2worldApiUrl] = useState('');
  const [ip2worldCategory, setIp2worldCategory] = useState<string>('static');
  const [ip2worldProviderType, setIp2worldProviderType] = useState<string>('datacenter');
  const [syncingIP2World, setSyncingIP2World] = useState(false);

  const handleSyncIP2World = async () => {
    setSyncingIP2World(true);
    try {
      const result = await syncIP2World(ip2worldApiUrl, ip2worldCategory, ip2worldProviderType);
      message.success(`同步成功：新增 ${result.added} 个代理`);
      setIsIP2WorldModalVisible(false);
      localStorage.setItem('ip2world_api_url', ip2worldApiUrl);
      fetchProxies(1, pagination.pageSize);
      fetchStats();
    } catch (error: any) {
      message.error(`同步失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setSyncingIP2World(false);
    }
  };

  // Initialization effect
  useEffect(() => {
    const savedUrl = localStorage.getItem('ip2world_api_url');
    if (savedUrl) {
      setIp2worldApiUrl(savedUrl);
    }
  }, []);

  const fetchProxies = async (page: number = 1, pageSize: number = 20) => {
    setLoading(true);
    try {
      const skip = (page - 1) * pageSize;
      const data = await getProxies(skip, pageSize, statusFilter, categoryFilter);
      setProxies(data);
      
      // 获取总数
      const count = await getProxyCount(statusFilter, categoryFilter);
      setPagination(prev => ({ ...prev, current: page, pageSize, total: count.total }));
    } catch (error) {
      message.error('获取代理列表失败');
    } finally {
      setLoading(false);
    }
  };

  const fetchStats = async () => {
    try {
      // 基础统计暂不带 filter，或者根据需求带上
      const [totalRes, activeRes, deadRes] = await Promise.all([
        getProxyCount(undefined, categoryFilter),
        getProxyCount('active', categoryFilter),
        getProxyCount('dead', categoryFilter),
      ]);
      setStats({
        total: totalRes.total,
        active: activeRes.total,
        dead: deadRes.total,
      });
    } catch (error) {
      console.error('获取统计信息失败', error);
    }
  };

  useEffect(() => {
    fetchProxies();
    fetchStats();
  }, [statusFilter, categoryFilter]);

  const handleCreate = async (values: ProxyCreate) => {
    try {
      await createProxy(values);
      message.success('代理创建成功');
      setIsModalVisible(false);
      form.resetFields();
      fetchProxies(pagination.current, pagination.pageSize);
      fetchStats();
    } catch (error) {
      message.error('创建代理失败');
    }
  };

  const handleDelete = async (id: number) => {
    try {
      await deleteProxy(id);
      message.success('代理删除成功');
      fetchProxies(pagination.current, pagination.pageSize);
      fetchStats();
    } catch (error) {
      message.error('删除代理失败');
    }
  };

  const handleUpload = async () => {
    if (fileList.length === 0) {
      message.error('请选择文件');
      return;
    }

    try {
      const file = fileList[0].originFileObj;
      const result = await uploadProxies(file, uploadCategory, uploadProviderType);
      message.success(`导入成功：${result.created} 个，跳过：${result.skipped} 个`);
      if (result.errors.length > 0) {
        message.warning(`有 ${result.errors.length} 个错误，请查看控制台`);
        console.error('导入错误:', result.errors);
      }
      setFileList([]);
      uploadForm.resetFields();
      fetchProxies(pagination.current, pagination.pageSize);
      fetchStats();
    } catch (error: any) {
      message.error(`导入失败: ${error.response?.data?.detail || error.message}`);
    }
  };

  const handleCheck = async (id: number) => {
    setChecking(prev => [...prev, id]);
    try {
      const result = await checkProxy(id);
      if (result.is_alive) {
        message.success(`代理 ${id} 检测成功`);
      } else {
        message.warning(`代理 ${id} 检测失败: ${result.error}`);
      }
      fetchProxies(pagination.current, pagination.pageSize);
      fetchStats();
    } catch (error) {
      message.error(`检测代理 ${id} 失败`);
    } finally {
      setChecking(prev => prev.filter(pid => pid !== id));
    }
  };

  const handleBatchCheck = async () => {
    const idsToCheck = selectedRowKeys.length > 0 ? (selectedRowKeys as number[]) : proxies.map(p => p.id);
    
    if (idsToCheck.length === 0) {
      message.warning('没有可检测的代理');
      return;
    }

    setChecking(idsToCheck);
    try {
      const result = await checkProxiesBatch(idsToCheck);
      message.info(`批量检测任务已提交，任务 ID: ${result.task_id}`);
      setTimeout(() => {
        fetchProxies(pagination.current, pagination.pageSize);
        fetchStats();
        setChecking([]);
      }, 5000);
      setSelectedRowKeys([]);
    } catch (error) {
      message.error('批量检测失败');
      setChecking([]);
    }
  };

  const handleBatchDelete = async () => {
    if (selectedRowKeys.length === 0) return;
    
    try {
      const result = await deleteProxiesBatch(selectedRowKeys as number[]);
      message.success(`成功删除 ${result.deleted_count} 个代理`);
      fetchProxies(pagination.current, pagination.pageSize);
      fetchStats();
      setSelectedRowKeys([]);
    } catch (error) {
      message.error('批量删除失败');
    }
  };

  const getStatusTag = (status: string) => {
    if (status === 'active') {
      return <Tag color="green" icon={<CheckCircleOutlined />}>活跃</Tag>;
    } else if (status === 'dead') {
      return <Tag color="red" icon={<CloseCircleOutlined />}>失效</Tag>;
    }
    return <Tag>{status}</Tag>;
  };

  const getCategoryTag = (category: string, providerType: string) => {
    let color = 'blue';
    let text = category;
    
    if (category === 'static') {
      text = '长期(Static)';
    } else if (category === 'rotating') {
      text = '短期(Rotating)';
      color = 'orange';
    }

    if (providerType === 'isp') {
      return (
        <Space orientation="vertical" size={0}>
          <Tag color={color}>{text}</Tag>
          <Tag color="purple">ISP(家庭)</Tag>
        </Space>
      );
    } else {
       return (
        <Space orientation="vertical" size={0}>
          <Tag color={color}>{text}</Tag>
          <Tag color="default">机房(DC)</Tag>
        </Space>
      );
    }
  };

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      key: 'id',
      width: 60,
    },
    {
      title: 'IP',
      dataIndex: 'ip',
      key: 'ip',
      render: (ip: string) => (
        <Space>
          {ip}
          {ip.includes(':') ? (
            <Tag color="purple">IPv6</Tag>
          ) : (
            <Tag color="blue">IPv4</Tag>
          )}
        </Space>
      ),
    },
    {
      title: '端口',
      dataIndex: 'port',
      key: 'port',
      width: 80,
    },
    {
      title: '用户名',
      dataIndex: 'username',
      key: 'username',
      render: (text: string) => text || '-',
    },
    {
      title: '密码',
      dataIndex: 'password',
      key: 'password',
      render: (text: string) => text ? '***' : '-',
    },
    {
      title: '类型',
      key: 'category',
      width: 140,
      render: (_: any, record: Proxy) => getCategoryTag(record.category || 'static', record.provider_type || 'datacenter'),
    },
    {
      title: '协议',
      dataIndex: 'protocol',
      key: 'protocol',
      width: 80,
    },
    {
      title: '状态',
      dataIndex: 'status',
      key: 'status',
      width: 100,
      render: (status: string) => getStatusTag(status),
    },
    {
      title: '失败数',
      dataIndex: 'fail_count',
      key: 'fail_count',
      width: 80,
    },
    {
      title: '过期时间',
      dataIndex: 'expire_time',
      key: 'expire_time',
      render: (text: string) => text ? new Date(text).toLocaleString() : '-',
    },
    {
      title: '最后检查',
      dataIndex: 'last_checked',
      key: 'last_checked',
      render: (text: string) => text ? new Date(text).toLocaleString() : '-',
    },
    {
      title: '操作',
      key: 'action',
      width: 180,
      render: (_: any, record: Proxy) => (
        <Space>
          <Button
            size="small"
            icon={<SyncOutlined />}
            loading={checking.includes(record.id)}
            onClick={() => handleCheck(record.id)}
          >
            检测
          </Button>
          <Popconfirm
            title="确定要删除这个代理吗？"
            onConfirm={() => handleDelete(record.id)}
            okText="确定"
            cancelText="取消"
          >
            <Button size="small" danger icon={<DeleteOutlined />}>
              删除
            </Button>
          </Popconfirm>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <Card style={{ marginBottom: 16 }}>
        <Row gutter={16}>
          <Col span={6}>
            <Statistic title="总代理数" value={stats.total} />
          </Col>
          <Col span={6}>
            <Statistic title="活跃代理" value={stats.active} styles={{ content: { color: '#3f8600' } }} />
          </Col>
          <Col span={6}>
            <Statistic title="失效代理" value={stats.dead} styles={{ content: { color: '#cf1322' } }} />
          </Col>
          <Col span={6}>
            <Statistic title="可用率" value={stats.total > 0 ? ((stats.active / stats.total) * 100).toFixed(1) : 0} suffix="%" />
          </Col>
        </Row>
      </Card>

      <Card>
        <div style={{ marginBottom: 16, display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: 8 }}>
          <Space wrap>
            <Button
              type="primary"
              icon={<PlusOutlined />}
              onClick={() => setIsModalVisible(true)}
            >
              添加代理
            </Button>
            <div style={{ border: '1px solid #d9d9d9', borderRadius: '6px', padding: '4px 8px', display: 'flex', alignItems: 'center', gap: 8 }}>
              <Select 
                value={uploadCategory} 
                onChange={setUploadCategory} 
                style={{ width: 100 }} 
                variant="borderless"
                size="small"
              >
                <Option value="static">长期</Option>
                <Option value="rotating">短期</Option>
              </Select>
              <Select 
                value={uploadProviderType} 
                onChange={setUploadProviderType} 
                style={{ width: 100 }} 
                variant="borderless"
                size="small"
              >
                <Option value="datacenter">机房</Option>
                <Option value="isp">ISP</Option>
              </Select>
              <Upload
                fileList={fileList}
                beforeUpload={() => false}
                onChange={({ fileList }) => setFileList(fileList)}
                accept=".txt"
                showUploadList={false}
              >
                <Button icon={<UploadOutlined />} size="small">选择文件</Button>
              </Upload>
            </div>
            
            {fileList.length > 0 && (
              <Button type="primary" onClick={handleUpload}>
                导入 {fileList.length} 个文件 ({uploadCategory === 'static' ? '长期' : '短期'})
              </Button>
            )}
            
            <Button
              icon={<CloudSyncOutlined />}
              onClick={() => setIsIP2WorldModalVisible(true)}
            >
              同步 IP2World
            </Button>
            <Button
              icon={<SyncOutlined />}
              onClick={handleBatchCheck}
              loading={checking.length > 0}
            >
              {selectedRowKeys.length > 0 ? `检测选中 (${selectedRowKeys.length})` : '批量检测'}
            </Button>
            {selectedRowKeys.length > 0 && (
              <Popconfirm
                title={`确定要删除选中的 ${selectedRowKeys.length} 个代理吗？`}
                onConfirm={handleBatchDelete}
                okText="确定"
                cancelText="取消"
              >
                <Button danger icon={<DeleteOutlined />}>
                  批量删除 ({selectedRowKeys.length})
                </Button>
              </Popconfirm>
            )}
            <Button icon={<ReloadOutlined />} onClick={() => fetchProxies(pagination.current, pagination.pageSize)}>
              刷新
            </Button>
          </Space>
          <Space>
            <Select
              style={{ width: 120 }}
              placeholder="筛选类型"
              allowClear
              value={categoryFilter}
              onChange={(value) => {
                setCategoryFilter(value);
                setPagination(prev => ({ ...prev, current: 1 }));
              }}
            >
              <Option value="static">长期代理</Option>
              <Option value="rotating">短期代理</Option>
            </Select>
            <Select
              style={{ width: 120 }}
              placeholder="筛选状态"
              allowClear
              value={statusFilter}
              onChange={(value) => {
                setStatusFilter(value);
                setPagination(prev => ({ ...prev, current: 1 }));
              }}
            >
              <Option value="active">活跃</Option>
              <Option value="dead">失效</Option>
            </Select>
          </Space>
        </div>

        <Table
          rowSelection={{
            type: 'checkbox',
            selectedRowKeys,
            onChange: (keys) => setSelectedRowKeys(keys),
          }}
          columns={columns}
          dataSource={proxies}
          rowKey="id"
          loading={loading}
          pagination={{
            current: pagination.current,
            pageSize: pagination.pageSize,
            total: pagination.total,
            showSizeChanger: true,
            showTotal: (total) => `共 ${total} 条`,
            onChange: (page, pageSize) => {
              setPagination(prev => ({ ...prev, current: page, pageSize }));
              fetchProxies(page, pageSize);
            },
          }}
        />
      </Card>

      <Modal
        title="添加代理"
        open={isModalVisible}
        onCancel={() => {
          setIsModalVisible(false);
          form.resetFields();
        }}
        onOk={() => form.submit()}
      >
        <Form
          form={form}
          layout="vertical"
          onFinish={handleCreate}
          initialValues={{
            protocol: 'socks5',
            category: 'static'
          }}
        >
          <Form.Item
            name="ip"
            label="IP 地址"
            rules={[{ required: true, message: '请输入 IP 地址' }]}
          >
            <Input placeholder="例如: 192.168.1.1" />
          </Form.Item>
          <Form.Item
            name="port"
            label="端口"
            rules={[{ required: true, message: '请输入端口' }]}
          >
            <InputNumber min={1} max={65535} style={{ width: '100%' }} placeholder="例如: 1080" />
          </Form.Item>
          <Form.Item
            name="username"
            label="用户名（可选）"
          >
            <Input placeholder="如果代理需要认证" />
          </Form.Item>
          <Form.Item
            name="password"
            label="密码（可选）"
          >
            <Input.Password placeholder="如果代理需要认证" />
          </Form.Item>
          <Form.Item
            name="protocol"
            label="协议"
          >
            <Select>
              <Option value="socks5">SOCKS5</Option>
              <Option value="http">HTTP</Option>
              <Option value="https">HTTPS</Option>
            </Select>
          </Form.Item>
          <Form.Item
            name="category"
            label="代理类型"
            help="长期代理用于养号，短期代理用于注册"
          >
            <Radio.Group>
              <Radio value="static">长期 (Static)</Radio>
              <Radio value="rotating">短期 (Rotating)</Radio>
            </Radio.Group>
          </Form.Item>
          <Form.Item
            name="provider_type"
            label="供应商类型"
            initialValue="datacenter"
          >
            <Radio.Group>
              <Radio value="datacenter">机房 (DataCenter)</Radio>
              <Radio value="isp">家庭 (ISP)</Radio>
            </Radio.Group>
          </Form.Item>
        </Form>
      </Modal>
      <Modal
        title="同步 IP2World 代理"
        open={isIP2WorldModalVisible}
        onCancel={() => setIsIP2WorldModalVisible(false)}
        onOk={handleSyncIP2World}
        confirmLoading={syncingIP2World}
        okText="开始同步"
        cancelText="取消"
      >
        <p>请输入您的 IP2World 提取链接 (API Link)：</p>
        <Input.TextArea
          placeholder="https://api.ip2world.com/..."
          value={ip2worldApiUrl} 
          onChange={(e) => setIp2worldApiUrl(e.target.value)}
          rows={4}
          style={{ marginBottom: 16 }}
        />
        
        <p>导入为类型：</p>
        <Radio.Group value={ip2worldCategory} onChange={e => setIp2worldCategory(e.target.value)}>
          <Radio value="static">长期 (Static)</Radio>
          <Radio value="rotating">短期 (Rotating)</Radio>
        </Radio.Group>
        
        <p style={{ marginTop: 16 }}>供应商类型：</p>
        <Radio.Group value={ip2worldProviderType} onChange={e => setIp2worldProviderType(e.target.value)}>
          <Radio value="datacenter">机房 (DataCenter)</Radio>
          <Radio value="isp">家庭 (ISP)</Radio>
        </Radio.Group>

        <div style={{ marginTop: 8, color: '#999', fontSize: '12px' }}>
          将自动访问此链接提取并存入代理池。
          <br />
          如果留空，将使用后端配置文件中设置的默认 URL。
        </div>
      </Modal>
    </div>
  );
};

export default ProxyList;
