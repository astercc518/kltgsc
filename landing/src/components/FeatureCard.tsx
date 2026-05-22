/**
 * FeatureCard — one feature in a grid.
 *
 * Variants:
 *   `blue`   Self-Serve product accent
 *   `purple` AI Marketing Assistant product accent
 *   `neutral` Plain (for security / generic features)
 *
 * Hover lifts the card and reveals a glow that matches the accent.
 * Pass a Lucide / Phosphor icon component (anything that accepts
 * `className` / `size` like other React icon libraries).
 */
import type { ComponentType, ReactNode } from 'react';

type Accent = 'blue' | 'purple' | 'neutral';

type IconProps = { className?: string; size?: number | string };

type Props = {
  icon?: ComponentType<IconProps>;
  title: string;
  description: ReactNode;
  accent?: Accent;
  /** Small overline above the title (e.g. price). Use `font-mono`. */
  badge?: ReactNode;
  className?: string;
};

const accentClasses: Record<Accent, { iconWrap: string; iconColor: string; hoverGlow: string }> = {
  blue: {
    iconWrap:  'bg-brand-blue-50',
    iconColor: 'text-brand-blue-600',
    hoverGlow: 'hover:shadow-glow-blue',
  },
  purple: {
    iconWrap:  'bg-brand-purple-50',
    iconColor: 'text-brand-purple-600',
    hoverGlow: 'hover:shadow-glow-purple',
  },
  neutral: {
    iconWrap:  'bg-brand-ink-100',
    iconColor: 'text-brand-ink-700',
    hoverGlow: 'hover:shadow-card-hover',
  },
};

export default function FeatureCard({
  icon: Icon, title, description, accent = 'neutral', badge, className,
}: Props) {
  const c = accentClasses[accent];
  return (
    <div
      className={[
        'group relative p-6 rounded-2xl bg-white border border-brand-ink-100',
        'shadow-card transition-all duration-200 hover:-translate-y-0.5',
        c.hoverGlow,
        className || '',
      ].join(' ')}
    >
      {Icon && (
        <div className={[
          'inline-flex items-center justify-center w-10 h-10 rounded-xl mb-4',
          c.iconWrap,
          c.iconColor,
        ].join(' ')}>
          <Icon size={20} aria-hidden />
        </div>
      )}
      {badge && (
        <div className="text-eyebrow text-brand-ink-500 mb-1 uppercase font-mono">
          {badge}
        </div>
      )}
      <h3 className="font-display text-lg font-semibold text-brand-ink-900 mb-2">
        {title}
      </h3>
      <p className="text-sm leading-relaxed text-brand-ink-600">
        {description}
      </p>
    </div>
  );
}
