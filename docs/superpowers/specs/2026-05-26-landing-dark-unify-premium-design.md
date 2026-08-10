# Landing Page — Dark Unification + Premium Polish (Phase 1)

**Date**: 2026-05-26
**Status**: Approved (brainstorm complete)
**Scope**: kltgsc.com / tg1.ai landing page
**Branch**: `feat/landing-dark-unify` (fresh, off `main`). The current `fix/landing-p0-bugs` branch is scoped to small bugfixes and should not absorb a major visual overhaul.

## Problem

The landing page currently alternates between dark and light sections six times in a row:

```
HeroDual (dark) → TrustBar (dark) → ProductSelfServe (light) → ProductAIAssistant (dark) →
HowItWorks (light) → Pricing (light) → PricingCalculator (light) → UseCases (light) →
Security (light) → FAQ (light) → FinalCTA (dark) → Footer (dark)
```

Each contrast flip is a jarring visual seam. User feedback: "一会暗一会亮 这样设计让人很不舒服".

Beyond unification, the page lacks the "premium" feel of modern dev/AI SaaS landing sites (Linear / Vercel reference). It needs subtle motion and atmospheric depth — without crossing into distracting territory.

## Goals

1. **Eliminate dark/light alternation** — all 12 sections share one dark base.
2. **Add atmospheric depth** — tonal variation between sections so the page has rhythm without contrast jumps.
3. **Layer in restrained motion** — scroll-triggered fade-ups, hover micro-interactions, shimmer, count-up. Linear-档, not festival-档.
4. **Add aurora gradient orbs** at hero + final CTA to give the page a "the model is thinking behind this" feel.
5. **Zero new heavy deps** — no framer-motion in new code, no spline, no 3D. Pure CSS + IntersectionObserver.

## Non-goals (deferred to Phase 2)

- Light theme toggle / dual-theme support
- CSS-variable token refactor
- Dot-grid background patterns
- Telegram paper-plane / chat-bubble decorations
- Neural-network / embedding scatter background

## Design

### 1. Tonal background system

Three dark layers replace the current monolithic `bg-brand-ink-950`:

| Layer | Hex | Used for |
|---|---|---|
| **L0 base** | `#0A0E1A` (existing ink-950) | Hero, Footer, page root |
| **L1 surface** | `#0F1320` (new ink-925) | Most section backgrounds |
| **L2 elevated** | `#161B2E` (existing ink-900) | Cards, price tiles, FAQ items |

**Rhythm**: adjacent sections alternate gently between L0 ↔ L1 (Δ lightness < 5%). The eye sees layered depth, not seams. Cards float on L2 with a 1px `rgba(255,255,255,0.08)` border.

### 2. Text + border tokens

Replace ad-hoc `text-brand-ink-{500..900}` with semantic tokens applied uniformly:

| Token | Hex | Use |
|---|---|---|
| `text-fg-primary` | `#F0F2F8` | Headlines, body |
| `text-fg-secondary` | `#8B92A8` | Subhead, supporting copy |
| `text-fg-muted` | `#5B6178` | Captions, metadata |
| `border-subtle` | `rgba(255,255,255,0.08)` | Card borders, dividers |
| `border-strong` | `rgba(255,255,255,0.14)` | Hover state, focus rings |

Brand accent gradients (`brand-blue-500` → `brand-purple-500`) stay untouched — they read better on dark.

### 3. Sections to convert (7 of 12)

| Section | Current | Target |
|---|---|---|
| ProductSelfServe | `bg-white` | L1 + L2 cards |
| HowItWorks | `bg-white` | L0 (sits between L1 sections for rhythm) |
| Pricing | `bg-white` + ink-300 borders | L1 + L2 tier cards |
| PricingCalculator | `bg-brand-ink-50` | L0 + L2 calc card |
| UseCases | `bg-brand-blue-50` / `purple-50` | L1 + tinted L2 cards (preserve color hint via low-opacity overlay) |
| Security | `bg-white` | L1 |
| FAQ | `bg-brand-ink-100/50` | L1 + L2 accordion items |

Already-dark sections (HeroDual, TrustBar, ProductAIAssistant, FinalCTA, Footer) get re-tokenized but stay dark.

### 4. Animation system (Linear-档)

All animations: GPU-friendly (transform / opacity only), `prefers-reduced-motion` respected, no layout thrash.

| Animation | Where | Spec |
|---|---|---|
| **Section reveal** | Every section's main content | IntersectionObserver-driven `opacity 0→1` + `translateY 12px→0`, 400ms `ease-out`, threshold 0.15 |
| **Stagger** | Grids of cards (Pricing tiers, UseCases, FAQ) | 80ms delay between siblings, max 4 children before stagger caps |
| **Card hover** | Pricing tiles, UseCase cards, FAQ items | `translateY -2px` + border-subtle → border-strong, 180ms `ease-out` |
| **CTA shimmer** | Primary buttons on hover | Linear gradient sweep (`background-position` animation), 700ms `ease-in-out`, one-shot per hover-enter |
| **Number count-up** | TrustBar stats (1,000+ / 5 / 768-dim / 99.9% / USDT) | On first viewport entry: numeric values count from 0 over 1200ms `ease-out`. Non-numeric labels (USDT) skip count-up. |

Implementation:
- **New** `components/ScrollReveal.tsx` — thin wrapper around `useInView` (already in `react-intersection-observer` dep). Children fade-up when entered.
- **New** `components/CountUp.tsx` — RAF-driven number tween, parses prefix/suffix (`1,000+`, `99.9%`) from string.
- **New** `hooks/usePrefersReducedMotion.ts` — single source of truth; both components short-circuit when true.
- No new npm packages.

### 5. Aurora atmosphere

Only two locations. Other sections stay clean — the tonal layers carry the depth.

**HeroDual**:
- 2 conic-gradient blobs absolutely positioned behind hero content
- Blob A: top-right, 600×600px, `conic-gradient` blue (`#0066FF`) → transparent, blur 200px, opacity 0.35
- Blob B: bottom-left, 700×700px, conic purple (`#A855F7`) → transparent, blur 240px, opacity 0.3
- Drift via `transform: translate3d()` keyframes, 80s loop, asymmetric so they don't sync
- `pointer-events: none`, `z-index: 0`, hero content `z-index: 1`

**FinalCTA**:
- 1 blob behind the CTA headline, 500×500px, blue→purple sweep, blur 180px, opacity 0.25
- Static (no drift) — section is too short for slow motion to register

**Tech**:
- Pure CSS keyframes, defined in `tokens.css`
- No JS, no canvas, no WebGL
- `will-change: transform` on drift elements, removed via `animation-fill-mode: backwards` when off-screen (rely on parent scroll-out for free perf)

### 6. Files touched

```
landing/src/
├── styles/
│   └── tokens.css                    # +L0/L1/L2, +text/border tokens, +aurora keyframes
├── tailwind.config.js                # extend colors with new tokens
├── components/
│   ├── ScrollReveal.tsx              # NEW
│   ├── CountUp.tsx                   # NEW
│   └── AuroraBlob.tsx                # NEW (encapsulates blob + drift)
├── hooks/
│   └── usePrefersReducedMotion.ts    # NEW
├── sections/
│   ├── HeroDual.tsx                  # add aurora layer + ScrollReveal on hero content
│   ├── TrustBar.tsx                  # CountUp on stats
│   ├── ProductSelfServe.tsx          # white → L1/L2, ScrollReveal
│   ├── ProductAIAssistant.tsx        # re-tokenize (already dark), ScrollReveal
│   ├── HowItWorks.tsx                # white → L0, ScrollReveal, stagger steps
│   ├── Pricing.tsx                   # white → L1/L2, ScrollReveal + stagger tiles, hover lift
│   ├── PricingCalculator.tsx         # ink-50 → L0/L2, ScrollReveal
│   ├── UseCases.tsx                  # blue-50/purple-50 → L1 + tinted L2, ScrollReveal + stagger
│   ├── Security.tsx                  # white → L1, ScrollReveal
│   ├── FAQ.tsx                       # ink-50/100 → L1/L2, ScrollReveal items
│   ├── FinalCTA.tsx                  # add small aurora blob, re-tokenize
│   └── Footer.tsx                    # re-tokenize text colors
```

Estimated diff: ~600-800 LOC changed, ~150 LOC new.

### 7. Component contracts

**`<ScrollReveal>`** — `children, delay?, as?`
- Wraps any block. Renders `opacity 0 translateY(12px)` until in viewport, then transitions to `opacity 1 translateY(0)`.
- `delay`: 0-400ms, for hand-tuned cases.
- For grid stagger, parent uses `<ScrollReveal>` per child with `delay={i * 80}`.
- Reduced motion: renders children in final state immediately.

**`<CountUp>`** — `value: string, durationMs?`
- Parses `"1,000+"`, `"99.9%"`, `"768-dim"` into prefix/numeric/suffix.
- Tweens numeric portion via RAF when in viewport.
- Reduced motion: renders final value immediately.

**`<AuroraBlob>`** — `color, size, position, blur, opacity, drift?`
- Absolutely-positioned div with `conic-gradient` background, blur, optional keyframe drift.
- Parent must be `position: relative` and `overflow: hidden`.

### 8. Performance budget

- New CSS: +2-3 KB gzipped (tokens + keyframes)
- New JS: +1-2 KB gzipped (ScrollReveal + CountUp + hook)
- No new dependencies
- Hero LCP: must not regress (>2.5s = fail). Aurora blobs are pure CSS, render off main thread.
- All `transform`/`opacity` animations — no paint/layout.

### 9. Testing

- Unit: `CountUp` parses formats correctly; `usePrefersReducedMotion` returns true under mock matchMedia.
- Visual: manually verify each section at 1440 / 1024 / 375 widths; verify smooth scroll from top to bottom with no contrast jumps.
- a11y: run axe on Home; verify `prefers-reduced-motion: reduce` disables all animation.
- Perf: Lighthouse mobile, hero LCP <2.5s, CLS <0.1.

## Open risks

- **UseCases tinted cards**: currently use `bg-brand-blue-50` / `purple-50` to color-code use cases by audience. Pure dark loses that signal. Mitigation: keep a low-opacity (5-8%) blue/purple wash on the L2 card per use case, plus an accent icon.
- **PricingCalculator chart colors**: Recharts (or whatever the calc uses) may have hardcoded light colors. Need to verify chart legibility on dark background and adjust series palette if needed.
- **Aurora on low-end mobile**: 200px blur on a 600px element is GPU-cheap on modern devices but could be costly on 3-year-old Androids. Acceptable; the page degrades gracefully (blob looks like a soft glow instead of crisp).

## Rollout

Single PR off `main`, lands as one deploy. No flag — the change is the whole point. Post-merge:
1. Run `cd landing && npm run build`
2. nginx auto-serves new `dist`
3. Smoke check kltgsc.com top-to-bottom

Phase 2 (theme toggle) gets its own brainstorm + spec.
