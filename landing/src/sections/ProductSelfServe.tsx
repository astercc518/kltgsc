/**
 * ProductSelfServe — deep-dive for 需求 1 (pay-as-you-go triple).
 *
 * Three feature cards (scrape / bulk send / invite) with their actual
 * unit prices from feature_registry. Below the cards, a small flow
 * diagram explaining the wallet prepay / auto-pause mechanic.
 *
 * Numbers cite alembic seed migration 2b3c4d5e6f7a:85-103 — KEEP IN SYNC.
 */
import React from 'react';
import { motion } from 'framer-motion';
import {
  Users, Send, UserPlus, Wallet, ArrowRight, PauseCircle,
} from 'lucide-react';
import FeatureCard from '@/components/FeatureCard';
import Reveal from '@/components/Reveal';
import CTAButton from '@/components/CTAButton';
import { LINKS } from '@/lib/links';
import { Events } from '@/lib/analytics';
import { useT } from '@/i18n';

const TRIPLET_ICONS = [Users, Send, UserPlus];

export default function ProductSelfServe() {
  const t = useT();
  const triplet = t.selfServe.triplet.map((item, i) => ({ ...item, icon: TRIPLET_ICONS[i] }));
  return (
    <section id="self-serve" className="bg-white scroll-mt-24">
      <div className="max-w-container mx-auto px-6 py-24 lg:py-32">
        {/* Eyebrow + title block */}
        <Reveal>
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 text-eyebrow font-mono text-brand-blue-500 uppercase">
              <span className="h-px w-8 bg-brand-blue-500" />
              {t.selfServe.eyebrow}
            </div>
            <h2 className="mt-4 font-display text-display-2 text-brand-ink-900">
              {t.selfServe.titleA}
              <span className="text-brand-ink-500"> {t.selfServe.titleB}</span>
            </h2>
            <p className="mt-5 text-lg text-brand-ink-600 leading-relaxed">
              {t.selfServe.subtitle}
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
                {t.selfServe.flowTitle}
              </span>
            </div>

            <div className="grid md:grid-cols-4 gap-4 items-stretch">
              {t.selfServe.flowSteps.map((s, i) => (
                <React.Fragment key={i}>
                  {i > 0 && <FlowArrow />}
                  <FlowStep
                    n={String(i + 1).padStart(2, '0')}
                    title={s.title}
                    desc={s.desc}
                    icon={i === 2 ? PauseCircle : undefined}
                  />
                </React.Fragment>
              ))}
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
            {t.selfServe.stripQuestion}
            <span className="text-brand-ink-500 font-normal"> {t.selfServe.stripQuiet}</span>
          </p>
          <CTAButton
            variant="primary"
            href="#pricing"
            trackEvent={Events.CTA_SIGNUP_CLICK}
            trackProps={{ source: 'self_serve_strip' }}
            className="!bg-brand-ink-900 hover:!bg-brand-ink-700 !shadow-none"
          >
            {t.selfServe.stripCta}
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
