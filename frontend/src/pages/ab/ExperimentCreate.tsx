/**
 * ExperimentCreate — Admin form to create a new A/B experiment.
 * Sections: basic info, scope, primary metric, variants (dynamic list).
 * On submit: POST to abApi.create → redirect to experiment list.
 */
import React from 'react';
import {
  Button, Card, Form, Input, InputNumber, Select, Space, Typography, message,
} from 'antd';
import { MinusCircleOutlined, PlusOutlined } from '@ant-design/icons';
import { useMutation } from '@tanstack/react-query';
import { useNavigate } from 'react-router-dom';
import { abApi, ABExperiment } from '../../services/groupAi';

const { Title } = Typography;
const { TextArea } = Input;
const { Option } = Select;

interface VariantField {
  tag: string;
  weight: number;
  params: string; // JSON string in the form
}

interface FormValues {
  name: string;
  description?: string;
  scope: 'global' | 'customer' | 'monitor';
  scope_value?: number;
  primary_metric?: string;
  variants: VariantField[];
}

export default function ExperimentCreate() {
  const navigate = useNavigate();
  const [form] = Form.useForm<FormValues>();
  const scopeValue = Form.useWatch('scope', form);

  const createMut = useMutation({
    mutationFn: (body: Partial<ABExperiment>) => abApi.create(body),
    onSuccess: () => {
      message.success('实验创建成功');
      navigate('/admin/ab/experiments');
    },
    onError: () => {
      message.error('创建失败，请检查表单');
    },
  });

  const handleSubmit = (values: FormValues) => {
    const variants = (values.variants || []).map(v => {
      let params: Record<string, any> = {};
      try {
        params = v.params ? JSON.parse(v.params) : {};
      } catch {
        // ignore parse errors — backend will validate
      }
      return { tag: v.tag, weight: Number(v.weight), params };
    });

    const body: Partial<ABExperiment> = {
      name: values.name,
      description: values.description || null,
      scope: values.scope,
      scope_value: values.scope_value ?? null,
      primary_metric: values.primary_metric ?? null,
      variants,
    };
    createMut.mutate(body);
  };

  return (
    <div style={{ maxWidth: 800, margin: '0 auto' }}>
      <Title level={4} style={{ marginBottom: 24 }}>创建 A/B 实验</Title>

      <Form
        form={form}
        layout="vertical"
        onFinish={handleSubmit}
        initialValues={{ scope: 'global', variants: [{ tag: 'control', weight: 0.5, params: '{}' }] }}
      >
        {/* ── 基本信息 ─────────────────────────── */}
        <Card title="基本信息" style={{ marginBottom: 16 }}>
          <Form.Item
            name="name"
            label="实验名称"
            rules={[{ required: true, message: '请输入实验名称' }]}
          >
            <Input placeholder="e.g. greeting-tone-v1" maxLength={120} />
          </Form.Item>

          <Form.Item name="description" label="描述（可选）">
            <TextArea rows={3} placeholder="实验目的、假设…" maxLength={500} />
          </Form.Item>
        </Card>

        {/* ── 范围设置 ─────────────────────────── */}
        <Card title="范围设置" style={{ marginBottom: 16 }}>
          <Form.Item
            name="scope"
            label="范围"
            rules={[{ required: true }]}
          >
            <Select>
              <Option value="global">全局</Option>
              <Option value="customer">客户</Option>
              <Option value="monitor">监控组</Option>
            </Select>
          </Form.Item>

          {(scopeValue === 'customer' || scopeValue === 'monitor') && (
            <Form.Item
              name="scope_value"
              label={scopeValue === 'customer' ? '客户 ID' : '监控组 ID'}
              rules={[{ required: true, message: '请输入 ID' }]}
            >
              <InputNumber style={{ width: '100%' }} min={1} placeholder="输入 ID" />
            </Form.Item>
          )}
        </Card>

        {/* ── 主要指标 ─────────────────────────── */}
        <Card title="主要指标" style={{ marginBottom: 16 }}>
          <Form.Item name="primary_metric" label="评价指标（可选）">
            <Select allowClear placeholder="选择主要评价指标">
              <Option value="reply_rate">回复率</Option>
              <Option value="private_conversion_rate">私聊转化率</Option>
              <Option value="kick_rate">踢人率</Option>
              <Option value="anti_hallucination_failure_rate">幻觉失败率</Option>
            </Select>
          </Form.Item>
        </Card>

        {/* ── 变体配置 ─────────────────────────── */}
        <Card title="变体配置" style={{ marginBottom: 24 }}>
          <Form.List name="variants">
            {(fields, { add, remove }) => (
              <>
                {fields.map(({ key, name, ...restField }) => (
                  <Card
                    key={key}
                    size="small"
                    style={{ marginBottom: 12, background: '#fafafa' }}
                    extra={
                      fields.length > 1 ? (
                        <MinusCircleOutlined
                          style={{ color: '#ff4d4f', cursor: 'pointer' }}
                          onClick={() => remove(name)}
                        />
                      ) : null
                    }
                  >
                    <Space style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }} align="start">
                      <Form.Item
                        {...restField}
                        name={[name, 'tag']}
                        label="标签 (tag)"
                        rules={[{ required: true, message: '请输入变体标签' }]}
                        style={{ flex: '1 1 160px', marginBottom: 0 }}
                      >
                        <Input placeholder="e.g. control / treatment_a" />
                      </Form.Item>

                      <Form.Item
                        {...restField}
                        name={[name, 'weight']}
                        label="权重 (0–1)"
                        rules={[{ required: true, message: '请输入权重' }]}
                        style={{ flex: '0 0 140px', marginBottom: 0 }}
                      >
                        <InputNumber min={0} max={1} step={0.1} style={{ width: '100%' }} />
                      </Form.Item>
                    </Space>

                    <Form.Item
                      {...restField}
                      name={[name, 'params']}
                      label="参数 (JSON)"
                      style={{ marginTop: 8, marginBottom: 0 }}
                      rules={[
                        {
                          validator: (_, value) => {
                            if (!value) return Promise.resolve();
                            try { JSON.parse(value); return Promise.resolve(); }
                            catch { return Promise.reject(new Error('无效 JSON')); }
                          },
                        },
                      ]}
                    >
                      <TextArea
                        rows={3}
                        placeholder='{"temperature": 0.7, "top_p": 0.9}'
                        style={{ fontFamily: 'monospace', fontSize: 12 }}
                      />
                    </Form.Item>
                  </Card>
                ))}

                <Button
                  type="dashed"
                  block
                  icon={<PlusOutlined />}
                  onClick={() => add({ tag: '', weight: 0.5, params: '{}' })}
                >
                  添加变体
                </Button>
              </>
            )}
          </Form.List>
        </Card>

        {/* ── 提交 ─────────────────────────── */}
        <Space>
          <Button type="primary" htmlType="submit" loading={createMut.isPending}>
            创建实验
          </Button>
          <Button onClick={() => navigate('/admin/ab/experiments')}>取消</Button>
        </Space>
      </Form>
    </div>
  );
}
