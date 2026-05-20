import React, { useEffect, useRef, useState } from 'react';
import {
  Card, Typography, Button, Space, Alert, Modal, Input, message, Tag, Spin, Popconfirm,
} from 'antd';
import { QRCode } from 'antd';
import {
  DisconnectOutlined, MobileOutlined, CheckCircleOutlined, LockOutlined,
} from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { mainAccountApi, QRStartResponse } from '../api';

const { Title, Text, Paragraph } = Typography;

const STATE_TAG: Record<string, { color: string; label: string }> = {
  pending: { color: 'blue', label: 'Waiting for scan' },
  password_required: { color: 'orange', label: '2FA password required' },
  success: { color: 'green', label: 'Connected' },
  expired: { color: 'default', label: 'QR expired' },
  error: { color: 'red', label: 'Error' },
};

const MainAccount: React.FC = () => {
  const qc = useQueryClient();
  const [qrSession, setQrSession] = useState<QRStartResponse | null>(null);
  const [polledState, setPolledState] = useState<string>('pending');
  const [polledError, setPolledError] = useState<string | undefined>();
  const [showPasswordModal, setShowPasswordModal] = useState(false);
  const [password, setPassword] = useState('');
  const pollRef = useRef<number | null>(null);

  const { data: current, refetch: refetchCurrent } = useQuery({
    queryKey: ['portal', 'main-account'],
    queryFn: mainAccountApi.current,
  });

  const startMut = useMutation({
    mutationFn: () => mainAccountApi.start(),
    onSuccess: (data) => {
      setQrSession(data);
      setPolledState(data.state);
      setPolledError(undefined);
      message.success(data.mock ? 'Mock mode — auto-completing in ~1s' : 'QR ready — scan with Telegram');
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.detail || 'Failed to start QR login');
    },
  });

  const passwordMut = useMutation({
    mutationFn: () => mainAccountApi.submitPassword(qrSession!.token, password),
    onSuccess: () => {
      message.success('Password submitted, waiting for confirmation...');
      setShowPasswordModal(false);
      setPassword('');
    },
    onError: (err: any) => {
      message.error(err?.response?.data?.detail || 'Password submission failed');
    },
  });

  const disconnectMut = useMutation({
    mutationFn: () => mainAccountApi.disconnect(),
    onSuccess: () => {
      message.success('Main account disconnected');
      qc.invalidateQueries({ queryKey: ['portal', 'main-account'] });
      setQrSession(null);
    },
  });

  // Polling loop while QR is active
  useEffect(() => {
    if (!qrSession || ['success', 'expired', 'error'].includes(polledState)) {
      if (pollRef.current) {
        window.clearInterval(pollRef.current);
        pollRef.current = null;
      }
      return;
    }
    pollRef.current = window.setInterval(async () => {
      try {
        const s = await mainAccountApi.status(qrSession.token);
        setPolledState(s.state);
        setPolledError(s.error);
        if (s.state === 'password_required') {
          setShowPasswordModal(true);
        }
        if (s.state === 'success') {
          message.success('Main account connected!');
          refetchCurrent();
        }
      } catch (e) {
        // ignore transient
      }
    }, 2000);
    return () => {
      if (pollRef.current) window.clearInterval(pollRef.current);
    };
  }, [qrSession, polledState, refetchCurrent]);

  // ── Render branches ────────────────────────────────────────────────

  // Already connected
  if (current?.connected) {
    return (
      <div>
        <Title level={3}>My Telegram Main Account</Title>
        <Text type="secondary">
          Your personal Telegram account is connected. Chat history can now be imported into
          a personal knowledge base, and AI marketing accounts will notify you on high-intent leads.
        </Text>

        <Card style={{ marginTop: 24, maxWidth: 540 }}>
          <Space direction="vertical" size="middle" style={{ width: '100%' }}>
            <Space>
              <CheckCircleOutlined style={{ fontSize: 24, color: '#22c55e' }} />
              <Title level={4} style={{ margin: 0 }}>Connected</Title>
              <Tag color="green">Active</Tag>
            </Space>
            <div>
              <Text type="secondary">Phone:</Text>{' '}
              <Text strong>+••• ••• {current.phone_last4 || '????'}</Text>
            </div>
            {current.connected_at && (
              <div>
                <Text type="secondary">Connected at:</Text>{' '}
                <Text>{new Date(current.connected_at).toLocaleString()}</Text>
              </div>
            )}
            <Alert
              type="info"
              showIcon
              message="Tip"
              description="To switch accounts, disconnect first then scan a new QR. Your imported KB will remain associated with your current subscription."
            />
            <Popconfirm
              title="Disconnect main account?"
              description="The encrypted session will be wiped. Your KB rows stay; you can rescan anytime."
              onConfirm={() => disconnectMut.mutate()}
              okType="danger"
            >
              <Button danger icon={<DisconnectOutlined />} loading={disconnectMut.isPending}>
                Disconnect
              </Button>
            </Popconfirm>
          </Space>
        </Card>
      </div>
    );
  }

  // Active QR session
  if (qrSession && polledState !== 'success') {
    const tagInfo = STATE_TAG[polledState] || STATE_TAG.pending;
    const showQR = polledState === 'pending' || polledState === 'password_required';
    return (
      <div>
        <Title level={3}>Scan to Connect Your Telegram</Title>
        <Card style={{ maxWidth: 480 }}>
          <Space direction="vertical" size="middle" align="center" style={{ width: '100%' }}>
            <Tag color={tagInfo.color} icon={polledState === 'pending' ? <Spin size="small" /> : undefined}>
              {tagInfo.label}
            </Tag>
            {showQR && (
              <QRCode
                value={qrSession.qr_url}
                size={240}
                icon="https://telegram.org/img/t_logo.png"
              />
            )}
            <Paragraph type="secondary" style={{ textAlign: 'center', marginBottom: 0 }}>
              Open Telegram on your phone → <strong>Settings → Devices → Link Desktop Device</strong> → scan this QR
            </Paragraph>
            {qrSession.mock && (
              <Alert
                type="warning"
                showIcon
                message="MOCK_QR_AUTOACCEPT=1 — completing automatically in ~1s for testing"
              />
            )}
            {polledState === 'expired' && (
              <Alert type="error" showIcon message="QR expired" />
            )}
            {polledState === 'error' && (
              <Alert type="error" showIcon message={`Error: ${polledError}`} />
            )}
            <Space>
              <Button onClick={() => { setQrSession(null); setPolledState('pending'); }}>Cancel</Button>
              {(polledState === 'expired' || polledState === 'error') && (
                <Button type="primary" onClick={() => startMut.mutate()}>
                  Restart
                </Button>
              )}
            </Space>
          </Space>
        </Card>

        <Modal
          open={showPasswordModal}
          onCancel={() => setShowPasswordModal(false)}
          onOk={() => passwordMut.mutate()}
          okText="Submit"
          confirmLoading={passwordMut.isPending}
          title={<><LockOutlined /> Two-factor password required</>}
        >
          <Paragraph>
            Your Telegram account has 2FA enabled. Enter your cloud password to complete login.
          </Paragraph>
          <Input.Password
            placeholder="2FA password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            onPressEnter={() => passwordMut.mutate()}
          />
        </Modal>
      </div>
    );
  }

  // Idle (no current connection, no active QR)
  return (
    <div>
      <Title level={3}>My Telegram Main Account</Title>
      <Text type="secondary">
        Connect your personal Telegram so we can:
      </Text>
      <ul style={{ marginTop: 8, color: '#475569' }}>
        <li>Import your chat history into a personal AI knowledge base</li>
        <li>Notify you in <strong>Saved Messages</strong> when a high-intent prospect appears</li>
        <li>Let AI marketing accounts cite your real product expertise</li>
      </ul>
      <Alert
        type="info"
        showIcon
        style={{ margin: '16px 0', maxWidth: 540 }}
        message="Your session is encrypted at rest (AES-256-GCM) and never leaves the platform."
      />
      <Button
        type="primary"
        size="large"
        icon={<MobileOutlined />}
        loading={startMut.isPending}
        onClick={() => startMut.mutate()}
        style={{ background: '#0066FF', borderColor: '#0066FF' }}
      >
        Connect via QR
      </Button>
    </div>
  );
};

export default MainAccount;
