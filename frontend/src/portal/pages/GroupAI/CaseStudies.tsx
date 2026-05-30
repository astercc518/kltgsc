import React from 'react';
import { Table, Button, Space, Drawer, Form, Input, Tag, Popconfirm, Typography } from 'antd';
import { PlusOutlined, ScanOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { groupAiApi, CaseStudy } from '../../api/groupAi';
import CaseExtractModal from './CaseExtractModal';

const { Title, Paragraph } = Typography;

export default function CaseStudies() {
  const [drawerOpen, setDrawerOpen] = React.useState(false);
  const [editing, setEditing] = React.useState<CaseStudy | null>(null);
  const [extractOpen, setExtractOpen] = React.useState(false);
  const [form] = Form.useForm();
  const qc = useQueryClient();

  const { data: cases = [] } = useQuery({
    queryKey: ['portal-cases'],
    queryFn: () => groupAiApi.listCases(),
  });

  const createMut = useMutation({
    mutationFn: (body: any) => groupAiApi.createCase(body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['portal-cases'] }); setDrawerOpen(false); form.resetFields(); },
  });
  const updateMut = useMutation({
    mutationFn: ({ id, body }: { id: number; body: any }) => groupAiApi.updateCase(id, body),
    onSuccess: () => { qc.invalidateQueries({ queryKey: ['portal-cases'] }); setDrawerOpen(false); setEditing(null); form.resetFields(); },
  });
  const deleteMut = useMutation({
    mutationFn: (id: number) => groupAiApi.deleteCase(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portal-cases'] }),
  });

  const columns = [
    { title: '行业', dataIndex: 'industry' },
    { title: '规模', dataIndex: 'deal_size' },
    { title: '周期', dataIndex: 'period' },
    { title: '问题', dataIndex: 'problem', ellipsis: true },
    { title: '方案', dataIndex: 'solution', ellipsis: true },
    { title: '效果', dataIndex: 'outcome', ellipsis: true },
    { title: '标签', dataIndex: 'tags',
      render: (t: string[]) => t?.map(x => <Tag key={x}>{x}</Tag>) },
    { title: '来源', dataIndex: 'source',
      render: (s: string) => <Tag color={s === 'manual_portal' ? 'blue' : 'green'}>{s}</Tag> },
    { title: '操作', render: (_: any, r: CaseStudy) => (
      <Space>
        <Button size="small" onClick={() => { setEditing(r); form.setFieldsValue(r); setDrawerOpen(true); }}>编辑</Button>
        <Popconfirm title="确认禁用?" onConfirm={() => deleteMut.mutate(r.id)}>
          <Button size="small" danger>禁用</Button>
        </Popconfirm>
      </Space>
    ) },
  ];

  return (
    <div>
      <Title level={3}>成交案例库</Title>
      <Paragraph type="secondary">
        AI 回复时会引用真实案例 + 具体数字, 避免空泛套话. 案例越多, 数字反幻觉越精准.
      </Paragraph>

      <Space style={{ marginBottom: 16 }}>
        <Button type="primary" icon={<PlusOutlined />}
                onClick={() => { setEditing(null); form.resetFields(); setDrawerOpen(true); }}>
          手动录入
        </Button>
        <Button icon={<ScanOutlined />} onClick={() => setExtractOpen(true)}>
          从历史会话扫描
        </Button>
      </Space>

      <Table columns={columns} dataSource={cases} rowKey="id" />

      <Drawer
        title={editing ? '编辑案例' : '新增案例'}
        open={drawerOpen} onClose={() => { setDrawerOpen(false); setEditing(null); }}
        width={600}
      >
        <Form form={form} layout="vertical"
              onFinish={(values) => {
                if (editing) updateMut.mutate({ id: editing.id, body: values });
                else createMut.mutate(values);
              }}>
          <Form.Item name="industry" label="行业"><Input /></Form.Item>
          <Form.Item name="deal_size" label="规模"><Input placeholder="100k USDT" /></Form.Item>
          <Form.Item name="period" label="周期"><Input placeholder="3 天" /></Form.Item>
          <Form.Item name="problem" label="问题" rules={[{ required: true }]}><Input.TextArea rows={3} /></Form.Item>
          <Form.Item name="solution" label="方案" rules={[{ required: true }]}><Input.TextArea rows={3} /></Form.Item>
          <Form.Item name="outcome" label="效果" rules={[{ required: true }]}><Input.TextArea rows={3} /></Form.Item>
          <Form.Item name="tags" label="标签">
            <Input placeholder="逗号分隔, e.g. OTC,USDT" />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createMut.isPending || updateMut.isPending}>
            保存
          </Button>
        </Form>
      </Drawer>

      <CaseExtractModal open={extractOpen} onClose={() => setExtractOpen(false)} />
    </div>
  );
}
