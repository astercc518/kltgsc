/**
 * Reveal — fade-up on viewport entry.
 *
 * Use to wrap any block that should animate in as the user scrolls.
 * Respects `prefers-reduced-motion` (handled via the global CSS rule in
 * tokens.css that nukes animation durations).
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
  /** Vertical offset (px) before the element settles. Default 16. */
  y?: number;
  /** Delay in ms before the in-view tween starts. */
  delay?: number;
  /** Re-trigger every time it scrolls back in. Default false (animate once). */
  once?: boolean;
  /** Pass-through Tailwind classes for the wrapper. */
  className?: string;
};

const buildVariants = (y: number): Variants => ({
  hidden:  { opacity: 0, y },
  visible: { opacity: 1, y: 0 },
});

export default function Reveal({
  children, y = 16, delay = 0, once = true, className,
}: Props) {
  const { ref, inView } = useInView({ triggerOnce: once, rootMargin: '-10% 0px' });
  return (
    <motion.div
      ref={ref}
      initial="hidden"
      animate={inView ? 'visible' : 'hidden'}
      variants={buildVariants(y)}
      transition={{
        duration: 0.6,
        delay: delay / 1000,
        ease: [0.22, 1, 0.36, 1],
      }}
      className={className}
    >
      {children}
    </motion.div>
  );
}
