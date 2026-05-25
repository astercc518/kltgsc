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
import { useCallback, useState } from 'react';
import { ArrowRight, Sparkles, Package, Bot, Shield } from 'lucide-react';
import CTAButton from '@/components/CTAButton';
import DemoVideoModal from '@/components/DemoVideoModal';
import { LINKS } from '@/lib/links';
import { Events } from '@/lib/analytics';
import { useT } from '@/i18n';

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: (delay: number) => ({
    opacity: 1, y: 0,
    transition: { delay, duration: 0.7, ease: [0.22, 1, 0.36, 1] as const },
  }),
};

export default function HeroDual() {
  const t = useT();
  const [demoOpen, setDemoOpen] = useState(false);
  const closeDemo = useCallback(() => setDemoOpen(false), []);
  return (
  <>
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
            <span>{t.hero.liveBadge}</span>
          </div>
        </motion.div>

        {/* Headline */}
        <motion.h1
          initial="hidden" animate="visible" variants={fadeUp} custom={0.1}
          className="mt-6 text-center font-display text-display-1 text-white"
        >
          {t.hero.titlePart1}{' '}
          <span className="bg-gradient-to-r from-brand-blue-400 to-brand-purple-400 bg-clip-text text-transparent">
            {t.hero.titlePart2}
          </span>
        </motion.h1>

        <motion.p
          initial="hidden" animate="visible" variants={fadeUp} custom={0.2}
          className="mt-5 text-center text-lg md:text-xl text-white/70 max-w-3xl mx-auto leading-relaxed"
        >
          {t.hero.subtitle}
          <br className="hidden md:block" />
          <span className="text-white/50 text-base">{t.hero.subtitleQuiet}</span>
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
            {t.hero.ctaPrimary}
          </CTAButton>
          <CTAButton
            variant="secondary"
            onClick={() => setDemoOpen(true)}
            trackEvent={Events.CTA_DEMO_CLICK}
            trackProps={{ source: 'hero' }}
          >
            {t.hero.ctaSecondary}
          </CTAButton>
          <CTAButton
            variant="tertiary"
            href={LINKS.telegramSales}
            external
            trackEvent={Events.CTA_TG_SALES_CLICK}
            trackProps={{ source: 'hero' }}
            className="!text-white/80 hover:!text-white"
          >
            {t.hero.ctaTertiary}
          </CTAButton>
        </motion.div>

        {/* Dual product split */}
        <motion.div
          initial="hidden" animate="visible" variants={fadeUp} custom={0.45}
          className="mt-16 lg:mt-20 grid md:grid-cols-2 gap-5 lg:gap-6"
        >
          <ProductCard
            tone="blue"
            tag={t.hero.selfServe.tag}
            icon={Package}
            title={t.hero.selfServe.title}
            blurb={t.hero.selfServe.blurb}
            bullets={t.hero.selfServe.bullets}
            fit={t.hero.selfServe.fit}
            seeLabel={t.hero.selfServe.see}
            anchor="#self-serve"
          />
          <ProductCard
            tone="purple"
            tag={t.hero.aiAssistant.tag}
            icon={Bot}
            title={t.hero.aiAssistant.title}
            blurb={t.hero.aiAssistant.blurb}
            bullets={t.hero.aiAssistant.bullets}
            fit={t.hero.aiAssistant.fit}
            seeLabel={t.hero.aiAssistant.see}
            anchor="#ai-assistant"
            safetyNote={<><Shield className="w-3 h-3 inline -mt-0.5 mr-1" /> {t.hero.aiAssistant.safetyNote}</>}
          />
        </motion.div>
      </div>
    </section>
    <DemoVideoModal open={demoOpen} onClose={closeDemo} />
  </>
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
  seeLabel: string;
  safetyNote?: React.ReactNode;
};

function ProductCard({ tone, tag, icon: Icon, title, blurb, bullets, fit, anchor, seeLabel, safetyNote }: CardProps) {
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
          {seeLabel}
          <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
        </span>
      </div>
    </a>
  );
}
