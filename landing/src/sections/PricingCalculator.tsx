/**
 * PricingCalculator — "what would I actually pay?" interactive estimator.
 *
 * Two sliders:
 *   1. expected monthly auto-leads (AI marketing)
 *   2. expected monthly bulk-send volume (self-serve)
 *
 * Computes the total monthly bill across all 3 plans, highlights the
 * cheapest tier, fires `pricing_calculator_used` to Plausible.
 */
import { useEffect, useMemo, useState } from 'react';
import Reveal from '@/components/Reveal';
import { track, Events } from '@/lib/analytics';
import { useT } from '@/i18n';

// Single source of truth — matches Pricing.tsx + alembic seed.
const UNIT = {
  AI_REPLY_CENTS: 5,
  AI_LEAD_CENTS: 50,
  BULK_SEND_CENTS: 10,
} as const;

const PLANS = [
  { code: 'starter', label: 'Starter', monthlyUsd: 199 },
  { code: 'growth',  label: 'Growth',  monthlyUsd: 299 },
  { code: 'pro',     label: 'Pro',     monthlyUsd: 599 },
];

export default function PricingCalculator() {
  const t = useT();
  const [leads, setLeads]   = useState(50);
  const [sends, setSends]   = useState(500);
  const [tracked, setTracked] = useState(false);

  // Repeating multi-touch: 1 lead ≈ 3 AI group replies (rough heuristic).
  const repliesEstimate = leads * 3;

  const variableMonthlyCents =
    repliesEstimate * UNIT.AI_REPLY_CENTS +
    leads * UNIT.AI_LEAD_CENTS +
    sends * UNIT.BULK_SEND_CENTS;

  const variableUsd = variableMonthlyCents / 100;

  const planTotals = useMemo(() =>
    PLANS.map((p) => ({ ...p, totalUsd: p.monthlyUsd + variableUsd })),
    [variableUsd],
  );
  const cheapest = planTotals.reduce((a, b) => (a.totalUsd < b.totalUsd ? a : b));

  // Fire analytics once per interaction session (debounced).
  useEffect(() => {
    if (tracked) return;
    const t = setTimeout(() => {
      track(Events.PRICING_CALC_USED, { leads, sends });
      setTracked(true);
    }, 1200);
    return () => clearTimeout(t);
  }, [leads, sends, tracked]);

  return (
    <section className="bg-white">
      <div className="max-w-container mx-auto px-6 py-20 lg:py-28">
        <Reveal>
          <div className="max-w-3xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 text-eyebrow font-mono text-brand-purple-500 uppercase">
              <span className="h-px w-8 bg-brand-purple-500" />
              {t.pricingCalc.eyebrow}
              <span className="h-px w-8 bg-brand-purple-500" />
            </div>
            <h2 className="mt-4 font-display text-display-3 text-brand-ink-900">
              {t.pricingCalc.title}
            </h2>
            <p className="mt-3 text-brand-ink-600">
              {t.pricingCalc.subtitle}
            </p>
          </div>
        </Reveal>

        <Reveal delay={120}>
          <div className="mt-12 max-w-3xl mx-auto rounded-3xl border border-brand-ink-200 bg-brand-ink-50 p-6 lg:p-8">
            {/* Sliders */}
            <Slider
              label={t.pricingCalc.leadsLabel}
              tone="purple"
              value={leads}
              min={0} max={500} step={10}
              suffix={t.pricingCalc.leadsSuffix}
              onChange={setLeads}
            />
            <Slider
              label={t.pricingCalc.sendsLabel}
              tone="blue"
              value={sends}
              min={0} max={10000} step={100}
              suffix={t.pricingCalc.sendsSuffix}
              onChange={setSends}
            />

            {/* Variable preview line */}
            <div className="mt-6 rounded-xl bg-white border border-brand-ink-100 px-5 py-4">
              <div className="text-eyebrow font-mono text-brand-ink-500 uppercase mb-2">
                {t.pricingCalc.walletCostHeader}
              </div>
              <div className="grid sm:grid-cols-3 gap-3 text-sm">
                <Line label={t.pricingCalc.aiRepliesLine} qty={repliesEstimate} priceCents={UNIT.AI_REPLY_CENTS} />
                <Line label={t.pricingCalc.aiLeadsLine}   qty={leads}            priceCents={UNIT.AI_LEAD_CENTS} />
                <Line label={t.pricingCalc.bulkSendLine}  qty={sends}            priceCents={UNIT.BULK_SEND_CENTS} />
              </div>
              <div className="mt-4 pt-3 border-t border-brand-ink-100 flex items-baseline justify-between">
                <span className="text-brand-ink-500 text-sm">{t.pricingCalc.totalLabel}</span>
                <span className="font-mono text-2xl font-semibold text-brand-ink-900">
                  ${variableUsd.toFixed(2)}
                </span>
              </div>
            </div>

            {/* Plan totals */}
            <div className="mt-5 grid sm:grid-cols-3 gap-3">
              {planTotals.map((p) => {
                const isCheap = p.code === cheapest.code;
                return (
                  <div
                    key={p.code}
                    className={[
                      'rounded-xl p-4 border transition-all',
                      isCheap
                        ? 'border-brand-purple-500 bg-white shadow-glow-purple'
                        : 'border-brand-ink-200 bg-white',
                    ].join(' ')}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className="font-display font-semibold text-brand-ink-900">{p.label}</span>
                      {isCheap && (
                        <span className="text-eyebrow font-mono text-brand-purple-500 uppercase">{t.pricingCalc.bestBadge}</span>
                      )}
                    </div>
                    <div className="text-brand-ink-400 text-xs font-mono mb-2">
                      ${p.monthlyUsd} {t.pricingCalc.subPlanLabel} · ${variableUsd.toFixed(0)} {t.pricingCalc.walletPlanLabel}
                    </div>
                    <div className="font-mono text-2xl font-semibold text-brand-ink-900">
                      ${p.totalUsd.toFixed(2)}<span className="text-sm text-brand-ink-400">{t.pricingCalc.perMo}</span>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}

function Slider({
  label, tone, value, min, max, step, suffix, onChange,
}: {
  label: string; tone: 'blue' | 'purple'; value: number;
  min: number; max: number; step: number; suffix: string;
  onChange: (v: number) => void;
}) {
  const accent = tone === 'blue' ? 'accent-brand-blue-500' : 'accent-brand-purple-500';
  return (
    <div className="mb-5">
      <div className="flex items-baseline justify-between mb-2">
        <label className="text-sm font-medium text-brand-ink-700">{label}</label>
        <span className="font-mono text-brand-ink-900 text-base">
          {value.toLocaleString()}{suffix}
        </span>
      </div>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
        className={`w-full ${accent}`}
      />
    </div>
  );
}

function Line({ label, qty, priceCents }: { label: string; qty: number; priceCents: number }) {
  return (
    <div>
      <div className="text-brand-ink-500">{label}</div>
      <div className="font-mono text-brand-ink-900">
        {qty.toLocaleString()} × ${(priceCents / 100).toFixed(2)} ={' '}
        <span className="font-semibold">${((qty * priceCents) / 100).toFixed(2)}</span>
      </div>
    </div>
  );
}
