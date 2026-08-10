# Landing Texture Polish — Design Spec

**Date:** 2026-05-26 → 2026-05-27
**Branch:** `polish/landing-texture` (PR #7)
**Scope:** Refine TG1.AI landing aesthetic without changing direction or copy. Push existing "modern dark-tech SaaS" foundation toward **engineering blueprint × atmospheric light** through eight focused rounds.

## Goal

Bring the landing from "shipped, functional" to "considered, distinctive" — Linear/Vercel-tier polish with TG1's electric blue + purple as **atmospheric accents**, not the dominant note. No copy changes (those live in PR #1). No layout reshuffles. No feature removals.

## Locked Aesthetic Direction

**Engineering blueprint × atmospheric light**

- Display type: Manrope with tighter tracking + Inter for body + JetBrains Mono for technical eyebrows
- Surface depth: 3-layer dark stack (`surface-1/2/3`) instead of `white/X` opacity hacks
- Background: composable atmosphere layer (`grid + radial + beam + noise`) instead of scattered divs
- Color: blue + purple reserved as accents; dominant dark tones do the work
- Motion: one snap easing curve `[0.16, 1, 0.3, 1]` applied universally
- Editorial chrome: `── 0X · SECTION NAME` anchors across every section

## What Shipped (8 rounds)

### Round 1 — Foundation ([ec2913e](https://github.com/astercc518/kltgsc/commit/ec2913e))

New components + design tokens:
- `BackgroundField` — unifies the previous 4-layer hero stack into one composable atmospheric layer with three variants (`hero` / `section` / `minimal`)
- `SectionLabel` — editorial anchor: `── 0X · LABEL` with mono numerals, dot separator, 32px rule
- `tokens.css` + `tailwind.config.js` — added `surface-1/2/3`, `fg-primary/secondary/muted/dim`, `line-subtle/medium/strong`, snap easing curve, 70ms cascade stagger

Hero refinement:
- Pure white headline + single-word gradient accent with underglow blur (was: full-clause gradient)
- Replaces fake `liveBadge` with SectionLabel `00 · TG1.AI / MARKETING OS`
- ProductCard always-visible corner arrow

CTAButton:
- Layered shadow stack (tight ring + middle halo + far diffuse + 1px top-edge ridge + shimmer)
- Tertiary variant gets hover border + ghost bg (reads as button)

TrustBar:
- Mono digits with `tabular-nums + slashed-zero` (fixes count-up wobble)
- Vertical hairline dividers between stats on `md+`
- Editorial `01 · TRUST SIGNALS` anchor

### Round 2 — Editorial chrome ([671c60b](https://github.com/astercc518/kltgsc/commit/671c60b))

- `ScrollProgress` — 2px gradient bar at top of viewport, RAF-throttled
- `SectionDivider` — hairline + cross-terminus blueprint markers (component-only; not wired site-wide because color contrast already does the job)
- SectionLabel applied to UseCases (04), Pricing (05), PricingCalculator (06), Security (07), FAQ (08), FinalCTA (09)
- FinalCTA refresh — adopts BackgroundField + headline recipe, snappier stagger
- Footer rewrite — 4 columns → 3, status indicator folded into brand column (no more orphan column with dead `<a href="#">`)

### Round 3 — Deep-dive sections ([7bcc93d](https://github.com/astercc518/kltgsc/commit/7bcc93d))

ProductSelfServe (02):
- SectionLabel `02 · SELF-SERVE`
- Refined flow diagram: wallet corner emblem + hairline FlowStep cards

ProductAIAssistant (03):
- BackgroundField section variant
- Step cards switched to surface-1/2 + line-medium tokens (no more white/X)
- Each card now has a hairline rule between number and icon (typographic spine)
- Engage step gets refined glow stack
- Safety wall gets gradient top-hairline accent + ring-on-icon
- CTA strip drops "Ask sales" tertiary (already in hero + FinalCTA)

PriceCard:
- Drops the lowercase `starter` eyebrow
- Featured ribbon: solid purple → gradient pill with shadow drop
- Price typography: font-display + tabular-nums + tracking-tight
- Featured CTA matches primary CTAButton's gradient + lift

### Round 4 — HowItWorks slim ([988ddfd](https://github.com/astercc518/kltgsc/commit/988ddfd))

- ScrollPin outer height `steps * 80vh` (480vh) → `steps * 50vh` (300vh). Saves a mobile reader 7 thumb-flicks.
- Schematic right panel now `hidden lg:block`. On mobile the left list carries enough info.
- Mobile shows all step blurbs (no scroll-driven reveal that depends on the pin)
- Schematic drops 3-ring pulse for one mask-faded radial + grid texture
- Title gets tracking-tight + text-balance

### Round 5 — Mobile + i18n verification ([2e5d817](https://github.com/astercc518/kltgsc/commit/2e5d817))

Tested at 390×844 (iPhone 12) and zh-CN locale:
- `SectionLabel` gets `flex-wrap` + each segment `shrink-0` so long labels don't orphan the rule on line 1
- Hero label switched from `00 · {selfServe.tag} · {aiAssistant.tag}` to brand-anchored `00 · TG1.AI / MARKETING OS`
- FinalCTA label: `09 · START / 5 MINUTES TO LIVE` mirrors hero's opening
- All 11 sections verified at mobile + zh-CN

### Round 6 — Header ScrollSpy + sticky bug fix ([9e20ce0](https://github.com/astercc518/kltgsc/commit/9e20ce0))

**Bug fix** (pre-existing): `html, body, #root { height: 100% }` made #root only viewport-tall, breaking the Header's `position: sticky` containing block. Split to `html, body { height: 100% }` + `#root { min-height: 100% }`.

**ScrollSpy**: Header nav links now grow a fine gradient underline when their target section is in the viewport. Tracked via IntersectionObserver with `rootMargin: -25% 0px -55% 0px`. Hover state grows a half-width underline.

Plus: vertical hairline separator between LangSwitcher and Sign-In (chrome cluster vs action cluster).

### Round 7 — Reveal + FeatureCard hover ([71f7f79](https://github.com/astercc518/kltgsc/commit/71f7f79))

Reveal — universal entry animation tightening:
- Easing curve → snap `[0.16, 1, 0.3, 1]` (matches hero / FinalCTA)
- y offset 16px → 12px
- Duration 0.6s → 0.7s but snap curve front-loads velocity
- rootMargin tightened so reveal fires after the element actually enters view

FeatureCard hover:
- Top accent rail grows in from left (1px gradient, scale-x-0 → 1, 500ms snap)
- Hover lift bumped from -0.5px to -1px
- Icon container subtle 1.05x scale
- Badge tabular-nums + slashed-zero
- Title tracking-tight

### Round 8 — Perf + closing touches (this commit)

- **AnimatedNumber**: `format` prop snapshot via ref so inline arrow lambdas don't retrigger the animate() effect every render. Easing curve updated to snap.
- **ScrollPin**: merged two `setState` calls per scroll frame into one combined state object (with identity guard).
- **Header**: scroll listener replaced with `IntersectionObserver` sentinel — observer fires only when the 24px threshold is actually crossed (twice per session) instead of every scroll event.
- **HeroDual subtitle**: responsive font size `text-base md:text-lg lg:text-xl` + 8px gap before subtitleQuiet (was 6px, looked cramped on mobile).

## File Inventory

**New components** (8 files):
- `landing/src/components/BackgroundField.tsx`
- `landing/src/components/SectionLabel.tsx`
- `landing/src/components/SectionDivider.tsx`
- `landing/src/components/ScrollProgress.tsx`

**Refreshed components**:
- `landing/src/components/CTAButton.tsx`
- `landing/src/components/FeatureCard.tsx`
- `landing/src/components/PriceCard.tsx`
- `landing/src/components/AnimatedNumber.tsx`
- `landing/src/components/ScrollPin.tsx`
- `landing/src/components/Reveal.tsx`

**Refreshed sections** (11 of 11 + Footer + Header):
- `landing/src/sections/Header.tsx`
- `landing/src/sections/HeroDual.tsx`
- `landing/src/sections/TrustBar.tsx`
- `landing/src/sections/ProductSelfServe.tsx`
- `landing/src/sections/ProductAIAssistant.tsx`
- `landing/src/sections/HowItWorks.tsx`
- `landing/src/sections/Pricing.tsx`
- `landing/src/sections/PricingCalculator.tsx`
- `landing/src/sections/UseCases.tsx`
- `landing/src/sections/Security.tsx`
- `landing/src/sections/FAQ.tsx`
- `landing/src/sections/FinalCTA.tsx`
- `landing/src/sections/Footer.tsx`

**Design tokens**:
- `landing/src/styles/tokens.css`
- `landing/src/styles/globals.css`
- `landing/tailwind.config.js`

**Wired**:
- `landing/src/pages/Home.tsx` (ScrollProgress inserted)

## Verification

- Build clean every round (5s ± 0.3s)
- Desktop 1440×900: walked through full page across 8 rounds via Playwright
- Mobile 390×844 (iPhone 12): all 11 sections verified
- Locale zh-CN: hero + headline + product cards rendered correctly with full translations
- Real-device mobile (iOS Safari / Android Chrome): **not yet verified** — out of session scope, recommended pre-merge

## Independence from PR #1

PR #1 (landing P0 fixes) and PR #7 (texture polish) are independent. Some fixes overlap naturally:

| Item | PR #1 | PR #7 (polish) |
|---|---|---|
| Hero `liveBadge` removed | ✅ | ✅ (replaced with SectionLabel) |
| Footer Status `<a>` → `<span>` | ✅ | ✅ (round 2) |
| Mobile menu body scroll lock | ✅ | — (no change) |
| ProductCard always-visible arrow | — | ✅ (round 1) |
| CTAButton tertiary border | — | ✅ (round 1) |
| PriceCard lowercase eyebrow removed | — | ✅ (round 3) |
| HowItWorks 480vh → reduced | — | ✅ (round 4) |
| Footer 4th column collapse | — | ✅ (round 2) |
| Tagline copy change | (PR #1 scope) | not changed |
| Pricing i18n .replace bug | (PR #1 scope) | not changed |
| UseCases card 2 metric | (PR #1 scope) | not changed |

Merge order suggestion: PR #1 first (semantic fixes), then PR #7 (visual polish). Conflicts will be minor — both touch HeroDual + Footer + CTAButton + PriceCard but on adjacent lines.

## Out of Scope

- Dark-mode adapter (light sections need their own design system)
- Custom cursor (gimmicky for this brand)
- Keyboard shortcuts (over-engineering for a marketing landing)
- Real Telegram demo preview video (separate work item)
- Pricing monthly/annual toggle (no business signal we'd offer annual discount)

## Done Definition

- All 8 polish rounds shipped on `polish/landing-texture`
- PR #7 open with comprehensive description
- Closing spec written (this doc)
- Build clean, no regressions vs. main
- After Done: PR #7 ready for review/merge
