import React, { useState, useEffect } from 'react';
import { Card, Table, Form, Input, Button, Select, message, Tabs, Space, Row, Col, Statistic, Tag, Divider, Modal, List, Badge, Checkbox } from 'antd';
import type { TabsProps } from 'antd';
import { TeamOutlined, SearchOutlined, UsergroupAddOutlined, ReloadOutlined, CheckCircleOutlined, CloseCircleOutlined, HistoryOutlined, EyeOutlined, FilterOutlined } from '@ant-design/icons';
import { getAccounts, joinGroup, joinGroupsBatch, scrapeMembers, scrapeMembersBatch, getTargetUsers, getTargetUsersCount, getScrapingTasks, getScrapingTaskDetail, Account, ScrapingTask } from '../services/api';

const { Option } = Select;
const { TextArea } = Input;

const Scraping: React.FC = () => {
    const [accounts, setAccounts] = useState<Account[]>([]);
    const [loading, setLoading] = useState(false);
    const [batchLoading, setBatchLoading] = useState(false);
    const [targetUsers, setTargetUsers] = useState<any[]>([]);
    const [pagination, setPagination] = useState({ current: 1, pageSize: 20, total: 0 });
    const [selectedAccountIds, setSelectedAccountIds] = useState<number[]>([]);
    const [batchResult, setBatchResult] = useState<any>(null);
    
    // Task History
    const [scrapingTasks, setScrapingTasks] = useState<ScrapingTask[]>([]);
    const [tasksLoading, setTasksLoading] = useState(false);
    const [selectedTaskDetail, setSelectedTaskDetail] = useState<any>(null);
    const [isDetailModalVisible, setIsDetailModalVisible] = useState(false);

    const [singleForm] = Form.useForm();
    const [batchForm] = Form.useForm();
    const [scrapeBatchForm] = Form.useForm();
    const [scrapeBatchLoading, setScrapeBatchLoading] = useState(false);
    const [scrapeBatchResult, setScrapeBatchResult] = useState<any>(null);

    useEffect(() => {
        loadAccounts();
        fetchUsers();
        fetchScrapingTasks();
    }, []);

    const loadAccounts = async () => {
        try {
            const data = await getAccounts(0, 100, 'active');
            setAccounts(data);
        } catch (e) {
            console.error('Failed to load accounts:', e);
        }
    };

    const fetchUsers = async (page?: number, pageSize?: number) => {
        setLoading(true);
        try {
            const currentPage = page || pagination.current;
            const currentPageSize = pageSize || pagination.pageSize;
            const skip = (currentPage - 1) * currentPageSize;
            
            const [data, total] = await Promise.all([
                getTargetUsers(skip, currentPageSize),
                getTargetUsersCount()
            ]);
            
            setTargetUsers(data);
            setPagination(prev => ({ 
                ...prev, 
                current: currentPage,
                pageSize: currentPageSize,
                total 
            }));
        } catch (e) {
            message.error('加载用户失败');
        } finally {
            setLoading(false);
        }
    };

    const fetchScrapingTasks = async () => {
        setTasksLoading(true);
        try {
            const data = await getScrapingTasks(0, 50);
            setScrapingTasks(data);
        } catch (e) {
            console.error('Failed to fetch scraping tasks:', e);
        } finally {
            setTasksLoading(false);
        }
    };

    const handleViewTaskDetail = async (taskId: number) => {
        try {
            const detail = await getScrapingTaskDetail(taskId);
            setSelectedTaskDetail(detail);
            setIsDetailModalVisible(true);
        } catch (e) {
            message.error('获取任务详情失败');
        }
    };

    const onJoinGroup = async (values: any) => {
        setLoading(true);
        try {
            const res = await joinGroup(values.account_id, values.group_link);
            message.success(res.message);
            singleForm.resetFields();
        } catch (e: any) {
            message.error(e.response?.data?.detail || '加入失败');
        } finally {
            setLoading(false);
        }
    };

    const onJoinGroupsBatch = async (values: any) => {
        if (selectedAccountIds.length === 0) {
            message.error('请选择至少一个账号');
            return;
        }
        
        const groupLinks = values.group_links
            .split('\n')
            .map((link: string) => link.trim())
            .filter((link: string) => link.length > 0);
        
        if (groupLinks.length === 0) {
            message.error('请输入至少一个群组链接');
            return;
        }
        
        setBatchLoading(true);
        setBatchResult(null);
        try {
            const res = await joinGroupsBatch(selectedAccountIds, groupLinks);
            message.success(res.message);
            setBatchResult(res);
            // 刷新任务列表
            setTimeout(() => fetchScrapingTasks(), 1000);
        } catch (e: any) {
            message.error(e.response?.data?.detail || '批量加群失败');
        } finally {
            setBatchLoading(false);
        }
    };

    const onScrape = async (values: any) => {
        setLoading(true);
        try {
            const res = await scrapeMembers(values.account_id, values.group_link, values.limit);
            message.success(`采集成功: ${res.scraped_count} 人 (新增 ${res.new_saved})`);
            fetchUsers();
        } catch (e: any) {
            message.error(e.response?.data?.detail || '采集失败');
        } finally {
            setLoading(false);
        }
    };

    const onScrapeBatch = async (values: any) => {
        if (selectedAccountIds.length === 0) {
            message.error('请选择至少一个账号');
            return;
        }
        
        const groupLinks = values.group_links
            .split('\n')
            .map((link: string) => link.trim())
            .filter((link: string) => link.length > 0);
        
        if (groupLinks.length === 0) {
            message.error('请输入至少一个群组链接');
            return;
        }
        
        setScrapeBatchLoading(true);
        setScrapeBatchResult(null);
        try {
            const res = await scrapeMembersBatch(selectedAccountIds, groupLinks, values.limit || 100, {
                active_only: values.filter_active_only,
                has_photo: values.filter_has_photo,
                has_username: values.filter_has_username
            });
            message.success(res.message);
            setScrapeBatchResult(res);
            // 刷新任务列表
            setTimeout(() => fetchScrapingTasks(), 1000);
        } catch (e: any) {
            message.error(e.response?.data?.detail || '批量采集失败');
        } finally {
            setScrapeBatchLoading(false);
        }
    };

    const getStatusTag = (status: string) => {
        const statusMap: any = {
            pending: { color: 'default', text: '等待中' },
            running: { color: 'processing', text: '执行中' },
            completed: { color: 'success', text: '已完成' },
            failed: { color: 'error', text: '失败' }
        };
        const s = statusMap[status] || { color: 'default', text: status };
        return <Tag color={s.color}>{s.text}</Tag>;
    };

    const getTaskTypeText = (type: string) => {
        const typeMap: any = {
            join_batch: '批量加群',
            join_group: '单个加群',
            scrape_members: '采集成员',
            scrape_members_batch: '批量采集'
        };
        return typeMap[type] || type;
    };

    const accountColumns = [
        { title: '手机号', dataIndex: 'phone_number', key: 'phone' },
        { title: '状态', dataIndex: 'status', key: 'status', render: (t: string) => <Tag color="green">{t}</Tag> },
    ];

    const userColumns = [
        { title: 'ID', dataIndex: 'telegram_id', width: 120 },
        { title: '用户名', dataIndex: 'username' },
        { title: '姓名', key: 'name', render: (r: any) => `${r.first_name || ''} ${r.last_name || ''}` },
        { title: '手机号', dataIndex: 'phone' },
        { title: '来源群组', dataIndex: 'source_group' },
        { title: '采集时间', dataIndex: 'created_at', render: (t: string) => new Date(t).toLocaleString() },
    ];

    const taskColumns = [
        { title: 'ID', dataIndex: 'id', width: 60 },
        { title: '类型', dataIndex: 'task_type', render: (t: string) => getTaskTypeText(t) },
        { title: '状态', dataIndex: 'status', render: (t: string) => getStatusTag(t) },
        { 
            title: '结果', 
            key: 'result',
            render: (_: any, r: ScrapingTask) => (
                <Space>
                    <Badge status="success" text={r.success_count} />
                    <Badge status="error" text={r.fail_count} />
                </Space>
            )
        },
        { title: '创建时间', dataIndex: 'created_at', render: (t: string) => new Date(t).toLocaleString() },
        {
            title: '操作',
            key: 'action',
            render: (_: any, r: ScrapingTask) => (
                <Button type="link" size="small" icon={<EyeOutlined />} onClick={() => handleViewTaskDetail(r.id)}>
                    详情
                </Button>
            )
        }
    ];

    const tabItems: TabsProps['items'] = [
        {
            key: 'batch',
            label: <span><UsergroupAddOutlined /> 批量加群</span>,
            children: (
                <Row gutter={24}>
                    <Col span={10}>
                        <Card title="选择账号" extra={
                            <Space>
                                <Button size="small" onClick={() => setSelectedAccountIds(accounts.map(a => a.id))}>
                                    全选
                                </Button>
                                <Button size="small" onClick={() => setSelectedAccountIds([])}>
                                    清空
                                </Button>
                            </Space>
                        }>
                            <Table
                                size="small"
                                rowSelection={{
                                    type: 'checkbox',
                                    selectedRowKeys: selectedAccountIds,
                                    onChange: (keys) => setSelectedAccountIds(keys as number[]),
                                }}
                                columns={accountColumns}
                                dataSource={accounts}
                                rowKey="id"
                                pagination={{ pageSize: 8 }}
                            />
                            <div style={{ marginTop: 12 }}>
                                <Statistic title="已选账号" value={selectedAccountIds.length} />
                            </div>
                        </Card>
                    </Col>
                    <Col span={14}>
                        <Card title="群组链接">
                            <Form form={batchForm} layout="vertical" onFinish={onJoinGroupsBatch}>
                                <Form.Item 
                                    name="group_links" 
                                    label="群组链接（每行一个）"
                                    rules={[{ required: true, message: '请输入群组链接' }]}
                                    help="支持格式：https://t.me/xxx, t.me/xxx, @xxx, 或邀请链接 https://t.me/+xxx"
                                >
                                    <TextArea 
                                        rows={10} 
                                        placeholder={`https://t.me/group1\nhttps://t.me/group2\n@group3\nhttps://t.me/+inviteCode`}
                                    />
                                </Form.Item>
                                <Form.Item>
                                    <Button 
                                        type="primary" 
                                        htmlType="submit" 
                                        loading={batchLoading} 
                                        icon={<UsergroupAddOutlined />}
                                        disabled={selectedAccountIds.length === 0}
                                        size="large"
                                        block
                                    >
                                        批量加入群组
                                    </Button>
                                </Form.Item>
                            </Form>
                            
                            {batchResult && (
                                <>
                                    <Divider />
                                    <Card size="small" title="任务结果">
                                        <Row gutter={16}>
                                            <Col span={8}>
                                                <Statistic title="账号数" value={batchResult.account_count} />
                                            </Col>
                                            <Col span={8}>
                                                <Statistic title="群组数" value={batchResult.group_count} />
                                            </Col>
                                            <Col span={8}>
                                                <Tag color="blue">任务已启动</Tag>
                                            </Col>
                                        </Row>
                                        <p style={{ marginTop: 12, color: '#888' }}>
                                            任务ID: {batchResult.scraping_task_id || batchResult.task_id}
                                        </p>
                                    </Card>
                                </>
                            )}
                        </Card>
                    </Col>
                </Row>
            ),
        },
        {
            key: 'batch_scrape',
            label: <span><FilterOutlined /> 批量采集</span>,
            children: (
                <Row gutter={24}>
                    <Col span={10}>
                        <Card title="选择采集账号" extra={
                            <Space>
                                <Button size="small" onClick={() => setSelectedAccountIds(accounts.map(a => a.id))}>
                                    全选
                                </Button>
                                <Button size="small" onClick={() => setSelectedAccountIds([])}>
                                    清空
                                </Button>
                            </Space>
                        }>
                            <Table
                                size="small"
                                rowSelection={{
                                    type: 'checkbox',
                                    selectedRowKeys: selectedAccountIds,
                                    onChange: (keys) => setSelectedAccountIds(keys as number[]),
                                }}
                                columns={accountColumns}
                                dataSource={accounts}
                                rowKey="id"
                                pagination={{ pageSize: 8 }}
                            />
                            <div style={{ marginTop: 12 }}>
                                <Statistic title="已选账号" value={selectedAccountIds.length} />
                            </div>
                        </Card>
                    </Col>
                    <Col span={14}>
                        <Card title="采集配置">
                            <Form form={scrapeBatchForm} layout="vertical" onFinish={onScrapeBatch} initialValues={{ limit: 100 }}>
                                <Form.Item 
                                    name="group_links" 
                                    label="目标群组链接（每行一个）"
                                    rules={[{ required: true, message: '请输入群组链接' }]}
                                    help="支持格式：https://t.me/xxx, t.me/xxx, @xxx"
                                >
                                    <TextArea 
                                        rows={6} 
                                        placeholder={`https://t.me/group1\nhttps://t.me/group2\n@group3`}
                                    />
                                </Form.Item>
                                
                                <Form.Item name="limit" label="单群采集数量">
                                    <Select>
                                        <Option value={100}>100人</Option>
                                        <Option value={200}>200人</Option>
                                        <Option value={500}>500人</Option>
                                        <Option value={1000}>1000人</Option>
                                    </Select>
                                </Form.Item>
                                
                                <div style={{ background: '#f0f5ff', padding: 12, borderRadius: 8, marginBottom: 16 }}>
                                    <div style={{ marginBottom: 8, fontWeight: 'bold', color: '#1890ff' }}>
                                        <FilterOutlined /> 高质量用户过滤（自动排除垃圾用户）
                                    </div>
                                    <Row gutter={[16, 8]}>
                                        <Col span={24}>
                                            <Form.Item name="filter_active_only" valuePropName="checked" noStyle>
                                                <Checkbox>仅活跃用户（最近7天在线）</Checkbox>
                                            </Form.Item>
                                        </Col>
                                        <Col span={12}>
                                            <Form.Item name="filter_has_photo" valuePropName="checked" noStyle>
                                                <Checkbox>必须有头像</Checkbox>
                                            </Form.Item>
                                        </Col>
                                        <Col span={12}>
                                            <Form.Item name="filter_has_username" valuePropName="checked" noStyle>
                                                <Checkbox>必须有用户名</Checkbox>
                                            </Form.Item>
                                        </Col>
                                    </Row>
                                </div>
                                
                                <Form.Item>
                                    <Button 
                                        type="primary" 
                                        htmlType="submit" 
                                        loading={scrapeBatchLoading} 
                                        icon={<SearchOutlined />}
                                        disabled={selectedAccountIds.length === 0}
                                        size="large"
                                        block
                                    >
                                        启动批量采集
                                    </Button>
                                </Form.Item>
                            </Form>
                            
                            {scrapeBatchResult && (
                                <>
                                    <Divider />
                                    <Card size="small" title="任务已启动">
                                        <Row gutter={16}>
                                            <Col span={8}>
                                                <Statistic title="账号数" value={scrapeBatchResult.account_count || selectedAccountIds.length} />
                                            </Col>
                                            <Col span={8}>
                                                <Statistic title="群组数" value={scrapeBatchResult.group_count || 0} />
                                            </Col>
                                            <Col span={8}>
                                                <Tag color="blue">后台执行中</Tag>
                                            </Col>
                                        </Row>
                                        <p style={{ marginTop: 12, color: '#888' }}>
                                            任务ID: {scrapeBatchResult.scraping_task_id}
                                        </p>
                                        {scrapeBatchResult.filters && (
                                            <p style={{ color: '#1890ff' }}>
                                                过滤条件: {scrapeBatchResult.filters}
                                            </p>
                                        )}
                                    </Card>
                                </>
                            )}
                        </Card>
                    </Col>
                </Row>
            ),
        },
        {
            key: 'single',
            label: <span><TeamOutlined /> 单个操作</span>,
            children: (
                <>
                    <Card title="加入群组" style={{ marginBottom: 24 }}>
                        <Form form={singleForm} layout="inline" onFinish={onJoinGroup}>
                            <Form.Item name="group_link" rules={[{ required: true, message: '请输入群组链接' }]}>
                                <Input placeholder="群组链接 (https://t.me/...)" style={{ width: 300 }} />
                            </Form.Item>
                            <Form.Item name="account_id" rules={[{ required: true, message: '请选择账号' }]}>
                                <Select placeholder="选择账号" style={{ width: 200 }} showSearch optionFilterProp="children">
                                    {accounts.map(acc => (
                                        <Option key={acc.id} value={acc.id}>{acc.phone_number}</Option>
                                    ))}
                                </Select>
                            </Form.Item>
                            <Form.Item>
                                <Button type="primary" htmlType="submit" loading={loading} icon={<TeamOutlined />}>加入群组</Button>
                            </Form.Item>
                        </Form>
                    </Card>

                    <Card title="采集成员">
                        <Form layout="inline" onFinish={onScrape}>
                            <Form.Item name="group_link" rules={[{ required: true, message: '请输入群组链接' }]}>
                                <Input placeholder="群组链接" style={{ width: 300 }} />
                            </Form.Item>
                            <Form.Item name="account_id" rules={[{ required: true, message: '请选择账号' }]}>
                                <Select placeholder="选择账号" style={{ width: 200 }} showSearch optionFilterProp="children">
                                    {accounts.map(acc => (
                                        <Option key={acc.id} value={acc.id}>{acc.phone_number}</Option>
                                    ))}
                                </Select>
                            </Form.Item>
                            <Form.Item name="limit" initialValue={100}>
                                <Input type="number" style={{ width: 100 }} placeholder="数量" />
                            </Form.Item>
                            <Form.Item>
                                <Button type="primary" htmlType="submit" loading={loading} icon={<SearchOutlined />}>开始采集</Button>
                            </Form.Item>
                        </Form>
                    </Card>
                </>
            ),
        },
        {
            key: 'history',
            label: <span><HistoryOutlined /> 任务历史</span>,
            children: (
                <Card extra={<Button icon={<ReloadOutlined />} onClick={fetchScrapingTasks}>刷新</Button>}>
                    <Table
                        dataSource={scrapingTasks}
                        columns={taskColumns}
                        rowKey="id"
                        loading={tasksLoading}
                        pagination={{ pageSize: 10 }}
                    />
                </Card>
            ),
        },
        {
            key: 'users',
            label: '目标用户库',
            children: (
                <Card extra={<Button icon={<ReloadOutlined />} onClick={fetchUsers}>刷新</Button>}>
                    <Table
                        dataSource={targetUsers}
                        columns={userColumns}
                        rowKey="id"
                        loading={loading}
                        pagination={{
                            ...pagination,
                            showSizeChanger: true,
                            showQuickJumper: true,
                            showTotal: (total) => `共 ${total} 条`,
                            pageSizeOptions: ['10', '20', '50', '100'],
                            onChange: (page, pageSize) => {
                                fetchUsers(page, pageSize);
                            }
                        }}
                    />
                </Card>
            ),
        },
    ];

    return (
        <div style={{ padding: 24 }}>
            <Tabs defaultActiveKey="batch" items={tabItems} />
            
            {/* Task Detail Modal */}
            <Modal
                title="任务详情"
                open={isDetailModalVisible}
                onCancel={() => setIsDetailModalVisible(false)}
                footer={null}
                width={700}
            >
                {selectedTaskDetail && (
                    <div>
                        <Row gutter={16} style={{ marginBottom: 16 }}>
                            <Col span={8}>
                                <Statistic title="类型" value={getTaskTypeText(selectedTaskDetail.task_type)} />
                            </Col>
                            <Col span={8}>
                                <Statistic 
                                    title="状态" 
                                    valueRender={() => getStatusTag(selectedTaskDetail.status)}
                                />
                            </Col>
                            <Col span={8}>
                                <Statistic title="成功/失败" value={`${selectedTaskDetail.success_count} / ${selectedTaskDetail.fail_count}`} />
                            </Col>
                        </Row>
                        
                        <Divider />
                        
                        <div style={{ marginBottom: 16 }}>
                            <strong>群组链接：</strong>
                            <div style={{ background: '#f5f5f5', padding: 8, borderRadius: 4, marginTop: 8, maxHeight: 100, overflow: 'auto' }}>
                                {selectedTaskDetail.group_links?.map((link: string, idx: number) => (
                                    <div key={idx}>{link}</div>
                                ))}
                            </div>
                        </div>
                        
                        {selectedTaskDetail.result && (
                            <>
                                {selectedTaskDetail.result.success?.length > 0 && (
                                    <div style={{ marginBottom: 16 }}>
                                        <strong style={{ color: 'green' }}>成功 ({selectedTaskDetail.result.success.length})：</strong>
                                        <List
                                            size="small"
                                            dataSource={selectedTaskDetail.result.success}
                                            renderItem={(item: any) => (
                                                <List.Item>
                                                    <CheckCircleOutlined style={{ color: 'green', marginRight: 8 }} />
                                                    {item.account} → {item.group}
                                                </List.Item>
                                            )}
                                            style={{ maxHeight: 150, overflow: 'auto', background: '#f6ffed', padding: 8, borderRadius: 4 }}
                                        />
                                    </div>
                                )}
                                
                                {selectedTaskDetail.result.failed?.length > 0 && (
                                    <div>
                                        <strong style={{ color: 'red' }}>失败 ({selectedTaskDetail.result.failed.length})：</strong>
                                        <List
                                            size="small"
                                            dataSource={selectedTaskDetail.result.failed}
                                            renderItem={(item: any) => (
                                                <List.Item>
                                                    <CloseCircleOutlined style={{ color: 'red', marginRight: 8 }} />
                                                    {item.account} → {item.group}: {item.error}
                                                </List.Item>
                                            )}
                                            style={{ maxHeight: 150, overflow: 'auto', background: '#fff2f0', padding: 8, borderRadius: 4 }}
                                        />
                                    </div>
                                )}
                            </>
                        )}
                        
                        {selectedTaskDetail.error_message && (
                            <div style={{ marginTop: 16, color: 'red' }}>
                                <strong>错误信息：</strong> {selectedTaskDetail.error_message}
                            </div>
                        )}
                        
                        <Divider />
                        
                        <Row gutter={16}>
                            <Col span={12}>
                                <small style={{ color: '#999' }}>
                                    创建时间: {selectedTaskDetail.created_at ? new Date(selectedTaskDetail.created_at).toLocaleString() : '-'}
                                </small>
                            </Col>
                            <Col span={12}>
                                <small style={{ color: '#999' }}>
                                    完成时间: {selectedTaskDetail.completed_at ? new Date(selectedTaskDetail.completed_at).toLocaleString() : '-'}
                                </small>
                            </Col>
                        </Row>
                    </div>
                )}
            </Modal>
        </div>
    );
};

export default Scraping;
