/**
 * DemoVideoModal — full-screen modal that plays a 75s product
 * UI simulation in place of a real demo video.
 *
 * Triggered from HeroDual's secondary CTA. ESC closes. While open,
 * body scroll is locked and initial focus moves to the close button;
 * focus is restored to the trigger when closing. Honors
 * prefers-reduced-motion (renders a tabbed static fallback instead of
 * the timeline). Timeline + raf only mount while the modal is open.
 */
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { useTimeline, type Act } from './useTimeline';
import { useBodyScrollLock } from '@/lib/useBodyScrollLock';
import { useFocusTrap } from './useFocusTrap';
import { DURATION_MS } from './demoScript';
import TopBar from './parts/TopBar';
import BottomBar from './parts/BottomBar';
import LeftPane from './parts/LeftPane';
import RightPane from './parts/RightPane';
import ReducedFallback from './parts/ReducedFallback';

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function DemoVideoModal({ open, onClose }: Props) {
  return createPortal(
    <AnimatePresence>
      {open && <ModalContent onClose={onClose} />}
    </AnimatePresence>,
    document.body,
  );
}

function ModalContent({ onClose }: { onClose: () => void }) {
  const timeline = useTimeline(DURATION_MS);
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const panelRef = useRef<HTMLDivElement>(null);
  const previouslyFocusedRef = useRef<HTMLElement | null>(null);

  const [reducedMotion, setReducedMotion] = useState(false);
  const [fallbackAct, setFallbackAct] = useState<Act>(1);

  useBodyScrollLock();
  useFocusTrap(panelRef);

  useEffect(() => {
    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
    setReducedMotion(mq.matches);
    const onChange = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
    mq.addEventListener('change', onChange);
    return () => mq.removeEventListener('change', onChange);
  }, []);

  // ESC + initial/restored focus. Mounted only while open because
  // ModalContent itself is gated by `{open && ...}` upstream.
  useEffect(() => {
    previouslyFocusedRef.current = document.activeElement as HTMLElement | null;

    // Defer focus to next frame so the close button is mounted + paintable.
    const focusFrame = requestAnimationFrame(() => {
      closeBtnRef.current?.focus();
    });

    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);

    return () => {
      cancelAnimationFrame(focusFrame);
      document.removeEventListener('keydown', onKey);
      // Restore focus to the element that opened the modal.
      previouslyFocusedRef.current?.focus?.();
    };
  }, [onClose]);

  return (
    <motion.div
      key="demo-modal"
      initial={{ opacity: 0 }}
      animate={{ opacity: 1 }}
      exit={{ opacity: 0 }}
      transition={{ duration: 0.2 }}
      className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-md p-4"
      onClick={onClose}
      role="presentation"
    >
      <motion.div
        ref={panelRef}
        initial={{ opacity: 0, scale: 0.96, y: 12 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.96, y: 12 }}
        transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
        className="relative w-full max-w-5xl aspect-[16/10] rounded-2xl overflow-hidden bg-brand-ink-950 border border-white/10 shadow-2xl flex flex-col"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-modal="true"
        aria-labelledby="demo-modal-title"
      >
        <TopBar
          ref={closeBtnRef}
          act={reducedMotion ? fallbackAct : timeline.act}
          onClose={onClose}
        />
        {reducedMotion ? (
          <ReducedFallback act={fallbackAct} onActChange={setFallbackAct} />
        ) : (
          <>
            <div className="flex-1 relative bg-gradient-to-br from-brand-ink-950 to-brand-ink-900 grid grid-cols-12 gap-px min-h-0">
              <LeftPane elapsedMs={timeline.elapsedMs} />
              <RightPane elapsedMs={timeline.elapsedMs} />
            </div>
            <BottomBar
              elapsedMs={timeline.elapsedMs}
              paused={timeline.paused}
              onPause={timeline.pause}
              onResume={timeline.resume}
              onRestart={timeline.restart}
            />
          </>
        )}
      </motion.div>
    </motion.div>
  );
}
