/**
 * Timeline hook for DemoVideoModal.
 *
 * Drives `elapsedMs` via requestAnimationFrame. Tab-hidden recovery
 * (deltas > 250ms) freezes time instead of jumping. Auto-pauses at
 * duration; restart resets to 0 and resumes.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

/** Boundaries that split the 75s timeline into 4 acts. */
export const ACT_BOUNDARIES = [0, 15000, 35000, 55000, 75000] as const;

export type Act = 1 | 2 | 3 | 4;

export interface Timeline {
  elapsedMs: number;
  progress: number;
  act: Act;
  paused: boolean;
  pause: () => void;
  resume: () => void;
  restart: () => void;
}

const TAB_HIDDEN_THRESHOLD_MS = 250;

function actFromElapsed(elapsed: number): Act {
  if (elapsed < ACT_BOUNDARIES[1]) return 1;
  if (elapsed < ACT_BOUNDARIES[2]) return 2;
  if (elapsed < ACT_BOUNDARIES[3]) return 3;
  return 4;
}

export function useTimeline(durationMs: number): Timeline {
  const [elapsedMs, setElapsedMs] = useState(0);
  const [paused, setPaused] = useState(false);
  const lastTickRef = useRef<number>(-1);
  const rafRef = useRef<number | null>(null);
  const pausedRef = useRef(false);
  const elapsedRef = useRef(0);

  pausedRef.current = paused;
  elapsedRef.current = elapsedMs;

  useEffect(() => {
    // Initialize lastTickRef at mount time so the first RAF frame
    // computes a meaningful delta from the hook's start timestamp.
    lastTickRef.current = performance.now();

    const tick = (ts: number) => {
      if (pausedRef.current) {
        lastTickRef.current = ts;
        rafRef.current = requestAnimationFrame(tick);
        return;
      }
      const delta = ts - lastTickRef.current;
      lastTickRef.current = ts;
      // Tab-hidden recovery: skip frames where the browser was hidden or
      // throttled. A single rAF delta > 250ms indicates the tab was
      // backgrounded; freeze time rather than jumping forward.
      if (delta > TAB_HIDDEN_THRESHOLD_MS) {
        rafRef.current = requestAnimationFrame(tick);
        return;
      }
      const next = Math.min(elapsedRef.current + delta, durationMs);
      elapsedRef.current = next;
      setElapsedMs(next);
      if (next >= durationMs) {
        setPaused(true);
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      lastTickRef.current = -1;
    };
  }, [durationMs]);

  const pause = useCallback(() => setPaused(true), []);
  const resume = useCallback(() => {
    // Reset lastTickRef to now so the paused interval isn't counted.
    lastTickRef.current = performance.now();
    setPaused(false);
  }, []);
  const restart = useCallback(() => {
    elapsedRef.current = 0;
    lastTickRef.current = performance.now();
    setElapsedMs(0);
    setPaused(false);
  }, []);

  return {
    elapsedMs,
    progress: durationMs > 0 ? Math.min(elapsedMs / durationMs, 1) : 0,
    act: actFromElapsed(elapsedMs),
    paused,
    pause,
    resume,
    restart,
  };
}
