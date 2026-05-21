import React from 'react';
import {
  Card, Table, Tag, Button, Space, Typography, Empty, Modal, Form, Input,
  InputNumber, Checkbox, message, Drawer, Statistic,
} from 'antd';
import {
  UsergroupAddOutlined, CloudDownloadOutlined, HistoryOutlined,
  ReloadOutlined, PhoneOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { accountsApi, SalesAccount } from '../api';
import { useT } from '../i18n';

const { Title, Text } = Typography;

const STATUS_COLOR: Record<string, string> = {
  active: 'green',
  inactive: 'default',
  banned: 'red',
  flood_wait: 'orange',
};

const AccountsPage: React.FC = () => {
  const qc = useQueryClient();
  const t = useT();
  const [joinFor, setJoinFor] = React.useState<SalesAccount | null>(null);
  const [scrapeFor, setScrapeFor] = React.useState<SalesAccount | null>(null);
  const [tasksFor, setTasksFor] = React.useState<SalesAccount | null>(null);
  const [joinForm] = Form.useForm();
  const [scrapeForm] = Form.useForm();

  const { data: accounts = [], isLoading, refetch } = useQuery({
    queryKey: ['sales', 'accounts'],
    queryFn: () => accountsApi.list(),
  });

  const { data: tasks = [], isLoading: tasksLoading } = useQuery({
    queryKey: ['sales', 'account-tasks', tasksFor?.id],
    queryFn: () => tasksFor ? accountsApi.scrapeTasks(tasksFor.id) : Promise.resolve([]),
    enabled: !!tasksFor,
  });

  const joinMut = useMutation({
    mutationFn: ({ id, group_link }: { id: number; group_link: string }) =>
      accountsApi.joinGroup(id, group_link),
    onSuccess: () => {
      message.success(t('accounts.joinSuccess'));
      setJoinFor(null); joinForm.resetFields();
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail || t('accounts.joinFailed')),
  });

  const scrapeMut = useMutation({
    mutationFn: ({ id, ...body }: any) => accountsApi.scrape(id, body),
    onSuccess: () => {
      message.success(t('accounts.scrapeSuccess'));
      setScrapeFor(null); scrapeForm.resetFields();
      qc.invalidateQueries({ queryKey: ['sales', 'accounts'] });
    },
    onError: (e: any) =>
      message.error(e?.response?.data?.detail || t('accounts.scrapeFailed')),
  });

  const totalAcc = accounts.length;
  const totalLeads = accounts.reduce((s, a) => s + (a.lead_count || 0), 0);
  const totalInv = accounts.reduce((s, a) => s + (a.daily_invite_count || 0), 0);

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <div>
          <Title level={3} style={{ margin: 0 }}>{t('accounts.title')}</Title>
          <Text type="secondary">{t('accounts.subtitle')}</Text>
        </div>
        <Button icon={<ReloadOutlined />} onClick={() => refetch()}>
          {t('common.refresh')}
        </Button>
      </div>

      <Space style={{ marginBottom: 16 }}>
        <Card><Statistic title={t('accounts.col.phone')} value={totalAcc} prefix={<PhoneOutlined />} /></Card>
        <Card><Statistic title={t('accounts.col.leads')} value={totalLeads} /></Card>
        <Card><Statistic title={t('accounts.col.invites24h')} value={totalInv} /></Card>
      </Space>

      <Card>
        <Table
          rowKey="id"
          dataSource={accounts}
          loading={isLoading}
          pagination={{ pageSize: 20 }}
          locale={{ emptyText: <Empty description={t('accounts.empty')} /> }}
          columns={[
            { title: 'ID', dataIndex: 'id', width: 60 },
            { title: t('accounts.col.phone'), dataIndex: 'phone_number' },
            { title: t('accounts.col.username'), dataIndex: 'customized_username',
              render: (u: string | null) => u ? `@${u}` : '—' },
            { title: t('accounts.col.status'), dataIndex: 'status', width: 100,
              render: (s: string) => <Tag color={STATUS_COLOR[s] || 'default'}>{s}</Tag> },
            { title: t('accounts.col.role'), dataIndex: 'role', width: 100,
              render: (r: string | null) => r ? <Tag>{r}</Tag> : '—' },
            { title: t('accounts.col.invites24h'), dataIndex: 'daily_invite_count', width: 110 },
            { title: t('accounts.col.leads'), dataIndex: 'lead_count', width: 100 },
            { title: t('accounts.col.actions'), key: 'actions', width: 280,
              render: (_: any, r: SalesAccount) => (
                <Space>
                  <Button size="small" icon={<UsergroupAddOutlined />}
                    onClick={() => setJoinFor(r)}>{t('accounts.action.join')}</Button>
                  <Button size="small" icon={<CloudDownloadOutlined />}
                    onClick={() => setScrapeFor(r)}>{t('accounts.action.scrape')}</Button>
                  <Button size="small" icon={<HistoryOutlined />}
                    onClick={() => setTasksFor(r)}>{t('accounts.action.tasks')}</Button>
                </Space>
              )},
          ]}
        />
      </Card>

      {/* Join group */}
      <Modal
        title={`${t('accounts.modal.join')} — acc #${joinFor?.id}`}
        open={!!joinFor}
        onCancel={() => setJoinFor(null)}
        onOk={async () => {
          try {
            const v = await joinForm.validateFields();
            joinMut.mutate({ id: joinFor!.id, group_link: v.group_link });
          } catch {}
        }}
        confirmLoading={joinMut.isPending}
      >
        <Form form={joinForm} layout="vertical">
          <Form.Item name="group_link" label={t('accounts.field.groupLink')}
            rules={[{ required: true }]}>
            <Input placeholder={t('accounts.field.groupLinkPh')} />
          </Form.Item>
        </Form>
      </Modal>

      {/* Scrape */}
      <Modal
        title={`${t('accounts.modal.scrape')} — acc #${scrapeFor?.id}`}
        open={!!scrapeFor}
        onCancel={() => setScrapeFor(null)}
        onOk={async () => {
          try {
            const v = await scrapeForm.validateFields();
            scrapeMut.mutate({ id: scrapeFor!.id, ...v });
          } catch {}
        }}
        confirmLoading={scrapeMut.isPending}
      >
        <Form form={scrapeForm} layout="vertical" initialValues={{ limit: 200 }}>
          <Form.Item name="group_link" label={t('accounts.field.groupLink')}
            rules={[{ required: true }]}>
            <Input placeholder={t('accounts.field.groupLinkPh')} />
          </Form.Item>
          <Form.Item name="limit" label={t('accounts.field.limit')}>
            <InputNumber min={1} max={5000} style={{ width: 200 }} />
          </Form.Item>
          <Form.Item label=" " colon={false}>
            <Space direction="vertical">
              <Form.Item name="filter_active_only" valuePropName="checked" noStyle>
                <Checkbox>{t('accounts.field.activeOnly')}</Checkbox>
              </Form.Item>
              <Form.Item name="filter_has_photo" valuePropName="checked" noStyle>
                <Checkbox>{t('accounts.field.hasPhoto')}</Checkbox>
              </Form.Item>
              <Form.Item name="filter_has_username" valuePropName="checked" noStyle>
                <Checkbox>{t('accounts.field.hasUsername')}</Checkbox>
              </Form.Item>
            </Space>
          </Form.Item>
        </Form>
      </Modal>

      {/* Tasks */}
      <Drawer
        title={`${t('accounts.modal.tasks')} — acc #${tasksFor?.id}`}
        open={!!tasksFor}
        onClose={() => setTasksFor(null)}
        width={640}
      >
        <Table
          rowKey="id"
          dataSource={tasks}
          loading={tasksLoading}
          size="small"
          pagination={false}
          columns={[
            { title: t('accounts.tasks.col.id'), dataIndex: 'id', width: 60 },
            { title: t('accounts.tasks.col.type'), dataIndex: 'task_type' },
            { title: t('accounts.tasks.col.status'), dataIndex: 'status',
              render: (s: string) => <Tag color={s === 'completed' ? 'green' : s === 'failed' ? 'red' : 'processing'}>{s}</Tag> },
            { title: t('accounts.tasks.col.success'), dataIndex: 'success_count' },
            { title: t('accounts.tasks.col.created'), dataIndex: 'created_at',
              render: (s: string) => s ? new Date(s).toLocaleString() : '—' },
          ]}
        />
      </Drawer>
    </div>
  );
};

export default AccountsPage;
