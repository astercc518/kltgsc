import React from 'react';
import { Card, Typography, Descriptions, Tag, Alert, Space } from 'antd';
import { decodeJwtPayload } from '../api';

const { Title, Text } = Typography;

const SalesSettings: React.FC = () => {
  const profile = decodeJwtPayload();

  return (
    <div>
      <Title level={3} style={{ margin: 0 }}>Settings</Title>
      <Text type="secondary">Your identity and preferences.</Text>

      <Card style={{ marginTop: 16 }} title="Account">
        <Descriptions column={1} bordered>
          <Descriptions.Item label="Email">{profile?.email}</Descriptions.Item>
          <Descriptions.Item label="Kind">
            <Tag color={profile?.kind === 'platform' ? 'purple' : 'cyan'}>
              {profile?.kind === 'platform' ? 'Platform sales' : 'Tenant sub-user'}
            </Tag>
          </Descriptions.Item>
          {profile?.kind === 'customer' && (
            <Descriptions.Item label="Tenant customer ID">
              {profile.customer_id}
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      <Alert
        style={{ marginTop: 16 }}
        type="info" showIcon
        message="Industry filter"
        description={
          <Space direction="vertical">
            <Text>
              The lead list auto-filters to your assigned industries. Ask your
              customer admin (or platform admin) to update this list — coming
              soon as a self-serve field.
            </Text>
          </Space>
        }
      />
    </div>
  );
};

export default SalesSettings;
