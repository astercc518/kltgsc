/**
 * BackgroundField — composable atmospheric layer for dark sections.
 *
 * Combines four sub-layers that collectively give a "blueprint under
 * stage light" feel without any single layer being loud:
 *
 *   1. base radial    — bottom-to-top dim gradient (default direction
 *                       reads "horizon below the fold")
 *   2. engineering    — fine 56px grid, animated drift, fades to edges
 *                       via radial mask. Off by default — opt in for
 *                       hero / showpiece sections only.
 *   3. overhead beam  — soft 540×360 spotlight from above, slow breath
 *   4. noise          — 1.5% texture grain to break gradient banding
 *
 * Usage:
 *   <section className="relative overflow-hidden">
 *     <BackgroundField variant="hero" />
 *     ...content...
 *   </section>
 *
 * All layers absolute-positioned at -z-10 so the parent section needs
 * `relative overflow-hidden`. The component renders no real DOM
 * dimensions of its own.
 */
import type { CSSProperties } from 'react';

type Variant =
  | 'hero'        // grid + beam + radial + noise (max texture)
  | 'section'    // radial + noise (calm)
  | 'minimal';   // noise only

type Props = {
  variant?: Variant;
  /** Reduce grid opacity for sections that sit behind heavy content */
  gridOpacity?: number;
};

export default function BackgroundField({
  variant = 'section',
  gridOpacity = 0.6,
}: Props) {
  const showGrid = variant === 'hero';
  const showBeam = variant === 'hero';
  const showRadial = variant !== 'minimal';

  // Grid is masked with a radial fade so it disappears at section edges —
  // this is what separates "blueprint" from "spreadsheet".
  const gridStyle: CSSProperties = {
    backgroundSize: '56px 56px, 56px 56px',
    WebkitMaskImage:
      'radial-gradient(ellipse 70% 60% at 50% 30%, #000 0%, transparent 90%)',
    maskImage:
      'radial-gradient(ellipse 70% 60% at 50% 30%, #000 0%, transparent 90%)',
    opacity: gridOpacity,
  };

  return (
    <>
      {showRadial && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10 bg-grad-radial-dark"
        />
      )}
      {showGrid && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10 bg-grid-fine animate-grid-drift"
          style={gridStyle}
        />
      )}
      {showBeam && (
        <div
          aria-hidden
          className="pointer-events-none absolute inset-0 -z-10 bg-beam-overhead animate-beam-pulse"
        />
      )}
      <div
        aria-hidden
        className="pointer-events-none absolute inset-0 -z-10 bg-noise opacity-70 mix-blend-overlay"
      />
    </>
  );
}
