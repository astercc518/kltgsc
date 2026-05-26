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
    <section id="pricing" className="bg-brand-ink-50 scroll-mt-24">
      <div className="max-w-container mx-auto px-6 py-24 lg:py-32">
        <Reveal>
          <div className="text-center max-w-3xl mx-auto">
            <div className="inline-flex items-center gap-2 text-eyebrow font-mono text-brand-ink-500 uppercase">
              <span className="h-px w-8 bg-brand-ink-300" />
              {t.pricing.eyebrow}
              <span className="h-px w-8 bg-brand-ink-300" />
            </div>
            <h2 className="mt-4 font-display text-display-2 text-brand-ink-900">
              {t.pricing.titlePart1}
              <br />
              <span className="text-brand-ink-500">{t.pricing.titlePart2}</span>
            </h2>
            <p className="mt-5 text-lg text-brand-ink-600">
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
          <div className="mt-14 max-w-3xl mx-auto rounded-2xl border border-brand-ink-200 bg-white overflow-hidden">
            <button
              type="button"
              className="w-full flex items-center justify-between gap-3 px-6 py-4 text-left transition-colors hover:bg-brand-ink-50"
              onClick={() => setTableOpen((v) => !v)}
              aria-expanded={tableOpen}
            >
              <div>
                <div className="font-display font-semibold text-brand-ink-900">
                  {t.pricing.tableTitle}
                </div>
                <div className="text-sm text-brand-ink-500">
                  {t.pricing.tableSubtitle}
                </div>
              </div>
              <ChevronDown
                className={`w-5 h-5 text-brand-ink-500 shrink-0 transition-transform ${tableOpen ? 'rotate-180' : ''}`}
              />
            </button>
            {tableOpen && (
              <div className="border-t border-brand-ink-100">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="text-eyebrow font-mono text-brand-ink-500 uppercase">
                      <th className="text-left px-6 py-3 font-semibold">{t.pricing.tableHeaders.product}</th>
                      <th className="text-left px-3 py-3 font-semibold">{t.pricing.tableHeaders.action}</th>
                      <th className="text-left px-3 py-3 font-semibold">{t.pricing.tableHeaders.unit}</th>
                      <th className="text-right px-6 py-3 font-semibold">{t.pricing.tableHeaders.price}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unitPrices.map((row) => (
                      <tr key={row.label} className="border-t border-brand-ink-50">
                        <td className="px-6 py-3 text-brand-ink-500">{row.groupKey === 'self_serve' ? t.hero.selfServe.tag : row.groupKey === 'ai' ? t.hero.aiAssistant.tag : 'KB'}</td>
                        <td className="px-3 py-3 text-brand-ink-900 font-medium">{row.label}</td>
                        <td className="px-3 py-3 text-brand-ink-500 font-mono text-[0.85rem]">{row.unit}</td>
                        <td className="px-6 py-3 text-right font-mono text-brand-ink-900">{row.price}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div data-testid="pricing-table-admin-note" className="px-6 py-3 bg-brand-ink-50 text-xs text-brand-ink-500">
                  {t.pricing.tableAdminNote.before}
                  <a href={LINKS.docsBilling} className="text-brand-blue-500 underline underline-offset-2">{t.pricing.tableAdminNote.linkLabel}</a>
                  {t.pricing.tableAdminNote.after}
                </div>
              </div>
            )}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
