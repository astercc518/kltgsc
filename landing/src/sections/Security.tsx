/**
 * Security — 4 enterprise concerns + the AI boundary promise.
 *
 * The "AI never DMs" wall is repeated here on purpose — it's the
 * single most-asked-about safety contract, and it deserves to be in
 * the security section, not just buried in the AI Assistant card.
 */
import { Lock, FileSearch, KeyRound, Wallet, Shield } from 'lucide-react';
import Reveal from '@/components/Reveal';
import { useT } from '@/i18n';

const PILLAR_ICONS = [Lock, FileSearch, KeyRound, Wallet];

export default function Security() {
  const t = useT();
  const pillars = t.security.pillars.map((p, i) => ({ ...p, icon: PILLAR_ICONS[i] }));
  return (
    <section className="bg-surface-1">
      <div className="max-w-container mx-auto px-6 py-24 lg:py-28">
        <Reveal>
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 text-eyebrow font-mono text-fg-muted uppercase">
              <span className="h-px w-8 bg-line-strong" />
              {t.security.eyebrow}
            </div>
            <h2 className="mt-4 font-display text-display-2 text-fg-primary">
              {t.security.title}
            </h2>
          </div>
        </Reveal>

        <div className="mt-12 grid md:grid-cols-2 lg:grid-cols-4 gap-5">
          {pillars.map((p, i) => (
            <Reveal key={p.title} delay={i * 80}>
              <div className="h-full p-6 rounded-2xl bg-brand-ink-900 border border-line-subtle">
                <p.icon className="w-6 h-6 text-fg-secondary mb-4" />
                <h3 className="font-display font-semibold text-fg-primary mb-2">{p.title}</h3>
                <p className="text-sm text-fg-secondary leading-relaxed">{p.desc}</p>
              </div>
            </Reveal>
          ))}
        </div>

        {/* The AI boundary wall — repeated promise */}
        <Reveal delay={250}>
          <div className="mt-12 rounded-3xl bg-brand-ink-950 border border-line-subtle text-fg-primary p-8 lg:p-10 flex flex-col lg:flex-row items-start gap-6">
            <div className="shrink-0 w-12 h-12 rounded-xl bg-brand-purple-500/20 inline-flex items-center justify-center">
              <Shield className="w-6 h-6 text-brand-purple-300" />
            </div>
            <div className="flex-1">
              <h3 className="font-display text-2xl font-semibold mb-2">
                {t.security.contractTitle}
              </h3>
              <ul className="space-y-3 text-fg-secondary leading-relaxed">
                <li className="flex gap-3">
                  <span className="font-mono text-brand-purple-300 shrink-0">1.</span>
                  <span>{t.security.contract1}</span>
                </li>
                <li className="flex gap-3">
                  <span className="font-mono text-brand-purple-300 shrink-0">2.</span>
                  <span>{t.security.contract2}</span>
                </li>
              </ul>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
