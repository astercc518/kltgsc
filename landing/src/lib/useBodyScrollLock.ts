/**
 * Body scroll lock that handles iOS Safari + multi-instance coordination.
 *
 * Plain `body.style.overflow = 'hidden'` does not stop touch-scroll on iOS
 * Safari; the page behind the modal still moves with momentum. The fix is
 * to additionally set `position: fixed` and cache + restore `window.scrollY`.
 *
 * Multiple modals can mount simultaneously (in tests, or if a future A/B
 * flow opens two at once). A module-level ref count ensures the original
 * scroll state is captured only on the first lock and restored only after
 * the last unlock.
 */
import { useEffect } from 'react';

interface SavedState {
  bodyOverflow: string;
  bodyPosition: string;
  bodyTop: string;
  bodyWidth: string;
  scrollY: number;
}

let lockCount = 0;
let saved: SavedState | null = null;

function apply() {
  const scrollY = window.scrollY;
  saved = {
    bodyOverflow: document.body.style.overflow,
    bodyPosition: document.body.style.position,
    bodyTop: document.body.style.top,
    bodyWidth: document.body.style.width,
    scrollY,
  };
  document.body.style.overflow = 'hidden';
  document.body.style.position = 'fixed';
  document.body.style.top = `-${scrollY}px`;
  document.body.style.width = '100%';
}

function restore() {
  if (!saved) return;
  document.body.style.overflow = saved.bodyOverflow;
  document.body.style.position = saved.bodyPosition;
  document.body.style.top = saved.bodyTop;
  document.body.style.width = saved.bodyWidth;
  window.scrollTo(0, saved.scrollY);
  saved = null;
}

export function useBodyScrollLock(): void {
  useEffect(() => {
    if (lockCount === 0) apply();
    lockCount += 1;
    return () => {
      lockCount -= 1;
      if (lockCount === 0) restore();
    };
  }, []);
}
