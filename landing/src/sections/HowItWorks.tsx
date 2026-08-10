/**
 * HowItWorks — 6-step end-to-end walkthrough.
 *
 * Uses ScrollPin to give a scrollytelling feel: section is tall, the
 * sticky panel pins to the viewport while user scrolls, and the active
 * step pulses through the 6 frames.
 *
 * Each step renders an inline SVG mock instead of a real screenshot —
 * keeps the bundle small (no png import), and stays readable across
 * 5 languages once we localize labels in PR4.
 */
import ScrollPin from '@/components/ScrollPin';
import {
  CreditCard, BookOpen, Sliders, Sparkles, MessageSquareText, Users,
} from 'lucide-react';
import { useT } from '@/i18n';

const STEP_ICONS = [CreditCard, BookOpen, Sliders, Sparkles, MessageSquareText, Users];

export default function HowItWorks() {
  const t = useT();
  const steps = t.howItWorks.steps.map((s, i) => ({
    num: i + 1,
    title: s.title,
    blurb: s.blurb,
    icon: STEP_ICONS[i],
  }));
  return (
    <ScrollPin steps={steps.length} className="bg-brand-ink-950 relative">
      {({ step, progress }) => {
        const active = steps[step];
        return (
          <div className="max-w-container mx-auto px-6 w-full grid lg:grid-cols-2 gap-12 items-center">
            {/* Left: text */}
            <div>
              <div className="text-eyebrow font-mono text-brand-blue-500 uppercase mb-3">
                {t.howItWorks.eyebrowPrefix} {String(step + 1).padStart(2, '0')} / 06
              </div>
              <h2 className="font-display text-display-2 text-fg-primary mb-6 leading-tight">
                {t.howItWorks.titleA}
                <br />
                <span className="text-fg-muted">{t.howItWorks.titleB}</span>
              </h2>

              <div className="space-y-3">
                {steps.map((s, i) => {
                  const isActive = i === step;
                  const Icon = s.icon;
                  return (
                    <div
                      key={s.num}
                      className={[
                        'flex items-start gap-4 p-4 rounded-xl transition-all duration-300',
                        isActive
                          ? 'bg-brand-blue-500/10 border border-brand-blue-500/40'
                          : 'border border-transparent opacity-50 hover:opacity-80',
                      ].join(' ')}
                    >
                      <div className={[
                        'shrink-0 w-9 h-9 rounded-lg inline-flex items-center justify-center transition-colors',
                        isActive ? 'bg-brand-blue-500 text-white' : 'bg-brand-ink-900 text-fg-muted',
                      ].join(' ')}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div>
                        <h3 className="font-display font-semibold text-fg-primary text-base">
                          {s.num.toString().padStart(2, '0')} · {s.title}
                        </h3>
                        {isActive && (
                          <p className="mt-1 text-sm text-fg-secondary leading-relaxed">
                            {s.blurb}
                          </p>
                        )}
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Right: schematic stage */}
            <div className="relative">
              <div className="aspect-square rounded-3xl bg-brand-ink-900 p-8 overflow-hidden border border-line-subtle shadow-card">
                {/* Pulse ring behind the icon */}
                <div className="absolute inset-0 flex items-center justify-center">
                  <div className="w-48 h-48 rounded-full border border-brand-blue-500/30 animate-pulse-soft" />
                  <div className="absolute w-72 h-72 rounded-full border border-brand-blue-500/15" />
                  <div className="absolute w-96 h-96 rounded-full border border-brand-blue-500/5" />
                </div>
                <div className="relative h-full flex flex-col items-center justify-center">
                  <div className="w-20 h-20 rounded-2xl bg-grad-hero-mixed shadow-glow-blue inline-flex items-center justify-center">
                    <active.icon className="w-9 h-9 text-white" />
                  </div>
                  <div className="mt-6 font-mono text-eyebrow text-white/40 uppercase">
                    Step {String(step + 1).padStart(2, '0')}
                  </div>
                  <div className="mt-1 font-display text-2xl text-white font-semibold">
                    {active.title}
                  </div>
                </div>
                {/* Progress bar at the bottom */}
                <div className="absolute bottom-6 left-6 right-6">
                  <div className="h-1 bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-grad-hero-mixed transition-all"
                      style={{ width: `${progress * 100}%` }}
                    />
                  </div>
                </div>
              </div>
            </div>
          </div>
        );
      }}
    </ScrollPin>
  );
}
