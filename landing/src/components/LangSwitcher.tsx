/**
 * LangSwitcher — dropdown for the 5 supported languages.
 *
 * Uses the legacy `useLang()` hook from `src/i18n.ts` (which manages the
 * language state in localStorage). When a new language is picked, the
 * provider updates `document.documentElement.lang` and persists.
 *
 * Visually a ghost button with a Languages icon + native name. On click
 * shows a small menu. Closes on outside click / Escape.
 */
import { Languages, Check, ChevronDown } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { LANGS, useLang, type Lang } from '@/i18n';
import { track, Events } from '@/lib/analytics';

type Props = {
  onDark?: boolean;
  className?: string;
};

export default function LangSwitcher({ onDark, className }: Props) {
  const { lang, setLang } = useLang();
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e: MouseEvent) => {
      if (!rootRef.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') setOpen(false); };
    document.addEventListener('mousedown', onClick);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onClick);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  const current = LANGS.find((l) => l.code === lang) ?? LANGS[0];

  const pick = (code: Lang) => {
    setLang(code);
    track(Events.LANG_SWITCH, { from: lang, to: code });
    setOpen(false);
  };

  const textColor = onDark ? 'text-white/80 hover:text-white' : 'text-brand-ink-700 hover:text-brand-ink-900';
  const borderColor = onDark ? 'border-white/15 hover:border-white/30' : 'border-brand-ink-200 hover:border-brand-ink-300';

  return (
    <div ref={rootRef} className={['relative', className || ''].join(' ')}>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={[
          'inline-flex items-center gap-1.5 rounded-full border px-3 py-1.5 text-sm transition-colors',
          textColor,
          borderColor,
        ].join(' ')}
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-label={`Language: ${current.english}`}
      >
        <Languages className="w-4 h-4" aria-hidden />
        <span className="font-medium">{current.native}</span>
        <ChevronDown className={`w-3.5 h-3.5 transition-transform ${open ? 'rotate-180' : ''}`} aria-hidden />
      </button>

      {open && (
        <ul
          role="listbox"
          className="absolute right-0 top-full mt-2 min-w-[180px] rounded-xl border border-brand-ink-200 bg-white shadow-card-hover overflow-hidden z-50"
        >
          {LANGS.map((l) => {
            const active = l.code === lang;
            return (
              <li key={l.code} role="option" aria-selected={active}>
                <button
                  type="button"
                  onClick={() => pick(l.code)}
                  className={[
                    'flex w-full items-center justify-between gap-2 px-3.5 py-2 text-sm',
                    active
                      ? 'bg-brand-blue-50 text-brand-blue-700'
                      : 'text-brand-ink-700 hover:bg-brand-ink-50',
                  ].join(' ')}
                >
                  <span className="flex items-center gap-2">
                    <span className="font-medium">{l.native}</span>
                    <span className="text-brand-ink-400 text-xs">{l.english}</span>
                  </span>
                  {active && <Check className="w-4 h-4" aria-hidden />}
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
