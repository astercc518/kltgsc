/**
 * DemoVideoModal — full-screen modal that plays a 75s product
 * UI simulation in place of a real demo video.
 *
 * Triggered from HeroDual's secondary CTA. ESC closes. While open,
 * body scroll is locked. Honors prefers-reduced-motion (renders a
 * tabbed static fallback instead of the timeline — added in task 10).
 */
import { useEffect } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { useTimeline } from './useTimeline';
import { DURATION_MS } from './demoScript';
import TopBar from './parts/TopBar';
import BottomBar from './parts/BottomBar';

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function DemoVideoModal({ open, onClose }: Props) {
  const timeline = useTimeline(DURATION_MS);

  // Body scroll lock + ESC handler
  useEffect(() => {
    if (!open) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      document.removeEventListener('keydown', onKey);
    };
  }, [open, onClose]);

  // Reset timeline whenever modal re-opens
  useEffect(() => {
    if (open) timeline.restart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          key="demo-modal"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-md p-4"
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-labelledby="demo-modal-title"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="relative w-full max-w-5xl aspect-[16/10] rounded-2xl overflow-hidden bg-brand-ink-950 border border-white/10 shadow-2xl flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <TopBar act={timeline.act} onClose={onClose} />
            <div className="flex-1 relative bg-gradient-to-br from-brand-ink-950 to-brand-ink-900 grid grid-cols-12 gap-px">
              {/* LeftPane / RightPane slot in later tasks */}
              <div className="col-span-7 p-4 text-white/30 text-xs font-mono">[left pane — task 7]</div>
              <div className="col-span-5 p-4 text-white/30 text-xs font-mono">[right pane — tasks 8, 9]</div>
            </div>
            <BottomBar
              elapsedMs={timeline.elapsedMs}
              paused={timeline.paused}
              onPause={timeline.pause}
              onResume={timeline.resume}
              onRestart={timeline.restart}
            />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
