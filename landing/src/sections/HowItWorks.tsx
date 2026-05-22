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

const steps = [
  { num: 1, title: 'Activate a plan',     blurb: 'USDT → Subscription active → 3/5/10 accounts auto-assigned + AI marketing feature unlocked.', icon: CreditCard },
  { num: 2, title: 'Upload your KB',      blurb: 'PDF / markdown / chat history → Gemini embedding → pgvector index. Cited automatically in replies.', icon: BookOpen },
  { num: 3, title: 'Configure a monitor', blurb: 'Pick keywords + target groups + persona. Active mode = AI replies in group; private DM is locked off.', icon: Sliders },
  { num: 4, title: 'AI engages in group', blurb: 'Listener fires → semantic judge confirms → AI posts a contextual reply with KB-cited details.', icon: Sparkles },
  { num: 5, title: 'Lead lands in inbox', blurb: 'Captured user → pre-assigned to your sales seat → atomic claim, no double-handoff.', icon: MessageSquareText },
  { num: 6, title: 'Sales closes',        blurb: 'One-click takeover. AI switches to draft mode, sales takes the DM, conversation logged to CRM.', icon: Users },
];

export default function HowItWorks() {
  return (
    <ScrollPin steps={steps.length} className="bg-white relative">
      {({ step, progress }) => {
        const active = steps[step];
        return (
          <div className="max-w-container mx-auto px-6 w-full grid lg:grid-cols-2 gap-12 items-center">
            {/* Left: text */}
            <div>
              <div className="text-eyebrow font-mono text-brand-blue-500 uppercase mb-3">
                How it works · {String(step + 1).padStart(2, '0')} / 06
              </div>
              <h2 className="font-display text-display-2 text-brand-ink-900 mb-6 leading-tight">
                From cold lead to closed deal,
                <br />
                <span className="text-brand-ink-500">one autonomous loop.</span>
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
                          ? 'bg-brand-blue-50 border border-brand-blue-200'
                          : 'border border-transparent opacity-50 hover:opacity-80',
                      ].join(' ')}
                    >
                      <div className={[
                        'shrink-0 w-9 h-9 rounded-lg inline-flex items-center justify-center transition-colors',
                        isActive ? 'bg-brand-blue-500 text-white' : 'bg-brand-ink-100 text-brand-ink-500',
                      ].join(' ')}>
                        <Icon className="w-4 h-4" />
                      </div>
                      <div>
                        <h3 className="font-display font-semibold text-brand-ink-900 text-base">
                          {s.num.toString().padStart(2, '0')} · {s.title}
                        </h3>
                        {isActive && (
                          <p className="mt-1 text-sm text-brand-ink-600 leading-relaxed">
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
              <div className="aspect-square rounded-3xl bg-brand-ink-950 p-8 overflow-hidden border border-brand-ink-200 shadow-card">
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
