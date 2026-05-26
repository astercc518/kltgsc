/**
 * Regression tests for Pricing tableAdminNote link rendering.
 *
 * Verifies that the billing-docs link is rendered inline (not orphaned)
 * in all 5 supported languages. The plain .replace('billing docs', '')
 * pattern only matched English; this suite catches that regression.
 */
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { render, screen, act, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { LangProvider, type Lang } from '@/i18n';
import Pricing from './Pricing';

const STORAGE_KEY = 'tg1.lang';

// All supported languages — note 'zh-CN', not 'zh'
const LANGS: Lang[] = ['en', 'zh-CN', 'ja', 'ko', 'es'];

// Link-label patterns per language (used to find the <a> inside the note)
const LINK_PATTERN: Record<Lang, RegExp> = {
  en:     /billing\s+docs/i,
  'zh-CN': /billing\s*文档/i,
  ja:     /billing\s*ドキュメント/i,
  ko:     /billing\s*문서/i,
  es:     /docs\s+de\s+billing/i,
};

describe('Pricing tableAdminNote', () => {
  beforeEach(() => {
    localStorage.clear();
    // jsdom doesn't implement IntersectionObserver; stub it so Reveal renders.
    vi.stubGlobal('IntersectionObserver', class {
      observe    = vi.fn();
      unobserve  = vi.fn();
      disconnect = vi.fn();
    });
  });

  afterEach(() => {
    vi.unstubAllGlobals();
  });

  for (const lang of LANGS) {
    it(`renders the billing-docs link inline in ${lang}`, async () => {
      // Pre-seed localStorage so LangProvider picks up the right language
      // on its detectLang() useEffect call.
      localStorage.setItem(STORAGE_KEY, lang);

      await act(async () => {
        render(
          <MemoryRouter>
            <LangProvider>
              <Pricing />
            </LangProvider>
          </MemoryRouter>,
        );
      });

      // The unit-price table is collapsed by default — expand it.
      // The toggle button uses aria-expanded; find the one that is collapsed.
      const toggleBtn = screen.getByRole('button', { expanded: false });
      fireEvent.click(toggleBtn);

      // The admin note container must exist.
      const note = screen.getByTestId('pricing-table-admin-note');

      // Find the billing-docs link inside the note using the language-specific pattern.
      const pattern = LINK_PATTERN[lang];
      const links = Array.from(note.querySelectorAll('a')).filter((a) =>
        pattern.test(a.textContent ?? ''),
      );
      expect(links.length).toBeGreaterThanOrEqual(1);

      // No orphan English "billing docs" text outside a link.
      const linkText = links[0]?.textContent ?? '';
      const textWithoutLink = (note.textContent ?? '').replace(linkText, '');
      expect(textWithoutLink).not.toMatch(/billing docs/i);
    });
  }
});
