# Landing Dark Unification + Premium Polish — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Unify all 12 landing sections to a 3-tier dark tonal system, add Linear-style scroll/hover/shimmer/count-up motion, and place aurora gradient orbs at hero + final CTA.

**Architecture:** Pure CSS for tonal layers and aurora; reuse existing `framer-motion` (already in deps) for `whileInView` scroll reveals and stagger; one bespoke `CountUp` component for stat tickers. No new npm dependencies. All animations respect `prefers-reduced-motion` via framer-motion's `useReducedMotion()` and existing global CSS guard in `tokens.css`.

**Tech Stack:** React 18 · TypeScript · Tailwind (darkMode: class) · framer-motion (existing) · Vite · IntersectionObserver (via framer's whileInView).

**Spec:** [docs/superpowers/specs/2026-05-26-landing-dark-unify-premium-design.md](../specs/2026-05-26-landing-dark-unify-premium-design.md)

**Branch:** `feat/landing-dark-unify` off `main`.

---

## File Map

```
landing/
├── src/
│   ├── styles/
│   │   └── tokens.css                    MODIFY  (add aurora keyframes)
│   ├── tailwind.config.js                MODIFY  (add surface/fg/border tokens + shimmer keyframes)
│   ├── lib/
│   │   └── motionVariants.ts             CREATE  (shared fadeUp + staggerContainer variants)
│   ├── components/
│   │   ├── AuroraBlob.tsx                CREATE  (positioned conic-gradient blob, optional drift)
│   │   ├── CountUp.tsx                   CREATE  (RAF-tweened number with prefix/suffix)
│   │   └── CTAButton.tsx                 MODIFY  (add shimmer-on-hover variant)
│   └── sections/
│       ├── HeroDual.tsx                  MODIFY  (add aurora blobs, keep existing framer-motion intact)
│       ├── TrustBar.tsx                  MODIFY  (re-tokenize, wire CountUp to numeric stats)
│       ├── ProductSelfServe.tsx          MODIFY  (light → L1/L2, scroll reveal)
│       ├── ProductAIAssistant.tsx        MODIFY  (re-tokenize, scroll reveal)
│       ├── HowItWorks.tsx                MODIFY  (white outer → L0, re-tokenize text/cards)
│       ├── Pricing.tsx                   MODIFY  (white → L1/L2, scroll-reveal stagger, hover lift)
│       ├── PricingCalculator.tsx         MODIFY  (ink-50 → L0/L2, scroll reveal)
│       ├── UseCases.tsx                  MODIFY  (blue-50/purple-50 → L1 + tinted L2)
│       ├── Security.tsx                  MODIFY  (white → L1, scroll reveal)
│       ├── FAQ.tsx                       MODIFY  (ink-50/100 → L1/L2, item reveal stagger)
│       ├── FinalCTA.tsx                  MODIFY  (add small aurora blob, re-tokenize)
│       └── Footer.tsx                    MODIFY  (re-tokenize text colors)
└── src/components/
    └── __tests__/CountUp.test.tsx        CREATE  (unit test for format parsing)
```

**Existing references (do not modify, but read for context):**
- `landing/tailwind.config.js:38-49` — ink palette (use `ink-950` as L0, `ink-900` as L2, add new `surface-1` for L1)
- `landing/src/sections/HeroDual.tsx:21-27` — existing `fadeUp` variant pattern (will be extracted into shared file)
- `landing/src/styles/tokens.css:59-66` — existing global `prefers-reduced-motion` guard (already kills CSS animations; CountUp and framer-motion need own opt-out)

---

## Token Decisions (resolves spec hex ambiguity)

The spec proposed L0/L1/L2 hex values, but the codebase already has `ink-950 #020617` and `ink-900 #0F172A`. To minimize churn and reuse existing tokens:

| Layer | Color | Source | Tailwind class |
|---|---|---|---|
| L0 base | `#020617` | existing `ink-950` | `bg-brand-ink-950` |
| L1 surface | `#0A0F1E` | **new** `surface-1` | `bg-surface-1` |
| L2 elevated | `#0F172A` | existing `ink-900` | `bg-brand-ink-900` |

Text/border tokens are new:

| Token | Hex / value | Tailwind class |
|---|---|---|
| `fg.primary` | `#F0F2F8` | `text-fg-primary` |
| `fg.secondary` | `#8B92A8` | `text-fg-secondary` |
| `fg.muted` | `#5B6178` | `text-fg-muted` |
| `border.subtle` | `rgba(255,255,255,0.08)` | `border-line-subtle` |
| `border.strong` | `rgba(255,255,255,0.14)` | `border-line-strong` |

---

## Task 1: Add new color + animation tokens to Tailwind config

**Files:**
- Modify: `landing/tailwind.config.js:36-49` (extend `colors` block) + `:85-92` (extend animations/keyframes)

- [ ] **Step 1: Add `surface`, `fg`, `line` color groups + shimmer keyframes**

Open `landing/tailwind.config.js`. Inside `theme.extend.colors`, **after** the closing `}` of the `brand` group (line 50), add:

```js
        surface: {
          1: '#0A0F1E',  // L1 — sits between ink-950 (#020617) and ink-900 (#0F172A)
        },
        fg: {
          primary:   '#F0F2F8',
          secondary: '#8B92A8',
          muted:     '#5B6178',
        },
        line: {
          subtle: 'rgba(255,255,255,0.08)',
          strong: 'rgba(255,255,255,0.14)',
        },
```

Inside `theme.extend.animation`, **add** these entries (keep existing `fade-up` and `pulse-soft`):

```js
        'aurora-drift':   'auroraDrift 80s ease-in-out infinite',
        'aurora-drift-2': 'auroraDrift2 90s ease-in-out infinite',
        'shimmer':        'shimmer 700ms ease-in-out',
        'count-fade':     'fadeIn 0.4s ease-out both',
```

Inside `theme.extend.keyframes`, **add** these entries (keep existing `fadeUp` and `pulseSoft`):

```js
        auroraDrift: {
          '0%, 100%': { transform: 'translate3d(0, 0, 0)' },
          '50%':      { transform: 'translate3d(40px, -30px, 0)' },
        },
        auroraDrift2: {
          '0%, 100%': { transform: 'translate3d(0, 0, 0)' },
          '50%':      { transform: 'translate3d(-30px, 40px, 0)' },
        },
        shimmer: {
          '0%':   { backgroundPosition: '-200% 0' },
          '100%': { backgroundPosition: '200% 0' },
        },
        fadeIn: {
          '0%':   { opacity: '0' },
          '100%': { opacity: '1' },
        },
```

- [ ] **Step 2: Verify Tailwind compiles**

Run: `cd landing && npm run build`
Expected: build succeeds, no Tailwind errors in stdout.

- [ ] **Step 3: Commit**

```bash
git add landing/tailwind.config.js
git commit -m "feat(landing/tokens): add dark surface/fg/line + aurora & shimmer keyframes"
```

---

## Task 2: Create shared motion variants module

**Files:**
- Create: `landing/src/lib/motionVariants.ts`

- [ ] **Step 1: Write the module**

```ts
/**
 * Shared framer-motion variants used by landing sections.
 *
 * Pattern:
 *   <motion.div initial="hidden" whileInView="visible" viewport={REVEAL_VIEWPORT} variants={fadeUp}>
 *
 * For staggered grids:
 *   <motion.div variants={staggerContainer} initial="hidden" whileInView="visible" viewport={REVEAL_VIEWPORT}>
 *     {items.map(i => <motion.div variants={fadeUp} key={i.id} />)}
 *   </motion.div>
 *
 * Reduced motion is handled at the call site via framer-motion's
 * `useReducedMotion()`; when true, pass `transition={{ duration: 0 }}` so
 * elements render in final state immediately.
 */
import type { Variants, Transition } from 'framer-motion';

export const REVEAL_VIEWPORT = { once: true, margin: '-80px 0px -80px 0px' };

export const fadeUpEase: Transition['ease'] = [0.22, 1, 0.36, 1];

export const fadeUp: Variants = {
  hidden:  { opacity: 0, y: 12 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.4, ease: fadeUpEase } },
};

export const staggerContainer: Variants = {
  hidden:  {},
  visible: { transition: { staggerChildren: 0.08, delayChildren: 0.05 } },
};
```

- [ ] **Step 2: Typecheck**

Run: `cd landing && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add landing/src/lib/motionVariants.ts
git commit -m "feat(landing): add shared fadeUp + stagger motion variants"
```

---

## Task 3: Create AuroraBlob component

**Files:**
- Create: `landing/src/components/AuroraBlob.tsx`

- [ ] **Step 1: Write the component**

```tsx
/**
 * AuroraBlob — soft conic-gradient orb used as atmospheric backdrop.
 *
 * Parent must be `position: relative` and `overflow: hidden`. Blob is
 * absolutely positioned, pointer-events disabled, z-index 0. Pair with
 * higher-z content above.
 *
 * Visual targets (from spec):
 *   Hero blob A:  600px, color="blue",   blur=200, opacity=0.35, drift=true
 *   Hero blob B:  700px, color="purple", blur=240, opacity=0.30, drift=true, driftAlt
 *   FinalCTA:     500px, color="mixed",  blur=180, opacity=0.25, drift=false
 */
import type { CSSProperties } from 'react';

type Color = 'blue' | 'purple' | 'mixed';

type Props = {
  color: Color;
  size: number;            // px, applied to both width and height
  blur: number;            // px
  opacity?: number;        // 0..1, default 0.3
  drift?: boolean;         // animate via auroraDrift keyframes
  driftAlt?: boolean;      // use the alternate (asymmetric) drift loop
  /** top/right/bottom/left in CSS units, e.g. '20%', '-10rem' */
  top?: string;
  right?: string;
  bottom?: string;
  left?: string;
  className?: string;
};

const GRADIENT: Record<Color, string> = {
  blue:   'conic-gradient(from 180deg at 50% 50%, #0066FF 0deg, transparent 200deg)',
  purple: 'conic-gradient(from 0deg   at 50% 50%, #A855F7 0deg, transparent 220deg)',
  mixed:  'conic-gradient(from 90deg  at 50% 50%, #0066FF 0deg, #A855F7 180deg, transparent 320deg)',
};

export default function AuroraBlob({
  color, size, blur, opacity = 0.3,
  drift = false, driftAlt = false,
  top, right, bottom, left,
  className,
}: Props) {
  const style: CSSProperties = {
    width: size,
    height: size,
    background: GRADIENT[color],
    filter: `blur(${blur}px)`,
    opacity,
    top, right, bottom, left,
    willChange: drift ? 'transform' : undefined,
  };
  const animClass = drift
    ? (driftAlt ? 'animate-aurora-drift-2' : 'animate-aurora-drift')
    : '';
  return (
    <div
      aria-hidden
      className={[
        'absolute pointer-events-none rounded-full',
        animClass,
        className || '',
      ].join(' ')}
      style={style}
    />
  );
}
```

- [ ] **Step 2: Typecheck**

Run: `cd landing && npx tsc --noEmit`
Expected: no errors.

- [ ] **Step 3: Commit**

```bash
git add landing/src/components/AuroraBlob.tsx
git commit -m "feat(landing): add AuroraBlob component (conic-gradient + drift)"
```

---

## Task 4: Create CountUp component (TDD)

**Files:**
- Create: `landing/src/components/__tests__/CountUp.test.tsx`
- Create: `landing/src/components/CountUp.tsx`

- [ ] **Step 1: Write failing tests**

```tsx
// landing/src/components/__tests__/CountUp.test.tsx
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
```

- [ ] **Step 2: Run tests to confirm they fail**

Run: `cd landing && npx vitest run src/components/__tests__/CountUp.test.tsx`
Expected: 4 FAIL with "Cannot find module '../CountUp'" or similar.

- [ ] **Step 3: Write the component**

```tsx
// landing/src/components/CountUp.tsx
/**
 * CountUp — animated number ticker.
 *
 * Parses values like "1,000+", "99.9%", "768-dim", "USDT" into
 * { prefix, numeric, suffix } and tweens the numeric part via RAF
 * when the element first enters the viewport.
 *
 * Non-numeric values (no digits) are rendered as-is.
 *
 * Respects prefers-reduced-motion: jumps to final value immediately.
 */
import { useEffect, useRef, useState } from 'react';
import { useReducedMotion } from 'framer-motion';

type Props = {
  value: string;
  durationMs?: number;   // default 1200
  className?: string;
};

type Parsed =
  | { kind: 'text';    raw: string }
  | { kind: 'number';  prefix: string; numeric: number; decimals: number; suffix: string };

function parse(value: string): Parsed {
  // Match optional non-digit prefix, the first numeric run (with optional decimal & commas),
  // and an optional non-digit suffix.
  const m = value.match(/^([^\d.,-]*)(-?[\d,]+(?:\.\d+)?)(.*)$/);
  if (!m) return { kind: 'text', raw: value };
  const [, prefix, numStr, suffix] = m;
  const cleaned = numStr.replace(/,/g, '');
  const numeric = Number(cleaned);
  if (Number.isNaN(numeric)) return { kind: 'text', raw: value };
  const decimals = (cleaned.split('.')[1] ?? '').length;
  return { kind: 'number', prefix, numeric, decimals, suffix };
}

function format(n: number, decimals: number, sample: string): string {
  // Preserve thousands-separator if the original had one.
  const hasComma = sample.includes(',');
  const fixed = n.toFixed(decimals);
  if (!hasComma) return fixed;
  const [intPart, decPart] = fixed.split('.');
  const withCommas = intPart.replace(/\B(?=(\d{3})+(?!\d))/g, ',');
  return decPart ? `${withCommas}.${decPart}` : withCommas;
}

export default function CountUp({ value, durationMs = 1200, className }: Props) {
  const parsed = parse(value);
  const reduce = useReducedMotion();
  const ref = useRef<HTMLSpanElement | null>(null);
  const [display, setDisplay] = useState(() =>
    parsed.kind === 'number' && !reduce
      ? `${parsed.prefix}${format(0, parsed.decimals, String(parsed.numeric))}${parsed.suffix}`
      : value
  );
  const startedRef = useRef(false);

  useEffect(() => {
    if (parsed.kind !== 'number') return;
    if (reduce || durationMs === 0) {
      setDisplay(value);
      return;
    }
    const el = ref.current;
    if (!el) return;

    const io = new IntersectionObserver((entries) => {
      const entry = entries[0];
      if (!entry?.isIntersecting || startedRef.current) return;
      startedRef.current = true;
      io.disconnect();

      const startTs = performance.now();
      const tick = (now: number) => {
        const t = Math.min(1, (now - startTs) / durationMs);
        const eased = 1 - Math.pow(1 - t, 3);  // ease-out cubic
        const current = parsed.numeric * eased;
        const raw = String(parsed.numeric);
        setDisplay(`${parsed.prefix}${format(current, parsed.decimals, raw)}${parsed.suffix}`);
        if (t < 1) requestAnimationFrame(tick);
      };
      requestAnimationFrame(tick);
    }, { threshold: 0.2 });

    io.observe(el);
    return () => io.disconnect();
  }, [parsed, reduce, durationMs, value]);

  return <span ref={ref} className={className}>{display}</span>;
}
```

- [ ] **Step 4: Run tests to confirm they pass**

Run: `cd landing && npx vitest run src/components/__tests__/CountUp.test.tsx`
Expected: 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add landing/src/components/CountUp.tsx landing/src/components/__tests__/CountUp.test.tsx
git commit -m "feat(landing): add CountUp with format-preserving RAF tween"
```

---

## Task 5: Add shimmer-on-hover variant to CTAButton

**Files:**
- Modify: `landing/src/components/CTAButton.tsx` (read first to confirm structure)

- [ ] **Step 1: Read the file to locate variant logic**

Run: `cat landing/src/components/CTAButton.tsx`

Identify the primary-variant className. The primary variant currently uses a solid blue or gradient background.

- [ ] **Step 2: Add shimmer overlay to primary variant**

Find the primary variant className. Wrap or extend it so the rendered button has:
- `relative overflow-hidden` on the outer button
- An absolutely-positioned inner `<span aria-hidden>` with class:
  `absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent group-hover:animate-shimmer group-hover:translate-x-full pointer-events-none`
- Add `group` to the outer button class so the inner span's `group-hover` triggers

If the existing CTAButton uses a `<button>`-or-`<a>` discriminator, add the shimmer span only inside the primary variant render path. Do NOT add it to secondary/tertiary.

Concrete pattern to add inside the primary variant's JSX (immediately before the children):

```tsx
{variant === 'primary' && (
  <span
    aria-hidden
    className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-700 ease-out group-hover:translate-x-full"
    style={{ backgroundSize: '200% 100%' }}
  />
)}
```

And ensure the wrapping element has `group relative overflow-hidden` in its base class list.

- [ ] **Step 3: Manual smoke**

Run: `cd landing && npm run dev` (or rely on running `kltgsc-landing` container hot-reload).
Open http://localhost:5173/ (or kltgsc.com). Hover a primary CTA — verify the light sweep moves left→right once and stops at the right edge.

- [ ] **Step 4: Typecheck + commit**

```bash
cd landing && npx tsc --noEmit
git add landing/src/components/CTAButton.tsx
git commit -m "feat(landing/cta): shimmer sweep on primary button hover"
```

---

## Task 6: Hero — add aurora blobs (no other changes)

**Files:**
- Modify: `landing/src/sections/HeroDual.tsx`

- [ ] **Step 1: Import AuroraBlob**

Add to imports (around line 14):

```tsx
import AuroraBlob from '@/components/AuroraBlob';
```

- [ ] **Step 2: Place blobs inside the `<section>` BEFORE the existing `bg-grad-radial-dark` div**

Find the line `<div className="absolute inset-0 -z-10 bg-grad-radial-dark" />` (currently line 39).

**Immediately before it**, add:

```tsx
      {/* Aurora atmospheric layer — sits behind the radial gradient */}
      <AuroraBlob
        color="blue"
        size={600}
        blur={200}
        opacity={0.35}
        drift
        top="-10%"
        right="-10%"
        className="-z-10"
      />
      <AuroraBlob
        color="purple"
        size={700}
        blur={240}
        opacity={0.30}
        drift
        driftAlt
        bottom="-15%"
        left="-15%"
        className="-z-10"
      />
```

- [ ] **Step 3: Visual smoke**

Hot-reload or `cd landing && npm run dev`. Open the page. You should see two diffuse soft glows (top-right blue, bottom-left purple) drifting very slowly behind hero content. Existing radial dark gradient stays on top.

If the blobs look TOO obvious: drop opacities to 0.25 / 0.22.
If they look invisible: bump to 0.45 / 0.40.

- [ ] **Step 4: Typecheck + commit**

```bash
cd landing && npx tsc --noEmit
git add landing/src/sections/HeroDual.tsx
git commit -m "feat(landing/hero): aurora gradient orbs behind hero content"
```

---

## Task 7: TrustBar — re-tokenize + CountUp on stats

**Files:**
- Modify: `landing/src/sections/TrustBar.tsx` (read first to identify stat structure)

- [ ] **Step 1: Read the file**

Run: `cat landing/src/sections/TrustBar.tsx`

Identify the stat array / map (the section that renders 5 cells like `1,000+`, `5`, `768-dim`, `99.9%`, `USDT`).

- [ ] **Step 2: Re-tokenize background + text**

- Outer section: keep `bg-brand-ink-950` (it's L0 — no change needed if already there) OR change to `bg-surface-1` if you want it to sit at L1. Per spec rhythm, TrustBar stays L0 (deep, immediately under hero).
- Numeric stat: ensure className includes `text-fg-primary` (replace any `text-white` or hardcoded color).
- Stat label: replace `text-white/60` or `text-brand-ink-400` with `text-fg-muted`.
- Section border (if any divider lines): replace with `border-line-subtle`.

- [ ] **Step 3: Wrap stat values in CountUp**

Add import:

```tsx
import CountUp from '@/components/CountUp';
```

For each stat's numeric display, wrap the rendered string:

```tsx
// before:
<div className="text-4xl font-display font-bold text-white">{stat.value}</div>

// after:
<div className="text-4xl font-display font-bold text-fg-primary">
  <CountUp value={stat.value} />
</div>
```

`USDT` will short-circuit to text-mode and render as-is.

- [ ] **Step 4: Manual smoke**

Reload the page. Scroll TrustBar into view. Numeric stats should count up from 0 over ~1.2s. `USDT` should appear instantly.

- [ ] **Step 5: Typecheck + commit**

```bash
cd landing && npx tsc --noEmit && npm run test -- --run
git add landing/src/sections/TrustBar.tsx
git commit -m "feat(landing/trustbar): re-tokenize + count-up on stat enter"
```

---

## Task 8: ProductSelfServe — light → dark with reveal

**Files:**
- Modify: `landing/src/sections/ProductSelfServe.tsx`

- [ ] **Step 1: Read the file**

Run: `cat landing/src/sections/ProductSelfServe.tsx`

- [ ] **Step 2: Convert outer background**

Replace `bg-white` (or any light bg on the outer `<section>`) with `bg-surface-1`. If there's a contrasting inner block, change to `bg-brand-ink-900` (L2).

- [ ] **Step 3: Re-tokenize text**

| Before | After |
|---|---|
| `text-brand-ink-900` / `text-black` | `text-fg-primary` |
| `text-brand-ink-700` / `text-brand-ink-600` | `text-fg-secondary` |
| `text-brand-ink-500` / `text-brand-ink-400` | `text-fg-muted` |
| `border-brand-ink-200` / `border-brand-ink-100` | `border-line-subtle` |
| `border-brand-ink-300` | `border-line-strong` |

Eyebrow / accent text using `text-brand-blue-500` or `text-brand-purple-500` stays as-is (it pops on dark).

Card backgrounds (anything light-tinted inside): use `bg-brand-ink-900` + `border-line-subtle`.

- [ ] **Step 4: Wrap main content in scroll reveal**

At the top of the section render, import variants:

```tsx
import { motion } from 'framer-motion';
import { fadeUp, REVEAL_VIEWPORT } from '@/lib/motionVariants';
```

Wrap the heading block (eyebrow + h2 + sub) in `<motion.div initial="hidden" whileInView="visible" viewport={REVEAL_VIEWPORT} variants={fadeUp}>...</motion.div>`.

For card grids, see Task 11 (Pricing) for the stagger pattern — apply the same here if SelfServe has a grid.

- [ ] **Step 5: Visual smoke**

Reload. Verify: no white background anywhere, no jarring contrast from TrustBar above. Heading fades up on scroll. Cards readable.

- [ ] **Step 6: Typecheck + commit**

```bash
cd landing && npx tsc --noEmit
git add landing/src/sections/ProductSelfServe.tsx
git commit -m "feat(landing/self-serve): convert to dark L1 surface + reveal"
```

---

## Task 9: ProductAIAssistant — re-tokenize (already dark)

**Files:**
- Modify: `landing/src/sections/ProductAIAssistant.tsx`

- [ ] **Step 1: Read the file**

Run: `cat landing/src/sections/ProductAIAssistant.tsx`

- [ ] **Step 2: Re-tokenize**

This section is already `bg-brand-ink-950` — keep that (L0) OR switch to `bg-surface-1` for rhythm (recommended: L0 if SelfServe is L1, so they alternate).

Apply the same text/border token replacements as Task 8 step 3. Cards inside use `bg-brand-ink-900` + `border-line-subtle`.

- [ ] **Step 3: Add scroll reveal**

Same imports as Task 8. Wrap heading block in `<motion.div>` with `fadeUp` variant.

- [ ] **Step 4: Smoke + commit**

```bash
cd landing && npx tsc --noEmit
git add landing/src/sections/ProductAIAssistant.tsx
git commit -m "refactor(landing/ai-assistant): re-tokenize + reveal heading"
```

---

## Task 10: HowItWorks — white outer → L0 + invert text

**Files:**
- Modify: `landing/src/sections/HowItWorks.tsx`

- [ ] **Step 1: Convert outer ScrollPin background**

Line 29 currently: `<ScrollPin steps={steps.length} className="bg-white relative">`

Change to: `<ScrollPin steps={steps.length} className="bg-brand-ink-950 relative">`

- [ ] **Step 2: Invert left-side step list**

Line 39: `text-brand-ink-900` → `text-fg-primary`
Line 42: `text-brand-ink-500` → `text-fg-muted`
Line 36: `text-brand-blue-500` (eyebrow) stays

For each step row (lines 51-77):
- Active state: change `bg-brand-blue-50 border border-brand-blue-200` → `bg-brand-blue-500/10 border border-brand-blue-500/40`
- Inactive icon chip: `bg-brand-ink-100 text-brand-ink-500` → `bg-brand-ink-900 text-fg-muted`
- Step title: `text-brand-ink-900` → `text-fg-primary`
- Active blurb: `text-brand-ink-600` → `text-fg-secondary`

- [ ] **Step 3: Right-side schematic stage**

Line 83 outer card already uses `bg-brand-ink-950` — change to `bg-brand-ink-900` (L2) so it floats above the L0 section background. Update `border-brand-ink-200` → `border-line-subtle`.

- [ ] **Step 4: Smoke + commit**

```bash
cd landing && npx tsc --noEmit
git add landing/src/sections/HowItWorks.tsx
git commit -m "feat(landing/how-it-works): white → L0 with inverted step palette"
```

---

## Task 11: Pricing — white → L1 + tier card stagger reveal + hover lift

**Files:**
- Modify: `landing/src/sections/Pricing.tsx`

- [ ] **Step 1: Read the file**

Run: `cat landing/src/sections/Pricing.tsx`

- [ ] **Step 2: Convert section + tier card bgs**

- Outer section: `bg-white` → `bg-surface-1`
- Each tier card (currently white with `border-brand-ink-300`): `bg-brand-ink-900` + `border-line-subtle`
- Featured/highlighted tier (if any has accent border): replace `border-brand-blue-500` with `border-brand-blue-500/60` and add subtle ring `ring-1 ring-brand-blue-500/20`

- [ ] **Step 3: Re-tokenize all tier text per Task 8 step 3 table**

Special: tier price (large display number) stays `text-fg-primary`. "$/mo" small unit → `text-fg-muted`. Feature checklist items → `text-fg-secondary`.

- [ ] **Step 4: Add stagger reveal**

```tsx
import { motion } from 'framer-motion';
import { fadeUp, staggerContainer, REVEAL_VIEWPORT } from '@/lib/motionVariants';
```

Wrap the tier-card grid:

```tsx
<motion.div
  className="grid md:grid-cols-3 gap-6"  // keep existing grid classes
  variants={staggerContainer}
  initial="hidden"
  whileInView="visible"
  viewport={REVEAL_VIEWPORT}
>
  {tiers.map((tier) => (
    <motion.div key={tier.id} variants={fadeUp} className="...existing card classes... transition-transform duration-200 ease-out hover:-translate-y-0.5">
      {/* card body */}
    </motion.div>
  ))}
</motion.div>
```

The `hover:-translate-y-0.5` adds the 2px lift from the spec. Card border-color hover bump:
`hover:border-line-strong` (already covered by Tailwind utility).

- [ ] **Step 5: Smoke + commit**

```bash
cd landing && npx tsc --noEmit
git add landing/src/sections/Pricing.tsx
git commit -m "feat(landing/pricing): dark L1 surface, staggered reveal, card hover lift"
```

---

## Task 12: PricingCalculator — ink-50 → L0 + chart palette check

**Files:**
- Modify: `landing/src/sections/PricingCalculator.tsx`

- [ ] **Step 1: Read the file (esp. chart/series colors)**

Run: `cat landing/src/sections/PricingCalculator.tsx`

Identify whether it uses Recharts / a chart lib with hardcoded series colors, or pure CSS bars.

- [ ] **Step 2: Convert backgrounds**

- Outer section: `bg-brand-ink-50` → `bg-brand-ink-950` (L0)
- Calc card / inner panel: `bg-white` → `bg-brand-ink-900` (L2)
- Input borders: `border-brand-ink-200` → `border-line-subtle`
- Input bg: `bg-white` (if inside the L2 card) → `bg-brand-ink-950/50` or `bg-transparent`

- [ ] **Step 3: Re-tokenize per Task 8 step 3 table**

- [ ] **Step 4: Verify chart colors on dark**

If chart series uses dark-text or `stroke="#000"` style: change to `text-fg-secondary` or explicit `#8B92A8` for axis, `#0066FF` / `#A855F7` for series (already bright enough).

If using Recharts `<CartesianGrid>` / `<XAxis>`: pass `stroke="rgba(255,255,255,0.08)"` for grid lines.

- [ ] **Step 5: Add scroll reveal on heading**

Wrap the section heading (h2 + sub) in `<motion.div variants={fadeUp} initial="hidden" whileInView="visible" viewport={REVEAL_VIEWPORT}>`.

Do NOT wrap the calc card itself in motion — it has interactive state and we don't want to delay first paint of inputs.

- [ ] **Step 6: Smoke + commit**

```bash
cd landing && npx tsc --noEmit
git add landing/src/sections/PricingCalculator.tsx
git commit -m "feat(landing/pricing-calc): convert to dark + verify chart legibility"
```

---

## Task 13: UseCases — blue/purple-50 → L1 + tinted L2 cards

**Files:**
- Modify: `landing/src/sections/UseCases.tsx`

- [ ] **Step 1: Read the file to inventory use-case cards**

Run: `cat landing/src/sections/UseCases.tsx`

Identify how cards are color-coded (which use case is blue, which is purple, etc.).

- [ ] **Step 2: Convert outer + card backgrounds**

- Outer section: `bg-brand-blue-50` / `bg-brand-purple-50` (whichever was used) → `bg-surface-1`
- Card per use case: replace light tinted bg with `bg-brand-ink-900` + a low-opacity color wash:
  - Blue use cases: add overlay `bg-brand-blue-500/[0.06]` via stacked div or `before:` pseudo
  - Purple use cases: add overlay `bg-brand-purple-500/[0.06]`
- Card border: `border-line-subtle` baseline; tinted variant `border-brand-blue-500/20` or `border-brand-purple-500/20`

Concrete card-className pattern:

```tsx
const accent = useCase.tone === 'blue'
  ? 'bg-brand-blue-500/[0.06] border-brand-blue-500/20'
  : 'bg-brand-purple-500/[0.06] border-brand-purple-500/20';

<div className={`relative rounded-2xl bg-brand-ink-900 border ${accent} p-6 transition-transform duration-200 ease-out hover:-translate-y-0.5 hover:border-line-strong ...`}>
```

(Hover lift + border bump matches the spec's "card hover" treatment, same as Pricing tiles in Task 11.)

- [ ] **Step 3: Re-tokenize text per Task 8 step 3 table**

- [ ] **Step 4: Stagger reveal on card grid**

Same pattern as Task 11 step 4.

- [ ] **Step 5: Smoke + commit**

```bash
cd landing && npx tsc --noEmit
git add landing/src/sections/UseCases.tsx
git commit -m "feat(landing/use-cases): convert to dark + preserve tonal color hint"
```

---

## Task 14: Security — white → L1 + reveal

**Files:**
- Modify: `landing/src/sections/Security.tsx`

- [ ] **Step 1: Read the file**

Run: `cat landing/src/sections/Security.tsx`

- [ ] **Step 2: Convert outer + content**

- Outer section: `bg-white` → `bg-surface-1`
- Any badge/checkbox light backgrounds: `bg-brand-ink-100` → `bg-brand-ink-900`, `bg-brand-ink-300` → `bg-brand-ink-800`
- Re-tokenize text per Task 8 step 3 table

- [ ] **Step 3: Reveal heading + content block**

Wrap main column in `<motion.div variants={fadeUp} ...>`.

- [ ] **Step 4: Smoke + commit**

```bash
cd landing && npx tsc --noEmit
git add landing/src/sections/Security.tsx
git commit -m "feat(landing/security): convert to dark L1 + reveal"
```

---

## Task 15: FAQ — ink-50/100 → L1/L2 with item stagger

**Files:**
- Modify: `landing/src/sections/FAQ.tsx`

- [ ] **Step 1: Read the file**

Run: `cat landing/src/sections/FAQ.tsx`

- [ ] **Step 2: Convert outer + items**

- Outer section: `bg-brand-ink-50` → `bg-surface-1`
- Each FAQ item (currently `bg-brand-ink-100` or `bg-white`): `bg-brand-ink-900` + `border-line-subtle`
- Open/expanded answer background: same or transparent
- Question text: `text-fg-primary`; answer: `text-fg-secondary`
- Chevron icon: `text-fg-muted`

- [ ] **Step 3: Stagger reveal on the FAQ item list**

```tsx
<motion.div
  className="space-y-3"
  variants={staggerContainer}
  initial="hidden"
  whileInView="visible"
  viewport={REVEAL_VIEWPORT}
>
  {faqs.map(f => (
    <motion.div
      key={f.q}
      variants={fadeUp}
      className="rounded-xl bg-brand-ink-900 border border-line-subtle transition-colors duration-200 ease-out hover:border-line-strong"
    >
      {/* FAQ item */}
    </motion.div>
  ))}
</motion.div>
```

(No translate on hover for FAQ items — they're full-width rows and lift would feel wrong. Only border bump.)

- [ ] **Step 4: Smoke + commit**

```bash
cd landing && npx tsc --noEmit && npm run test -- --run
git add landing/src/sections/FAQ.tsx
git commit -m "feat(landing/faq): convert to dark L1 + staggered item reveal"
```

---

## Task 16: FinalCTA — add aurora + re-tokenize

**Files:**
- Modify: `landing/src/sections/FinalCTA.tsx`

- [ ] **Step 1: Read the file**

Run: `cat landing/src/sections/FinalCTA.tsx`

- [ ] **Step 2: Ensure section wrapper has `relative overflow-hidden`**

Required for aurora positioning.

- [ ] **Step 3: Add AuroraBlob**

Import:

```tsx
import AuroraBlob from '@/components/AuroraBlob';
```

Inside the section, before the content `<div>`:

```tsx
<AuroraBlob
  color="mixed"
  size={500}
  blur={180}
  opacity={0.25}
  /* no drift — section is short */
  top="50%"
  left="50%"
  className="-translate-x-1/2 -translate-y-1/2"
/>
```

- [ ] **Step 4: Re-tokenize text/borders**

Most likely already dark — just ensure tokens (`text-fg-primary` / `text-fg-secondary`, `border-line-subtle`).

- [ ] **Step 5: Reveal content block**

Wrap headline + sub + CTA group in `<motion.div variants={fadeUp} ...>`.

- [ ] **Step 6: Smoke + commit**

```bash
cd landing && npx tsc --noEmit
git add landing/src/sections/FinalCTA.tsx
git commit -m "feat(landing/final-cta): aurora glow behind headline + reveal"
```

---

## Task 17: Footer — re-tokenize text/borders

**Files:**
- Modify: `landing/src/sections/Footer.tsx`

- [ ] **Step 1: Read the file**

Run: `cat landing/src/sections/Footer.tsx`

- [ ] **Step 2: Re-tokenize**

- Outer keeps `bg-brand-ink-950` (L0)
- Link text: `text-white/60` or `text-brand-ink-400` → `text-fg-secondary`
- Hover state: `hover:text-white` → `hover:text-fg-primary`
- Section headings: `text-white` → `text-fg-primary`
- Dividers / top border: `border-white/10` → `border-line-subtle`

- [ ] **Step 3: Commit**

```bash
cd landing && npx tsc --noEmit
git add landing/src/sections/Footer.tsx
git commit -m "refactor(landing/footer): adopt fg/line tokens"
```

---

## Task 18: Full-page smoke + Lighthouse + reduced-motion check

**Files:** none modified; verification only.

- [ ] **Step 1: Full build**

Run: `cd landing && npm run build`
Expected: build succeeds, bundle size delta under +5 KB gzipped vs previous build.

Compare against prior `index-*.js` size. If delta > +5 KB, investigate what bloated (likely duplicated motion imports — check that `motionVariants.ts` is imported once per section).

- [ ] **Step 2: Run full test suite**

Run: `cd landing && npm test -- --run`
Expected: all tests pass, including existing Pricing.test.tsx + Header.test.tsx + new CountUp.test.tsx.

- [ ] **Step 3: Visual smoke — desktop 1440**

Open https://kltgsc.com/ (or local preview). Scroll top to bottom. Checklist:
- [ ] No white/light backgrounds anywhere
- [ ] Section transitions feel smooth (no harsh seams)
- [ ] Aurora visible but not distracting on hero
- [ ] Aurora visible behind final CTA headline
- [ ] Each section reveals on scroll (fade-up)
- [ ] Pricing/UseCases/FAQ items stagger in
- [ ] Cards lift slightly on hover (Pricing tiers)
- [ ] Primary CTA buttons show shimmer sweep on hover
- [ ] TrustBar numbers count up on first scroll-into-view
- [ ] No console errors

- [ ] **Step 4: Visual smoke — mobile 375**

Open DevTools, set viewport to 375×812 (iPhone SE). Repeat scroll-through. Particular attention to:
- Aurora blobs don't overflow visibly off the side
- Reveal animations don't cause horizontal scrollbar
- Stagger doesn't feel slow on small screens (single-column grids reveal in ~400ms each)

- [ ] **Step 5: Reduced-motion check**

In DevTools → Rendering → Emulate CSS media feature `prefers-reduced-motion: reduce`. Reload. Verify:
- All section content renders immediately (no fade-up)
- Aurora drift stops (no movement)
- CountUp shows final values immediately
- CTA shimmer doesn't fire on hover

- [ ] **Step 6: Lighthouse mobile**

Run Lighthouse audit (DevTools → Lighthouse → Mobile → Performance only). Verify:
- LCP < 2.5s (target; the change should not regress this)
- CLS < 0.1
- No new "Avoid large layout shifts" warnings
- No new "Avoid long main-thread tasks" warnings

If LCP regressed: aurora blobs are the likely culprit. Reduce blur from 200→160px or opacity from 0.35→0.28.

- [ ] **Step 7: Commit verification artifacts (optional)**

If you took before/after screenshots, save them to `docs/superpowers/specs/img/2026-05-26-landing-dark-unify/` and commit. Otherwise this step is a no-op.

---

## Task 19: Open PR

**Files:** none modified; PR creation only.

- [ ] **Step 1: Push branch**

```bash
git push -u origin feat/landing-dark-unify
```

- [ ] **Step 2: Create PR**

```bash
gh pr create --title "feat(landing): dark unification + Linear-档 premium polish" --body "$(cat <<'EOF'
## Summary
- Unify all 12 landing sections to a 3-tier dark tonal system (L0 ink-950 / L1 surface-1 / L2 ink-900), eliminating the dark→light→dark seams users were calling out as 不舒服
- Add Linear-style restraint animations: scroll-triggered fade-up reveals, grid stagger, card hover lift, CTA shimmer, TrustBar count-up
- Aurora gradient orbs behind hero (drifting) and final CTA (static)
- Zero new npm dependencies — leans on existing framer-motion + CSS keyframes
- Light theme toggle is deferred to Phase 2 (separate brainstorm)

Spec: `docs/superpowers/specs/2026-05-26-landing-dark-unify-premium-design.md`

## Test plan
- [ ] `npm run build` succeeds with <+5 KB gzipped delta
- [ ] `npm test` all green (incl. new CountUp tests)
- [ ] Desktop 1440 walk-through: no white sections, smooth transitions, all motion fires
- [ ] Mobile 375: no overflow, reveals snappy
- [ ] `prefers-reduced-motion: reduce`: animations off, final state visible
- [ ] Lighthouse mobile: LCP <2.5s, CLS <0.1, no regression vs main

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 3: Return the PR URL to the user**

---

## Self-Review Notes (already addressed inline)

- **Spec coverage**: every spec section has at least one task. Tonal system → Task 1; motion system → Tasks 2/4/5 + section tasks; aurora → Tasks 3/6/16; reduced-motion → handled by existing tokens.css guard + framer's `useReducedMotion` (used in CountUp); testing → Task 4 unit + Task 18 visual/perf.
- **Resolved hex ambiguity**: Used existing `ink-950`/`ink-900` for L0/L2 and added `surface-1` for L1 only. This minimizes diff and reuses tokens already wired into other parts of the codebase.
- **No new deps**: confirmed framer-motion already in `package.json`. `useReducedMotion` is exported from it.
- **Risk of double-fade on HeroDual**: HeroDual already uses framer-motion with `initial=hidden animate=visible`. We do not wrap it in additional reveal — only add the AuroraBlob layer (Task 6). Other sections that use `whileInView` instead of `animate` are independent.
- **UseCases color-coding preservation**: addressed via tonal wash overlay (Task 13 step 2).
