/**
 * UseCases — 3 buyer ICPs with concrete back-of-napkin numbers.
 *
 * Each card includes one quantitative claim grounded in the
 * playbook (docs/internal_sales_playbook.md) — leave the numbers
 * conservative so they're defensible in a sales call.
 */
import { Coins, Briefcase, Megaphone } from 'lucide-react';
import Reveal from '@/components/Reveal';
import { useT } from '@/i18n';

const toneClasses = {
  blue:   { ring: 'ring-brand-blue-500/20',   text: 'text-brand-blue-400',   wash: 'bg-brand-blue-500/[0.06]',   pill: 'bg-brand-blue-500/15 text-brand-blue-200' },
  purple: { ring: 'ring-brand-purple-500/20', text: 'text-brand-purple-400', wash: 'bg-brand-purple-500/[0.06]', pill: 'bg-brand-purple-500/15 text-brand-purple-200' },
} as const;

// Icon + tone are visual (code-side); textual content comes from i18n.
const VISUAL = [
  { icon: Coins,     tone: 'purple' as const },
  { icon: Briefcase, tone: 'blue'   as const },
  { icon: Megaphone, tone: 'blue'   as const },
];

export default function UseCases() {
  const t = useT();
  const cases = t.useCases.cards.map((c, i) => ({ ...c, ...VISUAL[i] }));
  return (
    <section className="bg-surface-1">
      <div className="max-w-container mx-auto px-6 py-24 lg:py-28">
        <Reveal>
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 text-eyebrow font-mono text-fg-muted uppercase">
              <span className="h-px w-8 bg-line-strong" />
              {t.useCases.eyebrow}
            </div>
            <h2 className="mt-4 font-display text-display-2 text-fg-primary">
              {t.useCases.title}
            </h2>
          </div>
        </Reveal>

        <div className="mt-12 grid md:grid-cols-3 gap-6">
          {cases.map((c, i) => {
            const Icon = c.icon;
            const tc = toneClasses[c.tone];
            return (
              <Reveal key={c.title} delay={i * 100}>
                <div className={`relative h-full p-7 rounded-2xl bg-brand-ink-900 border border-line-subtle ring-1 ${tc.ring} transition-all duration-200 ease-out hover:-translate-y-0.5 hover:border-line-strong overflow-hidden`}>
                  <div className={`absolute inset-0 ${tc.wash} pointer-events-none`} aria-hidden />
                  <div className="relative">
                    <Icon className={`w-7 h-7 mb-5 ${tc.text}`} />
                    <h3 className="font-display text-xl font-semibold text-fg-primary mb-3">
                      {c.title}
                    </h3>
                    <p className="text-fg-secondary text-sm leading-relaxed mb-6">
                      {c.blurb}
                    </p>
                    <div className={`inline-block rounded-full px-3 py-1 text-sm font-mono ${tc.pill}`}>
                      {c.metric}
                    </div>
                    <p className="mt-2 text-xs text-fg-muted font-mono">
                      {c.sub}
                    </p>
                  </div>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
