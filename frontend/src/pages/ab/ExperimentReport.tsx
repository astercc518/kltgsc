/**
 * ExperimentReport — Admin A/B experiment report page.
 * Displays variant metric cards with CI ranges, significance test result,
 * and CSV download button.
 */
import React from 'react';
import {
  Button, Card, Col, Descriptions, Row, Spin, Statistic, Tag, Typography, Alert,
  Space, notification,
} from 'antd';
import { DownloadOutlined, ArrowLeftOutlined } from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { useParams, useNavigate } from 'react-router-dom';
import { abApi, ABReport } from '../../services/groupAi';

const { Title, Text } = Typography;

const METRIC_LABEL: Record<string, string> = {
  reply_rate: '回复率',
  private_conversion_rate: '私聊转化率',
  kick_rate: '踢人率',
  anti_hallucination_failure_rate: '幻觉失败率',
};

function pct(v: number) {
  return `${(v * 100).toFixed(2)}%`;
}

function ciStr(ci: [number, number] | undefined) {
  if (!ci) return '—';
  return `[${pct(ci[0])}, ${pct(ci[1])}]`;
}

interface VariantCardProps {
  v: ABReport['variants'][number];
  isPrimary: (metric: string) => boolean;
}

function VariantCard({ v, isPrimary }: VariantCardProps) {
  const sent = v.counters?.sent ?? 0;
  const suggested = v.counters?.suggested ?? 0;
  const skipped = v.counters?.skipped_total ?? 0;
  const failed = v.counters?.failed ?? 0;

  const replyRate = v.metrics?.reply_rate ?? 0;
  const pcrRate = v.metrics?.private_conversion_rate ?? 0;
  const kickRate = v.metrics?.kick_rate ?? 0;
  const ahfrRate = v.metrics?.anti_hallucination_failure_rate ?? 0;

  return (
    <Card
      title={
        <Space>
          <Tag color="blue">{v.tag}</Tag>
          <Text type="secondary" style={{ fontSize: 12 }}>
            发送 {sent} / 建议 {suggested} / 跳过 {skipped} / 失败 {failed}
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
            value={pct(replyRate)}
            valueStyle={{ color: isPrimary('reply_rate') ? '#1677ff' : undefined }}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            95% CI {ciStr(v.ci?.reply_rate_ci)}
          </Text>
        </Col>

        {/* Private conversion */}
        <Col xs={24} sm={12} md={6}>
          <Statistic
            title={<span style={{ fontWeight: isPrimary('private_conversion_rate') ? 700 : 400 }}>私聊转化率</span>}
            value={pct(pcrRate)}
            valueStyle={{ color: isPrimary('private_conversion_rate') ? '#1677ff' : undefined }}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            95% CI {ciStr(v.ci?.private_conversion_rate_ci)}
          </Text>
        </Col>

        {/* Kick rate */}
        <Col xs={24} sm={12} md={6}>
          <Statistic
            title={<span style={{ fontWeight: isPrimary('kick_rate') ? 700 : 400 }}>踢人率</span>}
            value={pct(kickRate)}
            valueStyle={{ color: isPrimary('kick_rate') ? '#ff4d4f' : undefined }}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            95% CI {ciStr(v.ci?.kick_rate_ci)}
          </Text>
        </Col>

        {/* Hallucination failure rate */}
        <Col xs={24} sm={12} md={6}>
          <Statistic
            title={<span style={{ fontWeight: isPrimary('anti_hallucination_failure_rate') ? 700 : 400 }}>幻觉失败率</span>}
            value={pct(ahfrRate)}
            valueStyle={{ color: isPrimary('anti_hallucination_failure_rate') ? '#ff4d4f' : undefined }}
          />
          <Text type="secondary" style={{ fontSize: 12 }}>
            95% CI {ciStr(v.ci?.anti_hallucination_failure_rate_ci)}
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

  const downloadCsv = async () => {
    const token = localStorage.getItem('token') || '';
    const url = abApi.csvUrl(numId);
    try {
      const res = await fetch(url, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const blob = await res.blob();
      const objectUrl = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = objectUrl;
      a.download = `ab_report_${report?.experiment ?? id}.csv`;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(objectUrl);
    } catch (e) {
      notification.error({ message: 'CSV 下载失败', description: String(e) });
    }
  };

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
            {report.experiment}
          </Title>
        </div>

        <Button icon={<DownloadOutlined />} onClick={downloadCsv}>下载 CSV</Button>
      </div>

      {/* ── Experiment metadata ── */}
      <Card style={{ marginBottom: 24 }}>
        <Descriptions size="small" column={{ xs: 1, sm: 2, md: 3 }}>
          <Descriptions.Item label="实验名称">{report.experiment}</Descriptions.Item>
          <Descriptions.Item label="主要指标">
            {report.primary_metric ? (METRIC_LABEL[report.primary_metric] ?? report.primary_metric) : '未设置'}
          </Descriptions.Item>
          <Descriptions.Item label="变体数">{report.variants.length}</Descriptions.Item>
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
            sig.significant ? (
              <Tag color="green">✓ 95% 置信显著</Tag>
            ) : (
              <Tag color="red">✗ 不显著</Tag>
            )
          }
        >
          <Descriptions size="small" column={{ xs: 1, sm: 3 }}>
            <Descriptions.Item label="指标">
              {METRIC_LABEL[sig.primary_metric] ?? sig.primary_metric}
            </Descriptions.Item>
            <Descriptions.Item label="Z 值">
              {sig.z_stat != null ? sig.z_stat.toFixed(4) : '—'}
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
