/**
 * Sales workbench token storage — separate from customer + admin so all
 * three identities can be open in the same browser. Token is the JWT
 * issued by POST /api/v1/auth/login when identifier resolves to a
 * CustomerUser or to a User with role='sales'.
 */
const STORAGE_KEY = 'tg1_sales_token';

export function getSalesToken(): string | null {
  return localStorage.getItem(STORAGE_KEY);
}

export function setSalesToken(token: string): void {
  localStorage.setItem(STORAGE_KEY, token);
}

export function clearSalesToken(): void {
  localStorage.removeItem(STORAGE_KEY);
}

export function isSalesAuthenticated(): boolean {
  return !!getSalesToken();
}

export function logoutSales(redirectTo: string = '/login'): void {
  clearSalesToken();
  window.location.href = redirectTo;
}
