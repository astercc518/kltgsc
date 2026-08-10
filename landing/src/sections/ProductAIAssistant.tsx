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
      {/* Subtle purple glow at the top */}
      <div className="absolute -top-32 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-brand-purple-500 opacity-10 blur-3xl pointer-events-none" />

      <div className="relative max-w-container mx-auto px-6 py-24 lg:py-32">
        <Reveal>
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 text-eyebrow font-mono text-brand-purple-400 uppercase">
              <span className="h-px w-8 bg-brand-purple-500" />
              {t.aiAssistant.eyebrow}
            </div>
            <h2 className="mt-4 font-display text-display-2 text-fg-primary">
              {t.aiAssistant.titleA}
              <span className="text-fg-muted"> {t.aiAssistant.titleB}</span>
            </h2>
            <p className="mt-5 text-lg text-fg-secondary leading-relaxed">
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
                  'h-full rounded-2xl border p-6 transition-all',
                  s.highlight
                    ? 'border-brand-purple-500/40 bg-brand-purple-500/[0.08] shadow-glow-purple'
                    : 'border-line-subtle bg-brand-ink-900 hover:border-line-strong hover:bg-brand-ink-800',
                ].join(' ')}
              >
                <div className="flex items-center gap-3 mb-4">
                  <span className="font-mono text-eyebrow text-fg-muted">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <div className={`inline-flex items-center justify-center w-10 h-10 rounded-xl ${s.highlight ? 'bg-brand-purple-500/20 text-brand-purple-300' : 'bg-brand-ink-800 text-fg-secondary'}`}>
                    <s.icon className="w-5 h-5" />
                  </div>
                </div>
                <h3 className="font-display text-xl font-semibold text-fg-primary mb-2">
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
          <div className="mt-14 rounded-2xl border border-brand-purple-500/30 bg-gradient-to-br from-brand-purple-500/10 to-transparent p-6 lg:p-8">
            <div className="flex items-start gap-5">
              <div className="shrink-0 w-12 h-12 rounded-xl bg-brand-purple-500/20 inline-flex items-center justify-center">
                <Shield className="w-6 h-6 text-brand-purple-300" />
              </div>
              <div className="flex-1">
                <h3 className="font-display text-xl font-semibold text-fg-primary mb-2">
                  {t.aiAssistant.safetyTitle}
                </h3>
                <p className="text-fg-secondary leading-relaxed">
                  {t.aiAssistant.safetyDesc}
                </p>
                <p className="mt-3 text-sm text-fg-muted">
                  {t.aiAssistant.safetyWhy}{' '}
                  <a href={LINKS.docsBilling} className="text-brand-purple-300 hover:text-brand-purple-200 underline underline-offset-4">
                    {t.aiAssistant.safetyLink}
                  </a>
                </p>
              </div>
            </div>
          </div>
        </Reveal>

        {/* CTA strip */}
        <div className="mt-12 flex flex-wrap items-center justify-between gap-6 rounded-2xl border border-line-subtle bg-brand-ink-900 px-6 py-5">
          <p className="text-fg-primary">
            {t.aiAssistant.stripText}
            <span className="text-fg-muted"> {t.aiAssistant.stripQuiet}</span>
          </p>
          <div className="flex gap-3">
            <CTAButton
              variant="primary"
              href="#pricing"
              trackEvent={Events.CTA_SIGNUP_CLICK}
              trackProps={{ source: 'ai_strip' }}
            >
              {t.aiAssistant.stripSeePlans}
            </CTAButton>
            <CTAButton
              variant="tertiary"
              href={LINKS.telegramSales}
              external
              trackEvent={Events.CTA_TG_SALES_CLICK}
              trackProps={{ source: 'ai_strip' }}
              className="!text-fg-secondary hover:!text-fg-primary"
            >
              {t.aiAssistant.stripAskSales}
            </CTAButton>
          </div>
        </div>
      </div>
    </section>
  );
}
