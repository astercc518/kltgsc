/**
 * GroupAIInteractions — admin view of group-AI replies (sent + suggested).
 * Approve/edit suggested rows. Auto-refetch every 15s + WS realtime push.
 */
import React from 'react';
import { Table, Tag, Button, Modal, Input, Space, Typography, Empty } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { groupAiAdminApi, InboxRow } from '../../services/groupAi';
import { useGroupAiWebsocket } from '../../hooks/useGroupAiWebsocket';

const { Title } = Typography;

export default function GroupAIInteractions() {
  const [customerId, setCustomerId] = React.useState<number | null>(null);
  useGroupAiWebsocket(customerId ?? undefined);
  const qc = useQueryClient();
  const [editing, setEditing] = React.useState<InboxRow | null>(null);
  const [editText, setEditText] = React.useState('');
  const [pendingApproveId, setPendingApproveId] = React.useState<number | null>(null);

  const { data: rows = [] } = useQuery({
    queryKey: ['admin-inbox-group-ai', customerId],
    queryFn: () => customerId ? groupAiAdminApi.listInbox(customerId) : Promise.resolve([]),
    enabled: customerId !== null,
    refetchInterval: 15000,
  });

  const approveMut = useMutation({
    mutationFn: (pr_id: number) => groupAiAdminApi.approveSuggested(pr_id),
    onMutate: (pr_id) => setPendingApproveId(pr_id),
    onSettled: () => setPendingApproveId(null),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['admin-inbox-group-ai', customerId] }),
  });
  const editMut = useMutation({
    mutationFn: ({ pr_id, text }: { pr_id: number; text: string }) =>
      groupAiAdminApi.editSuggested(pr_id, text),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['admin-inbox-group-ai', customerId] });
      setEditing(null);
    },
  });

  const columns = [
    { title: '状态', dataIndex: 'status', width: 100,
      render: (s: string) => <Tag color={s === 'sent' ? 'green' : 'orange'}>{s}</Tag> },
    { title: '客户消息', dataIndex: 'source_text', ellipsis: true },
    { title: '主题', dataIndex: 'solution_topic', width: 180 },
    { title: '需求点', dataIndex: 'extracted_needs', width: 240,
      render: (n: string[] | null) => (n || []).map(x => <Tag key={x}>{x}</Tag>) },
    { title: 'AI 回复', dataIndex: 'reply_text', ellipsis: true },
    { title: '操作', width: 220,
      render: (_: unknown, r: InboxRow) =>
        r.status === 'suggested' ? (
          <Space>
            <Button size="small" onClick={() => { setEditing(r); setEditText(r.reply_text || ''); }}>编辑</Button>
            <Button size="small" type="primary"
                    loading={approveMut.isPending && pendingApproveId === r.id}
                    onClick={() => approveMut.mutate(r.id)}>批准发送</Button>
          </Space>
        ) : null },
  ];

  return (
    <div>
      <Title level={4}>群内 AI 互动</Title>
      <Space style={{ marginBottom: 16 }}>
        <span>客户 ID:</span>
        <Input
          style={{ width: 200 }}
          placeholder="输入客户 ID"
          type="number"
          onPressEnter={(e) => setCustomerId(Number((e.target as HTMLInputElement).value) || null)}
          onBlur={(e) => setCustomerId(Number(e.target.value) || null)}
        />
      </Space>
      {customerId === null ? (
        <Empty description="先输入客户 ID 加载该客户的群内 AI 回复历史" />
      ) : (
        <Table dataSource={rows} columns={columns} rowKey="id" pagination={{ pageSize: 20 }} />
      )}

      <Modal title={`编辑 #${editing?.id}`} open={!!editing} onCancel={() => setEditing(null)}
             onOk={() => editing && editMut.mutate({ pr_id: editing.id, text: editText })}
             confirmLoading={editMut.isPending}>
        <Input.TextArea rows={4} value={editText} onChange={(e) => setEditText(e.target.value)} />
      </Modal>
    </div>
  );
}
