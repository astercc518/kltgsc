import React, { useEffect, useState } from 'react';
import { Select, Space, Tag, Tooltip, Spin } from 'antd';
import { RobotOutlined, StarFilled } from '@ant-design/icons';
import { getAIConfigs, AIConfigData } from '../services/api';

interface AISelectorProps {
  value?: number | null;
  onChange?: (value: number | null) => void;
  allowDefault?: boolean;  // 是否显示"使用默认配置"选项
  placeholder?: string;
  style?: React.CSSProperties;
  size?: 'small' | 'middle' | 'large';
  disabled?: boolean;
}

/**
 * AI 配置选择器组件
 * 用于在各功能模块中选择要使用的 AI 配置
 */
const AISelector: React.FC<AISelectorProps> = ({
  value,
  onChange,
  allowDefault = true,
  placeholder = '选择 AI 配置',
  style,
  size = 'middle',
  disabled = false,
}) => {
  const [configs, setConfigs] = useState<AIConfigData[]>([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    fetchConfigs();
  }, []);

  const fetchConfigs = async () => {
    setLoading(true);
    try {
      const data = await getAIConfigs(true); // 只获取启用的配置
      setConfigs(data);
    } catch (e) {
      console.error('Failed to fetch AI configs:', e);
    } finally {
      setLoading(false);
    }
  };

  const getProviderLabel = (provider: string) => {
    const labels: Record<string, string> = {
      openai: 'OpenAI',
      gemini: 'Gemini',
      anthropic: 'Claude',
      deepseek: 'DeepSeek',
      qwen: '通义',
      moonshot: 'Kimi',
      zhipu: 'GLM',
      doubao: '豆包',
      openrouter: 'OpenRouter',
    };
    return labels[provider] || provider;
  };

  const options = [
    ...(allowDefault ? [{
      value: null as any,
      label: (
        <Space>
          <RobotOutlined />
          <span>使用默认配置</span>
        </Space>
      ),
    }] : []),
    ...configs.map(config => ({
      value: config.id,
      label: (
        <Space>
          <span>{config.name}</span>
          <Tag color="blue" style={{ marginLeft: 4 }}>
            {getProviderLabel(config.provider)}
          </Tag>
          {config.is_default && (
            <Tooltip title="默认配置">
              <StarFilled style={{ color: '#faad14', fontSize: 12 }} />
            </Tooltip>
          )}
        </Space>
      ),
      config,
    })),
  ];

  return (
    <Select
      value={value}
      onChange={onChange}
      placeholder={placeholder}
      style={{ minWidth: 200, ...style }}
      size={size}
      disabled={disabled}
      loading={loading}
      allowClear={!allowDefault}
      options={options}
      optionFilterProp="label"
      notFoundContent={loading ? <Spin size="small" /> : '暂无配置'}
    />
  );
};

export default AISelector;
