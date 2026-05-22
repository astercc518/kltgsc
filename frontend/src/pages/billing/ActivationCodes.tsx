import React, { useState, useEffect } from "react";
import {
  Table, Button, Modal, Form, Input, InputNumber, Select,
  Tag, message, Space, Popconfirm, Card, Typography,
} from "antd";
import api from "../../services/api";

const { Title } = Typography;

interface ActivationCode {
  id: number;
  code: string;
  plan: string;
  duration_days: number;
  batch_id: string;
  status: "unused" | "redeemed" | "revoked";
  redeemed_by_customer_id: number | null;
  created_at: string;
  redeemed_at: string | null;
  notes: string | null;
}

const STATUS_COLOR: Record<string, string> = {
  unused: "blue",
  redeemed: "green",
  revoked: "red",
};

export const ActivationCodes: React.FC = () => {
  const [codes, setCodes] = useState<ActivationCode[]>([]);
  const [loading, setLoading] = useState(false);
  const [filterStatus, setFilterStatus] = useState<string | undefined>();
  const [filterPlan, setFilterPlan] = useState<string | undefined>();
  const [genModalOpen, setGenModalOpen] = useState(false);
  const [genForm] = Form.useForm();

  const fetchCodes = async () => {
    setLoading(true);
    const params: Record<string, string> = {};
    if (filterStatus) params.status = filterStatus;
    if (filterPlan) params.plan = filterPlan;
    const resp = await api.get("/admin/billing/activation-codes", { params });
    setCodes(resp.data);
    setLoading(false);
  };

  useEffect(() => { fetchCodes(); }, [filterStatus, filterPlan]);

  const handleGenerate = async (values: any) => {
    try {
      const resp = await api.post("/admin/billing/activation-codes/generate", values);
      message.success(`已生成 ${resp.data.codes.length} 个激活码，批次 ${resp.data.batch_id}`);
      setGenModalOpen(false);
      genForm.resetFields();
      fetchCodes();
    } catch (err: any) {
      message.error(err.response?.data?.detail || "生成失败");
    }
  };

  const handleRevoke = async (id: number) => {
    try {
      await api.post(`/admin/billing/activation-codes/${id}/revoke`);
      message.success("已撤销");
      fetchCodes();
    } catch (err: any) {
      message.error(err.response?.data?.detail || "撤销失败");
    }
  };

  const columns = [
    {
      title: "激活码",
      dataIndex: "code",
      key: "code",
      render: (v: string) =>
        <code style={{ fontFamily: "monospace" }}>
          {`${v.slice(0,4)}-${v.slice(4,8)}-${v.slice(8)}`}
        </code>,
    },
    {
      title: "套餐", dataIndex: "plan", key: "plan",
      render: (v: string) => <Tag>{v}</Tag>,
    },
    { title: "有效期(天)", dataIndex: "duration_days", key: "duration_days" },
    {
      title: "状态", dataIndex: "status", key: "status",
      render: (v: string) =>
        <Tag color={STATUS_COLOR[v] || "default"}>{v}</Tag>,
    },
    {
      title: "批次", dataIndex: "batch_id", key: "batch_id",
      render: (v: string) => <code>{v.slice(0,8)}</code>,
    },
    { title: "已兑换客户", dataIndex: "redeemed_by_customer_id", key: "redeemed_by_customer_id" },
    { title: "创建时间", dataIndex: "created_at", key: "created_at" },
    { title: "备注", dataIndex: "notes", key: "notes" },
    {
      title: "操作", key: "action",
      render: (_: any, record: ActivationCode) =>
        record.status === "unused" ? (
          <Popconfirm
            title="确定撤销？"
            onConfirm={() => handleRevoke(record.id)}
          >
            <Button type="link" danger>撤销</Button>
          </Popconfirm>
        ) : null,
    },
  ];

  return (
    <Card>
      <Space style={{ marginBottom: 16 }}>
        <Title level={4} style={{ margin: 0 }}>激活码管理</Title>
        <Select
          placeholder="状态筛选"
          allowClear
          style={{ width: 120 }}
          onChange={setFilterStatus}
          options={[
            { value: "unused", label: "未兑换" },
            { value: "redeemed", label: "已兑换" },
            { value: "revoked", label: "已撤销" },
          ]}
        />
        <Select
          placeholder="套餐筛选"
          allowClear
          style={{ width: 120 }}
          onChange={setFilterPlan}
          options={[
            { value: "starter", label: "Starter" },
            { value: "growth", label: "Growth" },
            { value: "pro", label: "Pro" },
          ]}
        />
        <Button type="primary" onClick={() => setGenModalOpen(true)}>
          批量生成
        </Button>
      </Space>

      <Table
        dataSource={codes}
        columns={columns}
        rowKey="id"
        loading={loading}
        pagination={{ pageSize: 20 }}
      />

      <Modal
        title="批量生成激活码"
        open={genModalOpen}
        onCancel={() => setGenModalOpen(false)}
        onOk={() => genForm.submit()}
      >
        <Form form={genForm} onFinish={handleGenerate} layout="vertical">
          <Form.Item name="plan" label="套餐" rules={[{ required: true }]}>
            <Select options={[
              { value: "starter", label: "Starter" },
              { value: "growth", label: "Growth" },
              { value: "pro", label: "Pro" },
            ]} />
          </Form.Item>
          <Form.Item
            name="count" label="数量" initialValue={10}
            rules={[{ required: true, type: "number", min: 1, max: 500 }]}
          >
            <InputNumber min={1} max={500} />
          </Form.Item>
          <Form.Item name="duration_days" label="有效期(天)" initialValue={30}>
            <InputNumber min={1} max={365} />
          </Form.Item>
          <Form.Item name="notes" label="备注">
            <Input placeholder="可选" />
          </Form.Item>
        </Form>
      </Modal>
    </Card>
  );
};

export default ActivationCodes;
