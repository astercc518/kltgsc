/**
 * HeroDual — dual-product hero.
 *
 * Top half: shared headline + sub + 3-tier CTA ladder.
 * Bottom half: split into two product cards (Self-Serve / AI Assistant),
 * each acting as a TOC entry-point for the section deep-dives below.
 *
 * The "Free $20 Trial" CTA carries `ref=landing&trial=20` in the URL so
 * /portal/register can credit a trial wallet on signup (handled in PR4
 * via a portal copy update).
 */
import { motion } from 'framer-motion';
import { ArrowRight, Sparkles, Package, Bot, Shield } from 'lucide-react';
import CTAButton from '@/components/CTAButton';
import { LINKS } from '@/lib/links';
import { Events } from '@/lib/analytics';

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: (delay: number) => ({
    opacity: 1, y: 0,
    transition: { delay, duration: 0.7, ease: [0.22, 1, 0.36, 1] as const },
  }),
};

export default function HeroDual() {
  return (
    <section className="relative overflow-hidden">
      {/* Subtle gradient backdrop. The .bg-noise utility (defined in
          tailwind.config.js) adds a 3% white-noise overlay so the
          gradient doesn't band on cheap monitors. */}
      <div className="absolute inset-0 -z-10 bg-grad-radial-dark" />
      <div className="absolute inset-0 -z-10 bg-noise opacity-60" />

      <div className="max-w-container mx-auto px-6 pt-20 pb-16 lg:pt-32 lg:pb-24">
        {/* Live status badge */}
        <motion.div
          initial="hidden" animate="visible" variants={fadeUp} custom={0}
          className="flex justify-center"
        >
          <div className="inline-flex items-center gap-2 rounded-full border border-white/15 bg-white/5 px-4 py-1.5 text-xs font-mono text-white/70 backdrop-blur">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
            </span>
            <span>1,247 AI monitor rules running right now</span>
          </div>
        </motion.div>

        {/* Headline */}
        <motion.h1
          initial="hidden" animate="visible" variants={fadeUp} custom={0.1}
          className="mt-6 text-center font-display text-display-1 text-white"
        >
          Two ways to grow{' '}
          <span className="bg-gradient-to-r from-brand-blue-400 to-brand-purple-400 bg-clip-text text-transparent">
            on Telegram
          </span>
        </motion.h1>

        <motion.p
          initial="hidden" animate="visible" variants={fadeUp} custom={0.2}
          className="mt-5 text-center text-lg md:text-xl text-white/70 max-w-3xl mx-auto leading-relaxed"
        >
          Pay-as-you-go scraping &amp; bulk send + an AI marketing assistant that listens
          to your target groups and pushes high-intent leads to your inbox.
          <br className="hidden md:block" />
          <span className="text-white/50 text-base">One platform, one account pool, one wallet.</span>
        </motion.p>

        {/* Three-tier CTA ladder */}
        <motion.div
          initial="hidden" animate="visible" variants={fadeUp} custom={0.3}
          className="mt-9 flex flex-wrap justify-center gap-3"
        >
          <CTAButton
            variant="primary"
            href={LINKS.trial}
            trackEvent={Events.CTA_SIGNUP_CLICK}
            trackProps={{ source: 'hero' }}
          >
            Free $20 Trial
          </CTAButton>
          <CTAButton
            variant="secondary"
            href={LINKS.demoVideo}
            trackEvent={Events.CTA_DEMO_CLICK}
            trackProps={{ source: 'hero' }}
          >
            Watch 90s Demo
          </CTAButton>
          <CTAButton
            variant="tertiary"
            href={LINKS.telegramSales}
            external
            trackEvent={Events.CTA_TG_SALES_CLICK}
            trackProps={{ source: 'hero' }}
            className="!text-white/80 hover:!text-white"
          >
            Talk on Telegram
          </CTAButton>
        </motion.div>

        {/* Dual product split */}
        <motion.div
          initial="hidden" animate="visible" variants={fadeUp} custom={0.45}
          className="mt-16 lg:mt-20 grid md:grid-cols-2 gap-5 lg:gap-6"
        >
          <ProductCard
            tone="blue"
            tag="Self-Serve"
            icon={Package}
            title="Pay-as-you-go bulk ops"
            blurb="Scrape, send, invite — three core actions, billed per unit, prepaid with USDT."
            bullets={[
              { label: 'Group scrape', price: '$0.01 / member' },
              { label: 'Bulk send',    price: '$0.10 / message' },
              { label: 'Bulk invite',  price: '$0.05 / invite' },
            ]}
            fit="Best for: in-house SDR tooling"
            anchor="#self-serve"
          />
          <ProductCard
            tone="purple"
            tag="AI Marketing Assistant"
            icon={Bot}
            title="Subscription that hires itself"
            blurb="Your TG accounts listen 24/7. AI replies in group on intent hits, pushes leads to your sales inbox."
            bullets={[
              { label: 'Listens to', price: 'your target groups' },
              { label: 'Replies in', price: 'group (not DM)' },
              { label: 'Hands off',  price: 'to your humans' },
            ]}
            fit="Best for: replacing an SDR / BDR team"
            anchor="#ai-assistant"
            safetyNote={<><Shield className="w-3 h-3 inline -mt-0.5 mr-1" /> AI never auto-DMs users — that decision stays with your sales</>}
          />
        </motion.div>
      </div>
    </section>
  );
}

type CardProps = {
  tone: 'blue' | 'purple';
  tag: string;
  icon: typeof Package;
  title: string;
  blurb: string;
  bullets: { label: string; price: string }[];
  fit: string;
  anchor: string;
  safetyNote?: React.ReactNode;
};

function ProductCard({ tone, tag, icon: Icon, title, blurb, bullets, fit, anchor, safetyNote }: CardProps) {
  const accent = tone === 'blue'
    ? { tag: 'text-brand-blue-400 bg-brand-blue-500/10 border-brand-blue-500/20', icon: 'text-brand-blue-400', divider: 'from-brand-blue-500/30' }
    : { tag: 'text-brand-purple-400 bg-brand-purple-500/10 border-brand-purple-500/20', icon: 'text-brand-purple-400', divider: 'from-brand-purple-500/30' };

  return (
    <a
      href={anchor}
      className="group relative rounded-2xl border border-white/10 bg-white/[0.04] p-6 lg:p-8 backdrop-blur-sm transition-all hover:border-white/20 hover:bg-white/[0.06]"
    >
      {/* top gradient bar */}
      <div className={`absolute inset-x-0 top-0 h-px bg-gradient-to-r ${accent.divider} to-transparent`} />
      <div className="flex items-center gap-3 mb-5">
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-mono ${accent.tag}`}>
          <Sparkles className="w-3 h-3" />
          {tag}
        </span>
        <Icon className={`w-5 h-5 ml-auto ${accent.icon}`} />
      </div>
      <h3 className="font-display text-2xl font-semibold text-white mb-2">{title}</h3>
      <p className="text-white/60 text-sm leading-relaxed mb-6">{blurb}</p>

      <ul className="space-y-2.5 mb-5">
        {bullets.map((b, i) => (
          <li key={i} className="flex items-center justify-between gap-3 py-2 border-b border-white/5 last:border-0">
            <span className="text-white/70 text-sm">{b.label}</span>
            <span className={`font-mono text-sm ${accent.icon}`}>{b.price}</span>
          </li>
        ))}
      </ul>

      {safetyNote && (
        <div className="mb-5 rounded-lg bg-white/[0.04] border border-white/10 px-3 py-2 text-xs text-white/55">
          {safetyNote}
        </div>
      )}

      <div className="flex items-center justify-between text-sm">
        <span className="text-white/50">{fit}</span>
        <span className="inline-flex items-center gap-1 text-white/70 group-hover:text-white transition-colors">
          See details
          <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
        </span>
      </div>
    </a>
  );
}
