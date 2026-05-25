# Landing Polish — Design Spec

**Date:** 2026-05-25
**Branch base:** `main` (after `feature/landing-demo-modal` merges)
**Strategy alignment:** "先 polish 再上 prod" — this spec is the last UX gate before flipping prod compose.

## Goal

Take the TG1.AI marketing site (`landing/`) from "shipped, functional" to "production-ready, conversion-coherent." A full UX audit produced 27 concrete issues across 13 sections; this spec groups them into 5 independently shippable PRs and locks the open product decisions.

Out of scope:
- The demo modal itself (`feature/landing-demo-modal`) — already shipped, audited separately, merges before PR-1 starts.
- Backend changes other than what PR-1 and PR-2 explicitly require.
- Adding new sections, new languages, or A/B testing.

## Source of Issues

Findings live in the conversation transcript that produced this spec. Each issue below carries an inline `file:line` pointer for traceability. The original audit graded 5 P0 / 15 P1 / 7 P2; this spec ships all 27.

## Locked Product Decisions

These are user-confirmed and override any text/copy currently in the codebase:

1. **Tagline replacement** — `landing/src/i18n.ts:418` (`footer.tagline`):
   `"Telegram growth, on autopilot."` → **`"Telegram growth, half-automated by design."`** (and equivalents in zh/ja/ko/es).
2. **Hero `liveBadge`** — `landing/src/sections/HeroDual.tsx:48-54` + `landing/src/i18n.ts:258` (`hero.liveBadge`):
   Remove the badge entirely. Drop the JSX node, the i18n key, and any prop wiring. Do not replace with a downgraded version.
3. **Footer Status indicator** — `landing/src/sections/Footer.tsx:114-120`:
   Keep the green-dot + "All systems normal" visual; change `<a href="#">` to `<span>`. Don't link to anything.

Other smaller copy/UX decisions are inlined per PR below; each is the spec's default — the user can override at spec review.

## PR Breakdown

Each PR has a self-contained branch off `main` and ships independently. Order is recommended; PR-2 and PR-3 can run in parallel since their file overlap is tiny (only `i18n.ts` for shared copy keys).

---

### PR-1 — Bug fixes (P0)

**Branch:** `fix/landing-p0-bugs`
**Reviewable in:** ~15 min
**Risk:** Low — all are localized.

| # | File:Line | Fix |
|---|-----------|-----|
| 1 | `landing/src/sections/Pricing.tsx:140-141` | i18n bug: `t.pricing.tableAdminNote.replace('billing docs', '')` only matches English. Refactor to split-render: change `pricing.tableAdminNote` shape to `{ before: "…", linkLabel: "…", after: "…" }` in all 5 languages; render `{before}<Link>{linkLabel}</Link>{after}`. Same pattern wherever `.replace()` is used to splice a link into an i18n string. |
| 2 | `landing/src/sections/Footer.tsx:114-120` | Change `<a href="#">` to `<span>` (see locked decision #3). |
| 3 | `landing/src/sections/Header.tsx:113` | Mobile menu body scroll lock. Add `useEffect` that toggles `document.body.style.overflow = 'hidden'` while `mobileOpen` is true; restore on cleanup. Mirror the pattern already in `DemoVideoModal/` (which solved this for iOS). |
| 4 | `landing/src/sections/HeroDual.tsx:48-54` + `landing/src/i18n.ts:258` | Remove `liveBadge` (see locked decision #2). Delete JSX node + i18n key in all 5 langs. |
| 5 | `landing/src/components/PricingCalculator.tsx:53-59` | Rename `const t = setTimeout(...)` → `const id = setTimeout(...)` to stop shadowing the outer `useT()` result. Add ESLint `no-shadow` to landing's config so this can't recur (separate config change, not blocking). |

**Acceptance:**
- Pricing admin note renders correctly in en/zh/ja/ko/es with the link in the right place. Add 5 vitest snapshot tests (one per language) — concrete assertion: rendered text + link href.
- Mobile menu opens → page behind no longer scrolls on iOS Safari (manual test on real device or BrowserStack).
- `liveBadge` no longer present in any rendered output.
- `npm run build` clean; no TS or lint errors.

---

### PR-2 — Conversion path / CTA ladder

**Branch:** `feat/landing-cta-cleanup`
**Reviewable in:** ~30 min
**Risk:** Medium — touches hero, two product sections, FinalCTA, CTAButton, PricingCalculator.

Changes:

1. **HeroDual dual-product cards** (`landing/src/sections/HeroDual.tsx:165-202`)
   Add the arrow indicator (`→` or chevron) to each card's top-right in the **rest state**, not just on hover. Keep the hover color change as secondary affordance.

2. **ProductSelfServe redundant CTA strip** (`landing/src/sections/ProductSelfServe.tsx:88-109`)
   Replace the "See pricing" strip with a **"Try a $20 wallet"** CTA that links to `/portal/billing` (or wherever the trial flow currently starts — confirm during implementation by grepping for the trial-grant route). This makes the strip useful instead of duplicating PR-3's next section.

3. **ProductAIAssistant secondary "Ask sales" CTA** (`landing/src/sections/ProductAIAssistant.tsx:108-134`)
   Drop the "Ask sales" button. Keep the "See plans" primary. Rationale: Hero and FinalCTA already carry "Ask sales"; in-section duplication dilutes the ladder.

4. **FinalCTA differentiation** (`landing/src/sections/FinalCTA.tsx:58-85`)
   Three CTAs become two with differentiated labels:
   - Primary: `"Claim your $20 starter wallet"` → trial flow
   - Secondary: `"Book a 15-min walkthrough"` → sales contact
   - Drop the tertiary "Talk on Telegram" (its target is duplicated by secondary).
   Update i18n in all 5 languages.

5. **CTAButton tertiary visual weight** (`landing/src/components/CTAButton.tsx:42`)
   Tertiary variant currently has no border/bg. Either:
   - **Default choice:** add a 1px `border-white/15` (dark hero) / `border-brand-ink-200` (light bg) — keep size — so it reads as a button, not paragraph text;
   - Smaller `px-3 py-1.5` if the user prefers visually demoted.
   Decision: go with bordered. If reviewer disagrees, swap in the implementation PR.

6. **PricingCalculator quota overflow + label** (`landing/src/components/PricingCalculator.tsx:43-49, 87`)
   - Rename "Best" → "Lowest total".
   - When the slider's `accounts` > tier cap or `groups` > tier cap, render an inline warning `⚠ Exceeds <Tier> quota — pick <NextTier>`. Tier caps live in `PRICING_TIERS` (or wherever they're defined — confirm in implementation).

**Acceptance:**
- Manual browser walk: Hero → click product card → land on right anchor → see CTA → click → land in /portal trial flow. No dead ends.
- FinalCTA has 2 distinct CTAs in all 5 languages.
- PricingCalculator quota warning visible at `accounts=10, groups=5000` with default plan = Starter.
- Lighthouse accessibility score on Home: no regression vs. main.

---

### PR-3 — Copy & brand voice (i18n)

**Branch:** `chore/landing-copy-polish`
**Reviewable in:** ~20 min
**Risk:** Low — almost entirely i18n string edits.

Changes:

1. **TrustBar engineer jargon** (`landing/src/sections/TrustBar.tsx:18-23`)
   Replace "5 listener shards" and "768-dim" with buyer-meaningful metrics. **Default choice:**
   - "Messages processed last 30d: 1.2M+" (pull from BizOps dashboard if accessible, otherwise hardcode a defensible round number with a footnote `*as of <month>` — call out in the PR description).
   - "Multilingual RAG (5 languages)" instead of "768-dim".
   Open question for reviewer: do we have a real MAU/messages number we want to expose publicly? If yes, parameterize via `landing/src/lib/stats.ts` (new file) reading a static JSON file checked in monthly. If no, use the hardcoded with footnote.

2. **Tagline contradiction** (`landing/src/i18n.ts:418` — locked decision #1)
   "Telegram growth, half-automated by design." in en; translate equivalently for zh/ja/ko/es. Suggested translations (verify with native speakers if available):
   - zh: `"Telegram 增长，半自动设计"`
   - ja: `"Telegram グロース、半自動設計"`
   - ko: `"텔레그램 그로스, 반자동 설계"`
   - es: `"Crecimiento en Telegram, semi-automático por diseño"`

3. **UseCases card 2 "50× cheaper" claim** (`landing/src/sections/UseCases.tsx:54` + `landing/src/i18n.ts:554`)
   Replace with `"Replace one offshore SDR seat per $299 Pro plan"` — concrete, defensible, ties to Pricing.

4. **PriceCard eyebrow casing** (`landing/src/components/PriceCard.tsx:58`)
   Eyebrow currently renders raw `starter`/`growth`/`pro`. Drop the eyebrow entirely (the plan name is right below it; the eyebrow adds nothing).

5. **Pricing borrows hero copy** (`landing/src/sections/Pricing.tsx:131`)
   Dedicated i18n keys `pricing.groupLabelSelfServe` / `pricing.groupLabelAIAssistant` instead of `t.hero.selfServe.tag`. Add to all 5 languages.

**Acceptance:**
- Switch language to each of the 5 → walk Hero/Pricing/UseCases/Footer → no engineer jargon, no contradiction with "half-automatic" elsewhere, no orphaned strings.
- Vitest snapshot for the 5 language switches (already partly covered by PR-1 snapshot infra).

---

### PR-4 — Structure dedup + mobile

**Branch:** `feat/landing-structure-mobile`
**Reviewable in:** ~30 min
**Risk:** Medium — biggest layout shifts of the bunch. Requires real-device mobile test.

Changes:

1. **HowItWorks ScrollPin height** (`landing/src/sections/HowItWorks.tsx:29` + `landing/src/components/ScrollPin.tsx:37`)
   Change `outerHeightVh = steps * 80` to `steps * 50` (= 300vh for 6 steps). Add a `lg:`-gated wrapper so on `<lg` screens the section renders as a plain stacked list (no ScrollPin, no pinning). Move the schematic into a `lg:block hidden` sibling.

2. **HowItWorks right-pane redundancy on mobile** — covered by #1.

3. **Security ↔ ProductAIAssistant safety contract dedup** (`landing/src/sections/Security.tsx:55-62` ↔ `landing/src/sections/ProductAIAssistant.tsx:84-106`)
   Decision: **trim ProductAIAssistant's safetyBlock to one sentence** ("AI never auto-DMs — half-automatic by design.") and let Security carry the full two-contract treatment. This puts the depth in the dedicated section.

4. **Footer 4th column** (`landing/src/sections/Footer.tsx:109-121`)
   Delete the column. Footer becomes 3 columns. PR-1 already handled the Status `<span>` change — move the green-dot indicator into the brand (first) column under the tagline.

5. **HeroDual mobile `<br>` spacing** (`landing/src/sections/HeroDual.tsx:73`)
   The `<br className="hidden md:block" />` jams subtitle and subtitleQuiet on mobile. Replace with `<span className="block md:inline md:before:content-['_']" />` wrapper around subtitleQuiet, or just `mt-1 md:mt-0 md:inline` on subtitleQuiet itself.

**Acceptance:**
- Real-phone test (iPhone Safari + a mid-range Android Chrome): walk full home, verify HowItWorks scroll feels natural (not 7 flicks), HeroDual subtitle breathes, Footer reads as intentional 3-column.
- Lighthouse mobile performance: no regression (HowItWorks scroll savings should slightly improve LCP).
- A11y: Security and ProductAIAssistant don't double-announce the same contract to screen readers.

---

### PR-5 — P2 micro-optimizations

**Branch:** `perf/landing-micro`
**Reviewable in:** ~15 min
**Risk:** Very low — internal-only.

Changes:

1. **AnimatedNumber memoize `format`** (`landing/src/components/AnimatedNumber.tsx:36-47`)
   Wrap effect deps so `format` identity changes don't retrigger the count-up. Either internal `useRef` snapshot or document at call sites that `format` must be stable.

2. **ScrollPin merge state** (`landing/src/components/ScrollPin.tsx:55-65`)
   Two motion-value subscriptions → one combined `setState({step, progress})`.

3. **Header scroll listener** (`landing/src/sections/Header.tsx:33-38`)
   Replace `scroll` listener with `IntersectionObserver` on a 24px sentinel `<div>`.

4. **FAQ magic font size** (`landing/src/sections/FAQ.tsx:65`)
   `text-[0.95rem]` → `text-sm`.

5. **Footer text contrast** (`landing/src/sections/Footer.tsx:46`)
   `text-white/60` → `text-white/70` on body text.

**Acceptance:**
- `npm run build` clean.
- Manual check: count-up still triggers correctly on TrustBar; HowItWorks scroll-pin still steps correctly; Header switches color on scroll.
- Lighthouse Performance: no regression.

---

## Execution Order

```
Step 0: 手测 feature/landing-demo-modal → merge → main           (no design, ops)
Step 1: PR-1 bug fixes                                            (sequential — unblocks everything)
Step 2: PR-3 copy/i18n + PR-2 conversion (parallel)               (low file overlap)
Step 3: PR-4 structure/mobile                                     (biggest review; serial)
Step 4: PR-5 P2 micro                                             (collapse window)
Step 5: All merged → tag landing-v1.0 → prod compose 切换         (separate spec)
```

## Testing Infrastructure

Vitest is already wired in (added on demo modal branch). For each PR:
- Add at least one snapshot or assertion test for any new/changed copy or i18n key.
- Manual: golden-path walk on desktop Chrome + iOS Safari (real device) + Android Chrome.
- Lighthouse before/after on the home page; no regression on Performance / Accessibility / Best Practices / SEO.

## Open Questions

1. **TrustBar real metrics** (PR-3 #1): do we have a public-safe MAU / messages-processed number to expose? If not, hardcode + footnote is acceptable per spec.
2. **ProductSelfServe "$20 wallet" target** (PR-2 #2): is the trial-grant flow accessible at `/portal/billing` or another route? Confirm during PR-2 implementation by grepping for trial-grant code.
3. **i18n translations for tagline & new strings**: spec provides default translations. If a native speaker is available, verify before merge; otherwise ship and iterate.

## Done Definition

- All 5 PRs merged to `main`.
- Lighthouse on `/` ≥ baseline scores recorded pre-PR-1.
- Real-device mobile pass on iPhone (Safari) + Android (Chrome).
- 5-language switch passes: no engineering jargon, no orphan strings, no copy contradictions with safety contracts.
- This spec's "Locked Product Decisions" all reflected in the rendered site.

After Done: this spec retires; the next spec is "Prod compose 切换 + go-live checklist".
