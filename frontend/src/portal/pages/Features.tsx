import React from 'react';
import {
  Card, Row, Col, Table, Tag, Typography, Statistic, Space, Empty, Alert,
} from 'antd';
import {
  AppstoreOutlined, DollarOutlined, CheckCircleOutlined, CloseCircleOutlined,
} from '@ant-design/icons';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { featureApi, walletApi, CustomerFeatureView, FeatureUsageView } from '../api';

const { Title, Text, Paragraph } = Typography;

const CATEGORY_LABEL: Record<string, { color: string; text: string }> = {
  marketing: { color: 'magenta', text: '营销' },
  scraping: { color: 'cyan', text: '采集' },
  ai: { color: 'purple', text: 'AI' },
  kb: { color: 'green', text: '知识库' },
  account: { color: 'orange', text: '账号' },
};

const formatCents = (c: number) => `$${(c / 100).toFixed(2)}`;

const PortalFeatures: React.FC = () => {
  const featuresQuery = useQuery({
    queryKey: ['portal', 'features'],
    queryFn: featureApi.list,
    refetchInterval: 60000,
  });
  const usageQuery = useQuery({
    queryKey: ['portal', 'features', 'usage'],
    queryFn: () => featureApi.usage(30),
    refetchInterval: 60000,
  });
  const walletQuery = useQuery({
    queryKey: ['portal', 'wallet'],
    queryFn: walletApi.get,
    refetchInterval: 30000,
  });

  const features = featuresQuery.data || [];
  const usage = usageQuery.data || [];
  const wallet = walletQuery.data;

  const usageMap = new Map<string, FeatureUsageView>(
    usage.map(u => [u.feature_slug, u])
  );

  const enabled = features.filter(f => f.enabled);
  const totalSpend30d = usage.reduce((s, u) => s + u.total_charged_cents, 0);

  const columns = [
    { title: '功能', key: 'feature', width: 200,
      render: (_: any, row: CustomerFeatureView) => (
        <Space direction="vertical" size={0}>
          <Text strong>{row.name_zh}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>{row.feature_slug}</Text>
        </Space>
      ),
    },
    { title: '类别', dataIndex: 'category', key: 'category', width: 90,
      render: (c: string) => {
        const info = CATEGORY_LABEL[c] || { color: 'default', text: c };
        return <Tag color={info.color}>{info.text}</Tag>;
      },
    },
    { title: '状态', dataIndex: 'enabled', key: 'enabled', width: 110,
      render: (e: boolean) => e
        ? <Tag color="green" icon={<CheckCircleOutlined />}>已开通</Tag>
        : <Tag icon={<CloseCircleOutlined />}>未开通</Tag>,
    },
    { title: '我的单价', key: 'price', width: 140,
      render: (_: any, row: CustomerFeatureView) => (
        <Space direction="vertical" size={0}>
          <Text strong>{formatCents(row.unit_price_cents)}</Text>
          <Text type="secondary" style={{ fontSize: 12 }}>
            / {row.billing_unit}
            {row.is_custom_price && <Tag color="gold" style={{ marginLeft: 4, fontSize: 10 }}>专属价</Tag>}
          </Text>
        </Space>
      ),
    },
    { title: '近 30 天用量', key: 'usage', width: 180,
      render: (_: any, row: CustomerFeatureView) => {
        const u = usageMap.get(row.feature_slug);
        if (!u || u.units_consumed === 0) return <Text type="secondary">无</Text>;
        return (
          <Space direction="vertical" size={0}>
            <Text>{u.units_consumed.toLocaleString()} {row.billing_unit}</Text>
            <Text type="secondary" style={{ fontSize: 12 }}>
              已花费 {formatCents(u.total_charged_cents)}
            </Text>
          </Space>
        );
      },
    },
    { title: '备注', dataIndex: 'notes', key: 'notes', ellipsis: true,
      render: (n: string) => n || <Text type="secondary">—</Text> },
  ];

  return (
    <div>
      <Title level={2}><AppstoreOutlined /> 我的功能包</Title>
      <Paragraph type="secondary">
        除了订阅套餐外开通的独立计费功能，按用量从钱包扣费。开通新功能请联系运营。
      </Paragraph>

      <Row gutter={16} style={{ marginBottom: 24 }}>
        <Col span={6}>
          <Card loading={walletQuery.isLoading}>
            <Statistic title="钱包余额"
              value={wallet ? wallet.balance_cents / 100 : 0}
              precision={2} prefix="$"
              valueStyle={{ color: '#0066FF', fontSize: 28 }}
            />
            <Link to="/portal/wallet" style={{ fontSize: 13 }}>去充值 →</Link>
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="已开通功能"
              value={enabled.length} suffix={`/ ${features.length}`}
              prefix={<CheckCircleOutlined style={{ color: '#22C55E' }} />}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="近 30 天花费"
              value={(totalSpend30d / 100).toFixed(2)} prefix="$"
              valueStyle={{ color: '#EF4444' }}
            />
          </Card>
        </Col>
        <Col span={6}>
          <Card>
            <Statistic title="活跃功能"
              value={usage.filter(u => u.units_consumed > 0).length}
              prefix={<DollarOutlined />}
            />
          </Card>
        </Col>
      </Row>

      {wallet && wallet.balance_cents < 2000 && (
        <Alert
          type="warning" showIcon style={{ marginBottom: 16 }}
          message="钱包余额不足 $20"
          description={<>建议立即 <Link to="/portal/wallet">去充值</Link>，否则功能调用会被拒绝。</>}
        />
      )}

      <Card title={`功能列表（${features.length}）`}>
        {features.length === 0 ? (
          <Empty description="暂无可用功能。请联系运营开通。" />
        ) : (
          <Table
            rowKey="feature_slug"
            dataSource={features}
            columns={columns}
            loading={featuresQuery.isLoading}
            pagination={false}
          />
        )}
      </Card>
    </div>
  );
};

export default PortalFeatures;
