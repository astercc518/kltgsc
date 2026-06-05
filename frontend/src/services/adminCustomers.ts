import axios, { AxiosError } from 'axios';

const api = axios.create({ baseURL: '/api/v1' });
api.interceptors.request.use((cfg) => {
  const token = localStorage.getItem('token');
  if (token) cfg.headers.Authorization = `Bearer ${token}`;
  return cfg;
});

// ---- Types (mirrors CustomerRead from backend/app/models/customer.py) ----

export type CustomerStatus = 'pending' | 'active' | 'suspended' | 'canceled';
export type Plan = 'starter' | 'growth' | 'pro';

export interface Customer {
  id: number;
  email: string;
  name: string | null;
  company: string | null;
  industry: string | null;
  status: CustomerStatus;
  plan: Plan | null;
  subscription_status: string | null;
  current_period_end: string | null;
  account_quota: number;
  group_quota: number;
  token_quota: number;
  seat_quota: number;
  account_used: number;
  group_used: number;
  token_used: number;
  seat_used: number;
  is_internal_pool: boolean;
  created_at: string;
  last_login_at: string | null;
}

export interface Invoice {
  id: number;
  customer_id: number;
  amount_cents: number;
  status: string;
  tx_hash: string | null;
  note: string | null;
  created_at: string;
}

// Two modes:
//   - create mode: provide new_customer_email + new_customer_password
//   - existing mode: provide customer_id only
// Backend validates one of the two; do not mix.
export type QuickProvisionPayload =
  | {
      new_customer_email: string;
      new_customer_password: string;
      new_customer_name?: string;
      new_customer_industry?: string;
      plan: Plan;
      wallet_credit_cents?: number;
      note?: string;
    }
  | {
      customer_id: number;
      plan: Plan;
      wallet_credit_cents?: number;
      note?: string;
    };

export interface FeatureRegistry {
  slug: string;
  name: string;
  description: string | null;
  default_enabled: boolean;
}

export interface CustomerFeature {
  slug: string;
  enabled: boolean;
  config_json: Record<string, unknown> | null;
}

export interface FeatureUsageSummary {
  slug: string;
  period_start: string;
  units_used: number;
}

// ---- Error normalization ----

export class AdminApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

function normalize(err: unknown, method: string, path: string): never {
  const ax = err as AxiosError<{ detail?: unknown }>;
  if (ax.response) {
    const detail = ax.response.data?.detail;
    const message =
      typeof detail === 'string' ? detail : `${method} ${path} → ${ax.response.status}`;
    throw new AdminApiError(ax.response.status, detail, message);
  }
  throw new AdminApiError(0, null, `${method} ${path} → network error`);
}

// ---- Customer endpoints ----

export async function listCustomers(params?: {
  status?: CustomerStatus;
  plan?: Plan;
  skip?: number;
  limit?: number;
}): Promise<Customer[]> {
  try {
    const res = await api.get<Customer[]>('/admin/billing/customers', { params });
    return res.data;
  } catch (e) {
    normalize(e, 'GET', '/admin/billing/customers');
  }
}

export async function getCustomerById(id: number): Promise<Customer | null> {
  // Backend has no /customers/{id} GET; fetch list with high limit and find.
  // Acceptable for <1000 customers per spec §3.
  const all = await listCustomers({ limit: 500 });
  return all.find((c) => c.id === id) ?? null;
}

export async function quickProvision(payload: QuickProvisionPayload): Promise<Customer> {
  try {
    const res = await api.post<Customer>('/admin/billing/quick-provision', payload);
    return res.data;
  } catch (e) {
    normalize(e, 'POST', '/admin/billing/quick-provision');
  }
}

export async function reallocateAccounts(customerId: number): Promise<void> {
  try {
    await api.post(`/admin/billing/customers/${customerId}/reallocate-accounts`);
  } catch (e) {
    normalize(e, 'POST', `/admin/billing/customers/${customerId}/reallocate-accounts`);
  }
}

export async function reallocateGroups(customerId: number): Promise<void> {
  try {
    await api.post(`/admin/billing/customers/${customerId}/reallocate-groups`);
  } catch (e) {
    normalize(e, 'POST', `/admin/billing/customers/${customerId}/reallocate-groups`);
  }
}

export async function regenerateKb(customerId: number): Promise<void> {
  try {
    await api.post(`/admin/billing/customers/${customerId}/regenerate-kb`);
  } catch (e) {
    normalize(e, 'POST', `/admin/billing/customers/${customerId}/regenerate-kb`);
  }
}

// ---- Invoice endpoints ----

export async function listInvoices(customerId: number): Promise<Invoice[]> {
  try {
    const res = await api.get<Invoice[]>('/admin/billing/invoices', {
      params: { customer_id: customerId, limit: 100 },
    });
    return res.data;
  } catch (e) {
    normalize(e, 'GET', '/admin/billing/invoices');
  }
}

// ---- Feature endpoints ----

export async function listFeatureRegistry(): Promise<FeatureRegistry[]> {
  try {
    const res = await api.get<FeatureRegistry[]>('/admin/features/features');
    return res.data;
  } catch (e) {
    normalize(e, 'GET', '/admin/features/features');
  }
}

export async function listCustomerFeatures(customerId: number): Promise<CustomerFeature[]> {
  try {
    const res = await api.get<CustomerFeature[]>(
      `/admin/features/customers/${customerId}/features`,
    );
    return res.data;
  } catch (e) {
    normalize(e, 'GET', `/admin/features/customers/${customerId}/features`);
  }
}

export async function upsertCustomerFeature(
  customerId: number,
  slug: string,
  enabled: boolean,
): Promise<CustomerFeature> {
  try {
    const res = await api.put<CustomerFeature>(
      `/admin/features/customers/${customerId}/features/${slug}`,
      { enabled },
    );
    return res.data;
  } catch (e) {
    normalize(e, 'PUT', `/admin/features/customers/${customerId}/features/${slug}`);
  }
}

export async function listCustomerUsage(
  customerId: number,
): Promise<FeatureUsageSummary[]> {
  try {
    const res = await api.get<FeatureUsageSummary[]>(
      `/admin/features/customers/${customerId}/usage`,
    );
    return res.data;
  } catch (e) {
    normalize(e, 'GET', `/admin/features/customers/${customerId}/usage`);
  }
}

// ---- Utilities ----

export function generateRandomPassword(length = 12): string {
  const charset =
    'ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnpqrstuvwxyz23456789!@#$%^&*';
  const arr = new Uint32Array(length);
  crypto.getRandomValues(arr);
  return Array.from(arr, (n) => charset[n % charset.length]).join('');
}
