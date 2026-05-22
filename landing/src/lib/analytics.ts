/**
 * Plausible analytics wrapper.
 *
 * Initialized once from main.tsx via `initAnalytics()`.  All conversion
 * tracking should go through `track(event, props)` — never call the
 * underlying tracker directly so we can swap providers later.
 *
 * Configuration via Vite env (set at build time, never at runtime):
 *   VITE_PLAUSIBLE_DOMAIN     domain registered in Plausible (e.g. tg1.ai)
 *   VITE_PLAUSIBLE_API_HOST   optional self-hosted endpoint
 *
 * If VITE_PLAUSIBLE_DOMAIN is unset (dev / preview), the wrapper turns
 * into a no-op — calls still type-check, no requests fire.
 */
import Plausible from 'plausible-tracker';

type EventProps = Record<string, string | number | boolean>;

let tracker: ReturnType<typeof Plausible> | null = null;
let enabled = false;

export function initAnalytics() {
  const domain = import.meta.env.VITE_PLAUSIBLE_DOMAIN as string | undefined;
  if (!domain) {
    enabled = false;
    return;
  }
  tracker = Plausible({
    domain,
    apiHost: (import.meta.env.VITE_PLAUSIBLE_API_HOST as string | undefined) || 'https://plausible.io',
    trackLocalhost: false,
  });
  enabled = true;
  // First pageview + auto pageview tracking on history change.
  tracker.enableAutoPageviews();
}

/** Conversion event. Use snake_case names; props get sent as Plausible
 *  custom properties (visible on the dashboard's per-event breakdown). */
export function track(event: string, props?: EventProps) {
  if (!enabled || !tracker) return;
  tracker.trackEvent(event, { props });
}

/** Canonical conversion events — keep this list in sync with the
 *  Plausible dashboard goals. */
export const Events = {
  CTA_SIGNUP_CLICK:   'cta_signup_click',
  CTA_DEMO_CLICK:     'cta_demo_click',
  CTA_TG_SALES_CLICK: 'cta_tg_sales_click',
  PRICING_CALC_USED:  'pricing_calculator_used',
  LANG_SWITCH:        'lang_switch',
} as const;

export type AnalyticsEvent = (typeof Events)[keyof typeof Events];
