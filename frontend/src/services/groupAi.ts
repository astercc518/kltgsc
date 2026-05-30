import api from './api';

export interface InboxRow {
  id: number; status: string; reply_text: string | null;
  chat_id: number; source_user_id: number; source_text: string;
  sent_at: string | null; created_at: string;
  solution_topic: string | null; extracted_needs: string[] | null;
}

export const groupAiAdminApi = {
  listInbox: (customer_id: number) =>
    api.get<InboxRow[]>(`/inbox/group-ai/customers/${customer_id}/recent`).then(r => r.data),
  approveSuggested: (pr_id: number) =>
    api.post(`/inbox/group-ai/suggested/${pr_id}/approve`),
  editSuggested: (pr_id: number, reply_text: string) =>
    api.put(`/inbox/group-ai/suggested/${pr_id}`, { reply_text }),
};

// ── A/B Experiment API ───────────────────────────────────────────────

export interface ABExperiment {
  id: number;
  name: string;
  description: string | null;
  scope: 'global' | 'customer' | 'monitor';
  scope_value: number | null;
  variants: { tag: string; weight: number; params: Record<string, any> }[];
  status: 'draft' | 'running' | 'finished' | 'paused';
  primary_metric: string | null;
  started_at: string | null;
  ended_at: string | null;
}

export interface ABMetric {
  sent: number; suggested: number; skipped_total: number; failed: number;
  reply_rate: number; private_conversion_rate: number;
  kick_rate: number; anti_hallucination_failure_rate: number;
}

export interface ABReport {
  /** Backend key is "experiment" (the experiment name string). */
  experiment: string;
  primary_metric: string | null;
  variants: Array<{
    tag: string;
    counters?: {
      sent: number;
      suggested: number;
      skipped_total: number;
      failed: number;
      private_conversion_count?: number;
      kick_count?: number;
      total_triggered?: number;
    };
    metrics?: {
      reply_rate: number;
      private_conversion_rate: number;
      kick_rate: number;
      anti_hallucination_failure_rate: number;
    };
    ci?: {
      reply_rate_ci?: [number, number];
      private_conversion_rate_ci?: [number, number];
      kick_rate_ci?: [number, number];
      anti_hallucination_failure_rate_ci?: [number, number];
    };
  }>;
  significance: {
    primary_metric: string;
    z_stat: number | null;
    p_value: number | null;
    significant: boolean;
  } | null;
}

export const abApi = {
  list: () =>
    api.get<ABExperiment[]>('/admin/group-ai/ab/experiments').then(r => r.data),
  create: (body: Partial<ABExperiment>) =>
    api.post<{ id: number }>('/admin/group-ai/ab/experiments', body),
  start: (id: number) =>
    api.put(`/admin/group-ai/ab/experiments/${id}/start`),
  stop: (id: number) =>
    api.put(`/admin/group-ai/ab/experiments/${id}/stop`),
  metrics: (id: number) =>
    api.get<Record<string, ABMetric>>(`/admin/group-ai/ab/experiments/${id}/metrics`).then(r => r.data),
  report: (id: number) =>
    api.get<ABReport>(`/admin/group-ai/ab/experiments/${id}/report`).then(r => r.data),
  csvUrl: (id: number) => `/api/v1/admin/group-ai/ab/experiments/${id}/report.csv`,
};
