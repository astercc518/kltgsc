/**
 * CountUp — animated number ticker.
 *
 * Parses values like "1,000+", "99.9%", "768-dim", "USDT" into
 * { prefix, numeric, suffix } and tweens the numeric part via RAF
 * when the element first enters the viewport.
 *
 * Non-numeric values (no digits) are rendered as-is.
 *
 * Respects prefers-reduced-motion: jumps to final value immediately.
 */
import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'framer-motion';

type Props = {
  value: string;
  durationMs?: number;   // default 1200
  className?: string;
};

type Parsed =
  | { kind: 'text';    raw: string }
  | { kind: 'number';  prefix: string; numeric: number; decimals: number; suffix: string };

function parse(value: string): Parsed {
  // Match optional non-digit prefix, the first numeric run (with optional decimal & commas),
  // and an optional non-digit suffix.
  const m = value.match(/^([^\d.,-]*)(-?[\d,]+(?:\.\d+)?)(.*)$/);
  if (!m) return { kind: 'text', raw: value };
  const [, prefix, numStr, suffix] = m;
  const cleaned = numStr.replace(/,/g, '');
  const numeric = Number(cleaned);
  if (Number.isNaN(numeric)) return { kind: 'text', raw: value };
  const decimals = (cleaned.split('.')[1] ?? '').length;
  return { kind: 'number', prefix, numeric, decimals, suffix };
}

function format(n: number, decimals: number, sample: string): string {
  // Preserve thousands-separator if the original had one.
  const hasComma = sample.includes(',');
  const fixed = n.toFixed(decimals);
  if (!hasComma) return fixed;
  const [intPart, decPart] = fixed.split('.');
  const withCommas = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return decPart ? `${withCommas}.${decPart}` : withCommas;
}

export default function CountUp({ value, durationMs = 1200, className }: Props) {
  const parsed = parse(value);
  const reduce = useReducedMotion();
  const ref = useRef<HTMLSpanElement | null>(null);
  const [display, setDisplay] = useState(() =>
    parsed.kind === 'number' && !reduce
      ? `${parsed.prefix}${format(0, parsed.decimals, String(parsed.numeric))}${parsed.suffix}`
      : value
  );
  const startedRef = useRef(false);

  useEffect(() => {
    if (parsed.kind !== 'number') return;
    if (reduce || durationMs === 0) {
      setDisplay(value);
      return;
    }
    const el = ref.current;
    if (!el) return;

    const io = new IntersectionObserver((entries) => {
      const entry = entries[0];
      if (!entry?.isIntersecting || startedRef.current) return;
      startedRef.current = true;
      io.disconnect();

      const startTs = performance.now();
      const tick = (now: number) => {
        const t = Math.min(1, (now - startTs) / durationMs);
        const eased = 1 - Math.pow(1 - t, 3);  // ease-out cubic
        const current = parsed.numeric * eased;
        const raw = String(parsed.numeric);
        setDisplay(`${parsed.prefix}${format(current, parsed.decimals, raw)}${parsed.suffix}`);
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }, { threshold: 0.2 });

    io.observe(el);
    return () => io.disconnect();
  }, [parsed, reduce, durationMs, value]);

  return <span ref={ref} className={className}>{display}</span>;
}
