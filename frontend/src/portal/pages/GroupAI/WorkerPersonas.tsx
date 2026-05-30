/**
 * WorkerPersonas — 每个 worker 账号一张人设卡, 可编辑/重置.
 *
 * 数据流: list accounts → click → 拉 persona → drawer 编辑 → upsert.
 */
import React from 'react';
import { Card, Avatar, Button, Drawer, Form, Input, Select, InputNumber, Space, Tag, Typography, Row, Col } from 'antd';
import { UserOutlined, EditOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { groupAiApi, WorkerPersona } from '../../api/groupAi';

const { Title, Paragraph } = Typography;

const SPEAKING_STYLES = [
  { value: 'formal', label: 'formal 正式' },
  { value: 'casual', label: 'casual 随意 (默认)' },
  { value: 'techy', label: 'techy 技术风' },
  { value: 'northeastern_dialect', label: '东北话' },
  { value: 'cantonese_flavor', label: '广东话' },
];

export default function WorkerPersonas() {
  const [editingAcc, setEditingAcc] = React.useState<number | null>(null);
  const [form] = Form.useForm();
  const qc = useQueryClient();

  const { data: accounts = [] } = useQuery({
    queryKey: ['portal-accounts'],
    queryFn: () => groupAiApi.listAccounts(),
  });
  const { data: persona } = useQuery({
    queryKey: ['portal-persona', editingAcc],
    queryFn: () => editingAcc ? groupAiApi.getPersona(editingAcc) : Promise.resolve(null),
    enabled: !!editingAcc,
  });

  React.useEffect(() => {
    if (persona) form.setFieldsValue(persona);
  }, [persona, form]);

  const upsertMut = useMutation({
    mutationFn: (body: any) => groupAiApi.upsertPersona(editingAcc!, body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['portal-persona', editingAcc] });
      setEditingAcc(null);
    },
  });

  return (
    <div>
      <Title level={3}>账号人设</Title>
      <Paragraph type="secondary">
        每个 worker 账号可独立配置语言风格 / 口头禅 / 活跃时段. 没配的账号用兜底默认 (保守模式).
      </Paragraph>

      <Row gutter={[16, 16]}>
        {accounts.map((acc) => (
          <Col span={8} key={acc.id}>
            <Card
              title={<Space><Avatar icon={<UserOutlined />} />{acc.phone}</Space>}
              extra={<Tag color={acc.status === 'active' ? 'green' : 'orange'}>{acc.status}</Tag>}
              actions={[
                <Button type="link" icon={<EditOutlined />} onClick={() => setEditingAcc(acc.id)}>
                  编辑人设
                </Button>,
              ]}
            >
              <Paragraph type="secondary">点击右下编辑</Paragraph>
            </Card>
          </Col>
        ))}
      </Row>

      <Drawer
        title={`人设: account #${editingAcc}`}
        open={!!editingAcc} onClose={() => setEditingAcc(null)} width={600}
      >
        <Form form={form} layout="vertical" initialValues={{
          customer_id: 0, // 占位; backend 实际从 token 推断
        }} onFinish={(values) => upsertMut.mutate({
          ...values, customer_id: 0,  // backend 会忽略, 用 customer auth
        })}>
          <Form.Item name="display_name" label="显示名"><Input /></Form.Item>
          <Form.Item name="region" label="地区"><Input placeholder="香港 / 上海" /></Form.Item>
          <Form.Item name="occupation" label="职业"><Input placeholder="OTC 中介 / SaaS 销售" /></Form.Item>
          <Form.Item name="speaking_style" label="语言风格"><Select options={SPEAKING_STYLES} /></Form.Item>
          <Form.Item name="catchphrases" label="口头禅 (一行一个)">
            <Select mode="tags" placeholder="搞不好 / 我跟你说" tokenSeparators={[',']} />
          </Form.Item>

          <Form.Item label="日回复上限">
            <Form.Item name="daily_reply_quota" noStyle><InputNumber min={1} max={50} /></Form.Item> 条/天
          </Form.Item>
          <Form.Item label="单群日限">
            <Form.Item name="per_chat_daily_quota" noStyle><InputNumber min={1} max={20} /></Form.Item> 条/群/天
          </Form.Item>
          <Form.Item label="单群冷却">
            <Form.Item name="per_chat_cooldown_minutes" noStyle><InputNumber min={0} max={1440} /></Form.Item> 分钟
          </Form.Item>
          <Form.Item label="日闲聊上限">
            <Form.Item name="daily_chitchat_quota" noStyle><InputNumber min={0} max={50} /></Form.Item> 条/天
          </Form.Item>

          {/* 活跃时段编辑器 — 简化版: 用 dynamic JSON; Phase 后续做时段网格 */}
          <Form.Item name="active_hours" label="活跃时段 (JSON)">
            <Input.TextArea rows={4} placeholder='{"mon": [[9, 18]], ...}' />
          </Form.Item>

          <Button type="primary" htmlType="submit" loading={upsertMut.isPending}>
            保存
          </Button>
        </Form>
      </Drawer>
    </div>
  );
}
