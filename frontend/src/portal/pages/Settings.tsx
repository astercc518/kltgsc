import React, { useEffect } from 'react';
import {
  Card, Form, Input, Switch, Button, message, Typography, Alert, Slider,
} from 'antd';
import { LinkOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import portalApi from '../api';

const { Title, Text } = Typography;

interface SettingsPayload {
  handover_group_link: string | null;
  takeover_timeout_minutes: number;
  notify_main_account: boolean;
}

const settingsApi = {
  get: () => portalApi.get<SettingsPayload>('/customer/settings').then(r => r.data),
  patch: (data: Partial<SettingsPayload>) =>
    portalApi.patch<SettingsPayload>('/customer/settings', data).then(r => r.data),
};

const PortalSettings: React.FC = () => {
  const qc = useQueryClient();
  const [form] = Form.useForm();

  const { data, isLoading } = useQuery({
    queryKey: ['portal', 'settings'],
    queryFn: settingsApi.get,
  });

  useEffect(() => {
    if (data) {
      form.setFieldsValue({
        handover_group_link: data.handover_group_link || '',
        takeover_timeout_minutes: data.takeover_timeout_minutes,
        notify_main_account: data.notify_main_account,
      });
    }
  }, [data, form]);

  const saveMut = useMutation({
    mutationFn: (values: Partial<SettingsPayload>) => settingsApi.patch(values),
    onSuccess: () => {
      message.success('Saved');
      qc.invalidateQueries({ queryKey: ['portal', 'settings'] });
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.detail || 'Save failed');
    },
  });

  return (
    <div>
      <Title level={3}>Settings</Title>
      <Text type="secondary">
        Configure how AI marketing accounts hand high-intent prospects over to you.
      </Text>

      <Alert
        type="info"
        showIcon
        style={{ margin: '16px 0', maxWidth: 720 }}
        message="How takeover works"
        description={
          <ul style={{ margin: 0, paddingLeft: 20 }}>
            <li>When AI detects a high-intent DM, you get a Saved Messages alert (if notifications enabled)</li>
            <li>If you don't claim the lead within the timeout, AI automatically DMs the prospect with your Handover Group link</li>
            <li>Either way, the lead lands in your CRM for follow-up</li>
          </ul>
        }
      />

      <Card style={{ maxWidth: 720 }} loading={isLoading}>
        <Form form={form} layout="vertical" onFinish={(v) => saveMut.mutate(v)}>
          <Form.Item
            name="handover_group_link"
            label={
              <span>
                <LinkOutlined /> Business Handover Group Link
              </span>
            }
            extra="A TG group invite link your sales team is monitoring. AI sends this to prospects you didn't claim in time."
          >
            <Input placeholder="https://t.me/+yourHandoverGroup" />
          </Form.Item>

          <Form.Item
            name="takeover_timeout_minutes"
            label="Takeover Timeout (minutes)"
            extra="Time you have to claim a high-intent lead before AI escalates. 1–30 min."
          >
            <Slider
              min={1}
              max={30}
              marks={{ 1: '1m', 5: '5m', 10: '10m', 30: '30m' }}
            />
          </Form.Item>

          <Form.Item
            name="notify_main_account"
            label="Notify my Main Account (Saved Messages)"
            valuePropName="checked"
            extra="Push high-intent alerts to your main Telegram account as a Saved Messages note."
          >
            <Switch />
          </Form.Item>

          <Button type="primary" htmlType="submit" loading={saveMut.isPending}
                  style={{ background: '#0066FF', borderColor: '#0066FF' }}>
            Save Settings
          </Button>
        </Form>
      </Card>
    </div>
  );
};

export default PortalSettings;
