/**
 * FinalCTA — repeating the conversion ladder one last time at fold-2.
 *
 * Visually mirrors the hero but inverted: dark background with the
 * gradient pulled in. Same three CTAs (Free Trial / Demo / TG).
 */
import { motion } from 'framer-motion';
import { ArrowRight } from 'lucide-react';
import CTAButton from '@/components/CTAButton';
import { LINKS } from '@/lib/links';
import { Events } from '@/lib/analytics';
import { useT } from '@/i18n';

export default function FinalCTA() {
  const t = useT();
  return (
    <section className="bg-brand-ink-950 relative overflow-hidden">
      {/* Gradient orbs in the corners */}
      <div className="absolute -left-32 -top-32 w-96 h-96 rounded-full bg-brand-blue-500 opacity-15 blur-3xl pointer-events-none" />
      <div className="absolute -right-32 -bottom-32 w-96 h-96 rounded-full bg-brand-purple-500 opacity-15 blur-3xl pointer-events-none" />

      <div className="relative max-w-container mx-auto px-6 py-24 lg:py-32 text-center">
        <motion.h2
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-15%' }}
          transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}
          className="font-display text-display-1 text-white"
        >
          {t.finalCta.titlePart1}
          <br />
          <span className="bg-gradient-to-r from-brand-blue-400 to-brand-purple-400 bg-clip-text text-transparent">
            {t.finalCta.titlePart2}
          </span>
        </motion.h2>
        <motion.p
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-15%' }}
          transition={{ duration: 0.7, delay: 0.1, ease: [0.22, 1, 0.36, 1] }}
          className="mt-5 text-lg text-white/70 max-w-2xl mx-auto"
        >
          {t.finalCta.subtitle}
        </motion.p>

        <motion.div
          initial={{ opacity: 0, y: 16 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true, margin: '-15%' }}
          transition={{ duration: 0.7, delay: 0.2, ease: [0.22, 1, 0.36, 1] }}
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
            href={LINKS.demoVideo}
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
  );
}
