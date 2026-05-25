/**
 * Integration tests for DemoVideoModal lifecycle: body scroll lock,
 * ESC handling, initial focus on close button, focus restoration.
 *
 * Focus trap cycling has its own hook-level coverage in
 * useFocusTrap.test.ts; tests here cover the modal end-to-end.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { LangProvider } from '@/i18n';
import DemoVideoModal from './index';

function wrap(open: boolean, onClose: () => void) {
  return render(
    <LangProvider>
      <DemoVideoModal open={open} onClose={onClose} />
    </LangProvider>,
  );
}

describe('DemoVideoModal', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', (query: string) => ({
      matches: false,
      media: query,
      onchange: null,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      addListener: vi.fn(),
      removeListener: vi.fn(),
      dispatchEvent: vi.fn(),
    }));
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    document.body.style.overflow = '';
    document.body.style.position = '';
    document.body.style.top = '';
    document.body.style.width = '';
  });

  it('renders nothing when open=false', () => {
    wrap(false, () => {});
    expect(screen.queryByRole('dialog')).toBeNull();
  });

  it('renders dialog when open=true', () => {
    wrap(true, () => {});
    expect(screen.getByRole('dialog')).toBeInTheDocument();
  });

  it('locks body scroll while open and restores after close+unmount', async () => {
    const { rerender, unmount } = wrap(true, () => {});
    expect(document.body.style.overflow).toBe('hidden');
    expect(document.body.style.position).toBe('fixed');

    // Trigger exit animation
    rerender(
      <LangProvider>
        <DemoVideoModal open={false} onClose={() => {}} />
      </LangProvider>,
    );
    // Force-unmount to bypass framer-motion exit animation latency in jsdom
    unmount();

    await waitFor(() => {
      expect(document.body.style.overflow).toBe('');
      expect(document.body.style.position).toBe('');
    });
  });

  it('calls onClose when ESC is pressed', () => {
    const onClose = vi.fn();
    wrap(true, onClose);
    fireEvent.keyDown(document, { key: 'Escape' });
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('does NOT call onClose when clicking the panel itself', () => {
    const onClose = vi.fn();
    wrap(true, onClose);
    const dialog = screen.getByRole('dialog');
    fireEvent.click(dialog);
    expect(onClose).toHaveBeenCalledTimes(0);
  });

  it('calls onClose when clicking the backdrop scrim', () => {
    const onClose = vi.fn();
    wrap(true, onClose);
    const dialog = screen.getByRole('dialog');
    const backdrop = dialog.parentElement!;
    fireEvent.click(backdrop);
    expect(onClose).toHaveBeenCalledTimes(1);
  });

  it('moves focus to the close button after open', async () => {
    wrap(true, () => {});
    await act(async () => {
      await new Promise((r) => requestAnimationFrame(() => r(null)));
    });
    const closeBtn = screen.getByRole('button', {
      name: /close demo|关闭演示|デモを閉じる|데모 닫기|cerrar demo/i,
    });
    expect(document.activeElement).toBe(closeBtn);
  });

  it('restores focus to the previously focused element on unmount', async () => {
    const trigger = document.createElement('button');
    trigger.textContent = 'open me';
    document.body.appendChild(trigger);
    trigger.focus();
    expect(document.activeElement).toBe(trigger);

    const { unmount } = wrap(true, () => {});
    await act(async () => {
      await new Promise((r) => requestAnimationFrame(() => r(null)));
    });
    expect(document.activeElement).not.toBe(trigger);

    unmount();
    expect(document.activeElement).toBe(trigger);

    document.body.removeChild(trigger);
  });
});
