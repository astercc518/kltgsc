/**
 * SectionDivider — fine hairline with cross terminus marks at each end.
 *
 * Renders as a 1px horizontal rule with small "+" markers 32px from
 * each edge (like a blueprint or technical drawing). Use between
 * sections that share a surface color so the seam reads intentional
 * rather than absent.
 *
 *      +─────────────────────────────────────────+
 *
 * Auto-adapts color to surface via the `tone` prop.
 */
type Tone = 'dark' | 'light';

type Props = {
  tone?: Tone;
  className?: string;
};

export default function SectionDivider({ tone = 'light', className }: Props) {
  const ruleColor = tone === 'dark' ? 'bg-line-medium' : 'bg-brand-ink-200';
  const markColor = tone === 'dark' ? 'text-white/35' : 'text-brand-ink-400';

  return (
    <div
      aria-hidden
      className={['relative w-full max-w-container mx-auto px-6', className || ''].join(' ')}
    >
      <div className="relative h-px">
        <div className={`absolute inset-x-8 top-0 h-px ${ruleColor}`} />
        <span
          className={`absolute left-6 top-0 -translate-y-1/2 font-mono text-[10px] leading-none ${markColor}`}
          style={{ fontVariantNumeric: 'tabular-nums' }}
        >
          +
        </span>
        <span
          className={`absolute right-6 top-0 -translate-y-1/2 font-mono text-[10px] leading-none ${markColor}`}
          style={{ fontVariantNumeric: 'tabular-nums' }}
        >
          +
        </span>
      </div>
    </div>
  );
}
