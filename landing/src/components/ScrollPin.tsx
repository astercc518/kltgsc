/**
 * ScrollPin — sticky container with normalized scroll progress (0..1).
 *
 * Wrap a tall section with multiple steps to get a "scrollytelling" effect:
 * the outer container is `min-h` long, the inner sticky panel snaps to the
 * viewport, and `<ScrollPin>` reports progress via render-prop so children
 * can switch artwork as the user scrolls.
 *
 * Usage:
 *   <ScrollPin steps={6} className="bg-brand-ink-900">
 *     {({ step, progress }) => (
 *       <div>Step {step + 1} of 6 — {(progress*100).toFixed(0)}%</div>
 *     )}
 *   </ScrollPin>
 */
import { motion, useScroll, useTransform } from 'framer-motion';
import { useRef, type ReactNode } from 'react';

type Render = (state: { step: number; progress: number }) => ReactNode;

type Props = {
  steps: number;
  className?: string;
  /** Tall outer height. Default `${steps * 80}vh`. */
  outerHeightVh?: number;
  children: Render;
};

export default function ScrollPin({ steps, className, outerHeightVh, children }: Props) {
  const ref = useRef<HTMLDivElement>(null);
  const { scrollYProgress } = useScroll({
    target: ref,
    offset: ['start start', 'end end'],
  });
  const stepProgress = useTransform(scrollYProgress, (p) => Math.min(steps - 1, Math.floor(p * steps)));
  const linear = useTransform(scrollYProgress, (p) => p);
  const outerHeight = `${outerHeightVh ?? steps * 80}vh`;

  // We can't read motion values during render directly; subscribe to a
  // local state-less render-prop via two child motion divs to capture
  // current step & progress. We use a small inline `Frame` that re-renders
  // on motion value change via `useMotionValueEvent`-like pattern.
  return (
    <section ref={ref} className={className} style={{ height: outerHeight }}>
      <div className="sticky top-0 h-screen flex items-center overflow-hidden">
        <Frame step={stepProgress} progress={linear}>
          {children}
        </Frame>
      </div>
    </section>
  );
}

/* Internal: subscribe to MotionValues so children re-render on change.
   Both step + progress merged into one state to avoid two React updates
   per scroll frame. */
import { useMotionValueEvent, type MotionValue } from 'framer-motion';
import { useState } from 'react';
function Frame({ step, progress, children }: {
  step: MotionValue<number>;
  progress: MotionValue<number>;
  children: Render;
}) {
  const [state, setState] = useState({ step: 0, progress: 0 });
  useMotionValueEvent(step, 'change', (v) => {
    setState((prev) => prev.step === v ? prev : { ...prev, step: v as number });
  });
  useMotionValueEvent(progress, 'change', (v) => {
    setState((prev) => prev.progress === v ? prev : { ...prev, progress: v as number });
  });
  return (
    <motion.div className="w-full">
      {children(state)}
    </motion.div>
  );
}
