/**
 * Customer-portal API wrappers for "群内 AI 销售员" features.
 * Backend: /portal/group-ai/*
 */
import portalApi from '../api';

// === Types ===

export interface DiscoveryCandidate {
  id: number;
  chat_link: string | null;
  chat_username: string | null;
  title: string | null;
  members_count: number | null;
  category: string | null;
  source: string;
  source_query: string | null;
  score: number | null;
  status: string;
  discovered_at: string;
}

export interface ICPState {
  icp_text: string | null;
  has_embedding: boolean;
  thresholds: {
    layer2_sim: number;
    layer3_score: number;
    layer3_confidence: number;
  };
}

export interface CaseStudy {
  id: number;
  industry: string | null;
  deal_size: string | null;
  period: string | null;
  problem: string;
  solution: string;
  outcome: string;
  tags: string[];
  active: boolean;
  source: string;
  created_at: string;
}

export interface CaseStudyExtractedCandidate {
  industry: string;
  deal_size: string;
  period: string;
  problem: string;
  solution: string;
  outcome: string;
  tags: string[];
}

export interface WorkerPersona {
  display_name: string | null;
  region: string | null;
  occupation: string | null;
  speaking_style: string | null;
  catchphrases: string[];
  active_hours: Record<string, [number, number][]>;
  daily_reply_quota: number;
  per_chat_daily_quota: number;
  per_chat_cooldown_minutes: number;
  daily_chitchat_quota: number;
  observation_window_seconds_range: [number, number];
  typing_delay_seconds_range: [number, number];
}

export interface ChitchatTopic {
  id: number;
  topic_category: string | null;
  prompt_template: string;
  tags: string[];
  scope: 'global' | 'customer';
}

export interface RecentStats {
  triggered_today: number;
  sent_today: number;
  suggested_today: number;
  failed_today: number;
  skipped: {
    human_replied: number;
    dup: number;
    throttled: number;
    borderline: number;
  };
}

// === API ===

export const groupAiApi = {
  // ICP
  getIcp: () => portalApi.get<ICPState>('/portal/group-ai/icp').then(r => r.data),
  updateIcp: (icp_text: string | null) =>
    portalApi.put('/portal/group-ai/icp', { icp_text }),

  // Thresholds
  updateThresholds: (body: Partial<ICPState['thresholds']>) =>
    portalApi.put('/portal/group-ai/thresholds', body),

  // Cases
  listCases: (include_inactive = false) =>
    portalApi.get<CaseStudy[]>('/portal/group-ai/case-studies', { params: { include_inactive } })
      .then(r => r.data),
  createCase: (body: Omit<CaseStudy, 'id' | 'active' | 'source' | 'created_at'>) =>
    portalApi.post<{ id: number }>('/portal/group-ai/case-studies', body),
  updateCase: (id: number, body: Partial<CaseStudy>) =>
    portalApi.put(`/portal/group-ai/case-studies/${id}`, body),
  deleteCase: (id: number) =>
    portalApi.delete(`/portal/group-ai/case-studies/${id}`),
  extractCases: (max_history = 100) =>
    portalApi.post<{ candidates: CaseStudyExtractedCandidate[] }>(
      '/portal/group-ai/case-studies/extract', null, { params: { max_history } },
    ).then(r => r.data),
  batchCreateCases: (cases: CaseStudyExtractedCandidate[]) =>
    portalApi.post<{ ids: number[] }>('/portal/group-ai/case-studies/batch', { cases }),

  // Accounts + persona
  listAccounts: () =>
    portalApi.get<{ id: number; phone: string; status: string }[]>('/portal/group-ai/accounts')
      .then(r => r.data),
  getPersona: (account_id: number) =>
    portalApi.get<WorkerPersona | null>(`/portal/group-ai/accounts/${account_id}/persona`)
      .then(r => r.data),
  upsertPersona: (account_id: number, body: Partial<WorkerPersona>) =>
    portalApi.put(`/portal/group-ai/accounts/${account_id}/persona`, body),

  // Chitchat
  listChitchatTopics: () =>
    portalApi.get<ChitchatTopic[]>('/portal/group-ai/chitchat-topics').then(r => r.data),
  createChitchatTopic: (body: Omit<ChitchatTopic, 'id' | 'scope'>) =>
    portalApi.post<{ id: number }>('/portal/group-ai/chitchat-topics', body),

  // Stats
  getRecentStats: () =>
    portalApi.get<RecentStats>('/portal/group-ai/stats/recent').then(r => r.data),

  // Discovery candidates
  listDiscoveryCandidates: (status = 'pending') =>
    portalApi.get<DiscoveryCandidate[]>('/portal/group-ai/discovery/candidates', { params: { status } })
      .then(r => r.data),
  approveDiscoveryCandidate: (id: number) =>
    portalApi.post(`/portal/group-ai/discovery/${id}/approve`),
  rejectDiscoveryCandidate: (id: number) =>
    portalApi.post(`/portal/group-ai/discovery/${id}/reject`),
};
