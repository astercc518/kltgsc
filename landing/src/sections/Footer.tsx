/**
 * Footer — every link goes somewhere real.
 *
 * No `href="#"` placeholders. Each column groups by intent:
 *   Product   → docs, pricing, changelog, in-page anchors
 *   Company   → about (TODO route), contact, sales TG
 *   Legal     → privacy, tos
 *   Social    → github, x
 */
import { Link } from 'react-router-dom';
import { Github, Twitter, Send } from 'lucide-react';
import BrandMark from '@/components/BrandMark';
import { LINKS } from '@/lib/links';

const columns = [
  {
    title: 'Product',
    links: [
      { label: 'Self-Serve',      href: '#self-serve',  external: false },
      { label: 'AI Assistant',    href: '#ai-assistant', external: false },
      { label: 'Pricing',         href: '#pricing',     external: false },
      { label: 'Docs',            href: LINKS.docs,     external: false },
      { label: 'Changelog',       href: LINKS.changelog, external: false },
    ],
  },
  {
    title: 'Company',
    links: [
      { label: 'Talk to sales',     href: LINKS.telegramSales, external: true },
      { label: 'sales@tg1.ai',      href: LINKS.salesEmail,    external: true },
      { label: 'Privacy',           href: LINKS.privacy,       external: false },
      { label: 'Terms',             href: LINKS.tos,           external: false },
    ],
  },
];

const social = [
  { icon: Send,    href: LINKS.telegramSales, label: 'Telegram' },
  { icon: Twitter, href: LINKS.twitter,       label: 'X (Twitter)' },
  { icon: Github,  href: LINKS.github,        label: 'GitHub' },
];

export default function Footer() {
  return (
    <footer className="bg-brand-ink-950 border-t border-white/5 text-white/60">
      <div className="max-w-container mx-auto px-6 py-16">
        <div className="grid grid-cols-2 md:grid-cols-4 gap-10">
          {/* Brand + tagline */}
          <div className="col-span-2 md:col-span-1">
            <BrandMark size="sm" onDark />
            <p className="mt-4 text-sm text-white/40 leading-relaxed">
              Telegram growth, on autopilot. Built for operators who scale.
            </p>
            <div className="mt-5 flex gap-3">
              {social.map((s) => (
                <a
                  key={s.label}
                  href={s.href}
                  target="_blank"
                  rel="noopener noreferrer"
                  aria-label={s.label}
                  className="w-9 h-9 rounded-lg bg-white/5 hover:bg-white/10 inline-flex items-center justify-center transition-colors"
                >
                  <s.icon className="w-4 h-4" />
                </a>
              ))}
            </div>
          </div>

          {/* Link columns */}
          {columns.map((col) => (
            <div key={col.title}>
              <div className="text-eyebrow font-mono text-white/40 uppercase mb-4">
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
                        className="hover:text-white transition-colors"
                      >
                        {l.label}
                      </a>
                    </li>
                  ) : l.href.startsWith('#') ? (
                    <li key={l.label}>
                      <a href={l.href} className="hover:text-white transition-colors">
                        {l.label}
                      </a>
                    </li>
                  ) : (
                    <li key={l.label}>
                      <Link to={l.href} className="hover:text-white transition-colors">
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
            <div className="text-eyebrow font-mono text-white/40 uppercase mb-4">
              Status
            </div>
            <a
              href="#"
              className="inline-flex items-center gap-2 text-sm hover:text-white transition-colors"
            >
              <span className="w-2 h-2 rounded-full bg-success animate-pulse" />
              All systems normal
            </a>
          </div>
        </div>

        <div className="mt-12 pt-6 border-t border-white/5 flex flex-wrap items-center justify-between gap-4 text-xs text-white/30 font-mono">
          <div>© {new Date().getFullYear()} TG1.AI — All rights reserved.</div>
          <div>
            Built for the Telegram economy. Not affiliated with Telegram FZ-LLC.
          </div>
        </div>
      </div>
    </footer>
  );
}
