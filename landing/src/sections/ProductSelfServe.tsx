/**
 * ProductSelfServe — deep-dive for 需求 1 (pay-as-you-go triple).
 *
 * Three feature cards (scrape / bulk send / invite) with their actual
 * unit prices from feature_registry. Below the cards, a small flow
 * diagram explaining the wallet prepay / auto-pause mechanic.
 *
 * Numbers cite alembic seed migration 2b3c4d5e6f7a:85-103 — KEEP IN SYNC.
 */
import { motion } from 'framer-motion';
import {
  Users, Send, UserPlus, Wallet, ArrowRight, PauseCircle,
} from 'lucide-react';
import FeatureCard from '@/components/FeatureCard';
import Reveal from '@/components/Reveal';
import CTAButton from '@/components/CTAButton';
import { LINKS } from '@/lib/links';
import { Events } from '@/lib/analytics';

const triplet = [
  {
    icon: Users,
    badge: '$0.01 / member',
    title: 'Group scrape',
    description:
      'Pull member lists from any group your account can see. Filter by activity, language, or join-date before exporting. Each scraped member deducts $0.01 from your wallet — failed rows are not charged.',
  },
  {
    icon: Send,
    badge: '$0.10 / message',
    title: 'Bulk send',
    description:
      'Schedule a campaign across hundreds of accounts. Template variants prevent flag detection; the dispatcher respects per-account daily limits. You pay only for deliveries that get a 200 OK.',
  },
  {
    icon: UserPlus,
    badge: '$0.05 / invite',
    title: 'Bulk invite',
    description:
      'Pull users into your community group from a scraped list. Auto-pauses if Telegram throttles your accounts; resumes when the cooldown clears. Each invite attempt — successful or not — is metered.',
  },
];

export default function ProductSelfServe() {
  return (
    <section id="self-serve" className="bg-white scroll-mt-24">
      <div className="max-w-container mx-auto px-6 py-24 lg:py-32">
        {/* Eyebrow + title block */}
        <Reveal>
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 text-eyebrow font-mono text-brand-blue-500 uppercase">
              <span className="h-px w-8 bg-brand-blue-500" />
              Self-Serve — Pay as you go
            </div>
            <h2 className="mt-4 font-display text-display-2 text-brand-ink-900">
              Three Telegram ops, three flat per-unit prices.
              <span className="text-brand-ink-500"> No subscription needed.</span>
            </h2>
            <p className="mt-5 text-lg text-brand-ink-600 leading-relaxed">
              Top up your USDT wallet, run scrape / send / invite. Any leftover credit rolls forward,
              and the platform auto-pauses tasks when your balance dips below the operation cost —
              you can't accidentally over-spend.
            </p>
          </div>
        </Reveal>

        {/* Three product cards */}
        <div className="mt-12 grid md:grid-cols-3 gap-5">
          {triplet.map((item, i) => (
            <Reveal key={item.title} delay={i * 100}>
              <FeatureCard
                accent="blue"
                icon={item.icon}
                badge={item.badge}
                title={item.title}
                description={item.description}
              />
            </Reveal>
          ))}
        </div>

        {/* Flow diagram */}
        <Reveal delay={200}>
          <div className="mt-16 rounded-3xl bg-brand-ink-50 border border-brand-ink-100 p-6 lg:p-10">
            <div className="flex items-center gap-3 mb-6">
              <Wallet className="w-5 h-5 text-brand-blue-500" />
              <span className="text-eyebrow font-mono text-brand-ink-500 uppercase">
                How the wallet works
              </span>
            </div>

            <div className="grid md:grid-cols-4 gap-4 items-stretch">
              <FlowStep n="01" title="Top up" desc="Transfer USDT to your tenant address. Auto-credited on chain confirmation." />
              <FlowArrow />
              <FlowStep n="02" title="Run task" desc="Each action deducts at the published per-unit price. Receipts in wallet history." />
              <FlowArrow />
              <FlowStep n="03" title="Auto-pause" desc="If balance < next-op cost, task pauses with `paused_no_funds` — no surprise overage." icon={PauseCircle} />
              <FlowArrow />
              <FlowStep n="04" title="Resume" desc="Top up again. Tasks pick up where they left off — no replay risk via idempotency keys." />
            </div>
          </div>
        </Reveal>

        {/* CTA strip */}
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-10%' }}
          transition={{ duration: 0.6, ease: [0.22, 1, 0.36, 1] }}
          className="mt-12 flex flex-wrap items-center justify-between gap-6 rounded-2xl border border-brand-blue-200 bg-brand-blue-50 px-6 py-5"
        >
          <p className="text-brand-ink-700 font-medium">
            Want to see the full unit price table?
            <span className="text-brand-ink-500 font-normal"> Includes scrape / send / invite tiering above 50k volume.</span>
          </p>
          <CTAButton
            variant="primary"
            href="#pricing"
            trackEvent={Events.CTA_SIGNUP_CLICK}
            trackProps={{ source: 'self_serve_strip' }}
            className="!bg-brand-ink-900 hover:!bg-brand-ink-700 !shadow-none"
          >
            See pricing
          </CTAButton>
        </motion.div>
      </div>
    </section>
  );
}

function FlowStep({
  n, title, desc, icon: Icon,
}: { n: string; title: string; desc: string; icon?: typeof PauseCircle }) {
  return (
    <div className="rounded-2xl bg-white border border-brand-ink-100 p-4">
      <div className="flex items-center justify-between mb-2">
        <span className="text-eyebrow font-mono text-brand-blue-500 uppercase">{n}</span>
        {Icon && <Icon className="w-4 h-4 text-brand-ink-400" />}
      </div>
      <h4 className="font-display font-semibold text-brand-ink-900 mb-1">{title}</h4>
      <p className="text-sm text-brand-ink-600 leading-relaxed">{desc}</p>
    </div>
  );
}

function FlowArrow() {
  return (
    <div className="hidden md:flex items-center justify-center text-brand-ink-300">
      <ArrowRight className="w-5 h-5" />
    </div>
  );
}
