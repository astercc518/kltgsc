import React from 'react';
import { Card, Typography, Descriptions, Tag, Alert, Space } from 'antd';
import { decodeJwtPayload } from '../api';
import { useT } from '../i18n';

const { Title, Text } = Typography;

const SalesSettings: React.FC = () => {
  const t = useT();
  const profile = decodeJwtPayload();

  return (
    <div>
      <Title level={3} style={{ margin: 0 }}>{t('settings.title')}</Title>
      <Text type="secondary">{t('settings.subtitle')}</Text>

      <Card style={{ marginTop: 16 }} title={t('settings.account')}>
        <Descriptions column={1} bordered>
          <Descriptions.Item label={t('settings.email')}>{profile?.email}</Descriptions.Item>
          <Descriptions.Item label={t('settings.kind')}>
            <Tag color={profile?.kind === 'platform' ? 'purple' : 'cyan'}>
              {profile?.kind === 'platform' ? t('settings.kindPlatform') : t('settings.kindTenant')}
            </Tag>
          </Descriptions.Item>
          {profile?.kind === 'customer' && (
            <Descriptions.Item label={t('settings.tenantId')}>
              {profile.customer_id}
            </Descriptions.Item>
          )}
        </Descriptions>
      </Card>

      <Alert
        style={{ marginTop: 16 }}
        type="info" showIcon
        message={t('settings.industryFilter')}
        description={<Space direction="vertical"><Text>{t('settings.industryFilterDesc')}</Text></Space>}
      />
    </div>
  );
};

export default SalesSettings;
