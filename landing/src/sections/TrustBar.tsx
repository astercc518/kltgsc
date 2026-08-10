/**
 * TrustBar — 5 credibility metrics under the hero.
 *
 * Uses AnimatedNumber for the integer stats so they count up when the
 * row scrolls into view. Strings come from real product caps.
 *
 * Polish notes (2026-05-26):
 *   - SectionLabel anchors the row with an editorial "01 · TRUST" marker.
 *   - Numerals now opt into tabular-nums + slashed-zero via inline style;
 *     fixes the wobble when the count-up rolls through different glyphs.
 *   - Stat units (suffix) demoted to muted weight so the value reads
 *     primary; previously suffix had the same color as the number.
 *   - Vertical dividers between stats on md+ for a typographic spine.
 */
import AnimatedNumber from '@/components/AnimatedNumber';
import Reveal from '@/components/Reveal';
import SectionLabel from '@/components/SectionLabel';
import { useT } from '@/i18n';

type Stat = {
  value: number;
  suffix?: string;
  label: string;
  format?: (n: number) => string;
  literal?: string;
};

export default function TrustBar() {
  const t = useT();
  const stats: Stat[] = [
    { value: 1000, suffix: '+',     label: t.trustBar.accounts, format: (n) => Math.round(n).toLocaleString() },
    { value: 5,    suffix: '',      label: t.trustBar.shards },
    { value: 768,  suffix: '-dim',  label: t.trustBar.rag },
    { value: 99.9, suffix: '%',     label: t.trustBar.uptime,   format: (n) => n.toFixed(1) },
    { value: 0,    literal: 'USDT', label: t.trustBar.networks },
  ];
  return (
    <section
      aria-label="Trust signals"
      className="relative bg-brand-ink-950 border-y border-line-subtle overflow-hidden"
    >
      {/* Faint top hairline accent that fades to edges */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.12] to-transparent" />
      <div className="max-w-container mx-auto px-6 py-14">
        <Reveal>
          <div className="mb-8 flex justify-center">
            <SectionLabel number="01" tone="dark">Trust signals</SectionLabel>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-5 gap-x-8 gap-y-10">
            {stats.map((s, i) => (
              <div
                key={i}
                className={[
                  'text-center md:text-left',
                  i > 0 ? 'md:pl-8 md:border-l md:border-line-subtle' : '',
                ].join(' ')}
              >
                <div
                  className="font-mono text-3xl md:text-4xl text-fg-primary font-semibold tracking-tight"
                  style={{ fontVariantNumeric: 'tabular-nums slashed-zero' }}
                >
                  {s.literal ? (
                    <span className="bg-gradient-to-br from-white to-brand-blue-300 bg-clip-text text-transparent">
                      {s.literal}
                    </span>
                  ) : (
                    <>
                      <AnimatedNumber value={s.value} format={s.format} />
                      {s.suffix && (
                        <span className="text-fg-muted text-2xl md:text-3xl font-normal ml-0.5">{s.suffix}</span>
                      )}
                    </>
                  )}
                </div>
                <div className="mt-2 text-[0.7rem] uppercase tracking-[0.16em] text-fg-muted font-mono">
                  {s.label}
                </div>
              </div>
            ))}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
