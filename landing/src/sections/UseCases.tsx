/**
 * UseCases — 3 buyer ICPs with concrete back-of-napkin numbers.
 *
 * Each card includes one quantitative claim grounded in the
 * playbook (docs/internal_sales_playbook.md) — leave the numbers
 * conservative so they're defensible in a sales call.
 */
import { Coins, Briefcase, Megaphone } from 'lucide-react';
import Reveal from '@/components/Reveal';

const cases = [
  {
    icon: Coins,
    title: 'Crypto & Web3 GTM',
    blurb:
      'IDO launches, airdrop campaigns, exchange referrals. AI listens across 30+ trader chats, posts contextual replies on "looking for X exchange" type intent, hands off conversion talk to your sales seat.',
    metric: '~$0.50 per qualified lead',
    sub: 'vs. $40 ICP CPL on paid social',
    tone: 'purple',
  },
  {
    icon: Briefcase,
    title: 'Fintech & forex outbound',
    blurb:
      'Compliance-friendly first-touch: AI replies in-group with publicly visible language, never DMs first. Your licensed sales rep does the regulated conversation manually.',
    metric: '50× cheaper than offshore SDRs',
    sub: 'with a paper trail per interaction',
    tone: 'blue',
  },
  {
    icon: Megaphone,
    title: 'Cross-border e-com & MCN',
    blurb:
      'Scrape competitor community members (per-MB billing). Run bulk send campaigns to high-overlap segments. AI assistant catches replies and triages to your team.',
    metric: '3 ops, one wallet',
    sub: 'scrape · send · invite — all USDT-metered',
    tone: 'blue',
  },
] as const;

const toneClasses = {
  blue:   { ring: 'ring-brand-blue-100',   text: 'text-brand-blue-500',   pill: 'bg-brand-blue-50 text-brand-blue-700' },
  purple: { ring: 'ring-brand-purple-100', text: 'text-brand-purple-500', pill: 'bg-brand-purple-50 text-brand-purple-700' },
} as const;

export default function UseCases() {
  return (
    <section className="bg-brand-ink-50">
      <div className="max-w-container mx-auto px-6 py-24 lg:py-28">
        <Reveal>
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 text-eyebrow font-mono text-brand-ink-500 uppercase">
              <span className="h-px w-8 bg-brand-ink-300" />
              Use cases
            </div>
            <h2 className="mt-4 font-display text-display-2 text-brand-ink-900">
              Built for the teams that ship at Telegram scale.
            </h2>
          </div>
        </Reveal>

        <div className="mt-12 grid md:grid-cols-3 gap-6">
          {cases.map((c, i) => {
            const Icon = c.icon;
            const tc = toneClasses[c.tone];
            return (
              <Reveal key={c.title} delay={i * 100}>
                <div className={`h-full p-7 rounded-2xl bg-white border border-brand-ink-100 shadow-card hover:shadow-card-hover transition-shadow ring-1 ${tc.ring}`}>
                  <Icon className={`w-7 h-7 mb-5 ${tc.text}`} />
                  <h3 className="font-display text-xl font-semibold text-brand-ink-900 mb-3">
                    {c.title}
                  </h3>
                  <p className="text-brand-ink-600 text-sm leading-relaxed mb-6">
                    {c.blurb}
                  </p>
                  <div className={`inline-block rounded-full px-3 py-1 text-sm font-mono ${tc.pill}`}>
                    {c.metric}
                  </div>
                  <p className="mt-2 text-xs text-brand-ink-500 font-mono">
                    {c.sub}
                  </p>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
