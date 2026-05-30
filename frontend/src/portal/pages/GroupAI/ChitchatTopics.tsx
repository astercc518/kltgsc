import React from 'react';
import { List, Card, Tag, Button, Form, Input, Select, Modal, Typography } from 'antd';
import { PlusOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { groupAiApi } from '../../api/groupAi';

const { Title, Paragraph } = Typography;

const CATEGORIES = ['weather', 'food', 'news', 'life', 'tech', 'sports', 'gossip', 'work', 'travel', 'mood'];

export default function ChitchatTopics() {
  const [modalOpen, setModalOpen] = React.useState(false);
  const [form] = Form.useForm();
  const qc = useQueryClient();

  const { data: topics = [] } = useQuery({
    queryKey: ['portal-chitchat-topics'],
    queryFn: () => groupAiApi.listChitchatTopics(),
  });
  const createMut = useMutation({
    mutationFn: (body: any) => groupAiApi.createChitchatTopic(body),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ['portal-chitchat-topics'] });
      setModalOpen(false);
      form.resetFields();
    },
  });

  return (
    <div>
      <Title level={3}>闲聊话题库</Title>
      <Paragraph type="secondary">
        账号在群里偶尔发的"非业务闲聊"模板. 系统内置 30+ 全局话题, 你也可以加自己的.
        闲聊永远会避开你的业务关键词, 不会无意触发自家 AI 回复.
      </Paragraph>

      <Button type="primary" icon={<PlusOutlined />} onClick={() => setModalOpen(true)} style={{ marginBottom: 16 }}>
        添加我的话题
      </Button>

      <List
        grid={{ gutter: 16, column: 3 }}
        dataSource={topics}
        renderItem={(t) => (
          <List.Item>
            <Card
              title={<Tag color={t.scope === 'global' ? 'blue' : 'green'}>{t.scope}</Tag>}
              size="small"
            >
              <p>{t.prompt_template}</p>
              <div>{t.tags?.map(tag => <Tag key={tag}>{tag}</Tag>)}</div>
            </Card>
          </List.Item>
        )}
      />

      <Modal title="添加话题" open={modalOpen} onCancel={() => setModalOpen(false)} footer={null}>
        <Form form={form} layout="vertical" onFinish={(v) => createMut.mutate(v)}>
          <Form.Item name="topic_category" label="分类"><Select options={CATEGORIES.map(c => ({ value: c, label: c }))} /></Form.Item>
          <Form.Item name="prompt_template" label="模板" rules={[{ required: true }]}>
            <Input.TextArea rows={3} placeholder="今天{城市}天气不错, 出门带伞" />
          </Form.Item>
          <Form.Item name="tags" label="标签">
            <Select mode="tags" tokenSeparators={[',']} />
          </Form.Item>
          <Button type="primary" htmlType="submit" loading={createMut.isPending}>添加</Button>
        </Form>
      </Modal>
    </div>
  );
}
