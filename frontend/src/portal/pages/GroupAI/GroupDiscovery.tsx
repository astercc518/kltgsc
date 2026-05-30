/**
 * GroupDiscovery — 客户审批每周系统推荐的候选线索群.
 *
 * 列表按 score desc 排序; approve → 系统尝试加群 (Phase 8 接入 CAPTCHA);
 * reject → 加入黑名单不再推.
 */
import React from 'react';
import { Card, Button, Tag, Space, Typography, Empty, Popconfirm, Tabs } from 'antd';
import { CheckOutlined, CloseOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { groupAiApi, DiscoveryCandidate } from '../../api/groupAi';

const { Title, Paragraph } = Typography;


function CandidateCard({ row, onApprove, onReject }: {
  row: DiscoveryCandidate;
  onApprove: () => void;
  onReject: () => void;
}) {
  return (
    <Card style={{ marginBottom: 12 }}
          extra={
            row.score !== null
              ? <Tag color={row.score > 70 ? 'green' : row.score > 50 ? 'blue' : 'default'}>
                  评分 {row.score.toFixed(0)}
                </Tag>
              : null
          }
          actions={[
            <Popconfirm key="approve" title="批准后系统会尝试加群" onConfirm={onApprove}>
              <Button type="primary" icon={<CheckOutlined />}>批准</Button>
            </Popconfirm>,
            <Popconfirm key="reject" title="拒绝后此群进黑名单不再推" onConfirm={onReject}>
              <Button danger icon={<CloseOutlined />}>拒绝</Button>
            </Popconfirm>,
          ]}>
      <h4>{row.title || row.chat_username || '(no title)'}</h4>
      <Paragraph type="secondary" style={{ marginBottom: 8 }}>
        {row.chat_link}
      </Paragraph>
      <Space wrap>
        {row.members_count && <Tag>{row.members_count.toLocaleString()} 成员</Tag>}
        {row.category && <Tag>{row.category}</Tag>}
        {row.source_query && <Tag color="purple">关键词: {row.source_query}</Tag>}
      </Space>
    </Card>
  );
}


export default function GroupDiscovery() {
  const [status, setStatus] = React.useState('pending');
  const qc = useQueryClient();

  const { data: rows = [] } = useQuery({
    queryKey: ['portal-discovery', status],
    queryFn: () => groupAiApi.listDiscoveryCandidates(status),
  });

  const approveMut = useMutation({
    mutationFn: (id: number) => groupAiApi.approveDiscoveryCandidate(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portal-discovery'] }),
  });
  const rejectMut = useMutation({
    mutationFn: (id: number) => groupAiApi.rejectDiscoveryCandidate(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portal-discovery'] }),
  });

  return (
    <div>
      <Title level={3}>线索群发现</Title>
      <Paragraph type="secondary">
        系统每周根据你的 ICP 画像自动搜索匹配的群 (TGStat 数据源).
        批准的群会进入监听列表; 拒绝的群进黑名单不再推荐.
      </Paragraph>

      <Tabs activeKey={status} onChange={setStatus} items={[
        { key: 'pending', label: '待审批' },
        { key: 'approved', label: '已批准' },
        { key: 'rejected', label: '已拒绝' },
      ]} />

      {rows.length === 0 ? (
        <Empty description={`暂无 ${status} 候选 (下周一上午刷新)`} />
      ) : (
        rows.map(r => (
          <CandidateCard
            key={r.id} row={r}
            onApprove={() => approveMut.mutate(r.id)}
            onReject={() => rejectMut.mutate(r.id)}
          />
        ))
      )}
    </div>
  );
}
