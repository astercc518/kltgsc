# Landing Polish PR-1 — Bug Fixes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix 5 P0 issues on the TG1.AI landing site (i18n splice bug, iOS scroll lock, fake live badge, useEffect variable shadow, fake status link) without changing any other behavior, on a new branch off `main`.

**Architecture:** Pure UI / i18n changes. Reuse the existing `useBodyScrollLock` hook (currently inside `DemoVideoModal/`) by lifting it to a shared `landing/src/lib/` path. Add Vitest coverage for the i18n bug across all 5 languages so the regression can't return.

**Tech Stack:** React 18 + TypeScript + Vite + Tailwind + Vitest + Testing Library. No backend changes.

**Spec reference:** [docs/superpowers/specs/2026-05-25-landing-polish-design.md](../specs/2026-05-25-landing-polish-design.md) — PR-1 section.

---

## Pre-flight

- [ ] **Step 0.1: Confirm `feature/landing-demo-modal` is merged**

Run: `git log main --oneline | grep -E "demo modal|landing-demo-modal" | head -3`
Expected: at least one commit from the demo modal branch on `main`. If not, STOP and tell the user — PR-1 must branch off the merged main, not before.

- [ ] **Step 0.2: Create the PR branch**

Run:
```bash
git checkout main
git pull --ff-only
git checkout -b fix/landing-p0-bugs
```
Expected: clean branch, no uncommitted changes.

- [ ] **Step 0.3: Verify tooling**

Run: `cd landing && npm install && npm test -- --run`
Expected: all existing tests pass (demo modal tests will be included). If anything fails on main, STOP and flag.

---

## Task 1: Lift `useBodyScrollLock` to shared lib

The Header mobile menu (Step 3) needs the same scroll-lock behavior as `DemoVideoModal`. Move the hook to a shared location first so both can use it.

**Files:**
- Create: `landing/src/lib/useBodyScrollLock.ts`
- Modify: `landing/src/components/DemoVideoModal/index.tsx` (update import)
- Delete: `landing/src/components/DemoVideoModal/useBodyScrollLock.ts`
- Test: `landing/src/components/DemoVideoModal/DemoVideoModal.test.tsx` (already exercises the hook — no edits needed, just confirms hook still works after move)

- [ ] **Step 1.1: Create the lib directory and move the file**

Run:
```bash
mkdir -p landing/src/lib
git mv landing/src/components/DemoVideoModal/useBodyScrollLock.ts landing/src/lib/useBodyScrollLock.ts
```
Expected: file moved, tracked by git.

- [ ] **Step 1.2: Update the DemoVideoModal import**

In `landing/src/components/DemoVideoModal/index.tsx`, find the line:
```ts
import { useBodyScrollLock } from './useBodyScrollLock';
```
Change to:
```ts
import { useBodyScrollLock } from '@/lib/useBodyScrollLock';
```

- [ ] **Step 1.3: Run existing tests + typecheck**

Run: `cd landing && npm test -- --run && npm run build`
Expected: all tests pass (DemoVideoModal scroll-lock test still green); TypeScript build clean. If the build complains about the import, double-check the `@/` alias resolves (it should — `vitest.config.ts` and `tsconfig` both have it).

- [ ] **Step 1.4: Commit**

```bash
git add landing/src/lib/useBodyScrollLock.ts landing/src/components/DemoVideoModal/index.tsx
git commit -m "refactor(landing): lift useBodyScrollLock to shared lib

So Header mobile menu can reuse it in the next commit."
```

---

## Task 2: Fix Pricing i18n `.replace` bug

Today `landing/src/sections/Pricing.tsx:140-141` does `t.pricing.tableAdminNote.replace('billing docs', '')` to splice out a link label, then renders `<a>billing docs</a>`. This only works in English; in zh/ja/ko/es the literal `'billing docs'` is not in the translation, so the full sentence renders followed by an orphaned "billing docs" link.

The fix is to change the i18n shape from a flat string to `{ before, linkLabel, after }` and split-render. This is also the pattern any future link-in-sentence should follow.

**Files:**
- Modify: `landing/src/i18n.ts` (type definition + 5 language blocks)
- Modify: `landing/src/sections/Pricing.tsx` (render logic)
- Test: `landing/src/sections/Pricing.test.tsx` (new file)

- [ ] **Step 2.1: Write the failing test first**

Create `landing/src/sections/Pricing.test.tsx`:

```tsx
import { describe, it, expect } from 'vitest';
import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Pricing from './Pricing';
import { LangProvider, type Lang } from '@/i18n';

const LANGS: Lang[] = ['en', 'zh', 'ja', 'ko', 'es'];

describe('Pricing tableAdminNote', () => {
  for (const lang of LANGS) {
    it(`renders the billing-docs link inline in ${lang}`, () => {
      render(
        <MemoryRouter>
          <LangProvider initial={lang}>
            <Pricing />
          </LangProvider>
        </MemoryRouter>,
      );
      // The link must exist exactly once, with the localized label.
      const links = screen.getAllByRole('link', { name: /billing|文档|ドキュメント|문서|docs/i });
      expect(links.length).toBeGreaterThanOrEqual(1);

      // There must be no orphan English "billing docs" floating outside a link
      // in non-English languages. We assert by checking the surrounding text
      // doesn't repeat the link label.
      const note = screen.getByTestId('pricing-table-admin-note');
      const linkText = links.find((l) => note.contains(l))?.textContent ?? '';
      const textWithoutLink = note.textContent?.replace(linkText, '') ?? '';
      expect(textWithoutLink).not.toMatch(/billing docs/);
    });
  }
});
```

Note: this test assumes `LangProvider` accepts an `initial` prop. If the current `i18n.ts` does not export `LangProvider` or doesn't accept `initial`, the test setup must be adjusted — see Step 2.2 below for the verification commands.

- [ ] **Step 2.2: Verify the test fails for the right reason**

Run: `cd landing && npm test -- --run src/sections/Pricing.test.tsx`
Expected:
- Either the test file fails to import (`LangProvider` missing / no `initial` prop) — meaning we need to inspect `i18n.ts`'s exports.
- Or the test runs and fails on at least one non-English language with the "orphan 'billing docs'" check.

If the import fails, run `grep -n "export" landing/src/i18n.ts | head -20` and adjust the test imports to match the actual exports (the test may need a `<I18nContext.Provider value={...}>` wrapper instead of a `LangProvider`).

The `data-testid="pricing-table-admin-note"` referenced by the test is added in Step 2.5 along with the renderer rewrite — until then the test will fail at `getByTestId`. This is acceptable: the failure proves the test is wired up. Step 2.6 is the assertion-pass checkpoint.

- [ ] **Step 2.3: Reshape the i18n type definition**

In `landing/src/i18n.ts`, find line ~99 (inside the `pricing` interface):
```ts
    tableAdminNote: string;     // "Admin can override any line per-customer for volume deals. See billing docs."
```
Change to:
```ts
    tableAdminNote: {
      before: string;            // "Admin can override any line per-customer for volume deals. See "
      linkLabel: string;         // "billing docs"
      after: string;             // "."
    };
```

- [ ] **Step 2.4: Update all 5 language blocks**

In each of the 5 language blocks, replace the `tableAdminNote` string with the structured form. Use grep to find each line first:

Run: `grep -n "tableAdminNote:" landing/src/i18n.ts`
Expected: 5 matches (one per language).

Replace each, language by language:

**en** (around line 409):
```ts
    tableAdminNote: {
      before: 'Admin can override any line per-customer for volume deals. See ',
      linkLabel: 'billing docs',
      after: '.',
    },
```

**zh** (around line 789):
```ts
    tableAdminNote: {
      before: '大客户可向 admin 申请单价覆盖，详见',
      linkLabel: 'billing 文档',
      after: '。',
    },
```

**ja** (around line 1154):
```ts
    tableAdminNote: {
      before: '大口取引は管理者が顧客ごとに単価を上書きできます。',
      linkLabel: 'billing ドキュメント',
      after: 'を参照。',
    },
```

**ko** (around line 1461):
```ts
    tableAdminNote: {
      before: '대량 거래는 관리자가 고객별로 단가를 재정의할 수 있습니다. ',
      linkLabel: 'billing 문서',
      after: ' 참조.',
    },
```

**es** (around line 1768):
```ts
    tableAdminNote: {
      before: 'Para grandes volúmenes, el admin puede sobrescribir cualquier línea por cliente. Ver ',
      linkLabel: 'docs de billing',
      after: '.',
    },
```

- [ ] **Step 2.5: Update the renderer**

In `landing/src/sections/Pricing.tsx:139-142`, replace:
```tsx
                <div className="px-6 py-3 bg-brand-ink-50 text-xs text-brand-ink-500">
                  {t.pricing.tableAdminNote.replace('billing docs', '')}
                  <a href={LINKS.docsBilling} className="text-brand-blue-500 underline underline-offset-2">billing docs</a>.
                </div>
```
With:
```tsx
                <div data-testid="pricing-table-admin-note" className="px-6 py-3 bg-brand-ink-50 text-xs text-brand-ink-500">
                  {t.pricing.tableAdminNote.before}
                  <a href={LINKS.docsBilling} className="text-brand-blue-500 underline underline-offset-2">{t.pricing.tableAdminNote.linkLabel}</a>
                  {t.pricing.tableAdminNote.after}
                </div>
```

- [ ] **Step 2.6: Run the test — verify it passes for all 5 languages**

Run: `cd landing && npm test -- --run src/sections/Pricing.test.tsx`
Expected: 5 tests pass (one per language). If any fail, the issue is almost always a stray `billing docs` literal in a translation — re-check Step 2.4.

- [ ] **Step 2.7: Typecheck + build**

Run: `cd landing && npm run build`
Expected: clean build. TypeScript will flag any language block where the shape doesn't match the new interface, so this is the safety net.

- [ ] **Step 2.8: Commit**

```bash
git add landing/src/i18n.ts landing/src/sections/Pricing.tsx landing/src/sections/Pricing.test.tsx
git commit -m "fix(landing/pricing): split-render billing-docs link across all 5 langs

The previous .replace('billing docs', '') only matched English, leaving
zh/ja/ko/es with the full sentence plus an orphan English link label.
Reshape tableAdminNote into {before, linkLabel, after} and split-render.

Add Pricing.test.tsx with one assertion per language so the regression
cannot return."
```

---

## Task 3: Header mobile menu — body scroll lock

When the mobile sheet opens, the page behind it currently scrolls on iOS Safari. Reuse the shared `useBodyScrollLock` hook from Task 1, but only when `mobileOpen` is true.

The hook as written locks on mount and unlocks on unmount — that fits exactly because the mobile sheet is conditionally rendered (`{mobileOpen && <div>...</div>}`), so mounting/unmounting maps 1:1 to open/close. Extract the sheet to a child component that calls the hook unconditionally; this is cleaner than adding an open-state branch to the hook.

**Files:**
- Modify: `landing/src/sections/Header.tsx`
- Test: `landing/src/sections/Header.test.tsx` (new file)

- [ ] **Step 3.1: Write the failing test first**

Create `landing/src/sections/Header.test.tsx`:

```tsx
import { describe, it, expect, afterEach } from 'vitest';
import { render, screen, fireEvent, cleanup } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import Header from './Header';

afterEach(() => {
  cleanup();
  document.body.style.overflow = '';
  document.body.style.position = '';
  document.body.style.top = '';
  document.body.style.width = '';
});

describe('Header mobile menu', () => {
  it('locks body scroll while open and restores on close', () => {
    render(
      <MemoryRouter>
        <Header />
      </MemoryRouter>,
    );

    expect(document.body.style.overflow).toBe('');

    fireEvent.click(screen.getByLabelText('Open menu'));
    expect(document.body.style.overflow).toBe('hidden');
    expect(document.body.style.position).toBe('fixed');

    fireEvent.click(screen.getByLabelText('Close menu'));
    expect(document.body.style.overflow).toBe('');
    expect(document.body.style.position).toBe('');
  });
});
```

- [ ] **Step 3.2: Run test, verify it fails**

Run: `cd landing && npm test -- --run src/sections/Header.test.tsx`
Expected: fails after clicking "Open menu", because the body styles never change.

- [ ] **Step 3.3: Extract a `MobileSheet` child component that calls the hook**

In `landing/src/sections/Header.tsx`, find the block `{mobileOpen && ( ... )}` at lines 111-156. Replace it with:
```tsx
      {mobileOpen && (
        <MobileSheet
          navLinks={navLinks}
          onClose={() => setMobileOpen(false)}
          signInLabel={t.nav.signIn}
          freeTrialLabel={t.nav.freeTrial}
        />
      )}
```

At the top of the file (after the existing imports), add:
```ts
import { useBodyScrollLock } from '@/lib/useBodyScrollLock';
```

At the bottom of the file (after the `Header` default export), add:
```tsx
interface MobileSheetProps {
  navLinks: { label: string; href: string }[];
  onClose: () => void;
  signInLabel: string;
  freeTrialLabel: string;
}

function MobileSheet({ navLinks, onClose, signInLabel, freeTrialLabel }: MobileSheetProps) {
  useBodyScrollLock();
  return (
    <div className="md:hidden fixed inset-0 z-50 bg-white">
      <div className="flex items-center justify-between px-6 h-16 border-b border-brand-ink-100">
        <BrandMark size="sm" />
        <button
          type="button"
          onClick={onClose}
          className="text-brand-ink-700 p-2"
          aria-label="Close menu"
        >
          <X className="w-6 h-6" />
        </button>
      </div>
      <nav className="flex flex-col gap-1 px-6 py-6 text-lg">
        {navLinks.map((l) => (
          <a
            key={l.href}
            href={l.href}
            onClick={onClose}
            className="py-3 text-brand-ink-700 hover:text-brand-blue-500"
          >
            {l.label}
          </a>
        ))}
        <a href={LINKS.signIn} className="py-3 text-brand-ink-700">
          {signInLabel}
        </a>
        <div className="py-4">
          <LangSwitcher />
        </div>
        <CTAButton
          variant="primary"
          href={LINKS.trial}
          trackEvent={Events.CTA_SIGNUP_CLICK}
          trackProps={{ source: 'header_mobile' }}
          noIcon
        >
          {freeTrialLabel}
        </CTAButton>
      </nav>
    </div>
  );
}
```

- [ ] **Step 3.4: Run the test — verify it passes**

Run: `cd landing && npm test -- --run src/sections/Header.test.tsx`
Expected: green.

- [ ] **Step 3.5: Run full suite + build**

Run: `cd landing && npm test -- --run && npm run build`
Expected: all tests pass, no TS errors.

- [ ] **Step 3.6: Commit**

```bash
git add landing/src/sections/Header.tsx landing/src/sections/Header.test.tsx
git commit -m "fix(landing/header): lock body scroll while mobile menu is open

Extract the mobile sheet to a MobileSheet child component that calls the
shared useBodyScrollLock hook (Task 1). Mounting on open + unmounting on
close maps 1:1 to lock/unlock, so iOS Safari no longer scrolls the page
behind the sheet."
```

---

## Task 4: Remove HeroDual `liveBadge`

User-locked decision: drop the badge entirely (JSX + i18n key + the `liveBadge: string` type field).

**Files:**
- Modify: `landing/src/sections/HeroDual.tsx`
- Modify: `landing/src/i18n.ts`

- [ ] **Step 4.1: Remove the JSX node**

In `landing/src/sections/HeroDual.tsx:43-55`, delete the entire `motion.div` containing the live status badge (the block beginning with `{/* Live status badge */}` through its closing `</motion.div>`).

- [ ] **Step 4.2: Remove the type-interface field**

In `landing/src/i18n.ts:53`, delete the line:
```ts
    liveBadge: string;         // "1,247 AI monitor rules running right now"
```

- [ ] **Step 4.3: Remove the 5 language-block entries**

Run: `grep -n "liveBadge:" landing/src/i18n.ts`
Expected: 5 matches.

Delete each `liveBadge: '...'` line (with its trailing comma). After this step, re-run the grep and expect 0 matches.

- [ ] **Step 4.4: Build + run all tests**

Run: `cd landing && npm run build && npm test -- --run`
Expected: clean. TypeScript catches any leftover reference to `liveBadge`.

- [ ] **Step 4.5: Commit**

```bash
git add landing/src/sections/HeroDual.tsx landing/src/i18n.ts
git commit -m "chore(landing/hero): remove fake liveBadge

The badge claimed a precise hardcoded number (1,247 AI monitor rules),
which reads as fabricated. Drop the JSX node, the i18n key, and the type
field across all 5 languages. Spec decision logged at
docs/superpowers/specs/2026-05-25-landing-polish-design.md."
```

---

## Task 5: Footer Status — change `<a href='#'>` to `<span>`

The green-dot "All systems normal" indicator is fine; the dead `href="#"` link is not. Convert to a non-interactive `<span>`. PR-4 will later move the indicator into the brand column when the 4th column gets deleted — for now, just make the link not lie.

**Files:**
- Modify: `landing/src/sections/Footer.tsx`

- [ ] **Step 5.1: Change the element**

In `landing/src/sections/Footer.tsx:114-120`, replace:
```tsx
            <a
              href="#"
              className="inline-flex items-center gap-2 text-sm hover:text-white transition-colors"
            >
              <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
              {t.footer.statusValue}
            </a>
```
With:
```tsx
            <span className="inline-flex items-center gap-2 text-sm">
              <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
              {t.footer.statusValue}
            </span>
```

- [ ] **Step 5.2: Build**

Run: `cd landing && npm run build`
Expected: clean.

- [ ] **Step 5.3: Commit**

```bash
git add landing/src/sections/Footer.tsx
git commit -m "fix(landing/footer): convert dead Status link to <span>

href='#' scrolled users to the top of the page. The indicator is
informational, not navigational — render as <span>. PR-4 will move it
into the brand column when the 4th footer column is deleted."
```

---

## Task 6: PricingCalculator — rename `t = setTimeout` shadow

`landing/src/sections/PricingCalculator.tsx:52-59` uses `const t = setTimeout(...)` inside an effect, shadowing the outer `const t = useT()`. No bug today, but it's a footgun the moment anyone references `t.*` inside the effect.

**Files:**
- Modify: `landing/src/sections/PricingCalculator.tsx`

- [ ] **Step 6.1: Rename**

In `landing/src/sections/PricingCalculator.tsx:52-59`, replace:
```ts
  useEffect(() => {
    if (tracked) return;
    const t = setTimeout(() => {
      track(Events.PRICING_CALC_USED, { leads, sends });
      setTracked(true);
    }, 1200);
    return () => clearTimeout(t);
  }, [leads, sends, tracked]);
```
With:
```ts
  useEffect(() => {
    if (tracked) return;
    const id = setTimeout(() => {
      track(Events.PRICING_CALC_USED, { leads, sends });
      setTracked(true);
    }, 1200);
    return () => clearTimeout(id);
  }, [leads, sends, tracked]);
```

- [ ] **Step 6.2: Build + test**

Run: `cd landing && npm run build && npm test -- --run`
Expected: clean.

- [ ] **Step 6.3: Commit**

```bash
git add landing/src/sections/PricingCalculator.tsx
git commit -m "refactor(landing/pricing-calc): rename setTimeout var to stop shadowing useT()"
```

---

## Task 7: Verification + PR creation

- [ ] **Step 7.1: Final clean build**

Run: `cd landing && npm test -- --run && npm run build`
Expected: all tests pass; no TS / lint errors.

- [ ] **Step 7.2: Manual smoke test — desktop**

Run: `cd landing && npm run dev`
Open http://localhost:5173 and verify:
- Hero no longer shows a "1,247 ..." badge.
- Footer "All systems normal" looks visually identical but doesn't react to hover/click.
- Pricing table footer: link to billing docs is in the right place (sentence reads naturally; no orphan "billing docs" string).
- Switch language to zh / ja / ko / es via the LangSwitcher; recheck the Pricing footer link in each.
- PricingCalculator slider still triggers the analytics debounce (network tab should show the `PRICING_CALC_USED` event after ~1.2s of stopped dragging).

- [ ] **Step 7.3: Manual smoke test — mobile menu**

Resize browser to <768px (or use device toolbar).
- Click the hamburger.
- Try to scroll the page behind the sheet: should NOT scroll.
- Close the sheet. Page scroll should be restored at the same position (not jumped to top).
- For real-device confidence: deploy to a preview URL or use BrowserStack on iOS Safari before merging.

- [ ] **Step 7.4: Push + open PR**

```bash
git push -u origin fix/landing-p0-bugs
gh pr create --base main --title "fix(landing): 5 P0 bug fixes (i18n splice, iOS scroll, fake badge, shadow, dead link)" --body "$(cat <<'EOF'
## Summary

PR-1 of the landing polish series — closes the 5 P0 issues from the audit.

- **i18n bug:** Pricing table footer's link was spliced via `.replace('billing docs', '')` which only matched English. Reshape to `{before, linkLabel, after}` and split-render. Vitest now covers all 5 languages.
- **Mobile scroll lock:** Header mobile menu now reuses the shared `useBodyScrollLock` hook (lifted from `DemoVideoModal/` to `landing/src/lib/`). Page behind the sheet no longer scrolls on iOS Safari.
- **Fake live badge:** Hero badge "1,247 AI monitor rules running right now" was hardcoded marketing fiction — removed entirely (JSX + i18n + type field × 5 langs).
- **Variable shadow:** `PricingCalculator` `const t = setTimeout(...)` no longer shadows the outer `t = useT()`.
- **Dead status link:** Footer "All systems normal" `<a href='#'>` → `<span>`. PR-4 will move the indicator into the brand column.

## Test plan

- [ ] CI green
- [ ] Manual desktop walk in 5 languages
- [ ] Mobile menu real-device test (iOS Safari)
- [ ] Lighthouse on `/` no worse than main

Spec: docs/superpowers/specs/2026-05-25-landing-polish-design.md

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```
Expected: PR URL returned.

---

## Done Definition

- All 7 tasks above complete.
- CI green on the PR.
- Manual desktop + mobile smoke tests pass.
- User signs off; merge to `main` lands the changes.
- PR-2 and PR-3 plans get written next.
