/**
 * CaptchaTemplates — 客户填写 captcha 自动答题 / admin DM 申请模板 (Phase 10)
 *
 * - captcha_join_template: text_qa handler 用做答题上下文 ("你为何加群")
 * - captcha_intro_template: admin_dm handler 用做申请加群话术
 *
 * 空 → handler 回退默认或拒答(no_template_set)，所以填了才能提高加群成功率。
 */
import React, { useEffect, useState } from 'react';
import { Alert, Button, Card, Form, Input, message, Skeleton, Space, Typography } from 'antd';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { groupAiApi, CaptchaTemplates } from '../../api/groupAi';

const { Title, Paragraph } = Typography;
const { TextArea } = Input;

const MAX_JOIN_LEN = 400;
const MAX_INTRO_LEN = 600;

export default function CaptchaTemplatesPage() {
  const queryClient = useQueryClient();
  const [form] = Form.useForm<CaptchaTemplates>();
  const [dirty, setDirty] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ['captcha-templates'],
    queryFn: () => groupAiApi.getCaptchaTemplates(),
  });

  useEffect(() => {
    if (data) {
      form.setFieldsValue({
        captcha_join_template: data.captcha_join_template ?? '',
        captcha_intro_template: data.captcha_intro_template ?? '',
      });
      setDirty(false);
    }
  }, [data, form]);

  const saveMut = useMutation({
    mutationFn: (values: CaptchaTemplates) => groupAiApi.updateCaptchaTemplates(values),
    onSuccess: (updated) => {
      message.success('已保存');
      queryClient.setQueryData(['captcha-templates'], updated);
      setDirty(false);
    },
    onError: () => message.error('保存失败，请重试'),
  });

  if (isLoading) {
    return <Card><Skeleton active /></Card>;
  }

  return (
    <Card>
      <Title level={4}>加群 CAPTCHA 应答模板</Title>
      <Paragraph type="secondary" style={{ marginBottom: 24 }}>
        我们的账号加入新群时，群 bot 通常会要求回答验证问题或发申请 DM 给管理员。
        这里填写的话术决定了答题/申请的真实度，直接影响"可加群率"。
        留空时系统使用通用默认话术，效果一般。
      </Paragraph>

      <Alert
        type="info"
        showIcon
        style={{ marginBottom: 24 }}
        message="text_qa 模板会被 LLM 当作背景上下文，不会原样发送；admin_dm 模板会原样作为 DM 内容发给群管理员。"
      />

      <Form
        form={form}
        layout="vertical"
        onValuesChange={() => setDirty(true)}
        onFinish={(values) =>
          saveMut.mutate({
            captcha_join_template: (values.captcha_join_template || '').trim() || null,
            captcha_intro_template: (values.captcha_intro_template || '').trim() || null,
          })
        }
      >
        <Form.Item
          label="text_qa 答题背景 (captcha_join_template)"
          name="captcha_join_template"
          extra={`≤ ${MAX_JOIN_LEN} 字。例: "我是做加密 OTC 的，看到群里有不少同行在聊行情"`}
          rules={[
            {
              max: MAX_JOIN_LEN,
              message: `不能超过 ${MAX_JOIN_LEN} 字`,
            },
          ]}
        >
          <TextArea
            rows={3}
            maxLength={MAX_JOIN_LEN}
            showCount
            placeholder="留空 → 使用默认 '我是行业内朋友推荐知道的'"
          />
        </Form.Item>

        <Form.Item
          label="admin_dm 申请话术 (captcha_intro_template)"
          name="captcha_intro_template"
          extra={`≤ ${MAX_INTRO_LEN} 字。留空时遇到 admin_dm captcha 会直接进失败队列。`}
          rules={[
            {
              max: MAX_INTRO_LEN,
              message: `不能超过 ${MAX_INTRO_LEN} 字`,
            },
          ]}
        >
          <TextArea
            rows={4}
            maxLength={MAX_INTRO_LEN}
            showCount
            placeholder="例: '你好，朋友推荐的群，想加进来跟同行交流学习一下，多谢。'"
          />
        </Form.Item>

        <Space>
          <Button
            type="primary"
            htmlType="submit"
            loading={saveMut.isPending}
            disabled={!dirty}
          >
            保存
          </Button>
          <Button
            onClick={() => {
              form.setFieldsValue({
                captcha_join_template: data?.captcha_join_template ?? '',
                captcha_intro_template: data?.captcha_intro_template ?? '',
              });
              setDirty(false);
            }}
            disabled={!dirty}
          >
            撤销
          </Button>
        </Space>
      </Form>
    </Card>
  );
}
