/**
 * ProductAIAssistant — deep-dive for 需求 2 (AI marketing assistant).
 *
 * 6-step closed-loop timeline (Listen → Recognize → Engage → Push →
 * Takeover → CRM), centred around the safety promise: "AI never auto-DMs."
 *
 * Visually distinct from ProductSelfServe by using the purple accent
 * and a dark surface — signals "this is the premium / subscription"
 * product without redundant copy.
 */
import {
  Ear, Brain, MessageCircleMore, Inbox, HandshakeIcon, BookOpenCheck,
  Shield,
} from 'lucide-react';
import Reveal from '@/components/Reveal';
import CTAButton from '@/components/CTAButton';
import BackgroundField from '@/components/BackgroundField';
import SectionLabel from '@/components/SectionLabel';
import { LINKS } from '@/lib/links';
import { Events } from '@/lib/analytics';
import { useT } from '@/i18n';

const STEP_ICONS = [Ear, Brain, MessageCircleMore, Inbox, HandshakeIcon, BookOpenCheck];

export default function ProductAIAssistant() {
  const t = useT();
  const steps = t.aiAssistant.steps.map((s, i) => ({
    ...s,
    icon: STEP_ICONS[i],
    highlight: i === 2, // "Engage" step gets the purple-glow card
  }));
  return (
    <section id="ai-assistant" className="bg-brand-ink-950 scroll-mt-24 relative overflow-hidden">
      <BackgroundField variant="section" />
      {/* Single purple glow — top center, tamed */}
      <div
        aria-hidden
        className="absolute -top-40 left-1/2 -translate-x-1/2 w-[700px] h-[500px] rounded-full bg-brand-purple-500 opacity-[0.08] blur-3xl pointer-events-none"
      />

      <div className="relative max-w-container mx-auto px-6 py-24 lg:py-32">
        <Reveal>
          <div className="max-w-3xl">
            <SectionLabel number="03" tone="dark">{t.aiAssistant.eyebrow}</SectionLabel>
            <h2 className="mt-5 font-display text-display-2 text-fg-primary tracking-tight text-balance">
              {t.aiAssistant.titleA}
              <span className="text-fg-muted"> {t.aiAssistant.titleB}</span>
            </h2>
            <p className="mt-5 text-lg text-fg-secondary leading-relaxed max-w-2xl">
              {t.aiAssistant.subtitle}
            </p>
          </div>
        </Reveal>

        {/* 6-step timeline grid */}
        <div className="mt-14 grid md:grid-cols-2 lg:grid-cols-3 gap-4">
          {steps.map((s, i) => (
            <Reveal key={s.title} delay={i * 80}>
              <div
                className={[
                  'group h-full rounded-2xl border p-6 transition-all duration-300',
                  s.highlight
                    ? 'border-brand-purple-500/35 bg-gradient-to-br from-brand-purple-500/[0.10] to-brand-purple-500/[0.02]'
                    : 'border-line-medium bg-surface-1/60 hover:border-line-strong hover:bg-surface-2/70 hover:-translate-y-0.5',
                ].join(' ')}
                style={s.highlight ? { boxShadow: '0 0 0 1px rgba(168,85,247,0.18), 0 18px 36px -12px rgba(168,85,247,0.25)' } : undefined}
              >
                <div className="flex items-center gap-3 mb-5">
                  <span
                    className="font-mono text-[0.78rem] font-medium text-fg-muted"
                    style={{ fontVariantNumeric: 'tabular-nums' }}
                  >
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <span className="h-px flex-1 bg-line-subtle" aria-hidden />
                  <div className={`inline-flex items-center justify-center w-10 h-10 rounded-xl ${s.highlight ? 'bg-brand-purple-500/20 text-brand-purple-200' : 'bg-surface-2 text-fg-secondary group-hover:text-fg-primary transition-colors'}`}>
                    <s.icon className="w-5 h-5" />
                  </div>
                </div>
                <h3 className="font-display text-xl font-semibold text-fg-primary mb-2 tracking-tight">
                  {s.title}
                </h3>
                <p className="text-sm text-fg-secondary leading-relaxed">
                  {s.desc}
                </p>
              </div>
            </Reveal>
          ))}
        </div>

        {/* Safety wall — the most important contract */}
        <Reveal delay={200}>
          <div
            className="mt-16 rounded-3xl border border-brand-purple-500/25 bg-gradient-to-br from-brand-purple-500/[0.08] to-transparent p-6 lg:p-10 relative overflow-hidden"
          >
            {/* Decorative hairline accent */}
            <div className="absolute inset-x-10 top-0 h-px bg-gradient-to-r from-brand-purple-500/60 via-brand-purple-300/40 to-transparent" />
            <div className="flex items-start gap-5">
              <div className="shrink-0 w-12 h-12 rounded-xl bg-brand-purple-500/20 ring-1 ring-brand-purple-500/30 inline-flex items-center justify-center">
                <Shield className="w-6 h-6 text-brand-purple-200" />
              </div>
              <div className="flex-1">
                <h3 className="font-display text-xl font-semibold text-fg-primary mb-2 tracking-tight">
                  {t.aiAssistant.safetyTitle}
                </h3>
                <p className="text-fg-secondary leading-relaxed">
                  {t.aiAssistant.safetyDesc}
                </p>
                <p className="mt-3 text-sm text-fg-muted">
                  {t.aiAssistant.safetyWhy}{' '}
                  <a href={LINKS.docsBilling} className="text-brand-purple-200 hover:text-brand-purple-100 underline underline-offset-4 decoration-brand-purple-500/40 hover:decoration-brand-purple-300">
                    {t.aiAssistant.safetyLink}
                  </a>
                </p>
              </div>
            </div>
          </div>
        </Reveal>

        {/* CTA strip — single primary CTA. "Ask sales" lives in hero + FinalCTA
            already, no need to duplicate here. */}
        <div className="mt-12 flex flex-wrap items-center justify-between gap-6 rounded-2xl border border-line-medium bg-surface-1/70 px-7 py-5">
          <p className="text-fg-secondary">
            {t.aiAssistant.stripText}
            <span className="text-fg-muted"> {t.aiAssistant.stripQuiet}</span>
          </p>
          <CTAButton
            variant="primary"
            href="#pricing"
            trackEvent={Events.CTA_SIGNUP_CLICK}
            trackProps={{ source: 'ai_strip' }}
          >
            {t.aiAssistant.stripSeePlans}
          </CTAButton>
        </div>
      </div>
    </section>
  );
}
