/**
 * Customer portal token storage — kept under a separate localStorage key
 * from the admin app's `token`, so the two sessions can coexist in the
 * same browser without stepping on each other.
 */
const STORAGE_KEY = 'tg1_customer_token';

export function getCustomerToken(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function setCustomerToken(token: string): void {
  localStorage.setItem(STORAGE_KEY, token);
}

export function clearCustomerToken(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function isCustomerAuthenticated(): boolean {
  return !!getCustomerToken();
}

export function logoutCustomer(redirectTo: string = '/portal/login'): void {
  clearCustomerToken();
  window.location.href = redirectTo;
}
