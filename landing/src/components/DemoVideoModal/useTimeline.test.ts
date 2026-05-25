import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTimeline } from './useTimeline';

describe('useTimeline', () => {
  let rafCallbacks: Map<number, FrameRequestCallback>;
  let rafId: number;
  let now: number;

  beforeEach(() => {
    rafCallbacks = new Map();
    rafId = 0;
    now = 0;
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      rafId += 1;
      rafCallbacks.set(rafId, cb);
      return rafId;
    });
    vi.stubGlobal('cancelAnimationFrame', (id: number) => {
      rafCallbacks.delete(id);
    });
    vi.spyOn(performance, 'now').mockImplementation(() => now);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  /**
   * Advance the fake clock by `ms` milliseconds, breaking the advance into
   * 16ms chunks that each fire a single rAF callback. This mirrors real
   * browser behaviour where rAF fires at ~60fps (≈16ms/frame) and ensures
   * no single frame has a delta large enough to trigger the tab-hidden
   * threshold (250ms).
   */
  function tick(ms: number) {
    const FRAME_MS = 16;
    let remaining = ms;
    while (remaining > 0) {
      const chunk = Math.min(FRAME_MS, remaining);
      now += chunk;
      remaining -= chunk;
      const callbacks = Array.from(rafCallbacks.values());
      rafCallbacks.clear();
      act(() => callbacks.forEach((cb) => cb(now)));
    }
  }

  it('starts at elapsedMs=0, act=1, not paused', () => {
    const { result } = renderHook(() => useTimeline(75000));
    expect(result.current.elapsedMs).toBe(0);
    expect(result.current.act).toBe(1);
    expect(result.current.paused).toBe(false);
    expect(result.current.progress).toBe(0);
  });

  it('advances elapsed on each frame', () => {
    const { result } = renderHook(() => useTimeline(75000));
    tick(16);
    expect(result.current.elapsedMs).toBe(16);
    tick(34);
    expect(result.current.elapsedMs).toBe(50);
  });

  it('computes act from act boundaries [0, 15000, 35000, 55000, 75000]', () => {
    const { result } = renderHook(() => useTimeline(75000));
    tick(10000);
    expect(result.current.act).toBe(1);
    tick(10000); // 20000
    expect(result.current.act).toBe(2);
    tick(20000); // 40000
    expect(result.current.act).toBe(3);
    tick(20000); // 60000
    expect(result.current.act).toBe(4);
  });

  it('progress is elapsed/duration clamped 0-1', () => {
    const { result } = renderHook(() => useTimeline(1000));
    tick(500);
    expect(result.current.progress).toBeCloseTo(0.5);
    tick(2000);
    expect(result.current.progress).toBe(1);
  });

  it('pause freezes elapsed, resume continues from frozen point', () => {
    const { result } = renderHook(() => useTimeline(75000));
    tick(1000);
    act(() => result.current.pause());
    tick(500);
    expect(result.current.elapsedMs).toBe(1000);
    expect(result.current.paused).toBe(true);
    act(() => result.current.resume());
    tick(500);
    expect(result.current.elapsedMs).toBe(1500);
  });

  it('restart resets elapsed to 0 and resumes', () => {
    const { result } = renderHook(() => useTimeline(75000));
    tick(20000);
    act(() => result.current.restart());
    expect(result.current.elapsedMs).toBe(0);
    expect(result.current.paused).toBe(false);
    expect(result.current.act).toBe(1);
  });

  it('auto-pauses when reaching duration', () => {
    const { result } = renderHook(() => useTimeline(1000));
    tick(2000);
    expect(result.current.elapsedMs).toBe(1000);
    expect(result.current.paused).toBe(true);
  });

  it('ignores frame deltas > 250ms (tab hidden recovery)', () => {
    const { result } = renderHook(() => useTimeline(75000));
    tick(100);
    expect(result.current.elapsedMs).toBe(100);
    // Simulate a single rAF frame with a 5000ms gap (tab was hidden).
    // Bypass the chunked tick helper to fire one frame with a giant delta.
    now += 5000;
    const callbacks = Array.from(rafCallbacks.values());
    rafCallbacks.clear();
    act(() => callbacks.forEach((cb) => cb(now)));
    expect(result.current.elapsedMs).toBe(100); // frozen, not 5100
  });

  it('cancels raf on unmount', () => {
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame');
    const { unmount } = renderHook(() => useTimeline(75000));
    unmount();
    expect(cancelSpy).toHaveBeenCalled();
  });
});
