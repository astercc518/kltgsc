/**
 * SectionLabel — editorial section anchor.
 *
 * Renders a small mono caption with optional 01-style numeral and a
 * 32px horizontal rule terminus. Reads like a print magazine pull or
 * a Browser Company landing chapter mark, not a generic SaaS eyebrow.
 *
 *   ── 03 · LISTEN
 *
 * Numeral uses JetBrains Mono with tabular figures for crisp digits.
 * Eyebrow uses UPPERCASE with 0.16em tracking — wider than the system
 * default eyebrow (0.12em) so it reads as "label", not "tiny title".
 *
 * Variants:
 *   tone='dark'   light text on dark surface (default)
 *   tone='light'  dark text on light surface
 */
import type { ReactNode } from 'react';

type Tone = 'dark' | 'light';

type Props = {
  number?: string;
  children: ReactNode;
  tone?: Tone;
  /** Hide the leading rule (use for stacked use under section title) */
  rule?: boolean;
  className?: string;
};

export default function SectionLabel({
  number,
  children,
  tone = 'dark',
  rule = true,
  className,
}: Props) {
  const ruleColor = tone === 'dark' ? 'bg-white/25' : 'bg-brand-ink-300';
  const numberColor = tone === 'dark' ? 'text-white/90' : 'text-brand-ink-900';
  const labelColor = tone === 'dark' ? 'text-white/55' : 'text-brand-ink-500';
  const dotColor   = tone === 'dark' ? 'bg-white/30' : 'bg-brand-ink-400';

  return (
    <div
      className={[
        // flex-wrap lets the text span drop to its own line on narrow
        // viewports without leaving the rule orphaned on line 1.
        'inline-flex items-center gap-x-3 gap-y-1.5 flex-wrap font-mono uppercase',
        'text-[0.6875rem] leading-none tracking-[0.16em]',
        className || '',
      ].join(' ')}
      style={{ fontVariantNumeric: 'tabular-nums slashed-zero' }}
    >
      {rule && <span className={`h-px w-8 shrink-0 ${ruleColor}`} aria-hidden />}
      {number && (
        <>
          <span className={`shrink-0 ${numberColor} font-medium`}>{number}</span>
          <span className={`h-1 w-1 rounded-full shrink-0 ${dotColor}`} aria-hidden />
        </>
      )}
      <span className={labelColor}>{children}</span>
    </div>
  );
}
