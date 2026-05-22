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

const plans = [
  {
    tier: 'starter' as const,
    name: 'Starter',
    pricePerMonthUsd: 199,
    quotaLines: [
      '3 TG accounts',
      '500 target groups',
      '2M LLM tokens / mo',
      '1 sales seat',
    ],
    featureLines: [
      'AI marketing assistant included',
      'Customer KB upload + RAG',
      'Wallet pay-as-you-go ops',
      'USDT-only billing',
      'Email support, 24h SLA',
    ],
    ctaLabel: 'Start with Starter',
    ctaHref: `${LINKS.signUp}&plan=starter`,
  },
  {
    tier: 'growth' as const,
    name: 'Growth',
    pricePerMonthUsd: 299,
    featured: true,
    quotaLines: [
      '5 TG accounts',
      '1,000 target groups',
      '5M LLM tokens / mo',
      '3 sales seats',
    ],
    featureLines: [
      'Everything in Starter',
      'Priority listener shard',
      'Lead pre-assign + claim race-safe',
      'Auto-pause + low-balance Slack alerts',
      'Email + Telegram support, 12h SLA',
    ],
    ctaLabel: 'Pick Growth',
    ctaHref: `${LINKS.signUp}&plan=growth`,
  },
  {
    tier: 'pro' as const,
    name: 'Pro',
    pricePerMonthUsd: 599,
    quotaLines: [
      '10 TG accounts',
      '3,000 target groups',
      '15M LLM tokens / mo',
      '10 sales seats',
    ],
    featureLines: [
      'Everything in Growth',
      'Dedicated success engineer',
      'SSO + audit log export',
      'Custom feature pricing',
      '99.9% SLA, 4h response',
    ],
    ctaLabel: 'Go Pro',
    ctaHref: `${LINKS.signUp}&plan=pro`,
  },
];

const unitPrices = [
  { group: 'Self-Serve', label: 'Group scrape',         unit: 'per member',  price: '$0.01' },
  { group: 'Self-Serve', label: 'Bulk send',            unit: 'per message', price: '$0.10' },
  { group: 'Self-Serve', label: 'Bulk invite',          unit: 'per invite',  price: '$0.05' },
  { group: 'AI Assistant', label: 'AI group reply',     unit: 'per reply',   price: '$0.05' },
  { group: 'AI Assistant', label: 'AI auto-lead',       unit: 'per lead',    price: '$0.50' },
  { group: 'AI Assistant', label: 'Sales lead view',    unit: 'per view',    price: '$0.10' },
  { group: 'KB', label: 'KB file embed',                unit: 'per MB',      price: '$0.20' },
];

export default function Pricing() {
  const [tableOpen, setTableOpen] = useState(false);
  return (
    <section id="pricing" className="bg-brand-ink-50 scroll-mt-24">
      <div className="max-w-container mx-auto px-6 py-24 lg:py-32">
        <Reveal>
          <div className="text-center max-w-3xl mx-auto">
            <div className="inline-flex items-center gap-2 text-eyebrow font-mono text-brand-ink-500 uppercase">
              <span className="h-px w-8 bg-brand-ink-300" />
              Pricing
              <span className="h-px w-8 bg-brand-ink-300" />
            </div>
            <h2 className="mt-4 font-display text-display-2 text-brand-ink-900">
              Subscription unlocks the platform.
              <br />
              <span className="text-brand-ink-500">Wallet meters the ops.</span>
            </h2>
            <p className="mt-5 text-lg text-brand-ink-600">
              Both products billed in USDT. Subscription is the recurring infrastructure cost
              (accounts, groups, tokens, seats). Bulk ops + AI replies are pay-as-you-go on top.
            </p>
          </div>
        </Reveal>

        {/* Tier grid */}
        <div className="mt-14 grid md:grid-cols-3 gap-6 items-stretch">
          {plans.map((p, i) => (
            <Reveal key={p.tier} delay={i * 100}>
              <PriceCard {...p} />
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
                  Full unit price table
                </div>
                <div className="text-sm text-brand-ink-500">
                  Every wallet-charged action, single source of truth.
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
                      <th className="text-left px-6 py-3 font-semibold">Product</th>
                      <th className="text-left px-3 py-3 font-semibold">Action</th>
                      <th className="text-left px-3 py-3 font-semibold">Billed as</th>
                      <th className="text-right px-6 py-3 font-semibold">Default</th>
                    </tr>
                  </thead>
                  <tbody>
                    {unitPrices.map((row) => (
                      <tr key={row.label} className="border-t border-brand-ink-50">
                        <td className="px-6 py-3 text-brand-ink-500">{row.group}</td>
                        <td className="px-3 py-3 text-brand-ink-900 font-medium">{row.label}</td>
                        <td className="px-3 py-3 text-brand-ink-500 font-mono text-[0.85rem]">{row.unit}</td>
                        <td className="px-6 py-3 text-right font-mono text-brand-ink-900">{row.price}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <div className="px-6 py-3 bg-brand-ink-50 text-xs text-brand-ink-500">
                  Admin can override any line per-customer for volume deals. See{' '}
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
