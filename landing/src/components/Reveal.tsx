/**
 * Reveal — fade-up on viewport entry.
 *
 * Use to wrap any block that should animate in as the user scrolls.
 * Respects `prefers-reduced-motion` (handled via the global CSS rule in
 * tokens.css that nukes animation durations).
 *
 * Polish notes (2026-05-27 round 7):
 *   - Easing tightened to snap curve [0.16, 1, 0.3, 1] matching the
 *     hero / FinalCTA reveal motion. Previous [0.22, 1, 0.36, 1] was
 *     a touch slower and made the page feel hesitant.
 *   - Default y offset reduced from 16px → 12px so the parallax feels
 *     like a settle, not a paragraph-break.
 *   - Default duration 0.6s → 0.7s but the snap curve front-loads the
 *     velocity so it still reads fast.
 *   - rootMargin tightened from `-10% 0px` to `-12% 0px 0px` — slightly
 *     later trigger so the reveal happens after the user actually sees
 *     the element start to enter (less "ghost reveal" at the bottom).
 *
 * Usage:
 *   <Reveal>...</Reveal>           // 0ms delay
 *   <Reveal delay={120}>...</Reveal>
 *   <Reveal y={32} once={false}>...</Reveal>
 */
import { motion, type Variants } from 'framer-motion';
import { useInView } from 'react-intersection-observer';
import type { ReactNode } from 'react';

type Props = {
  children: ReactNode;
  /** Vertical offset (px) before the element settles. Default 12. */
  y?: number;
  /** Delay in ms before the in-view tween starts. */
  delay?: number;
  /** Re-trigger every time it scrolls back in. Default false (animate once). */
  once?: boolean;
  /** Pass-through Tailwind classes for the wrapper. */
  className?: string;
};

const SNAP = [0.16, 1, 0.3, 1] as const;

const buildVariants = (y: number): Variants => ({
  hidden:  { opacity: 0, y },
  visible: { opacity: 1, y: 0 },
});

export default function Reveal({
  children, y = 12, delay = 0, once = true, className,
}: Props) {
  const { ref, inView } = useInView({
    triggerOnce: once,
    rootMargin: '-12% 0px 0px',
  });
  return (
    <motion.div
      ref={ref}
      initial="hidden"
      animate={inView ? 'visible' : 'hidden'}
      variants={buildVariants(y)}
      transition={{
        duration: 0.7,
        delay: delay / 1000,
        ease: SNAP,
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
