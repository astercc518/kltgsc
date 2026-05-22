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
  Shield, Lock,
} from 'lucide-react';
import Reveal from '@/components/Reveal';
import CTAButton from '@/components/CTAButton';
import { LINKS } from '@/lib/links';
import { Events } from '@/lib/analytics';

const steps = [
  {
    icon: Ear,
    title: 'Listen',
    desc: 'Your TG accounts sit in your target groups 24/7. The listener fans out across 5 prod shards, ~200 accounts each.',
  },
  {
    icon: Brain,
    title: 'Recognize',
    desc: 'Two-stage match: keyword pre-filter (fast) → Vertex Gemini semantic judge (precise). Cosine-rerank via BGE cross-encoder for the win.',
  },
  {
    icon: MessageCircleMore,
    title: 'Engage',
    desc: 'On intent hit, AI posts a contextual reply IN the source group. Personas come from your KB, with sales-line stripping so it never looks like a billboard.',
    highlight: true,
  },
  {
    icon: Inbox,
    title: 'Push',
    desc: 'A Lead row materialises — pre-assigned to the salesperson who owns that TG account, source-group attribution intact.',
  },
  {
    icon: HandshakeIcon,
    title: 'Takeover',
    desc: 'Sales clicks once: AI drops to "draft mode" (suggestions only), conversation is theirs. Atomic claim, no double-handoff.',
  },
  {
    icon: BookOpenCheck,
    title: 'CRM sink',
    desc: 'Unconverted leads land in CRM with industry tag + interaction history — your sales team has tomorrow\'s call list before they wake up.',
  },
];

export default function ProductAIAssistant() {
  return (
    <section id="ai-assistant" className="bg-brand-ink-950 scroll-mt-24 relative overflow-hidden">
      {/* Subtle purple glow at the top */}
      <div className="absolute -top-32 left-1/2 -translate-x-1/2 w-[600px] h-[600px] rounded-full bg-brand-purple-500 opacity-10 blur-3xl pointer-events-none" />

      <div className="relative max-w-container mx-auto px-6 py-24 lg:py-32">
        <Reveal>
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 text-eyebrow font-mono text-brand-purple-400 uppercase">
              <span className="h-px w-8 bg-brand-purple-500" />
              AI Marketing Assistant — Subscription
            </div>
            <h2 className="mt-4 font-display text-display-2 text-white">
              An SDR / BDR team that ships in 24 hours.
              <span className="text-white/50"> Half-automatic by design.</span>
            </h2>
            <p className="mt-5 text-lg text-white/70 leading-relaxed">
              Configure a monitor rule once. AI handles first-touch in the group — friendly, on-brand,
              contextual — and routes high-intent leads to a human inbox. You decide who gets the DM.
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
                    : 'border-white/10 bg-white/[0.03] hover:border-white/20 hover:bg-white/[0.05]',
                ].join(' ')}
              >
                <div className="flex items-center gap-3 mb-4">
                  <span className="font-mono text-eyebrow text-white/40">
                    {String(i + 1).padStart(2, '0')}
                  </span>
                  <div className={`inline-flex items-center justify-center w-10 h-10 rounded-xl ${s.highlight ? 'bg-brand-purple-500/20 text-brand-purple-300' : 'bg-white/5 text-white/70'}`}>
                    <s.icon className="w-5 h-5" />
                  </div>
                </div>
                <h3 className="font-display text-xl font-semibold text-white mb-2">
                  {s.title}
                </h3>
                <p className="text-sm text-white/60 leading-relaxed">
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
                <h3 className="font-display text-xl font-semibold text-white mb-2">
                  AI never auto-DMs your prospects.
                </h3>
                <p className="text-white/70 leading-relaxed">
                  The reply layer is half-automatic on purpose. AI posts <em>in the source group</em>
                  where everyone can see — that's social proof. Private outreach stays a human
                  decision; your sales clicks "claim", AI switches to draft suggestions, the DM is
                  yours to send.
                </p>
                <p className="mt-3 text-sm text-white/50">
                  Why? Ban risk is concentrated in unsolicited DMs, not in-group replies. We keep
                  your accounts alive by design.{' '}
                  <a href={LINKS.docsBilling} className="text-brand-purple-300 hover:text-brand-purple-200 underline underline-offset-4">
                    Read the safety doc →
                  </a>
                </p>
              </div>
            </div>
          </div>
        </Reveal>

        {/* CTA strip */}
        <div className="mt-12 flex flex-wrap items-center justify-between gap-6 rounded-2xl border border-white/10 bg-white/[0.03] px-6 py-5">
          <p className="text-white/80">
            Activate the assistant on any paid plan.
            <span className="text-white/40"> Sub gates access; wallet meters each AI reply ($0.05) + lead ($0.50).</span>
          </p>
          <div className="flex gap-3">
            <CTAButton
              variant="primary"
              href="#pricing"
              trackEvent={Events.CTA_SIGNUP_CLICK}
              trackProps={{ source: 'ai_strip' }}
            >
              See plans
            </CTAButton>
            <CTAButton
              variant="tertiary"
              href={LINKS.telegramSales}
              external
              trackEvent={Events.CTA_TG_SALES_CLICK}
              trackProps={{ source: 'ai_strip' }}
              className="!text-white/80 hover:!text-white"
            >
              Ask sales
            </CTAButton>
          </div>
        </div>
      </div>
    </section>
  );
}
