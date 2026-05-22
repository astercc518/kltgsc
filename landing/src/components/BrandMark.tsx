/**
 * BrandMark — TG1.AI wordmark.
 *
 * Renders an inline SVG `T·G·1` glyph next to the wordmark, with the `.AI`
 * accent painted in brand purple to echo the AI Marketing Assistant
 * accent across the site.
 *
 * Sizes are driven by the `size` prop ('sm' | 'md' | 'lg'), which maps to
 * coordinated text + icon scales so the wordmark stays optically balanced.
 */
type Size = 'sm' | 'md' | 'lg';

type Props = {
  size?: Size;
  /** Dark surface? Switch text to white. Default false. */
  onDark?: boolean;
  className?: string;
};

const SIZES: Record<Size, { wrapper: string; icon: number; text: string }> = {
  sm: { wrapper: 'gap-2',  icon: 22, text: 'text-lg  font-display font-bold' },
  md: { wrapper: 'gap-2.5', icon: 28, text: 'text-2xl font-display font-bold' },
  lg: { wrapper: 'gap-3',  icon: 40, text: 'text-4xl font-display font-bold' },
};

export default function BrandMark({ size = 'md', onDark, className }: Props) {
  const s = SIZES[size];
  return (
    <span
      className={['inline-flex items-center', s.wrapper, className || ''].join(' ')}
      aria-label="TG1.AI"
    >
      <svg
        width={s.icon}
        height={s.icon}
        viewBox="0 0 40 40"
        fill="none"
        xmlns="http://www.w3.org/2000/svg"
        aria-hidden
      >
        <defs>
          <linearGradient id="tg1-mark" x1="0" y1="0" x2="40" y2="40" gradientUnits="userSpaceOnUse">
            <stop stopColor="#0066FF" />
            <stop offset="1" stopColor="#A855F7" />
          </linearGradient>
        </defs>
        {/* rounded square with stylized telegram-paper-plane diagonal */}
        <rect width="40" height="40" rx="9" fill="url(#tg1-mark)" />
        <path
          d="M9 21.5L31 11l-6.5 19-7-7-2 5z"
          fill="white"
          fillOpacity="0.95"
        />
      </svg>
      <span className={s.text}>
        <span className={onDark ? 'text-white' : 'text-brand-ink-900'}>TG1</span>
        <span className="text-brand-purple-500">.AI</span>
      </span>
    </span>
  );
}
