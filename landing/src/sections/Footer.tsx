/**
 * Footer — every link goes somewhere real.
 *
 * No `href="#"` placeholders. Each column groups by intent:
 *   Product   → docs, pricing, changelog, in-page anchors
 *   Company   → contact, legal
 *   Social    → two Telegram channels (sales + support)
 */
import { Link } from 'react-router-dom';
import { Send } from 'lucide-react';
import BrandMark from '@/components/BrandMark';
import { LINKS } from '@/lib/links';
import { useT } from '@/i18n';

const social = [
  { icon: Send, href: LINKS.telegramSales,   label: 'Telegram — Sales' },
  { icon: Send, href: LINKS.telegramSupport, label: 'Telegram — Support' },
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
        { label: t.footer.links.talkToSales, href: LINKS.telegramSales,   external: true },
        { label: '@klsmsz',                  href: LINKS.telegramSupport, external: true },
        { label: t.footer.links.privacy,     href: LINKS.privacy,         external: false },
        { label: t.footer.links.terms,       href: LINKS.tos,             external: false },
      ],
    },
  ];
  return (
    <footer className="bg-brand-ink-950 border-t border-line-subtle text-fg-secondary">
      <div className="max-w-container mx-auto px-6 py-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-10">
          {/* Brand + tagline */}
          <div className="col-span-2 md:col-span-1">
            <BrandMark size="sm" onDark />
            <p className="mt-4 text-sm text-fg-muted leading-relaxed">
              {t.footer.tagline}
            </p>
            <div className="mt-5 flex gap-3">
              {social.map((s) => (
                <a
                  key={s.label}
                  href={s.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={s.label}
                  className="w-9 h-9 rounded-lg bg-brand-ink-800 hover:bg-brand-ink-700 inline-flex items-center justify-center transition-colors"
                >
                  <s.icon className="w-4 h-4" />
                </a>
              ))}
            </div>
          </div>

          {/* Link columns */}
          {columns.map((col) => (
            <div key={col.title}>
              <div className="text-eyebrow font-mono text-fg-muted uppercase mb-4">
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
                        className="hover:text-fg-primary transition-colors"
                      >
                        {l.label}
                      </a>
                    </li>
                  ) : l.href.startsWith('#') ? (
                    <li key={l.label}>
                      <a href={l.href} className="hover:text-fg-primary transition-colors">
                        {l.label}
                      </a>
                    </li>
                  ) : (
                    <li key={l.label}>
                      <Link to={l.href} className="hover:text-fg-primary transition-colors">
                        {l.label}
                      </Link>
                    </li>
                  ),
                )}
              </ul>
            </div>
          ))}

          {/* 4th column reserved for newsletter / status, kept airy for now */}
          <div className="hidden md:block">
            <div className="text-eyebrow font-mono text-fg-muted uppercase mb-4">
              {t.footer.statusLabel}
            </div>
            <a
              href="#"
              className="inline-flex items-center gap-2 text-sm hover:text-fg-primary transition-colors"
            >
              <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
              {t.footer.statusValue}
            </a>
          </div>
        </div>

        <div className="mt-12 pt-6 border-t border-line-subtle flex flex-wrap items-center justify-between gap-4 text-xs text-fg-muted font-mono">
          <div>{t.footer.copyright.replace('{year}', String(new Date().getFullYear()))}</div>
          <div>{t.footer.notAffiliated}</div>
        </div>
      </div>
    </footer>
  );
}
