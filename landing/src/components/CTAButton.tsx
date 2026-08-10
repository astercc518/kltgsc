/**
 * CTAButton — three variants matching the landing's conversion ladder.
 *
 *   primary    Free $20 Trial (highest intent — visible blue gradient pill)
 *   secondary  Watch 90s Demo (medium — outlined, opens video modal)
 *   tertiary   Talk on Telegram (low — ghost + paper plane icon)
 *
 * Renders as `<a>` when `href` is provided (right-click → open in new tab
 * works for navigation CTAs). Renders as `<button type="button">` when
 * only `onClick` is provided (action CTAs like opening a modal — avoids
 * the URL hash flash from `href="#"` + preventDefault).
 *
 * Analytics: pass `trackEvent` to fire a Plausible event when clicked.
 */
import { ArrowRight, Send, PlayCircle } from 'lucide-react';
import type { ReactNode, MouseEventHandler } from 'react';
import { track } from '@/lib/analytics';

type Variant = 'primary' | 'secondary' | 'tertiary';

type Props = {
  variant?: Variant;
  /** Render as `<a href>` for navigation. Omit to render as `<button>`. */
  href?: string;
  children: ReactNode;
  /** External link opens in a new tab. Ignored when rendering as `<button>`. */
  external?: boolean;
  /** Plausible event name to fire on click. */
  trackEvent?: string;
  /** Extra props for analytics. */
  trackProps?: Record<string, string | number | boolean>;
  /** Click handler. Required when `href` is omitted. */
  onClick?: MouseEventHandler<HTMLElement>;
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
    'group relative overflow-hidden ' +
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
  const cls = [baseClasses, variantClasses[variant], className || ''].join(' ');

  const handleClick: MouseEventHandler<HTMLElement> = (e) => {
    if (trackEvent) track(trackEvent, trackProps);
    onClick?.(e);
  };

  const content = (
    <>
      {variant === 'primary' && (
        <span
          aria-hidden
          className="pointer-events-none absolute inset-0 -translate-x-full bg-gradient-to-r from-transparent via-white/25 to-transparent transition-transform duration-700 ease-out group-hover:translate-x-full"
          style={{ backgroundSize: '200% 100%' }}
        />
      )}
      <span className="relative">{children}</span>
      {!noIcon && <Icon className="w-4 h-4 relative" aria-hidden />}
    </>
  );

  if (href === undefined) {
    return (
      <button type="button" onClick={handleClick} className={cls}>
        {content}
      </button>
    );
  }

  return (
    <a
      href={href}
      target={external ? '_blank' : undefined}
      rel={external ? 'noopener noreferrer' : undefined}
      onClick={handleClick}
      className={cls}
    >
      {content}
    </a>
  );
}
