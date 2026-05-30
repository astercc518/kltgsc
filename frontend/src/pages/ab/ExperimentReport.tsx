/**
 * ExperimentReport — Admin A/B experiment report page.
 * Displays variant metric cards with CI ranges, significance test result,
 * and CSV download button.
 */
import React from 'react';
import {
  Button, Card, Col, Descriptions, Row, Spin, Statistic, Tag, Typography, Alert,
  Space,
} from 'antd';
import { DownloadOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { abApi, ABReport } from '../../services/groupAi';

const { Title, Text } = Typography;

const STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  running: 'green',
  finished: 'blue',
  paused: 'orange',
};

const METRIC_LABEL: Record<string, string> = {
  reply_rate: '回复率',
  private_conversion_rate: '私聊转化率',
  kick_rate: '踢人率',
  anti_hallucination_failure_rate: '幻觉失败率',
};

function pct(v: number) {
  return `${(v * 100).toFixed(2)}%`;
}

function ciStr(lo: number, hi: number) {
  return `[${pct(lo)}, ${pct(hi)}]`;
}

interface VariantCardProps {
  v: ABReport['variants'][number];
  isPrimary: (metric: string) => boolean;
}

function VariantCard({ v, isPrimary }: VariantCardProps) {
  return (
    <Card
      title={
        <Space>
          <Tag color="blue">{v.tag}</Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>
            发送 {v.sent} / 建议 {v.suggested} / 跳过 {v.skipped_total} / 失败 {v.failed}
          </Text>
        </Space>
      }
      style={{ marginBottom: 16 }}
    >
      <Row gutter={[16, 16]}>
        {/* Reply rate */}
        <Col xs={24} sm={12} md={6}>
          <Statistic
            title={<span style={{ fontWeight: isPrimary('reply_rate') ? 700 : 400 }}>回复率</span>}
            value={pct(v.reply_rate)}
            valueStyle={{ color: isPrimary('reply_rate') ? '#1677ff' : undefined }}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            95% CI {ciStr(v.reply_ci_lo, v.reply_ci_hi)}
          </Text>
        </Col>

        {/* Private conversion */}
        <Col xs={24} sm={12} md={6}>
          <Statistic
            title={<span style={{ fontWeight: isPrimary('private_conversion_rate') ? 700 : 400 }}>私聊转化率</span>}
            value={pct(v.private_conversion_rate)}
            valueStyle={{ color: isPrimary('private_conversion_rate') ? '#1677ff' : undefined }}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            95% CI {ciStr(v.private_conversion_ci_lo, v.private_conversion_ci_hi)}
          </Text>
        </Col>

        {/* Kick rate */}
        <Col xs={24} sm={12} md={6}>
          <Statistic
            title={<span style={{ fontWeight: isPrimary('kick_rate') ? 700 : 400 }}>踢人率</span>}
            value={pct(v.kick_rate)}
            valueStyle={{ color: isPrimary('kick_rate') ? '#ff4d4f' : undefined }}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            95% CI {ciStr(v.kick_ci_lo, v.kick_ci_hi)}
          </Text>
        </Col>

        {/* Hallucination failure rate */}
        <Col xs={24} sm={12} md={6}>
          <Statistic
            title={<span style={{ fontWeight: isPrimary('anti_hallucination_failure_rate') ? 700 : 400 }}>幻觉失败率</span>}
            value={pct(v.anti_hallucination_failure_rate)}
            valueStyle={{ color: isPrimary('anti_hallucination_failure_rate') ? '#ff4d4f' : undefined }}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            95% CI {ciStr(v.failure_ci_lo, v.failure_ci_hi)}
          </Text>
        </Col>
      </Row>
    </Card>
  );
}

export default function ExperimentReport() {
  const { id } = useParams<{ id: string }>();
  const numId = Number(id);
  const navigate = useNavigate();

  const { data: report, isLoading, error } = useQuery({
    queryKey: ['ab-report', numId],
    queryFn: () => abApi.report(numId),
    enabled: !!numId,
    refetchInterval: 60000,
  });

  if (isLoading) {
    return (
      <div style={{ textAlign: 'center', padding: 48 }}>
        <Spin tip="加载报告中…" />
      </div>
    );
  }

  if (error || !report) {
    return (
      <Alert
        type="error"
        message="加载失败"
        description="无法获取实验报告，请检查实验 ID 或稍后重试。"
        action={
          <Button size="small" onClick={() => navigate('/admin/ab/experiments')}>返回列表</Button>
        }
      />
    );
  }

  const isPrimary = (metric: string) => metric === report.primary_metric;
  const sig = report.significance;

  return (
    <div style={{ maxWidth: 1100, margin: '0 auto' }}>
      {/* ── Header ── */}
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 24 }}>
        <div>
          <Button
            icon={<ArrowLeftOutlined />}
            type="text"
            onClick={() => navigate('/admin/ab/experiments')}
            style={{ paddingLeft: 0, marginBottom: 4 }}
          >
            返回列表
          </Button>
          <Title level={4} style={{ margin: 0 }}>
            {report.experiment_name}
            <Tag
              color={STATUS_COLOR[report.status] ?? 'default'}
              style={{ marginLeft: 12, verticalAlign: 'middle', fontSize: 12 }}
            >
              {report.status}
            </Tag>
          </Title>
          <Text type="secondary" style={{ fontSize: 12 }}>
            报告生成时间: {new Date(report.generated_at).toLocaleString('zh-CN')}
          </Text>
        </div>

        <a href={abApi.csvUrl(numId)} download>
          <Button icon={<DownloadOutlined />}>下载 CSV</Button>
        </a>
      </div>

      {/* ── Experiment metadata ── */}
      <Card style={{ marginBottom: 24 }}>
        <Descriptions size="small" column={{ xs: 1, sm: 2, md: 3 }}>
          <Descriptions.Item label="实验 ID">{report.experiment_id}</Descriptions.Item>
          <Descriptions.Item label="状态">
            <Tag color={STATUS_COLOR[report.status] ?? 'default'}>{report.status}</Tag>
          </Descriptions.Item>
          <Descriptions.Item label="主要指标">
            {report.primary_metric ? (METRIC_LABEL[report.primary_metric] ?? report.primary_metric) : '未设置'}
          </Descriptions.Item>
        </Descriptions>
      </Card>

      {/* ── Variant cards ── */}
      <Title level={5} style={{ marginBottom: 12 }}>变体对比</Title>
      {report.variants.map(v => (
        <VariantCard key={v.tag} v={v} isPrimary={isPrimary} />
      ))}

      {/* ── Significance ── */}
      {sig ? (
        <Card
          title="显著性检验"
          style={{ marginTop: 8 }}
          extra={
            sig.significant_at_95 ? (
              <Tag color="green">✓ 95% 置信显著</Tag>
            ) : (
              <Tag color="red">✗ 不显著</Tag>
            )
          }
        >
          <Descriptions size="small" column={{ xs: 1, sm: 3 }}>
            <Descriptions.Item label="指标">
              {METRIC_LABEL[sig.metric] ?? sig.metric}
            </Descriptions.Item>
            <Descriptions.Item label="Z 值">
              {sig.z != null ? sig.z.toFixed(4) : '—'}
            </Descriptions.Item>
            <Descriptions.Item label="P 值">
              {sig.p_value != null ? sig.p_value.toFixed(4) : '—'}
            </Descriptions.Item>
          </Descriptions>
        </Card>
      ) : (
        <Alert
          type="info"
          message="暂无显著性检验数据"
          description="实验变体数据不足或尚未运行，无法进行统计显著性检验。"
          style={{ marginTop: 8 }}
        />
      )}
    </div>
  );
}
