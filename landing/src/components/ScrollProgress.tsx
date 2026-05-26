/**
 * ScrollProgress — 2px bar at the top of the page tracking scroll
 * position. Reads as a fine detail (not a chrome element) — gradient
 * pill that fills left-to-right as you scroll the document.
 *
 * Uses requestAnimationFrame instead of scroll listener so it stays
 * smooth on long pages. Single setState per RAF tick.
 */
import { useEffect, useState } from 'react';

export default function ScrollProgress() {
  const [progress, setProgress] = useState(0);

  useEffect(() => {
    let raf = 0;
    let pending = false;

    const compute = () => {
      pending = false;
      const docH = document.documentElement.scrollHeight - window.innerHeight;
      if (docH <= 0) {
        setProgress(0);
        return;
      }
      const pct = Math.min(1, Math.max(0, window.scrollY / docH));
      setProgress(pct);
    };

    const onScroll = () => {
      if (pending) return;
      pending = true;
      raf = requestAnimationFrame(compute);
    };

    compute();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => {
      window.removeEventListener('scroll', onScroll);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div
      aria-hidden
      className="fixed inset-x-0 top-0 z-50 h-[2px] pointer-events-none"
    >
      <div
        className="h-full bg-gradient-to-r from-brand-blue-500 via-brand-blue-400 to-brand-purple-500 transition-[width] duration-100 ease-out"
        style={{
          width: `${progress * 100}%`,
          boxShadow: progress > 0 ? '0 0 12px rgba(0,102,255,0.45)' : 'none',
        }}
      />
    </div>
  );
}
