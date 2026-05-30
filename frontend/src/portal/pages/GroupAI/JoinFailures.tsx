/**
 * JoinFailures — 加群失败队列 (Phase 8)
 *
 * Shows join_attempts in 'failed' status so the customer can review and
 * either abandon (stop retrying) or handle them manually.
 */
import React, { useState } from 'react';
import { Button, Empty, message, Space, Table, Tag, Tooltip, Typography } from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { groupAiApi, JoinFailureRow } from '../../api/groupAi';

const { Text } = Typography;

const CAPTCHA_TYPE_COLORS: Record<string, string> = {
  inline_button: 'blue',
  text_qa: 'purple',
  vision: 'orange',
  admin_dm: 'cyan',
  unknown: 'default',
};

export default function JoinFailures() {
  const queryClient = useQueryClient();

  const { data: rows = [], isLoading } = useQuery({
    queryKey: ['join-failures'],
    queryFn: () => groupAiApi.listJoinFailures(),
    refetchInterval: 30_000,
  });

  const abandonMut = useMutation({
    mutationFn: (id: number) => groupAiApi.abandonJoinAttempt(id),
    onSuccess: () => {
      message.success('已标记为放弃');
      queryClient.invalidateQueries({ queryKey: ['join-failures'] });
    },
    onError: () => {
      message.error('操作失败，请重试');
    },
  });

  const columns = [
    {
      title: '群链接',
      dataIndex: 'chat_link',
      key: 'chat_link',
      render: (v: string) => (
        <a href={v} target="_blank" rel="noreferrer">
          {v}
        </a>
      ),
    },
    {
      title: '验证类型',
      dataIndex: 'captcha_type',
      key: 'captcha_type',
      width: 120,
      render: (v: string | null) =>
        v ? (
          <Tag color={CAPTCHA_TYPE_COLORS[v] || 'default'}>{v}</Tag>
        ) : (
          <Text type="secondary">—</Text>
        ),
    },
    {
      title: '尝试次数',
      dataIndex: 'captcha_attempts',
      key: 'captcha_attempts',
      width: 90,
      align: 'center' as const,
    },
    {
      title: '错误信息',
      dataIndex: 'last_error',
      key: 'last_error',
      ellipsis: true,
      render: (v: string | null) =>
        v ? (
          <Tooltip title={v}>
            <Text type="danger" ellipsis style={{ maxWidth: 260 }}>
              {v}
            </Text>
          </Tooltip>
        ) : (
          <Text type="secondary">—</Text>
        ),
    },
    {
      title: '失败时间',
      dataIndex: 'updated_at',
      key: 'updated_at',
      width: 170,
      render: (v: string) => new Date(v).toLocaleString('zh-CN'),
    },
    {
      title: '操作',
      key: 'action',
      width: 100,
      render: (_: unknown, row: JoinFailureRow) => (
        <Button
          danger
          size="small"
          loading={abandonMut.isPending}
          onClick={() => abandonMut.mutate(row.id)}
        >
          放弃
        </Button>
      ),
    },
  ];

  return (
    <Space direction="vertical" style={{ width: '100%' }} size={16}>
      <Typography.Title level={4} style={{ margin: 0 }}>
        加群失败队列
      </Typography.Title>
      <Typography.Text type="secondary">
        以下群组的自动加入流程失败，需人工处理（联系群主/通过熟人邀请等）。
        点击"放弃"停止重试。
      </Typography.Text>

      <Table<JoinFailureRow>
        rowKey="id"
        dataSource={rows}
        columns={columns}
        loading={isLoading}
        pagination={{ pageSize: 20, showSizeChanger: false }}
        locale={{
          emptyText: (
            <Empty
              image={Empty.PRESENTED_IMAGE_SIMPLE}
              description="暂无失败记录"
            />
          ),
        }}
      />
    </Space>
  );
}
