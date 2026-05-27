/**
 * HeroDual — dual-product hero.
 *
 * Top half: shared headline + sub + 3-tier CTA ladder.
 * Bottom half: split into two product cards (Self-Serve / AI Assistant),
 * each acting as a TOC entry-point for the section deep-dives below.
 *
 * The "Free $20 Trial" CTA carries `ref=landing&trial=20` in the URL so
 * /portal/register can credit a trial wallet on signup.
 *
 * Polish notes (2026-05-26):
 *   - Background atmosphere unified via <BackgroundField variant="hero" />
 *     (grid + beam + radial + noise).
 *   - Headline switched from full-clause gradient to single-word
 *     emphasis. Pure white reads more confident; gradient is reserved
 *     as accent.
 *   - Animation curve tightened to [0.16, 1, 0.3, 1]; stagger reduced
 *     to 70ms steps for a cascade rather than a slideshow.
 *   - SectionLabel intro replaces the fake "1,247 monitors" live badge.
 */
import { motion } from 'framer-motion';
import { useCallback, useState } from 'react';
import { ArrowRight, Sparkles, Package, Bot, Shield } from 'lucide-react';
import CTAButton from '@/components/CTAButton';
import BackgroundField from '@/components/BackgroundField';
import SectionLabel from '@/components/SectionLabel';
import DemoVideoModal from '@/components/DemoVideoModal';
import { LINKS } from '@/lib/links';
import { Events } from '@/lib/analytics';
import { useT } from '@/i18n';

const SNAP = [0.16, 1, 0.3, 1] as const;
const STEP = 0.07;

const fadeUp = {
  hidden: { opacity: 0, y: 24 },
  visible: (delay: number) => ({
    opacity: 1, y: 0,
    transition: { delay, duration: 0.75, ease: SNAP },
  }),
};

export default function HeroDual() {
  const t = useT();
  const [demoOpen, setDemoOpen] = useState(false);
  const closeDemo = useCallback(() => setDemoOpen(false), []);
  return (
  <>
    <section className="relative overflow-hidden">
      <BackgroundField variant="hero" />

      <div className="max-w-container mx-auto px-6 pt-24 pb-20 lg:pt-36 lg:pb-28">
        {/* Editorial section anchor */}
        <motion.div
          initial="hidden" animate="visible" variants={fadeUp} custom={STEP * 0}
          className="flex justify-center"
        >
          <SectionLabel number="00" tone="dark">TG1.AI <span className="text-white/30">/</span> Marketing OS</SectionLabel>
        </motion.div>

        {/* Headline — pure white, single-word gradient accent */}
        <motion.h1
          initial="hidden" animate="visible" variants={fadeUp} custom={STEP * 2}
          className="mt-7 text-center font-display text-display-1 text-white text-balance"
          style={{
            fontFeatureSettings: '"cv11", "ss01", "ss03"',
            textShadow: '0 1px 0 rgba(255,255,255,0.04)',
          }}
        >
          {t.hero.titlePart1}{' '}
          <span className="relative inline-block">
            <span className="bg-gradient-to-br from-white via-brand-blue-200 to-brand-purple-300 bg-clip-text text-transparent">
              {t.hero.titlePart2}
            </span>
            {/* Subtle underglow on the gradient word */}
            <span
              aria-hidden
              className="absolute -inset-x-2 -bottom-2 h-8 -z-10 blur-2xl opacity-70"
              style={{
                background:
                  'linear-gradient(90deg, rgba(0,102,255,0.25), rgba(168,85,247,0.25))',
              }}
            />
          </span>
        </motion.h1>

        <motion.p
          initial="hidden" animate="visible" variants={fadeUp} custom={STEP * 3}
          className="mt-6 text-center text-lg md:text-xl text-fg-secondary max-w-3xl mx-auto leading-relaxed text-balance"
        >
          {t.hero.subtitle}
          <span className="block mt-1.5 text-fg-muted text-[0.95rem]">{t.hero.subtitleQuiet}</span>
        </motion.p>

        {/* Three-tier CTA ladder */}
        <motion.div
          initial="hidden" animate="visible" variants={fadeUp} custom={STEP * 4}
          className="mt-10 flex flex-wrap justify-center gap-3"
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
            className="!text-white/75 hover:!text-white"
          >
            {t.hero.ctaTertiary}
          </CTAButton>
        </motion.div>

        {/* Dual product split */}
        <motion.div
          initial="hidden" animate="visible" variants={fadeUp} custom={STEP * 6}
          className="mt-20 lg:mt-24 grid md:grid-cols-2 gap-5 lg:gap-6"
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
    ? { tag: 'text-brand-blue-300 bg-brand-blue-500/[0.08] border-brand-blue-500/25', icon: 'text-brand-blue-300', divider: 'from-brand-blue-500/40', glowHover: 'group-hover:shadow-glow-blue' }
    : { tag: 'text-brand-purple-300 bg-brand-purple-500/[0.08] border-brand-purple-500/25', icon: 'text-brand-purple-300', divider: 'from-brand-purple-500/40', glowHover: 'group-hover:shadow-glow-purple' };

  return (
    <a
      href={anchor}
      className={[
        'group relative rounded-2xl border border-line-medium bg-surface-1/60 p-6 lg:p-8',
        'backdrop-blur-sm overflow-hidden',
        'transition-all duration-300 ease-out',
        'hover:border-line-strong hover:bg-surface-2/70 hover:-translate-y-0.5',
        'shadow-recess',
      ].join(' ')}
    >
      {/* Top gradient hairline — terminus accent */}
      <div className={`absolute inset-x-6 top-0 h-px bg-gradient-to-r ${accent.divider} via-white/30 to-transparent`} />
      {/* Persistent corner arrow — always visible affordance (not hover-only) */}
      <ArrowRight
        className="absolute top-6 right-6 w-4 h-4 text-fg-muted opacity-60 group-hover:opacity-100 group-hover:text-fg-primary group-hover:translate-x-0.5 group-hover:-translate-y-0.5 transition-all"
        aria-hidden
      />
      <div className="flex items-center gap-3 mb-5">
        <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[0.7rem] font-mono uppercase tracking-wider ${accent.tag}`}>
          <Sparkles className="w-3 h-3" />
          {tag}
        </span>
        <Icon className={`w-5 h-5 ml-auto ${accent.icon}`} />
      </div>
      <h3 className="font-display text-2xl font-semibold text-fg-primary mb-2 tracking-tight">{title}</h3>
      <p className="text-fg-secondary text-sm leading-relaxed mb-6">{blurb}</p>

      <ul className="space-y-0 mb-5">
        {bullets.map((b, i) => (
          <li key={i} className="flex items-center justify-between gap-3 py-2.5 border-b border-line-subtle last:border-0">
            <span className="text-fg-secondary text-sm">{b.label}</span>
            <span className={`font-mono text-sm tabular-nums ${accent.icon}`}>{b.price}</span>
          </li>
        ))}
      </ul>

      {safetyNote && (
        <div className="mb-5 rounded-lg bg-surface-2/60 border border-line-subtle px-3 py-2 text-xs text-fg-muted">
          {safetyNote}
        </div>
      )}

      <div className="flex items-center justify-between text-sm">
        <span className="text-fg-muted">{fit}</span>
        <span className="inline-flex items-center gap-1 text-fg-secondary group-hover:text-fg-primary transition-colors">
          {seeLabel}
          <ArrowRight className="w-4 h-4 group-hover:translate-x-1 transition-transform" />
        </span>
      </div>
    </a>
  );
}
