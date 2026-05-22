/**
 * CTAButton — three variants matching the landing's conversion ladder.
 *
 *   primary    Free $20 Trial (highest intent — visible blue gradient pill)
 *   secondary  Watch 90s Demo (medium — outlined, opens video modal)
 *   tertiary   Talk on Telegram (low — ghost + paper plane icon)
 *
 * Wraps an <a> by default (so right-click → open in new tab works). If
 * `onClick` is provided, the click handler still fires before the link
 * follows (useful for analytics).
 *
 * Analytics: pass `trackEvent` to fire a Plausible event when clicked.
 */
import { ArrowRight, Send, PlayCircle } from 'lucide-react';
import type { ReactNode, MouseEventHandler } from 'react';
import { track } from '@/lib/analytics';

type Variant = 'primary' | 'secondary' | 'tertiary';

type Props = {
  variant?: Variant;
  href: string;
  children: ReactNode;
  /** External link opens in a new tab. */
  external?: boolean;
  /** Plausible event name to fire on click. */
  trackEvent?: string;
  /** Extra props for analytics. */
  trackProps?: Record<string, string | number | boolean>;
  /** Extra click handler that runs before navigation. */
  onClick?: MouseEventHandler<HTMLAnchorElement>;
  /** Override Tailwind classes (appended). */
  className?: string;
  /** Hide the default trailing icon. */
  noIcon?: boolean;
};

const baseClasses =
  'inline-flex items-center justify-center gap-2 font-medium ' +
  'rounded-full px-6 py-3 text-base ' +
  'transition-all duration-150 active:scale-[0.98] ' +
  'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-offset-2';

const variantClasses: Record<Variant, string> = {
  primary:
    'bg-brand-blue-500 text-white shadow-glow-blue ' +
    'hover:bg-brand-blue-600 focus-visible:ring-brand-blue-500',
  secondary:
    'bg-white text-brand-ink-900 border border-brand-ink-200 ' +
    'hover:border-brand-ink-300 hover:bg-brand-ink-50 ' +
    'focus-visible:ring-brand-ink-300',
  tertiary:
    'text-brand-ink-700 hover:text-brand-blue-600 ' +
    'focus-visible:ring-brand-ink-300',
};

const variantIcon: Record<Variant, typeof ArrowRight> = {
  primary:   ArrowRight,
  secondary: PlayCircle,
  tertiary:  Send,
};

export default function CTAButton({
  variant = 'primary', href, children, external, trackEvent, trackProps,
  onClick, className, noIcon,
}: Props) {
  const Icon = variantIcon[variant];

  const handleClick: MouseEventHandler<HTMLAnchorElement> = (e) => {
    if (trackEvent) track(trackEvent, trackProps);
    onClick?.(e);
  };

  return (
    <a
      href={href}
      target={external ? '_blank' : undefined}
      rel={external ? 'noopener noreferrer' : undefined}
      onClick={handleClick}
      className={[baseClasses, variantClasses[variant], className || ''].join(' ')}
    >
      <span>{children}</span>
      {!noIcon && <Icon className="w-4 h-4" aria-hidden />}
    </a>
  );
}
