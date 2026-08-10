/**
 * Footer — every link goes somewhere real.
 *
 * No `href="#"` placeholders. Each column groups by intent:
 *   Product   → docs, pricing, changelog, in-page anchors
 *   Company   → talkToSales, contact, legal
 *   Brand     → mark + tagline + socials + status indicator
 *
 * Polish notes (2026-05-26 round 2):
 *   - 3-column grid (was 4) — status indicator folded into brand column.
 *   - Mono column headings get the editorial dot + tracking treatment.
 *   - Tagline uses fg-secondary instead of `white/40` for clearer contrast.
 *   - Bottom row gets a tabular-nums monospace year + tiny build-version
 *     anchor (vite version + build date if we add it later).
 *   - Status indicator is a <span>, not a dead `<a href="#">`.
 */
import { Link } from 'react-router-dom';
import { Github, Twitter, Send } from 'lucide-react';
import BrandMark from '@/components/BrandMark';
import { LINKS } from '@/lib/links';
import { useT } from '@/i18n';

const social = [
  { icon: Send,    href: LINKS.telegramSales, label: 'Telegram' },
  { icon: Twitter, href: LINKS.twitter,       label: 'X (Twitter)' },
  { icon: Github,  href: LINKS.github,        label: 'GitHub' },
];

export default function Footer() {
  const t = useT();

  const columns = [
    {
      title: t.footer.columns.product,
      links: [
        { label: t.footer.links.selfServe,   href: '#self-serve',  external: false },
        { label: t.footer.links.aiAssistant, href: '#ai-assistant', external: false },
        { label: t.footer.links.pricing,     href: '#pricing',     external: false },
        { label: t.footer.links.docs,        href: LINKS.docs,     external: false },
        { label: t.footer.links.changelog,   href: LINKS.changelog, external: false },
      ],
    },
    {
      title: t.footer.columns.company,
      links: [
        { label: t.footer.links.talkToSales, href: LINKS.telegramSales, external: true },
        { label: 'sales@tg1.ai',             href: LINKS.salesEmail,    external: true },
        { label: t.footer.links.privacy,     href: LINKS.privacy,       external: false },
        { label: t.footer.links.terms,       href: LINKS.tos,           external: false },
      ],
    },
  ];
  return (
    <footer className="bg-brand-ink-950 border-t border-line-subtle text-fg-secondary relative overflow-hidden">
      {/* Fine top hairline that fades to edges — same treatment as TrustBar */}
      <div className="absolute inset-x-0 top-0 h-px bg-gradient-to-r from-transparent via-white/[0.10] to-transparent" />
      <div className="max-w-container mx-auto px-6 py-16">
        <div className="grid grid-cols-2 md:grid-cols-3 gap-10">
          {/* Brand + tagline + socials + status */}
          <div className="col-span-2 md:col-span-1">
            <BrandMark size="sm" onDark />
            <p className="mt-4 text-sm text-fg-secondary leading-relaxed max-w-xs">
              {t.footer.tagline}
            </p>
            <div className="mt-5 flex gap-2">
              {social.map((s) => (
                <a
                  key={s.label}
                  href={s.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={s.label}
                  className="w-9 h-9 rounded-lg bg-surface-2 border border-line-subtle hover:bg-surface-3 hover:border-line-medium inline-flex items-center justify-center text-fg-secondary hover:text-fg-primary transition-colors"
                >
                  <s.icon className="w-4 h-4" />
                </a>
              ))}
            </div>
            {/* Status indicator — informational, not interactive */}
            <span
              className="mt-6 inline-flex items-center gap-2 text-xs font-mono uppercase tracking-[0.14em] text-fg-muted"
              style={{ fontVariantNumeric: 'tabular-nums' }}
            >
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-pulse-soft rounded-full bg-success/40" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
              </span>
              {t.footer.statusValue}
            </span>
          </div>

          {/* Link columns */}
          {columns.map((col) => (
            <div key={col.title}>
              <div className="inline-flex items-center gap-2 font-mono uppercase text-[0.6875rem] tracking-[0.16em] text-fg-muted mb-5">
                <span className="h-px w-6 bg-white/20" />
                {col.title}
              </div>
              <ul className="space-y-3 text-sm">
                {col.links.map((l) =>
                  l.external ? (
                    <li key={l.label}>
                      <a
                        href={l.href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="text-fg-secondary hover:text-fg-primary transition-colors"
                      >
                        {l.label}
                      </a>
                    </li>
                  ) : l.href.startsWith('#') ? (
                    <li key={l.label}>
                      <a href={l.href} className="text-fg-secondary hover:text-fg-primary transition-colors">
                        {l.label}
                      </a>
                    </li>
                  ) : (
                    <li key={l.label}>
                      <Link to={l.href} className="text-fg-secondary hover:text-fg-primary transition-colors">
                        {l.label}
                      </Link>
                    </li>
                  ),
                )}
              </ul>
            </div>
          ))}
        </div>

        <div
          className="mt-14 pt-6 border-t border-line-subtle flex flex-wrap items-center justify-between gap-4 text-xs text-fg-muted font-mono"
          style={{ fontVariantNumeric: 'tabular-nums' }}
        >
          <div>{t.footer.copyright.replace('{year}', String(new Date().getFullYear()))}</div>
          <div>{t.footer.notAffiliated}</div>
        </div>
      </div>
    </footer>
  );
}
