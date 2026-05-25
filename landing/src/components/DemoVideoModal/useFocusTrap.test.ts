/**
 * Unit tests for useFocusTrap — exercises the Tab / Shift+Tab cycling
 * logic against a controlled container, avoiding integration-test
 * flakiness with framer-motion + jsdom focus quirks.
 */
import { describe, it, expect, beforeEach, afterEach } from 'vitest';
import { renderHook } from '@testing-library/react';
import { useFocusTrap } from './useFocusTrap';

describe('useFocusTrap', () => {
  let container: HTMLDivElement;
  let buttons: HTMLButtonElement[];

  beforeEach(() => {
    container = document.createElement('div');
    buttons = [];
    for (let i = 0; i < 3; i += 1) {
      const btn = document.createElement('button');
      btn.textContent = `btn-${i}`;
      // jsdom: offsetParent is null by default; spoof it as visible
      Object.defineProperty(btn, 'offsetParent', {
        get: () => container,
        configurable: true,
      });
      container.appendChild(btn);
      buttons.push(btn);
    }
    document.body.appendChild(container);
  });

  afterEach(() => {
    document.body.removeChild(container);
  });

  function trapWith() {
    const ref = { current: container };
    renderHook(() => useFocusTrap(ref));
  }

  function dispatchTab(shift = false) {
    const e = new KeyboardEvent('keydown', {
      key: 'Tab',
      shiftKey: shift,
      bubbles: true,
      cancelable: true,
    });
    container.dispatchEvent(e);
    return e;
  }

  it('Tab from last focusable wraps to first', () => {
    trapWith();
    buttons[2].focus();
    expect(document.activeElement).toBe(buttons[2]);

    const e = dispatchTab(false);
    expect(document.activeElement).toBe(buttons[0]);
    expect(e.defaultPrevented).toBe(true);
  });

  it('Shift+Tab from first focusable wraps to last', () => {
    trapWith();
    buttons[0].focus();
    expect(document.activeElement).toBe(buttons[0]);

    const e = dispatchTab(true);
    expect(document.activeElement).toBe(buttons[2]);
    expect(e.defaultPrevented).toBe(true);
  });

  it('Tab from a middle element lets browser handle it (no cycle)', () => {
    trapWith();
    buttons[1].focus();
    const e = dispatchTab(false);
    // Trap should NOT preventDefault; native Tab handles intra-container moves
    expect(e.defaultPrevented).toBe(false);
  });

  it('Tab from outside container pulls focus to first', () => {
    trapWith();
    const outside = document.createElement('button');
    document.body.appendChild(outside);
    outside.focus();

    dispatchTab(false);
    expect(document.activeElement).toBe(buttons[0]);

    document.body.removeChild(outside);
  });
});
