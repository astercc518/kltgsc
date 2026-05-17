import React, { useState, useEffect } from 'react';
import {
  Modal,
  Form,
  Select,
  Tag,
  Card,
  Row,
  Col,
  message,
  Tabs,
  InputNumber,
  Button,
  Alert,
  Table,
  Space,
} from 'antd';
import { CoffeeOutlined, ThunderboltOutlined } from '@ant-design/icons';
import {
  Account,
  getWarmupTemplates,
  createWarmupTask,
  WarmupTemplate,
  autoAssignAccounts,
  getPersonas,
  PersonaData,
} from '../../services/api';
import { getCombatRoleName } from './helpers';
import { PaginationState } from './types';

const { Option } = Select;

interface CombatRoleManagerProps {
  accounts: Account[];
  selectedRowKeys: React.Key[];
  setSelectedRowKeys: React.Dispatch<React.SetStateAction<React.Key[]>>;
  fetchAccounts: (page?: number, pageSize?: number) => Promise<void>;
  pagination: PaginationState;

  // Combat role modal
  isCombatRoleModalVisible: boolean;
  setIsCombatRoleModalVisible: React.Dispatch<React.SetStateAction<boolean>>;

  // Warmup modal
  isWarmupModalVisible: boolean;
  setIsWarmupModalVisible: React.Dispatch<React.SetStateAction<boolean>>;
}

const CombatRoleManager: React.FC<CombatRoleManagerProps> = ({
  accounts,
  selectedRowKeys,
  setSelectedRowKeys,
  fetchAccounts,
  pagination,
  isCombatRoleModalVisible,
  setIsCombatRoleModalVisible,
  isWarmupModalVisible,
  setIsWarmupModalVisible,
}) => {
  // Combat Role State
  const [combatRoleStats, setCombatRoleStats] = useState<any>({});
  const [selectedCombatRole, setSelectedCombatRole] = useState<string>('cannon');
  const [combatRoleLoading, setCombatRoleLoading] = useState(false);

  // Quick Warmup State
  const [warmupTemplates, setWarmupTemplates] = useState<WarmupTemplate[]>([]);
  const [selectedWarmupTemplateId, setSelectedWarmupTemplateId] = useState<number | null>(null);
  const [warmupLoading, setWarmupLoading] = useState(false);

  // AI 智能分配 state
  const [aiStrategy, setAiStrategy] = useState<'balanced' | 'quota'>('balanced');
  const [aiQuotas, setAiQuotas] = useState({ listener: 1, actor: 5, cannon: 13 });
  const [aiPersonas, setAiPersonas] = useState<PersonaData[]>([]);
  const [aiPersonaPool, setAiPersonaPool] = useState<number[]>([]);
  const [aiPlan, setAiPlan] = useState<any[]>([]);
  const [aiPlanLoading, setAiPlanLoading] = useState(false);
  const [aiApplying, setAiApplying] = useState(false);
  const [aiScopeAll, setAiScopeAll] = useState(true);

  useEffect(() => {
    if (isCombatRoleModalVisible && aiPersonas.length === 0) {
      getPersonas().then((data) => {
        setAiPersonas(data);
        // 默认全选（除了 28/29 客服 bot）
        setAiPersonaPool(data.filter((p) => p.id !== 28 && p.id !== 29).map((p) => p.id));
      }).catch(() => { /* ignore */ });
    }
  }, [isCombatRoleModalVisible]);

  const handleAiPreview = async () => {
    setAiPlanLoading(true);
    try {
      const params: any = {
        strategy: aiStrategy,
        preview: true,
        persona_pool: aiPersonaPool.length > 0 ? aiPersonaPool : undefined,
      };
      if (aiStrategy === 'quota') params.quotas = aiQuotas;
      if (!aiScopeAll && selectedRowKeys.length > 0) {
        params.account_ids = selectedRowKeys.map((k) => Number(k));
      }
      const res = await autoAssignAccounts(params);
      setAiPlan(res.plan);
      message.success(`生成预览：${res.total} 个账号`);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '预览失败';
      message.error(`预览失败: ${msg}`);
    } finally {
      setAiPlanLoading(false);
    }
  };

  const handleAiApply = async () => {
    if (aiPlan.length === 0) {
      message.warning('请先点「预览」生成分配计划');
      return;
    }
    setAiApplying(true);
    try {
      const params: any = {
        strategy: aiStrategy,
        preview: false,
        persona_pool: aiPersonaPool.length > 0 ? aiPersonaPool : undefined,
      };
      if (aiStrategy === 'quota') params.quotas = aiQuotas;
      if (!aiScopeAll && selectedRowKeys.length > 0) {
        params.account_ids = selectedRowKeys.map((k) => Number(k));
      }
      const res = await autoAssignAccounts(params);
      message.success(`已应用：${res.total} 个账号已更新`);
      setAiPlan([]);
      setIsCombatRoleModalVisible(false);
      await fetchAccounts(pagination.current, pagination.pageSize);
    } catch (e: any) {
      const msg = e?.response?.data?.detail || e?.message || '应用失败';
      message.error(`应用失败: ${msg}`);
    } finally {
      setAiApplying(false);
    }
  };

  const fetchCombatRoleStats = async () => {
    try {
      const res = await fetch('/api/v1/accounts/combat-roles/stats', {
        headers: { 'Authorization': `Bearer ${localStorage.getItem('token')}` },
      });
      if (res.ok) {
        const data = await res.json();
        setCombatRoleStats(data);
      }
    } catch (error) {
      console.error('获取战斗角色统计失败', error);
    }
  };

  const fetchWarmupTemplates = async () => {
    try {
      const data = await getWarmupTemplates();
      setWarmupTemplates(data);
      const defaultTemplate = data.find(t => t.is_default);
      if (defaultTemplate) {
        setSelectedWarmupTemplateId(defaultTemplate.id);
      } else if (data.length > 0) {
        setSelectedWarmupTemplateId(data[0].id);
      }
    } catch (e) {
      console.error('Failed to fetch warmup templates:', e);
    }
  };

  useEffect(() => {
    fetchCombatRoleStats();
  }, []);

  useEffect(() => {
    if (isWarmupModalVisible) {
      fetchWarmupTemplates();
    }
  }, [isWarmupModalVisible]);

  const handleCombatRoleSubmit = async () => {
    setCombatRoleLoading(true);
    try {
      const accountIds = selectedRowKeys.map(k => Number(k));
      const res = await fetch('/api/v1/accounts/combat-roles/batch-assign', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${localStorage.getItem('token')}`,
        },
        body: JSON.stringify({
          account_ids: accountIds,
          combat_role: selectedCombatRole,
        }),
      });

      if (res.ok) {
        const data = await res.json();
        message.success(`成功分配 ${data.updated_count} 个账号到${getCombatRoleName(selectedCombatRole)}`);
        setIsCombatRoleModalVisible(false);
        setSelectedRowKeys([]);
        fetchAccounts(pagination.current, pagination.pageSize);
        fetchCombatRoleStats();
      } else {
        const err = await res.json();
        message.error(`分配失败: ${err.detail}`);
      }
    } catch (error: any) {
      message.error(`分配失败: ${error.message}`);
    } finally {
      setCombatRoleLoading(false);
    }
  };

  const handleQuickWarmup = async () => {
    if (!selectedWarmupTemplateId) {
      message.error('请选择一个养号模板');
      return;
    }

    const template = warmupTemplates.find(t => t.id === selectedWarmupTemplateId);
    if (!template) {
      message.error('模板不存在');
      return;
    }

    const activeAccountIds = accounts
      .filter(a => selectedRowKeys.includes(a.id) && a.status === 'active')
      .map(a => a.id);

    if (activeAccountIds.length === 0) {
      message.error('没有可用的活跃账号');
      return;
    }

    setWarmupLoading(true);
    try {
      await createWarmupTask({
        name: `${template.name} - ${new Date().toLocaleDateString()}`,
        account_ids: activeAccountIds,
        action_type: template.action_type,
        min_delay: template.min_delay,
        max_delay: template.max_delay,
        duration_minutes: template.duration_minutes,
        target_channels: template.target_channels,
      });
      message.success(`养号任务已启动，${activeAccountIds.length} 个账号`);
      setIsWarmupModalVisible(false);
      setSelectedRowKeys([]);
    } catch (error: any) {
      message.error(`启动失败: ${error.response?.data?.detail || error.message}`);
    } finally {
      setWarmupLoading(false);
    }
  };

  return (
    <>
      {/* Combat Role Modal */}
      <Modal
        title="账号角色分配"
        open={isCombatRoleModalVisible}
        onCancel={() => { setIsCombatRoleModalVisible(false); setAiPlan([]); }}
        footer={null}
        width={900}
      >
        <Tabs
          defaultActiveKey="manual"
          items={[
            {
              key: 'manual',
              label: '战斗角色 (combat_role)',
              children: (
                <>
                  <div style={{ marginBottom: 16 }}>
                    <p>已选择 <strong>{selectedRowKeys.length}</strong> 个账号</p>
                  </div>

                  <div style={{ marginBottom: 16 }}>
                    <Row gutter={8}>
                      {Object.entries(combatRoleStats).map(([role, data]: [string, any]) => (
                        <Col span={6} key={role}>
                          <Card size="small" style={{ textAlign: 'center' }}>
                            <div style={{ fontSize: 18, fontWeight: 'bold' }}>{data.active}/{data.total}</div>
                            <div style={{ fontSize: 12, color: '#666' }}>{data.display_name}</div>
                          </Card>
                        </Col>
                      ))}
                    </Row>
                  </div>

                  <Form layout="vertical">
                    <Form.Item label="目标战斗角色" required>
                      <Select value={selectedCombatRole} onChange={setSelectedCombatRole} style={{ width: '100%' }}>
                        <Option value="cannon">
                          <Tag color="red">炮灰组</Tag> 廉价弹药，群发/拉人/高风险操作
                        </Option>
                        <Option value="scout">
                          <Tag color="blue">侦察组</Tag> 情报收集，潜伏采集、监控（禁止发消息）
                        </Option>
                        <Option value="actor">
                          <Tag color="purple">演员组</Tag> 信任铺垫，炒群造势、剧本对话
                        </Option>
                        <Option value="sniper">
                          <Tag color="gold">狙击组</Tag> 精准打击，高价值客户转化（严格限制）
                        </Option>
                      </Select>
                    </Form.Item>
                  </Form>

                  <Space style={{ marginTop: 16 }}>
                    <Button onClick={() => setIsCombatRoleModalVisible(false)}>取消</Button>
                    <Button type="primary" loading={combatRoleLoading} onClick={handleCombatRoleSubmit}>应用</Button>
                  </Space>

                  <div style={{ fontSize: 12, color: '#888', marginTop: 16 }}>
                    <p><strong>角色说明：</strong></p>
                    <ul style={{ paddingLeft: 16 }}>
                      <li><strong>炮灰</strong>：每日100条，30-60秒间隔，用完即弃</li>
                      <li><strong>侦察</strong>：只读操作，禁止发消息，用于采集监控</li>
                      <li><strong>演员</strong>：每日50条，2-5分钟间隔，需使用剧本</li>
                      <li><strong>狙击</strong>：每日20条，5-10分钟间隔，只打高分用户</li>
                    </ul>
                  </div>
                </>
              ),
            },
            {
              key: 'ai',
              label: <><ThunderboltOutlined /> AI 智能分配</>,
              children: (
                <>
                  <Alert
                    type="info"
                    showIcon
                    style={{ marginBottom: 12 }}
                    message="自动按 last_active 分配 listener / actor / cannon 三类角色，并给 actor 随机绑定 AI 人设。"
                  />

                  <Form layout="vertical" size="small">
                    <Form.Item label="操作范围">
                      <Select value={aiScopeAll ? 'all' : 'selected'} onChange={(v) => setAiScopeAll(v === 'all')}>
                        <Option value="all">所有 active 账号</Option>
                        <Option value="selected">仅已选 {selectedRowKeys.length} 个</Option>
                      </Select>
                    </Form.Item>

                    <Form.Item label="分配策略">
                      <Select value={aiStrategy} onChange={setAiStrategy}>
                        <Option value="balanced">balanced - 自动 5% listener / 25% actor / 70% cannon</Option>
                        <Option value="quota">quota - 自定义数量</Option>
                      </Select>
                    </Form.Item>

                    {aiStrategy === 'quota' && (
                      <Row gutter={8}>
                        <Col span={8}>
                          <Form.Item label="listener (主号)">
                            <InputNumber min={0} value={aiQuotas.listener} onChange={(v) => setAiQuotas({ ...aiQuotas, listener: Number(v) || 0 })} style={{ width: '100%' }} />
                          </Form.Item>
                        </Col>
                        <Col span={8}>
                          <Form.Item label="actor (演员)">
                            <InputNumber min={0} value={aiQuotas.actor} onChange={(v) => setAiQuotas({ ...aiQuotas, actor: Number(v) || 0 })} style={{ width: '100%' }} />
                          </Form.Item>
                        </Col>
                        <Col span={8}>
                          <Form.Item label="cannon (炮灰)">
                            <InputNumber min={0} value={aiQuotas.cannon} onChange={(v) => setAiQuotas({ ...aiQuotas, cannon: Number(v) || 0 })} style={{ width: '100%' }} />
                          </Form.Item>
                        </Col>
                      </Row>
                    )}

                    <Form.Item label={`候选 AI 人设池（actor 账号会从中随机选）：当前选了 ${aiPersonaPool.length} 个`}>
                      <Select
                        mode="multiple"
                        showSearch
                        optionFilterProp="label"
                        maxTagCount={5}
                        value={aiPersonaPool}
                        onChange={setAiPersonaPool}
                        options={aiPersonas.map((p) => ({ value: p.id, label: `${p.name} (${p.tone})` }))}
                        placeholder="不选则使用全部（除 FAQ/小蜜外）"
                      />
                    </Form.Item>
                  </Form>

                  <Space style={{ marginBottom: 12 }}>
                    <Button onClick={handleAiPreview} loading={aiPlanLoading}>预览分配计划</Button>
                    <Button type="primary" disabled={aiPlan.length === 0} onClick={handleAiApply} loading={aiApplying}>
                      应用变更（{aiPlan.length} 个账号）
                    </Button>
                  </Space>

                  {aiPlan.length > 0 && (
                    <Table
                      size="small"
                      dataSource={aiPlan}
                      rowKey="account_id"
                      pagination={{ pageSize: 8 }}
                      columns={[
                        { title: 'ID', dataIndex: 'account_id', width: 60 },
                        { title: '手机号', dataIndex: 'phone', width: 140, ellipsis: true },
                        {
                          title: 'Tier', dataIndex: 'tier', width: 80,
                          render: (v: string) => <Tag color={v === 'tier1' ? 'red' : v === 'tier2' ? 'purple' : 'default'}>{v}</Tag>,
                        },
                        {
                          title: 'Combat Role', dataIndex: 'combat_role', width: 100,
                          render: (v: string) => <Tag color={v === 'scout' ? 'blue' : v === 'actor' ? 'purple' : 'red'}>{v}</Tag>,
                        },
                        { title: 'AI 人设', dataIndex: 'persona_name', ellipsis: true },
                      ]}
                    />
                  )}
                </>
              ),
            },
          ]}
        />
      </Modal>

      {/* Quick Warmup Modal */}
      <Modal
        title={<span><CoffeeOutlined /> 一键养号</span>}
        open={isWarmupModalVisible}
        onCancel={() => setIsWarmupModalVisible(false)}
        onOk={handleQuickWarmup}
        confirmLoading={warmupLoading}
        okText="启动养号"
        cancelText="取消"
      >
        <div style={{ marginBottom: 16 }}>
          <p>已选择 <strong>{selectedRowKeys.length}</strong> 个账号</p>
          <p style={{ color: '#888', fontSize: 12 }}>
            仅活跃状态的账号会参与养号
          </p>
        </div>

        {warmupTemplates.length === 0 ? (
          <div style={{ textAlign: 'center', padding: '20px 0' }}>
            <p style={{ color: '#999' }}>暂无养号模板</p>
            <p style={{ fontSize: 12, color: '#bbb' }}>
              请先到「养号管理」页面创建模板
            </p>
          </div>
        ) : (
          <div>
            <p style={{ marginBottom: 8 }}>选择养号模板：</p>
            <Select
              style={{ width: '100%' }}
              value={selectedWarmupTemplateId}
              onChange={setSelectedWarmupTemplateId}
              placeholder="选择模板"
            >
              {warmupTemplates.map(t => (
                <Option key={t.id} value={t.id}>
                  {t.is_default && '\u2B50 '}{t.name} - {t.duration_minutes}分钟
                </Option>
              ))}
            </Select>
            {selectedWarmupTemplateId && (
              <div style={{ marginTop: 16, padding: 12, background: '#f5f5f5', borderRadius: 4 }}>
                {(() => {
                  const t = warmupTemplates.find(t => t.id === selectedWarmupTemplateId);
                  if (!t) return null;
                  return (
                    <>
                      <p><strong>目标频道：</strong>{t.target_channels || '无'}</p>
                      <p><strong>操作类型：</strong>{t.action_type === 'mixed' ? '混合模式' : '仅浏览'}</p>
                      <p><strong>持续时长：</strong>{t.duration_minutes} 分钟</p>
                      <p><strong>操作延迟：</strong>{t.min_delay}-{t.max_delay} 秒</p>
                    </>
                  );
                })()}
              </div>
            )}
          </div>
        )}
      </Modal>
    </>
  );
};

export default CombatRoleManager;
