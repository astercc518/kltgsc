import { render, screen, act } from '@testing-library/react';
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest';
import CountUp from '../CountUp';

describe('CountUp value parsing', () => {
  beforeEach(() => {
    // Mock IntersectionObserver to fire "in view" immediately
    class IO {
      callback: IntersectionObserverCallback;
      constructor(cb: IntersectionObserverCallback) { this.callback = cb; }
      observe(target: Element) {
        this.callback(
          [{ isIntersecting: true, target } as IntersectionObserverEntry],
          this as unknown as IntersectionObserver,
        );
      }
      unobserve() {}
      disconnect() {}
      takeRecords() { return []; }
      root = null; rootMargin = ''; thresholds = [];
    }
    vi.stubGlobal('IntersectionObserver', IO);
    vi.useFakeTimers();
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
  });

  it('renders non-numeric values as-is', () => {
    render(<CountUp value="USDT" />);
    expect(screen.getByText('USDT')).toBeInTheDocument();
  });

  it('parses "1,000+" prefix-less suffix-plus', () => {
    render(<CountUp value="1,000+" durationMs={0} />);
    act(() => { vi.advanceTimersByTime(50); });
    expect(screen.getByText('1,000+')).toBeInTheDocument();
  });

  it('parses "99.9%" suffix-percent', () => {
    render(<CountUp value="99.9%" durationMs={0} />);
    act(() => { vi.advanceTimersByTime(50); });
    expect(screen.getByText('99.9%')).toBeInTheDocument();
  });

  it('parses "768-dim" prefix-numeric suffix-text', () => {
    render(<CountUp value="768-dim" durationMs={0} />);
    act(() => { vi.advanceTimersByTime(50); });
    expect(screen.getByText('768-dim')).toBeInTheDocument();
  });
});
