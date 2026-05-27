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

  // Featured tier gets a real glow stack (no "border-2 + shadow" which fights
  // browser kerning); non-featured uses a hairline + card shadow that lifts
  // a hair on hover.
  const wrapperClasses = featured
    ? 'relative bg-white shadow-glow-purple'
    : 'relative bg-white border border-brand-ink-200 shadow-card hover:shadow-card-hover hover:-translate-y-0.5 transition-all duration-300';

  return (
    <div className={['rounded-3xl p-7 lg:p-8 flex flex-col', wrapperClasses, className || ''].join(' ')}>
      {featured && (
        <span className="absolute -top-3 left-1/2 -translate-x-1/2 inline-flex items-center gap-1 rounded-full bg-gradient-to-b from-brand-purple-400 to-brand-purple-600 px-3 py-1 text-[0.7rem] font-medium uppercase tracking-[0.12em] text-white shadow-[0_4px_12px_rgba(168,85,247,0.35)]">
          {badge ?? 'Most Popular'}
        </span>
      )}

      <h3 className="font-display text-2xl font-semibold text-brand-ink-900 mb-5 tracking-tight">
        {name}
      </h3>

      <div className="flex items-end gap-2 mb-6">
        <span
          className="font-display text-[3.25rem] leading-[0.95] font-bold text-brand-ink-900 tracking-tight"
          style={{ fontVariantNumeric: 'tabular-nums' }}
        >
          ${dollars}
        </span>
        <span className="text-brand-ink-500 text-xs font-mono pb-1.5 whitespace-nowrap">
          {priceSuffix ?? '/ mo · USDT'}
        </span>
      </div>

      <ul className="space-y-2 mb-6 text-sm text-brand-ink-700">
        {quotaLines.map((q, i) => (
          <li
            key={i}
            className="font-mono text-[0.82rem] text-brand-ink-600"
            style={{ fontVariantNumeric: 'tabular-nums slashed-zero' }}
          >
            {q}
          </li>
        ))}
      </ul>

      <div className="h-px bg-brand-ink-100 mb-5" />

      <ul className="space-y-2.5 mb-7 text-sm text-brand-ink-700 flex-1">
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
          'block w-full text-center rounded-full px-5 py-3 font-medium transition-all duration-200 ease-out',
          featured
            ? 'bg-gradient-to-b from-brand-purple-400 to-brand-purple-600 text-white hover:from-brand-purple-300 hover:to-brand-purple-500 hover:-translate-y-px shadow-[0_4px_16px_rgba(168,85,247,0.30)]'
            : 'bg-brand-ink-900 text-white hover:bg-brand-ink-700 hover:-translate-y-px',
        ].join(' ')}
      >
        {ctaLabel}
      </a>
    </div>
  );
}
