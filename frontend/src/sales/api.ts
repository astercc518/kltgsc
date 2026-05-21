import axios from 'axios';
import { clearSalesToken, getSalesToken } from './auth';

const salesApi = axios.create({ baseURL: '/api/v1' });

salesApi.interceptors.request.use((config) => {
  const token = getSalesToken();
  if (token) {
    config.headers = config.headers || {};
    (config.headers as any).Authorization = `Bearer ${token}`;
  }
  return config;
});

salesApi.interceptors.response.use(
  (r) => r,
  (error) => {
    const status = error?.response?.status;
    if (status === 401 || status === 403) {
      clearSalesToken();
      if (window.location.pathname !== '/login') {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  }
);

// ─── Types ────────────────────────────────────────────────────────────

export interface SalesWallet {
  owner_type: 'customer_sales' | 'platform_sales';
  owner_id: number;
  balance_cents: number;
  total_topup_cents: number;
  total_spent_cents: number;
}

export interface SalesWalletTxn {
  id: number;
  type: 'topup' | 'charge' | 'refund' | 'adjust';
  amount_cents: number;
  balance_after_cents: number;
  description: string;
  invoice_id: number | null;
  lead_id: number | null;
  created_at: string;
}

export interface LeadCard {
  id: number;
  industry: string | null;
  category: string | null;
  source: string;
  status: string;
  first_name_hint: string | null;
  username_hint: string | null;
  phone_hint: string | null;
  has_notes: boolean;
  view_count: number;
  already_viewed_today: boolean;
  last_interaction_at: string;
  created_at: string;
}

export interface LeadFull {
  id: number;
  industry: string | null;
  category: string | null;
  source: string;
  bulk_batch_id: number | null;
  status: string;
  telegram_user_id: number;
  username: string | null;
  first_name: string | null;
  last_name: string | null;
  phone: string | null;
  notes: string | null;
  view_count: number;
  customer_id: number | null;
  account_id: number;
  tags: string[];
  last_interaction_at: string;
  created_at: string;
  interactions: Array<{
    id: number;
    direction: string;
    message_type: string;
    content: string;
    created_at: string;
  }>;
}

export interface ViewReceipt {
  lead: LeadFull;
  charged_cents: number;
  balance_after_cents: number;
  charge_skipped: boolean;
}

export interface IndustryStat {
  industry: string;
  count: number;
}

export interface SalesProfile {
  email: string;
  role: string;
  customer_id: number | null;
  kind: 'customer' | 'platform';
  industry_filter: string[];
}

// ─── API surfaces ─────────────────────────────────────────────────────

export const walletApi = {
  get: () => salesApi.get<SalesWallet>('/sales/wallet').then(r => r.data),
  transactions: (params: { type?: string; limit?: number } = {}) =>
    salesApi.get<SalesWalletTxn[]>('/sales/wallet/transactions', { params }).then(r => r.data),
  topup: (amount_usd: number, network: string = 'TRC20') =>
    salesApi.post('/sales/wallet/topup', { amount_usd, network }).then(r => r.data),
};

export const leadsApi = {
  list: (params: {
    industry?: string; category?: string; status?: string; source?: string;
    skip?: number; limit?: number;
  } = {}) =>
    salesApi.get<LeadCard[]>('/sales/leads', { params }).then(r => r.data),
  view: (id: number) =>
    salesApi.get<ViewReceipt>(`/sales/leads/${id}/view`).then(r => r.data),
  industries: () =>
    salesApi.get<IndustryStat[]>('/sales/leads/industries').then(r => r.data),
};

// industry_filter editor — uses customer-side endpoint when sub-user OR
// admin-only when platform-sales. For now expose just the read via JWT decode.
export function decodeJwtPayload(): SalesProfile | null {
  const token = getSalesToken();
  if (!token) return null;
  try {
    const part = token.split('.')[1];
    const padded = part + '='.repeat((4 - part.length % 4) % 4);
    const decoded = atob(padded.replace(/-/g, '+').replace(/_/g, '/'));
    const obj = JSON.parse(decoded);
    return {
      email: obj.sub,
      role: 'sales',
      customer_id: obj.customer_id ?? null,
      kind: obj.type === 'customer_sales' ? 'customer' : 'platform',
      industry_filter: [], // placeholder; populate from /sales/profile if added later
    };
  } catch {
    return null;
  }
}

// ─── Phase G — sales monitors + assigned accounts ────────────────────────

export interface SalesMonitor {
  id: number;
  keyword: string;
  match_type: string;            // partial | exact | regex | semantic
  target_groups: string | null;
  industry: string | null;
  is_active: boolean;
  cooldown_seconds: number;
  marketing_mode: string;        // 'passive' (sales-owned can't be 'active')
  auto_capture_lead: boolean;
  score_weight: number;
  scenario_description: string | null;
  similarity_threshold: number;
  description: string | null;
  created_at: string;
  created_by_sales_user_id: number | null;
  created_by_sales_kind: string | null;
}

export interface SalesMonitorRecentHit {
  id: number;
  source_group_name: string | null;
  source_user_name: string | null;
  snippet: string;
  detected_at: string;
}

export const monitorsApi = {
  list: (params: { is_active?: boolean } = {}) =>
    salesApi.get<SalesMonitor[]>('/sales/monitors', { params }).then(r => r.data),
  get: (id: number) =>
    salesApi.get<SalesMonitor>(`/sales/monitors/${id}`).then(r => r.data),
  create: (body: Partial<SalesMonitor>) =>
    salesApi.post<SalesMonitor>('/sales/monitors', body).then(r => r.data),
  update: (id: number, body: Partial<SalesMonitor>) =>
    salesApi.put<SalesMonitor>(`/sales/monitors/${id}`, body).then(r => r.data),
  remove: (id: number) =>
    salesApi.delete(`/sales/monitors/${id}`).then(r => r.data),
  recentHits: (id: number, hours: number = 24) =>
    salesApi.get<SalesMonitorRecentHit[]>(`/sales/monitors/${id}/recent-hits`,
      { params: { hours } }).then(r => r.data),
};

export interface SalesAccount {
  id: number;
  phone_number: string | null;
  customized_username: string | null;
  customized_first_name: string | null;
  status: string;
  role: string | null;
  customer_id: number | null;
  created_at: string;
  daily_invite_count: number;
  lead_count: number;
}

export interface ScrapeTaskRow {
  id: number;
  task_type: string;
  status: string;
  success_count: number;
  fail_count: number;
  created_at: string;
  completed_at: string | null;
}

export const accountsApi = {
  list: () => salesApi.get<SalesAccount[]>('/sales/accounts').then(r => r.data),
  joinGroup: (id: number, group_link: string) =>
    salesApi.post(`/sales/accounts/${id}/join-group`, { group_link }).then(r => r.data),
  scrape: (id: number, body: {
    group_link: string;
    limit?: number;
    filter_active_only?: boolean;
    filter_has_photo?: boolean;
    filter_has_username?: boolean;
  }) => salesApi.post(`/sales/accounts/${id}/scrape`, body).then(r => r.data),
  scrapeTasks: (id: number, limit = 20) =>
    salesApi.get<ScrapeTaskRow[]>(`/sales/accounts/${id}/scrape-tasks`,
      { params: { limit } }).then(r => r.data),
};

export default salesApi;
