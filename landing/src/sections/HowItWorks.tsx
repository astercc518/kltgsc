/**
 * HowItWorks — 6-step end-to-end walkthrough.
 *
 * Polish notes (2026-05-27 round 4):
 *   - ScrollPin outer height reduced from steps * 80vh (480vh) to
 *     steps * 50vh (300vh). Saves the mobile reader 7 thumb-flicks.
 *   - Schematic panel hidden on <lg (was visually redundant on mobile
 *     anyway since the active step's title was already in the list).
 *   - On <lg the step list always shows every blurb — no scroll-driven
 *     reveal — because the pin behaviour is invisible without the
 *     paired right panel.
 *   - Design tokens applied (surface/fg/line) on the schematic stage;
 *     dropped the 3-ring pulse stack for a single mask-faded radial
 *     accent + a fine grid texture, matching the BackgroundField
 *     blueprint aesthetic.
 *   - Title gets tracking-tight + text-balance to stop the awkward
 *     mid-clause break.
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
    <ScrollPin
      steps={steps.length}
      outerHeightVh={steps.length * 50}
      className="bg-white relative"
    >
      {({ step, progress }) => {
        const active = steps[step];
        return (
          <div className="max-w-container mx-auto px-6 w-full grid lg:grid-cols-2 gap-12 items-center">
            {/* Left: text */}
            <div>
              <div
                className="inline-flex items-center gap-2 font-mono uppercase text-[0.6875rem] tracking-[0.16em] text-brand-blue-500 mb-4"
                style={{ fontVariantNumeric: 'tabular-nums slashed-zero' }}
              >
                <span className="h-px w-8 bg-brand-blue-500/60" />
                {t.howItWorks.eyebrowPrefix} {String(step + 1).padStart(2, '0')} / 06
              </div>
              <h2 className="font-display text-display-2 text-brand-ink-900 mb-6 leading-tight tracking-tight text-balance">
                {t.howItWorks.titleA}
                <br />
                <span className="text-brand-ink-500">{t.howItWorks.titleB}</span>
              </h2>

              <div className="space-y-2.5">
                {steps.map((s, i) => {
                  const isActive = i === step;
                  const Icon = s.icon;
                  return (
                    <div
                      key={s.num}
                      className={[
                        'flex items-start gap-4 p-4 rounded-xl transition-all duration-300',
                        // On lg+, dim the inactive items to focus the eye.
                        // On mobile, every step stays at full opacity since
                        // the scroll-pinned right panel isn't visible.
                        isActive
                          ? 'bg-brand-blue-50/70 border border-brand-blue-200/80'
                          : 'border border-transparent lg:opacity-45 lg:hover:opacity-80 transition-opacity',
                      ].join(' ')}
                    >
                      <div className={[
                        'shrink-0 w-9 h-9 rounded-lg inline-flex items-center justify-center transition-colors',
                        isActive ? 'bg-brand-blue-500 text-white' : 'bg-brand-ink-100 text-brand-ink-500',
                      ].join(' ')}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div>
                        <h3 className="font-display font-semibold text-brand-ink-900 text-base tracking-tight">
                          <span
                            className="font-mono text-brand-ink-500 text-sm mr-1.5"
                            style={{ fontVariantNumeric: 'tabular-nums' }}
                          >
                            {s.num.toString().padStart(2, '0')}
                          </span>
                          {s.title}
                        </h3>
                        <p
                          className={[
                            'mt-1 text-sm text-brand-ink-600 leading-relaxed',
                            // mobile: always visible. lg: only when active.
                            isActive ? '' : 'lg:hidden',
                          ].join(' ')}
                        >
                          {s.blurb}
                        </p>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>

            {/* Right: schematic stage — desktop only.
                On mobile the left list carries enough information; showing
                a giant stage panel below the list adds dead scroll. */}
            <div className="hidden lg:block relative">
              <div className="aspect-square rounded-3xl bg-brand-ink-950 p-8 overflow-hidden border border-line-medium relative">
                {/* Grid texture — matches BackgroundField */}
                <div
                  aria-hidden
                  className="absolute inset-0 bg-grid-fine opacity-50"
                  style={{
                    backgroundSize: '40px 40px, 40px 40px',
                    WebkitMaskImage: 'radial-gradient(ellipse 70% 60% at 50% 50%, #000 0%, transparent 80%)',
                    maskImage: 'radial-gradient(ellipse 70% 60% at 50% 50%, #000 0%, transparent 80%)',
                  }}
                />
                {/* Single soft radial accent behind icon, no ripple stack */}
                <div
                  aria-hidden
                  className="absolute inset-0 flex items-center justify-center"
                >
                  <div
                    className="w-72 h-72 rounded-full opacity-60 transition-opacity duration-700"
                    style={{
                      background: 'radial-gradient(circle, rgba(0,102,255,0.35) 0%, rgba(168,85,247,0.18) 35%, transparent 70%)',
                    }}
                  />
                </div>

                <div className="relative h-full flex flex-col items-center justify-center">
                  <div className="w-20 h-20 rounded-2xl bg-grad-hero-mixed shadow-glow-blue inline-flex items-center justify-center">
                    <active.icon className="w-9 h-9 text-white" />
                  </div>
                  <div
                    className="mt-6 font-mono text-[0.7rem] uppercase tracking-[0.16em] text-white/40"
                    style={{ fontVariantNumeric: 'tabular-nums slashed-zero' }}
                  >
                    Step {String(step + 1).padStart(2, '0')} / 06
                  </div>
                  <div className="mt-2 font-display text-2xl text-white font-semibold tracking-tight">
                    {active.title}
                  </div>
                </div>

                {/* Progress bar at the bottom */}
                <div className="absolute bottom-6 left-6 right-6">
                  <div className="h-[2px] bg-white/10 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-brand-blue-400 via-brand-blue-500 to-brand-purple-500 transition-all duration-200"
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
