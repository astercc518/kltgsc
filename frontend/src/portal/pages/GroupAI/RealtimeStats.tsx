/**
 * RealtimeStats — 今日 3 核心数字 + 可展开 skip_reason 分布.
 *
 * 数据来自 GET /portal/group-ai/stats/recent. 每 30s refetch.
 */
import React from 'react';
import { Card, Row, Col, Statistic, Collapse, Tag, Typography, Empty } from 'antd';
import { useQuery } from '@tanstack/react-query';
import { groupAiApi } from '../../api/groupAi';
import { usePortalStatsWebsocket } from '../../hooks/usePortalStatsWebsocket';

const { Title, Paragraph } = Typography;

export default function RealtimeStats() {
  usePortalStatsWebsocket();  // Phase 6: WS push + 30s polling fallback
  const { data } = useQuery({
    queryKey: ['portal-stats'],
    queryFn: () => groupAiApi.getRecentStats(),
    refetchInterval: 30000,
  });

  if (!data) return <Empty description="加载中" />;

  const conversion = data.sent_today > 0
    ? `${((data.sent_today / Math.max(1, data.triggered_today)) * 100).toFixed(1)}%`
    : '0%';
  const skippedTotal = Object.values(data.skipped).reduce((a, b) => a + b, 0);

  return (
    <div>
      <Title level={3}>今日数据 (UTC)</Title>
      <Paragraph type="secondary">
        每 30 秒自动刷新. 客户私聊转化率反映"群里被回复后主动私聊主号"的比例.
      </Paragraph>

      <Row gutter={16}>
        <Col span={8}>
          <Card>
            <Statistic title="今日命中" value={data.triggered_today} suffix="条" />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="今日发出" value={data.sent_today} suffix="条" />
          </Card>
        </Col>
        <Col span={8}>
          <Card>
            <Statistic title="发出占比" value={conversion} />
          </Card>
        </Col>
      </Row>

      <Collapse style={{ marginTop: 16 }} items={[{
        key: '1',
        label: `跳过明细 (共 ${skippedTotal} 条) + 失败/草稿`,
        children: (
          <div>
            <p><Tag>真人接话</Tag> {data.skipped.human_replied} 条 — 真人或其他号已接, AI 礼貌避让</p>
            <p><Tag>同线索去重</Tag> {data.skipped.dup} 条 — 48h 内已经回过同一客户</p>
            <p><Tag>限流</Tag> {data.skipped.throttled} 条 — 账号日额 / 群冷却保护</p>
            <p><Tag>边界值</Tag> {data.skipped.borderline} 条 — Layer 3 评分边缘, 留存供后续训练阈值</p>
            <p><Tag color="orange">副驾驶草稿</Tag> {data.suggested_today} 条 — 反幻觉拒, 待你在 Inbox 审</p>
            <p><Tag color="red">失败</Tag> {data.failed_today} 条 — LLM / 发送失败</p>
          </div>
        ),
      }]} />
    </div>
  );
}
