/**
 * Customer-portal axios instance.
 *
 * Distinct from src/services/api.ts so that:
 *   - it sends the customer token (separate localStorage key)
 *   - 401/403 redirects to /portal/login (not /login)
 *   - tag-team coexistence with the admin app
 */
import axios, { AxiosError, AxiosResponse, InternalAxiosRequestConfig } from 'axios';
import { getCustomerToken, clearCustomerToken } from './auth';

const portalApi = axios.create({
  baseURL: '/api/v1',
  headers: { 'Content-Type': 'application/json' },
});

portalApi.interceptors.request.use(
  (config: InternalAxiosRequestConfig) => {
    const token = getCustomerToken();
    if (token) {
      config.headers.Authorization = `Bearer ${token}`;
    }
    return config;
  },
  (error) => Promise.reject(error),
);

portalApi.interceptors.response.use(
  (response: AxiosResponse) => response,
  (error: AxiosError) => {
    const status = error.response?.status;
    // 402 = subscription not active; let the page handle by redirecting to billing
    if (status === 401 || status === 403) {
      clearCustomerToken();
      if (window.location.pathname !== '/login'
          && !window.location.pathname.startsWith('/portal/register')) {
        window.location.href = '/login';
      }
    }
    return Promise.reject(error);
  },
);

// ── Typed API helpers ────────────────────────────────────────────────────

export interface CustomerProfile {
  id: number;
  email: string;
  name?: string;
  company?: string;
  industry?: string;
  status: string;
  plan?: string | null;
  subscription_status?: string | null;
  current_period_end?: string | null;
  account_quota: number;
  group_quota: number;
  token_quota: number;
  seat_quota: number;
  account_used: number;
  group_used: number;
  token_used: number;
  created_at: string;
  last_login_at?: string;
}

export interface QuotaInfo {
  plan: string | null;
  status: string;
  subscription_status: string | null;
  current_period_end: string | null;
  limits: {
    account_quota: number;
    group_quota: number;
    token_quota: number;
    seat_quota: number;
  };
  usage: {
    accounts: number;
    leads: number;
    knowledge_bases: number;
    tokens: number;
  };
}

export interface Invoice {
  id: number;
  customer_id: number;
  subscription_id: number | null;
  plan: string;
  amount_usd: number;
  amount_crypto: number;
  currency: string;
  network: string;
  payment_address: string;
  status: string;
  tx_hash: string | null;
  description: string;
  paid_at: string | null;
  created_at: string;
  expires_at: string;
}

export interface Subscription {
  id: number;
  customer_id: number;
  plan: string;
  status: string;
  period_start: string;
  period_end: string;
  auto_renew: boolean;
  activated_at: string | null;
  created_at: string;
}

export interface LoginResponse {
  access_token: string;
  token_type: string;
  customer: CustomerProfile;
}

export const authApi = {
  register: (data: { email: string; password: string; name?: string; company?: string; industry?: string }) =>
    portalApi.post<LoginResponse>('/customer/register', data).then(r => r.data),
  login: (email: string, password: string) =>
    portalApi.post<LoginResponse>('/customer/login', { email, password }).then(r => r.data),
  me: () => portalApi.get<CustomerProfile>('/customer/me').then(r => r.data),
};

export const billingApi = {
  subscribe: (plan: string, network: string = 'TRC20') =>
    portalApi.post<Invoice>('/customer/subscribe', { plan, network }).then(r => r.data),
  listInvoices: () =>
    portalApi.get<Invoice[]>('/customer/invoices').then(r => r.data),
  getInvoice: (id: number) =>
    portalApi.get<Invoice>(`/customer/invoices/${id}`).then(r => r.data),
  getSubscription: () =>
    portalApi.get<Subscription>('/customer/subscription').then(r => r.data),
};

export const resourcesApi = {
  quota: () => portalApi.get<QuotaInfo>('/customer/quota').then(r => r.data),
  accounts: () => portalApi.get<any[]>('/customer/accounts').then(r => r.data),
  leads: (params: { source?: string; bulk_batch_id?: number; status?: string; limit?: number } = {}) =>
    portalApi.get<any[]>('/customer/leads', { params }).then(r => r.data),
  knowledgeBases: () => portalApi.get<any[]>('/customer/knowledge-bases').then(r => r.data),
};

// Bulk Send W1 — wallet
export interface Wallet {
  customer_id: number;
  balance_cents: number;
  total_topup_cents: number;
  total_spent_cents: number;
  created_at: string;
  updated_at: string;
}

export interface WalletTransaction {
  id: number;
  type: 'topup' | 'charge' | 'refund' | 'adjust';
  amount_cents: number;
  balance_after_cents: number;
  description: string;
  bulk_batch_id?: number | null;
  invoice_id?: number | null;
  created_at: string;
}

export interface TopupResponse {
  invoice_id: number;
  amount_usd: number;
  amount_crypto: number;
  bonus_pct: number;
  bonus_cents: number;
  final_credit_cents: number;
  currency: string;
  network: string;
  payment_address: string;
  expires_at: string;
}

export const walletApi = {
  get: () => portalApi.get<Wallet>('/customer/wallet').then(r => r.data),
  topup: (amount_usd: number, network: string = 'TRC20') =>
    portalApi.post<TopupResponse>('/customer/wallet/topup', { amount_usd, network }).then(r => r.data),
  transactions: (params: { type?: string; skip?: number; limit?: number } = {}) =>
    portalApi.get<WalletTransaction[]>('/customer/wallet/transactions', { params }).then(r => r.data),
};

// ─── Feature Pack (customer view) ────────────────────────────────────────

export interface CustomerFeatureView {
  feature_slug: string;
  name_zh: string;
  name_en: string;
  category: string;
  billing_unit: string;
  enabled: boolean;
  unit_price_cents: number;
  is_custom_price: boolean;
  notes: string;
}

export interface FeatureUsageView {
  feature_slug: string;
  name_zh: string;
  units_consumed: number;
  total_charged_cents: number;
  last_charged_at: string | null;
}

export interface EstimateResponse {
  feature_slug: string;
  units: number;
  unit_price_cents: number;
  total_cost_cents: number;
  can_afford: boolean;
  balance_cents: number;
}

export const featureApi = {
  list: () => portalApi.get<CustomerFeatureView[]>('/customer/features').then(r => r.data),
  estimate: (slug: string, units: number) =>
    portalApi.post<EstimateResponse>(`/customer/features/${slug}/estimate`, { units }).then(r => r.data),
  usage: (days: number = 30) =>
    portalApi.get<FeatureUsageView[]>('/customer/features/usage', { params: { days } }).then(r => r.data),
};

// ─── Bulk Send W2 ────────────────────────────────────────────────────────

export interface BulkBatch {
  id: number;
  customer_id: number;
  name: string;
  message_template: string;
  status: string;
  total_targets: number;
  sent_count: number;
  delivered_count: number;
  failed_count: number;
  replied_count: number;
  skipped_count: number;
  estimated_unit_price_cents: number;
  estimated_total_cents: number;
  min_delay_sec: number;
  max_delay_sec: number;
  started_at: string | null;
  completed_at: string | null;
  paused_at: string | null;
  pause_reason: string | null;
  created_at: string;
}

export interface BulkTarget {
  id: number;
  batch_id: number;
  tg_user_id: number | null;
  tg_username: string | null;
  phone: string | null;
  display_name: string | null;
  country: string | null;
  status: string;
  assigned_account_id: number | null;
  sent_at: string | null;
  failed_reason: string | null;
  created_at: string;
}

export interface BulkVariant {
  id: number;
  batch_id: number;
  content: string;
  weight: number;
  use_count: number;
  created_at: string;
}

export interface BulkBatchDetail extends BulkBatch {
  variants: BulkVariant[];
  targets_preview: BulkTarget[];
}

export interface CostPreview {
  target_count: number;
  current_tier_unit_cents: number;
  total_cost_cents: number;
  balance_cents: number;
  balance_sufficient: boolean;
  shortfall_cents: number;
  breakdown: { count: number; unit_cents: number; subtotal_cents: number }[];
}

export interface CreateBatchRequest {
  name: string;
  message_template: string;
  csv_text?: string;
  variants?: string[];
  min_delay_sec?: number;
  max_delay_sec?: number;
}

export const bulkApi = {
  previewCost: (target_count: number) =>
    portalApi.post<CostPreview>('/customer/bulk/preview-cost', { target_count }).then(r => r.data),
  createBatch: (data: CreateBatchRequest) =>
    portalApi.post<BulkBatchDetail>('/customer/bulk/batches', data).then(r => r.data),
  listBatches: (params: { status?: string; skip?: number; limit?: number } = {}) =>
    portalApi.get<BulkBatch[]>('/customer/bulk/batches', { params }).then(r => r.data),
  getBatch: (id: number) =>
    portalApi.get<BulkBatchDetail>(`/customer/bulk/batches/${id}`).then(r => r.data),
  cancelBatch: (id: number) =>
    portalApi.delete<{ ok: boolean }>(`/customer/bulk/batches/${id}`).then(r => r.data),
  startBatch: (id: number) =>
    portalApi.post<BulkBatchDetail>(`/customer/bulk/batches/${id}/start`, {}).then(r => r.data),
  pauseBatch: (id: number) =>
    portalApi.post<BulkBatchDetail>(`/customer/bulk/batches/${id}/pause`, {}).then(r => r.data),
  resumeBatch: (id: number) =>
    portalApi.post<BulkBatchDetail>(`/customer/bulk/batches/${id}/resume`, {}).then(r => r.data),
  addVariant: (batchId: number, content: string, weight: number = 1) =>
    portalApi.post<BulkVariant>(`/customer/bulk/batches/${batchId}/variants`,
      { content, weight }).then(r => r.data),
  updateVariant: (variantId: number, payload: { content?: string; weight?: number }) =>
    portalApi.put<BulkVariant>(`/customer/bulk/variants/${variantId}`, payload).then(r => r.data),
  deleteVariant: (variantId: number) =>
    portalApi.delete<{ ok: boolean }>(`/customer/bulk/variants/${variantId}`).then(r => r.data),
};

// Epic 4.1 — KB CRUD + upload
export interface KBEntry {
  id: number;
  name: string;
  description?: string;
  content: string;
  source_type: string;
  category?: string;
  language?: string;
  source_filename?: string;
  parent_doc_id?: string;
  chunk_index?: number;
  created_at: string;
  updated_at: string;
}

export interface UploadResponse {
  name: string;
  total_chunks: number;
  embedded_chunks: number;
  extension: string;
}

// Epic 5.1 — Chat-history import
export const importApi = {
  start: (data: {
    since?: string; until?: string;
    dialog_types?: string[];
    max_messages_per_chat: number;
    cost_cap_usd: number;
  }) => portalApi.post<{
    scrape_task_id: string;
    scraping_task_id: number;
    extract_task_id: string;
    main_account_id: number;
  }>('/customer/knowledge-bases/import-history', data).then(r => r.data),
  status: (scrapingTaskId: number) => portalApi.get<{
    status: string;
    progress: any;
    kb_extracted_total: number;
    error?: string;
    completed_at?: string;
  }>(`/customer/knowledge-bases/import-history/${scrapingTaskId}/status`).then(r => r.data),
};

// Epic 5.0 — Main account QR login
export interface QRStartResponse {
  token: string;
  qr_url: string;
  qr_png_b64: string;
  expires_at: number;
  state: string;
  mock?: boolean;
}

export interface QRStatusResponse {
  token: string;
  state: 'pending' | 'password_required' | 'success' | 'expired' | 'error';
  error?: string;
  username?: string;
  phone_last4?: string;
}

export interface MainAccountStatus {
  connected: boolean;
  account_id?: number;
  phone_last4?: string;
  username?: string;
  first_name?: string;
  connected_at?: string;
  status?: string;
}

export const mainAccountApi = {
  start: () => portalApi.post<QRStartResponse>('/customer/main-account/qr/start').then(r => r.data),
  status: (token: string) =>
    portalApi.get<QRStatusResponse>('/customer/main-account/qr/status', { params: { token } }).then(r => r.data),
  submitPassword: (token: string, password: string) =>
    portalApi.post('/customer/main-account/qr/password', { token, password }).then(r => r.data),
  current: () => portalApi.get<MainAccountStatus>('/customer/main-account').then(r => r.data),
  disconnect: () => portalApi.delete('/customer/main-account').then(r => r.data),
};

export const kbApi = {
  get: (id: number) => portalApi.get<KBEntry>(`/customer/knowledge-bases/${id}`).then(r => r.data),
  create: (data: { name: string; content: string; description?: string; category?: string; language?: string }) =>
    portalApi.post<KBEntry>('/customer/knowledge-bases/', data).then(r => r.data),
  update: (id: number, data: Partial<{ name: string; content: string; description: string; category: string; language: string }>) =>
    portalApi.patch<KBEntry>(`/customer/knowledge-bases/${id}`, data).then(r => r.data),
  delete: (id: number) => portalApi.delete(`/customer/knowledge-bases/${id}`).then(() => undefined),
  upload: (file: File, opts?: { category?: string; name?: string }) => {
    const form = new FormData();
    form.append('file', file);
    if (opts?.category) form.append('category', opts.category);
    if (opts?.name) form.append('name', opts.name);
    return portalApi.post<UploadResponse>('/customer/knowledge-bases/upload', form, {
      headers: { 'Content-Type': 'multipart/form-data' },
    }).then(r => r.data);
  },
  supportedTypes: () =>
    portalApi.get<{ extensions: string[]; max_bytes: number }>('/customer/knowledge-bases/_meta/supported-types').then(r => r.data),
};

export default portalApi;
