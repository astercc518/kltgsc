/**
 * TrustBar — 5 credibility metrics under the hero.
 *
 * Uses AnimatedNumber for the integer stats so they count up when the
 * row scrolls into view. Strings come from real product caps:
 *   - 1000+ accounts per customer       (PROJECT_OVERVIEW.md §2)
 *   - 5 listener shards in prod         (project_capacity_plan.md)
 *   - Vertex Gemini RAG                 (project_gemini_on_vertex.md)
 *   - 99.9% uptime SLA                  (operational target)
 *   - USDT billing                      (project_payment_decision.md)
 */
import AnimatedNumber from '@/components/AnimatedNumber';
import Reveal from '@/components/Reveal';
import { useT } from '@/i18n';

export default function TrustBar() {
  const t = useT();
  const stats = [
    { value: 1000, suffix: '+',   label: t.trustBar.accounts, format: (n: number) => Math.round(n).toLocaleString() },
    { value: 5,    suffix: '',    label: t.trustBar.shards },
    { value: 768,  suffix: '-dim', label: t.trustBar.rag },
    { value: 99.9, suffix: '%',   label: t.trustBar.uptime,   format: (n: number) => n.toFixed(1) },
  ];
  return (
    <section
      aria-label="Trust signals"
      className="bg-brand-ink-950 border-y border-line-subtle"
    >
      <div className="max-w-container mx-auto px-6 py-12">
        <Reveal>
          <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 gap-x-8 gap-y-8">
            {stats.map((s, i) => (
              <div key={i} className="text-center md:text-left">
                <div className="font-mono text-3xl md:text-4xl text-fg-primary font-semibold tracking-tight">
                  <AnimatedNumber
                    value={s.value}
                    suffix={s.suffix}
                    format={s.format}
                  />
                </div>
                <div className="mt-1 text-xs uppercase tracking-wider text-fg-muted">
                  {s.label}
                </div>
              </div>
            ))}
            {/* Fifth slot doubles as the "billing" callout — non-numeric */}
            <div className="text-center md:text-left col-span-2 md:col-span-1">
              <div className="font-mono text-3xl md:text-4xl text-fg-primary font-semibold tracking-tight">
                USDT
              </div>
              <div className="mt-1 text-xs uppercase tracking-wider text-fg-muted">
                {t.trustBar.networks}
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
