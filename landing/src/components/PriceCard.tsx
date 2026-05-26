/**
 * PriceCard — one tier in the pricing grid.
 *
 * Each tier has:
 *   - tier code (starter / growth / pro) used for accent + URL params
 *   - display name + monthly USD price
 *   - quota list (account / group / token / seat)
 *   - feature highlights (3–5 lines)
 *   - primary CTA href (registers + carries `plan` query)
 *
 * The "Growth" tier is marked `featured` and gets the purple gradient
 * border + "Most Popular" eyebrow.
 *
 * Numbers come from /var/tgsc/backend/app/models/customer.py PLAN_QUOTA —
 * KEEP IN SYNC.
 */
import { Check } from 'lucide-react';
import type { ReactNode } from 'react';
import { track, Events } from '@/lib/analytics';

type TierCode = 'starter' | 'growth' | 'pro';

type Props = {
  tier: TierCode;
  name: string;
  pricePerMonthUsd: number;
  /** Suffix shown right of the price. Override for i18n; defaults to "/ month · USDT". */
  priceSuffix?: string;
  quotaLines: string[];        // 3-4 lines like "5 TG 账号", "1,000 群配额"
  featureLines: string[];      // 4-6 short feature highlights
  ctaLabel: string;
  ctaHref: string;
  featured?: boolean;
  /** Featured-tier ribbon label. Defaults to "Most Popular". */
  badge?: ReactNode;
  className?: string;
};

export default function PriceCard({
  tier, name, pricePerMonthUsd, priceSuffix, quotaLines, featureLines,
  ctaLabel, ctaHref, featured, badge, className,
}: Props) {
  const dollars = pricePerMonthUsd.toFixed(0);

  const wrapperClasses = featured
    ? 'relative bg-brand-ink-900 border-2 border-brand-purple-500 shadow-glow-purple transition-transform duration-200 ease-out hover:-translate-y-0.5'
    : 'relative bg-brand-ink-900 border border-line-subtle hover:border-line-strong transition-all duration-200 ease-out hover:-translate-y-0.5';

  return (
    <div className={['rounded-3xl p-7 flex flex-col', wrapperClasses, className || ''].join(' ')}>
      {featured && (
        <div className="absolute -top-3 left-1/2 -translate-x-1/2 inline-flex items-center gap-1 rounded-full bg-brand-purple-500 px-3 py-1 text-xs font-medium text-white">
          {badge ?? 'Most Popular'}
        </div>
      )}

      <div className="text-eyebrow text-fg-muted font-mono uppercase">
        {tier}
      </div>
      <h3 className="font-display text-2xl font-semibold text-fg-primary mt-1 mb-4">
        {name}
      </h3>

      <div className="flex items-baseline gap-1 mb-6">
        <span className="font-mono text-5xl font-bold text-fg-primary">${dollars}</span>
        <span className="text-fg-muted text-sm">{priceSuffix ?? '/ month · USDT'}</span>
      </div>

      <ul className="space-y-2 mb-6 text-sm text-fg-secondary">
        {quotaLines.map((q, i) => (
          <li key={i} className="font-mono text-[0.85rem]">{q}</li>
        ))}
      </ul>

      <div className="h-px bg-line-subtle mb-5" />

      <ul className="space-y-2.5 mb-7 text-sm text-fg-secondary flex-1">
        {featureLines.map((f, i) => (
          <li key={i} className="flex items-start gap-2.5">
            <Check className={`w-4 h-4 mt-0.5 shrink-0 ${featured ? 'text-brand-purple-500' : 'text-brand-blue-500'}`} aria-hidden />
            <span>{f}</span>
          </li>
        ))}
      </ul>

      <a
        href={ctaHref}
        onClick={() => track(Events.CTA_SIGNUP_CLICK, { tier })}
        className={[
          'block w-full text-center rounded-full px-5 py-3 font-medium transition-all',
          featured
            ? 'bg-brand-purple-500 text-white hover:bg-brand-purple-600'
            : 'border border-line-strong text-fg-primary hover:bg-brand-ink-800',
        ].join(' ')}
      >
        {ctaLabel}
      </a>
    </div>
  );
}
