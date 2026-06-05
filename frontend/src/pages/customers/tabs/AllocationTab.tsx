import React from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { App, Card, Button, Space, Typography } from 'antd';
import { ReloadOutlined, BulbOutlined } from '@ant-design/icons';
import {
  getCustomerById,
  reallocateAccounts,
  reallocateGroups,
  regenerateKb,
  AdminApiError,
} from '../../../services/adminCustomers';

const { Paragraph, Text } = Typography;

const AllocationTab: React.FC<{ customerId: number }> = ({ customerId }) => {
  const queryClient = useQueryClient();
  const { modal, message } = App.useApp();

  const { data: customer } = useQuery({
    queryKey: ['admin-customer', customerId],
    queryFn: () => getCustomerById(customerId),
  });

  const onErr = (err: unknown) =>
    message.error(err instanceof AdminApiError ? err.message : '操作失败');
  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: ['admin-customer', customerId] });

  const accountsM = useMutation({
    mutationFn: () => reallocateAccounts(customerId),
    onSuccess: () => { message.success('账号已重新分配'); invalidate(); },
    onError: onErr,
  });
  const groupsM = useMutation({
    mutationFn: () => reallocateGroups(customerId),
    onSuccess: () => { message.success('群组已重新分配'); invalidate(); },
    onError: onErr,
  });
  const kbM = useMutation({
    mutationFn: () => regenerateKb(customerId),
    onSuccess: () => { message.success('行业 KB 已重新生成'); invalidate(); },
    onError: onErr,
  });

  const confirmAccounts = () =>
    modal.confirm({
      title: '重新分配账号',
      okText: '确认',
      cancelText: '取消',
      content: (
        <>
          <Paragraph>
            将释放当前 <Text strong>{customer?.account_used ?? '?'}</Text> 个账号回池，
            并按当前套餐配额（<Text strong>{customer?.account_quota ?? '?'}</Text> 个）重新分配。
          </Paragraph>
          <Paragraph type="warning">此操作影响客户群控运行，建议提前通知。</Paragraph>
        </>
      ),
      onOk: () => accountsM.mutateAsync(),
    });

  const confirmGroups = () =>
    modal.confirm({
      title: '重新分配群组',
      okText: '确认',
      cancelText: '取消',
      content: (
        <>
          <Paragraph>
            将释放当前 <Text strong>{customer?.group_used ?? '?'}</Text> 个群组，
            并按套餐配额（<Text strong>{customer?.group_quota ?? '?'}</Text> 个）重新分配。
          </Paragraph>
        </>
      ),
      onOk: () => groupsM.mutateAsync(),
    });

  const confirmKb = () =>
    modal.confirm({
      title: '重新生成行业 KB',
      okText: '确认',
      cancelText: '取消',
      content: (
        <Paragraph>
          将删除当前所有行业 KB 条目并按客户行业重新生成。约耗时 30 秒。
        </Paragraph>
      ),
      onOk: () => kbM.mutateAsync(),
    });

  return (
    <Space orientation="vertical" size="large" style={{ width: '100%' }}>
      <Card title="重新分配账号">
        <Paragraph>
          当前已分配 {customer?.account_used ?? '?'} / {customer?.account_quota ?? '?'} 个 TG 账号。
        </Paragraph>
        <Button icon={<ReloadOutlined />} loading={accountsM.isPending} onClick={confirmAccounts}>
          重新分配账号
        </Button>
      </Card>
      <Card title="重新分配群组">
        <Paragraph>
          当前已加入 {customer?.group_used ?? '?'} / {customer?.group_quota ?? '?'} 个群。
        </Paragraph>
        <Button icon={<ReloadOutlined />} loading={groupsM.isPending} onClick={confirmGroups}>
          重新分配群组
        </Button>
      </Card>
      <Card title="重新生成行业 KB">
        <Paragraph>清空当前行业 KB 并按客户当前 industry 重新生成 4 条 KB（含 embedding）。</Paragraph>
        <Button icon={<BulbOutlined />} loading={kbM.isPending} onClick={confirmKb}>
          重新生成行业 KB
        </Button>
      </Card>
    </Space>
  );
};

export default AllocationTab;
