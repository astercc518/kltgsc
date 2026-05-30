/**
 * IcpEditor — ICP 画像自由文本编辑器 (200-500 字).
 *
 * 保存后自动 re-embed (backend 自动). 前端只显示 has_embedding 状态。
 */
import React from 'react';
import { Form, Input, Button, Alert, Space, Typography } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { groupAiApi } from '../../api/groupAi';

const { TextArea } = Input;
const { Title, Paragraph } = Typography;

const EXAMPLE_PLACEHOLDER = `示例:
想找 BTC/USDT 大额场外买家, 单笔 100k USDT 以上, 海外华人优先.
不要小白和倒卖中间人, 不要询价不付钱的.
理想行业: 矿企 / 海外贸易 / 跨境支付.`;

export default function IcpEditor() {
  const [form] = Form.useForm();
  const qc = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ['portal-icp'],
    queryFn: () => groupAiApi.getIcp(),
  });
  const mutation = useMutation({
    mutationFn: (icp_text: string | null) => groupAiApi.updateIcp(icp_text),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portal-icp'] }),
  });

  React.useEffect(() => {
    if (data) form.setFieldsValue({ icp_text: data.icp_text || '' });
  }, [data, form]);

  return (
    <div style={{ maxWidth: 800 }}>
      <Title level={3}>ICP 客户画像</Title>
      <Paragraph type="secondary">
        用 200-500 字自由文本描述你的理想客户. 保存后系统会自动生成 embedding,
        用于群消息的 Layer 2 智能过滤 (与你描述相似的消息才会触发 AI 回复).
      </Paragraph>

      {data && !data.has_embedding && data.icp_text && (
        <Alert
          type="warning"
          message="ICP 文本已保存但 embedding 生成失败"
          description="Layer 2 暂时关闭. 系统会在后台重试 embedding. 你也可以点'保存'重新触发."
          style={{ marginBottom: 16 }}
        />
      )}

      <Form
        form={form}
        layout="vertical"
        onFinish={(values) => mutation.mutate(values.icp_text || null)}
      >
        <Form.Item
          name="icp_text"
          rules={[
            { max: 500, message: '不要超过 500 字' },
          ]}
        >
          <TextArea
            rows={10}
            placeholder={EXAMPLE_PLACEHOLDER}
            showCount
            maxLength={500}
          />
        </Form.Item>

        <Form.Item>
          <Space>
            <Button
              type="primary" htmlType="submit"
              loading={mutation.isPending}
            >
              保存并重新生成 embedding
            </Button>
            <Button onClick={() => form.setFieldsValue({ icp_text: '' })}>
              清空
            </Button>
          </Space>
        </Form.Item>
      </Form>
    </div>
  );
}
