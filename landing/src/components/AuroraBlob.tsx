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
