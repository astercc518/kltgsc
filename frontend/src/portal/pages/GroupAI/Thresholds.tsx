/**
 * Thresholds — 三层过滤灵敏度滑块.
 *
 * - Layer 2 ICP 相似度 (0.3 - 0.8)
 * - Layer 3 LLM 评分 (40 - 90)
 * - Layer 3 置信度 (0.5 - 0.95)
 */
import React from 'react';
import { Slider, Card, Button, Space, Typography, Tag } from 'antd';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { groupAiApi } from '../../api/groupAi';

const { Title, Text } = Typography;

const DEFAULTS = { layer2_sim: 0.55, layer3_score: 60, layer3_confidence: 0.7 };

export default function Thresholds() {
  const qc = useQueryClient();
  const { data } = useQuery({
    queryKey: ['portal-icp'],
    queryFn: () => groupAiApi.getIcp(),
  });
  const [values, setValues] = React.useState(DEFAULTS);

  React.useEffect(() => {
    if (data?.thresholds) setValues(data.thresholds);
  }, [data]);

  const mutation = useMutation({
    mutationFn: (body: typeof DEFAULTS) => groupAiApi.updateThresholds(body),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['portal-icp'] }),
  });

  return (
    <div style={{ maxWidth: 700 }}>
      <Title level={3}>识别灵敏度</Title>

      <Card title="Layer 2: ICP 画像相似度阈值" style={{ marginBottom: 16 }}>
        <Text type="secondary">
          消息与你 ICP 画像的余弦相似度 ≥ 此值才进入 Layer 3.
          阈值越低识别越宽松 (更多消息进入下一层), 越高越严.
        </Text>
        <Slider
          min={0.3} max={0.8} step={0.05}
          value={values.layer2_sim}
          onChange={(v) => setValues({ ...values, layer2_sim: v as number })}
          marks={{ 0.3: '0.3 宽松', 0.55: '默认', 0.8: '0.8 严格' }}
          style={{ marginTop: 24 }}
        />
      </Card>

      <Card title="Layer 3: LLM 评分阈值" style={{ marginBottom: 16 }}>
        <Text type="secondary">
          LLM 给消息打 0-100 分 (业务需求强度). 此值以上才生成回复.
        </Text>
        <Slider
          min={40} max={90} step={5}
          value={values.layer3_score}
          onChange={(v) => setValues({ ...values, layer3_score: v as number })}
          marks={{ 40: '40 宽', 60: '默认', 90: '90 严' }}
          style={{ marginTop: 24 }}
        />
      </Card>

      <Card title="Layer 3: LLM 置信度阈值" style={{ marginBottom: 16 }}>
        <Slider
          min={0.5} max={0.95} step={0.05}
          value={values.layer3_confidence}
          onChange={(v) => setValues({ ...values, layer3_confidence: v as number })}
          marks={{ 0.5: '0.5', 0.7: '默认', 0.95: '0.95' }}
          style={{ marginTop: 24 }}
        />
      </Card>

      <Space>
        <Button
          type="primary" loading={mutation.isPending}
          onClick={() => mutation.mutate(values)}
        >
          保存
        </Button>
        <Button onClick={() => setValues(DEFAULTS)}>恢复默认</Button>
        <Tag>当前生效: L2={data?.thresholds.layer2_sim} L3-S={data?.thresholds.layer3_score} L3-C={data?.thresholds.layer3_confidence}</Tag>
      </Space>
    </div>
  );
}
