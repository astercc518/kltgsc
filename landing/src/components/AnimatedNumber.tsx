/**
 * AnimatedNumber — count-up to target value once visible.
 *
 * For TrustBar stats like "1,000+ accounts", "10M+ messages/day".
 * Uses framer-motion's animate() to drive a number; updates DOM via
 * requestAnimationFrame, no React re-renders per frame.
 *
 * Pass `format` to control rendering (e.g. abbreviate millions, add %).
 */
import { animate } from 'framer-motion';
import { useEffect, useRef } from 'react';
import { useInView } from 'react-intersection-observer';

type Props = {
  value: number;
  /** Animation duration in seconds. Default 1.6s. */
  duration?: number;
  /** Optional formatter; default `n => n.toLocaleString()` */
  format?: (n: number) => string;
  /** Tailwind classes for the span. */
  className?: string;
  /** Prefix string rendered before the number (not animated). */
  prefix?: string;
  /** Suffix string rendered after the number (not animated). */
  suffix?: string;
};

const defaultFormat = (n: number) => Math.round(n).toLocaleString();

export default function AnimatedNumber({
  value, duration = 1.6, format = defaultFormat, className, prefix, suffix,
}: Props) {
  const elRef = useRef<HTMLSpanElement | null>(null);
  const { ref: inViewRef, inView } = useInView({ triggerOnce: true, rootMargin: '-10% 0px' });

  useEffect(() => {
    if (!inView || !elRef.current) return;
    const node = elRef.current;
    const controls = animate(0, value, {
      duration,
      ease: [0.22, 1, 0.36, 1],
      onUpdate(v) {
        node.textContent = format(v);
      },
    });
    return () => controls.stop();
  }, [inView, value, duration, format]);

  // Combine the two refs into one callback for the wrapper.
  const setRefs = (el: HTMLSpanElement | null) => {
    elRef.current = el;
    inViewRef(el);
  };

  return (
    <span className={className}>
      {prefix}
      <span ref={setRefs}>{format(0)}</span>
      {suffix}
    </span>
  );
}
