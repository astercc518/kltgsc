/**
 * FinalCTA — repeating the conversion ladder one last time at fold-2.
 *
 * Visually mirrors the hero but inverted: dark background with the
 * gradient pulled in. Same three CTAs (Free Trial / Demo / TG).
 */
import { motion } from 'framer-motion';
import { useCallback, useState } from 'react';
import { ArrowRight } from 'lucide-react';
import CTAButton from '@/components/CTAButton';
import BackgroundField from '@/components/BackgroundField';
import SectionLabel from '@/components/SectionLabel';
import DemoVideoModal from '@/components/DemoVideoModal';
import { LINKS } from '@/lib/links';
import { Events } from '@/lib/analytics';
import { useT } from '@/i18n';

const SNAP = [0.16, 1, 0.3, 1] as const;

export default function FinalCTA() {
  const t = useT();
  const [demoOpen, setDemoOpen] = useState(false);
  const closeDemo = useCallback(() => setDemoOpen(false), []);
  return (
    <>
    <section className="bg-brand-ink-950 relative overflow-hidden">
      <BackgroundField variant="hero" gridOpacity={0.35} />
      {/* Soft corner orbs — kept but tamed */}
      <div className="absolute -left-32 -top-32 w-96 h-96 rounded-full bg-brand-blue-500 opacity-10 blur-3xl pointer-events-none" />
      <div className="absolute -right-32 -bottom-32 w-96 h-96 rounded-full bg-brand-purple-500 opacity-10 blur-3xl pointer-events-none" />

      <div className="relative max-w-container mx-auto px-6 py-28 lg:py-36 text-center">
        <motion.div
          initial={{ opacity: 0, y: 12 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-15%' }}
          transition={{ duration: 0.7, ease: SNAP }}
          className="flex justify-center mb-7"
        >
          <SectionLabel number="09" tone="dark">Start <span className="text-white/30">/</span> 5 minutes to live</SectionLabel>
        </motion.div>
        <motion.h2
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-15%' }}
          transition={{ duration: 0.75, delay: 0.07, ease: SNAP }}
          className="font-display text-display-1 text-white tracking-tight text-balance"
        >
          {t.finalCta.titlePart1}
          <br />
          <span className="relative inline-block">
            <span className="bg-gradient-to-br from-white via-brand-blue-200 to-brand-purple-300 bg-clip-text text-transparent">
              {t.finalCta.titlePart2}
            </span>
            <span
              aria-hidden
              className="absolute -inset-x-2 -bottom-2 h-8 -z-10 blur-2xl opacity-70"
              style={{ background: 'linear-gradient(90deg, rgba(0,102,255,0.25), rgba(168,85,247,0.25))' }}
            />
          </span>
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-15%' }}
          transition={{ duration: 0.7, delay: 0.14, ease: SNAP }}
          className="mt-6 text-lg text-fg-secondary max-w-2xl mx-auto text-balance"
        >
          {t.finalCta.subtitle}
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-15%' }}
          transition={{ duration: 0.7, delay: 0.21, ease: SNAP }}
          className="mt-10 flex flex-wrap justify-center gap-3"
        >
          <CTAButton
            variant="primary"
            href={LINKS.trial}
            trackEvent={Events.CTA_SIGNUP_CLICK}
            trackProps={{ source: 'final_cta' }}
          >
            {t.hero.ctaPrimary}
          </CTAButton>
          <CTAButton
            variant="secondary"
            onClick={() => setDemoOpen(true)}
            trackEvent={Events.CTA_DEMO_CLICK}
            trackProps={{ source: 'final_cta' }}
          >
            {t.hero.ctaSecondary}
          </CTAButton>
          <CTAButton
            variant="tertiary"
            href={LINKS.telegramSales}
            external
            trackEvent={Events.CTA_TG_SALES_CLICK}
            trackProps={{ source: 'final_cta' }}
            className="!text-white/80 hover:!text-white"
          >
            {t.hero.ctaTertiary}
            <ArrowRight className="w-4 h-4" />
          </CTAButton>
        </motion.div>
      </div>
    </section>
    <DemoVideoModal open={demoOpen} onClose={closeDemo} />
    </>
  );
}
