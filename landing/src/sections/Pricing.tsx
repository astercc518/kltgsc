/**
 * Pricing — 3 plans + per-action unit price table.
 *
 * Numbers from PROJECT_OVERVIEW.md §2 + customer.py PLAN_QUOTA. KEEP IN
 * SYNC. The featured tier (Growth) is the recommended one — same
 * weighting as the pitch deck.
 *
 * Bottom: a folding unit-price table covering all 7 wallet-charged
 * actions across both products.
 */
import { useState } from 'react';
import { ChevronDown } from 'lucide-react';
import PriceCard from '@/components/PriceCard';
import Reveal from '@/components/Reveal';
import { LINKS } from '@/lib/links';
import { useT } from '@/i18n';

// Unit-price table is intentionally code-only (not localized) — the
// labels translate but the numeric prices are USD anchors that shouldn't
// drift across languages.
const unitPrices = [
  { groupKey: 'self_serve', label: 'Group scrape',     unit: 'per member',  price: '$0.01' },
  { groupKey: 'self_serve', label: 'Bulk send',        unit: 'per message', price: '$0.10' },
  { groupKey: 'self_serve', label: 'Bulk invite',      unit: 'per invite',  price: '$0.05' },
  { groupKey: 'ai',         label: 'AI group reply',   unit: 'per reply',   price: '$0.05' },
  { groupKey: 'ai',         label: 'AI auto-lead',     unit: 'per lead',    price: '$0.50' },
  { groupKey: 'ai',         label: 'Sales lead view',  unit: 'per view',    price: '$0.10' },
  { groupKey: 'kb',         label: 'KB file embed',    unit: 'per MB',      price: '$0.20' },
];

export default function Pricing() {
  const [tableOpen, setTableOpen] = useState(false);
  const t = useT();

  const plans = [
    {
      tier: 'starter' as const,
      name: 'Starter',
      pricePerMonthUsd: 199,
      quotaLines: t.pricing.plans.starter.quotaLines,
      featureLines: t.pricing.plans.starter.features,
      ctaLabel: t.pricing.plans.starter.ctaLabel,
      ctaHref: `${LINKS.signUp}&plan=starter`,
    },
    {
      tier: 'growth' as const,
      name: 'Growth',
      pricePerMonthUsd: 299,
      featured: true,
      badge: t.pricing.mostPopular,
      quotaLines: t.pricing.plans.growth.quotaLines,
      featureLines: t.pricing.plans.growth.features,
      ctaLabel: t.pricing.plans.growth.ctaLabel,
      ctaHref: `${LINKS.signUp}&plan=growth`,
    },
    {
      tier: 'pro' as const,
      name: 'Pro',
      pricePerMonthUsd: 599,
      quotaLines: t.pricing.plans.pro.quotaLines,
      featureLines: t.pricing.plans.pro.features,
      ctaLabel: t.pricing.plans.pro.ctaLabel,
      ctaHref: `${LINKS.signUp}&plan=pro`,
    },
  ];
  return (
    <section id="pricing" className="bg-surface-1 scroll-mt-24">
      <div className="max-w-container mx-auto px-6 py-24 lg:py-32">
        <Reveal>
          <div className="text-center max-w-3xl mx-auto">
            <div className="inline-flex items-center gap-2 text-eyebrow font-mono text-fg-muted uppercase">
              <span className="h-px w-8 bg-line-strong" />
              {t.pricing.eyebrow}
              <span className="h-px w-8 bg-line-strong" />
            </div>
            <h2 className="mt-4 font-display text-display-2 text-fg-primary">
              {t.pricing.titlePart1}
              <br />
              <span className="text-fg-muted">{t.pricing.titlePart2}</span>
            </h2>
            <p className="mt-5 text-lg text-fg-secondary">
              {t.pricing.subtitle}
            </p>
          </div>
        </Reveal>

        {/* Tier grid */}
        <div className="mt-14 grid md:grid-cols-3 gap-6 items-stretch">
          {plans.map((p, i) => (
            <Reveal key={p.tier} delay={i * 100}>
              <PriceCard {...p} priceSuffix={t.pricing.perMonthUsdt} />
            </Reveal>
          ))}
        </div>

        {/* Foldable unit-price table */}
        <Reveal delay={200}>
          <div className="mt-14 max-w-3xl mx-auto rounded-2xl border border-line-subtle bg-brand-ink-900 overflow-hidden">
            <button
              type="button"
              className="w-full flex items-center justify-between gap-3 px-6 py-4 text-left transition-colors hover:bg-brand-ink-800"
              onClick={() => setTableOpen((v) => !v)}
              aria-expanded={tableOpen}
            >
              <div>
                <div className="font-display font-semibold text-fg-primary">
                  {t.pricing.tableTitle}
                </div>
                <div className="text-sm text-fg-muted">
                  {t.pricing.tableSubtitle}
                </div>
              </div>
              <ChevronDown
                className={`w-5 h-5 text-fg-muted shrink-0 transition-transform ${tableOpen ? 'rotate-180' : ''}`}
              />
            </button>
            {tableOpen && (
              <div className="border-t border-line-subtle">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-eyebrow font-mono text-fg-muted uppercase">
                      <th className="text-left px-6 py-3 font-semibold">{t.pricing.tableHeaders.product}</th>
                      <th className="text-left px-3 py-3 font-semibold">{t.pricing.tableHeaders.action}</th>
                      <th className="text-left px-3 py-3 font-semibold">{t.pricing.tableHeaders.unit}</th>
                      <th className="text-right px-6 py-3 font-semibold">{t.pricing.tableHeaders.price}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unitPrices.map((row) => (
                      <tr key={row.label} className="border-t border-line-subtle">
                        <td className="px-6 py-3 text-fg-muted">{row.groupKey === 'self_serve' ? t.hero.selfServe.tag : row.groupKey === 'ai' ? t.hero.aiAssistant.tag : 'KB'}</td>
                        <td className="px-3 py-3 text-fg-primary font-medium">{row.label}</td>
                        <td className="px-3 py-3 text-fg-muted font-mono text-[0.85rem]">{row.unit}</td>
                        <td className="px-6 py-3 text-right font-mono text-fg-primary">{row.price}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="px-6 py-3 bg-brand-ink-950 text-xs text-fg-muted">
                  {t.pricing.tableAdminNote.replace('billing docs', '')}
                  <a href={LINKS.docsBilling} className="text-brand-blue-500 underline underline-offset-2">billing docs</a>.
                </div>
              </div>
            )}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
