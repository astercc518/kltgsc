/**
 * ExperimentList — Admin A/B experiment list page.
 * Shows all experiments with status, scope, primary metric, and variants.
 * Start/stop actions via mutations. Row click → report page.
 */
import React from 'react';
import { Table, Tag, Button, Space, Typography, Tooltip } from 'antd';
import { PlusOutlined, PlayCircleOutlined, PauseCircleOutlined } from '@ant-design/icons';
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query';
import { useNavigate, Link } from 'react-router-dom';
import { abApi, ABExperiment } from '../../services/groupAi';

const { Title } = Typography;

const STATUS_COLOR: Record<string, string> = {
  draft: 'default',
  running: 'green',
  finished: 'blue',
  paused: 'orange',
};

const STATUS_LABEL: Record<string, string> = {
  draft: '草稿',
  running: '运行中',
  finished: '已结束',
  paused: '已暂停',
};

const SCOPE_LABEL: Record<string, string> = {
  global: '全局',
  customer: '客户',
  monitor: '监控组',
};

const METRIC_LABEL: Record<string, string> = {
  reply_rate: '回复率',
  private_conversion_rate: '私聊转化率',
  kick_rate: '踢人率',
  anti_hallucination_failure_rate: '幻觉失败率',
};

export default function ExperimentList() {
  const navigate = useNavigate();
  const qc = useQueryClient();

  const { data: experiments = [], isLoading } = useQuery({
    queryKey: ['ab-experiments'],
    queryFn: abApi.list,
    refetchInterval: 30000,
  });

  const startMut = useMutation({
    mutationFn: (id: number) => abApi.start(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ab-experiments'] }),
  });

  const stopMut = useMutation({
    mutationFn: (id: number) => abApi.stop(id),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['ab-experiments'] }),
  });

  const columns = [
    {
      title: 'ID',
      dataIndex: 'id',
      width: 60,
    },
    {
      title: '实验名称',
      dataIndex: 'name',
      render: (name: string, r: ABExperiment) => (
        <a onClick={() => navigate(`/admin/ab/experiments/${r.id}`)}>{name}</a>
      ),
    },
    {
      title: '范围',
      dataIndex: 'scope',
      width: 100,
      render: (scope: string, r: ABExperiment) => (
        <Tooltip title={r.scope_value != null ? `ID: ${r.scope_value}` : undefined}>
          <Tag>{SCOPE_LABEL[scope] ?? scope}</Tag>
        </Tooltip>
      ),
    },
    {
      title: '主要指标',
      dataIndex: 'primary_metric',
      width: 140,
      render: (m: string | null) => m ? (METRIC_LABEL[m] ?? m) : '—',
    },
    {
      title: '状态',
      dataIndex: 'status',
      width: 100,
      render: (s: string) => (
        <Tag color={STATUS_COLOR[s] ?? 'default'}>{STATUS_LABEL[s] ?? s}</Tag>
      ),
    },
    {
      title: '变体',
      dataIndex: 'variants',
      width: 200,
      render: (variants: ABExperiment['variants']) =>
        (variants || []).map(v => (
          <Tag key={v.tag} style={{ marginBottom: 2 }}>
            {v.tag} ({(v.weight * 100).toFixed(0)}%)
          </Tag>
        )),
    },
    {
      title: '开始时间',
      dataIndex: 'started_at',
      width: 160,
      render: (t: string | null) => t ? new Date(t).toLocaleString('zh-CN') : '—',
    },
    {
      title: '操作',
      width: 200,
      render: (_: unknown, r: ABExperiment) => (
        <Space>
          {r.status === 'draft' || r.status === 'paused' ? (
            <Button
              size="small"
              type="primary"
              icon={<PlayCircleOutlined />}
              loading={startMut.isPending && startMut.variables === r.id}
              onClick={(e) => { e.stopPropagation(); startMut.mutate(r.id); }}
            >
              启动
            </Button>
          ) : null}
          {r.status === 'running' ? (
            <Button
              size="small"
              danger
              icon={<PauseCircleOutlined />}
              loading={stopMut.isPending && stopMut.variables === r.id}
              onClick={(e) => { e.stopPropagation(); stopMut.mutate(r.id); }}
            >
              停止
            </Button>
          ) : null}
          <Button
            size="small"
            onClick={(e) => { e.stopPropagation(); navigate(`/admin/ab/experiments/${r.id}`); }}
          >
            报告
          </Button>
        </Space>
      ),
    },
  ];

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>A/B 实验管理</Title>
        <Link to="/admin/ab/experiments/new">
          <Button type="primary" icon={<PlusOutlined />}>创建实验</Button>
        </Link>
      </div>
      <Table
        dataSource={experiments}
        columns={columns}
        rowKey="id"
        loading={isLoading}
        pagination={{ pageSize: 20 }}
        onRow={(r) => ({
          onClick: () => navigate(`/admin/ab/experiments/${r.id}`),
          style: { cursor: 'pointer' },
        })}
      />
    </div>
  );
}
