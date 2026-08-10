/**
 * Shared framer-motion variants used by landing sections.
 *
 * Pattern:
 *   <motion.div initial="hidden" whileInView="visible" viewport={REVEAL_VIEWPORT} variants={fadeUp}>
 *
 * For staggered grids:
 *   <motion.div variants={staggerContainer} initial="hidden" whileInView="visible" viewport={REVEAL_VIEWPORT}>
 *     {items.map(i => <motion.div variants={fadeUp} key={i.id} />)}
 *   </motion.div>
 *
 * Reduced motion is handled at the call site via framer-motion's
 * `useReducedMotion()`; when true, pass `transition={{ duration: 0 }}` so
 * elements render in final state immediately.
 */
import type { Variants, Transition } from 'framer-motion';

export const REVEAL_VIEWPORT = { once: true, margin: '-80px 0px -80px 0px' };

export const fadeUpEase = [0.22, 1, 0.36, 1] as const;

export const fadeUp: Variants = {
  hidden:  { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: fadeUpEase } },
};

export const staggerContainer: Variants = {
  hidden:  {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
};
