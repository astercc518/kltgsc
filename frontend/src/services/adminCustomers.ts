import type { AxiosError } from 'axios';
import api from './api';

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

// Mirrors backend/app/models/subscription.py InvoiceRead
export interface AdminInvoice {
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
      plan?: Plan;            // optional: omit for a pure wallet top-up
      wallet_credit_cents?: number;
      note?: string;
    };

// quick-provision returns a summary (not a Customer). Only the fields we use.
export interface QuickProvisionResult {
  ok: boolean;
  customer_id: number;
  customer_email: string;
  plan_activated: string | null;
  wallet_balance_cents: number;
  wallet_credit_txn_id: number | null;
}

export interface CustomerWallet {
  customer_id: number;
  balance_cents: number;
  total_topup_cents: number;
  total_spent_cents: number;
}

// Mirrors backend/app/models/feature.py FeatureRegistryRead
export interface AdminFeatureEntry {
  slug: string;
  name_zh: string;
  name_en: string;
  description: string;
  billing_unit: string;
  default_price_cents: number;
  enabled_by_default: boolean;
  category: string;
  is_active: boolean;
}

// Mirrors backend/app/models/feature.py CustomerFeatureRead
export interface AdminCustomerFeature {
  feature_slug: string;
  enabled: boolean;
  unit_price_cents: number;
  is_custom_price: boolean;
  billing_unit: string;
  name_zh: string;
  name_en: string;
  category: string;
  notes: string;
}

// Mirrors backend/app/models/feature.py FeatureUsageSummary
export interface AdminFeatureUsageSummary {
  feature_slug: string;
  name_zh: string;
  units_consumed: number;
  total_charged_cents: number;
  last_charged_at: string | null;
}

export interface CustomerFeatureUpdate {
  enabled: boolean;
  custom_price_cents?: number | null;
  notes?: string;
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

export async function getCustomerWallet(customerId: number): Promise<CustomerWallet> {
  try {
    const res = await api.get<CustomerWallet>(`/admin/billing/customers/${customerId}/wallet`);
    return res.data;
  } catch (e) {
    normalize(e, 'GET', `/admin/billing/customers/${customerId}/wallet`);
  }
}

/** Top up an existing customer's wallet by `cents` (no plan change). */
export async function creditWallet(
  customerId: number,
  cents: number,
  note?: string,
): Promise<QuickProvisionResult> {
  try {
    const res = await api.post<QuickProvisionResult>('/admin/billing/quick-provision', {
      customer_id: customerId,
      wallet_credit_cents: cents,
      note: note ?? 'admin wallet top-up',
    });
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

export async function listInvoices(customerId: number): Promise<AdminInvoice[]> {
  try {
    const res = await api.get<AdminInvoice[]>('/admin/billing/invoices', {
      params: { customer_id: customerId, limit: 100 },
    });
    return res.data;
  } catch (e) {
    normalize(e, 'GET', '/admin/billing/invoices');
  }
}

// ---- Feature endpoints ----

export async function listFeatureRegistry(): Promise<AdminFeatureEntry[]> {
  try {
    const res = await api.get<AdminFeatureEntry[]>('/admin/features/features');
    return res.data;
  } catch (e) {
    normalize(e, 'GET', '/admin/features/features');
  }
}

export async function listCustomerFeatures(customerId: number): Promise<AdminCustomerFeature[]> {
  try {
    const res = await api.get<AdminCustomerFeature[]>(
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
  update: CustomerFeatureUpdate,
): Promise<AdminCustomerFeature> {
  try {
    const res = await api.put<AdminCustomerFeature>(
      `/admin/features/customers/${customerId}/features/${slug}`,
      update,
    );
    return res.data;
  } catch (e) {
    normalize(e, 'PUT', `/admin/features/customers/${customerId}/features/${slug}`);
  }
}

export async function listCustomerUsage(
  customerId: number,
): Promise<AdminFeatureUsageSummary[]> {
  try {
    const res = await api.get<AdminFeatureUsageSummary[]>(
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
