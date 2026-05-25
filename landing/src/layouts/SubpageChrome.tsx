/**
 * SubpageChrome — minimal header + footer for /docs /changelog /legal.
 *
 * Header is much simpler than the Home's (no in-page anchor nav, no
 * mobile sheet) because subpages don't need to TOC the home. Just:
 * BrandMark → home, language picker, Sign In, Free Trial.
 *
 * Footer is a one-line bar with a back-to-home link + copyright.
 */
import { Link } from 'react-router-dom';
import BrandMark from '@/components/BrandMark';
import LangSwitcher from '@/components/LangSwitcher';
import CTAButton from '@/components/CTAButton';
import { LINKS } from '@/lib/links';
import { Events } from '@/lib/analytics';
import type { ReactNode } from 'react';

export function SubpageHeader() {
  return (
    <header className="sticky top-0 z-40 bg-white/90 backdrop-blur-md border-b border-brand-ink-100">
      <div className="max-w-container mx-auto px-6 h-16 flex items-center justify-between gap-4">
        <Link to="/" className="shrink-0" aria-label="TG1.AI home">
          <BrandMark size="sm" />
        </Link>
        <div className="flex items-center gap-3">
          <LangSwitcher />
          <Link to={LINKS.signIn} className="hidden sm:inline-block text-sm text-brand-ink-700 hover:text-brand-ink-900 px-3 py-1.5">
            Sign In
          </Link>
          <CTAButton
            variant="primary"
            href={LINKS.trial}
            trackEvent={Events.CTA_SIGNUP_CLICK}
            trackProps={{ source: 'subpage_header' }}
            className="!px-4 !py-2 !text-sm"
            noIcon
          >
            Free $20
          </CTAButton>
        </div>
      </div>
    </header>
  );
}

export function SubpageFooter() {
  return (
    <footer className="border-t border-brand-ink-100 bg-brand-ink-50 mt-12">
      <div className="max-w-container mx-auto px-6 py-8 flex flex-wrap items-center justify-between gap-4 text-xs text-brand-ink-500 font-mono">
        <div className="flex items-center gap-4">
          <Link to="/" className="hover:text-brand-ink-900">← Back to home</Link>
          <Link to={LINKS.docs} className="hover:text-brand-ink-900">Docs</Link>
          <Link to={LINKS.changelog} className="hover:text-brand-ink-900">Changelog</Link>
          <Link to={LINKS.privacy} className="hover:text-brand-ink-900">Privacy</Link>
          <Link to={LINKS.tos} className="hover:text-brand-ink-900">Terms</Link>
        </div>
        <div>© {new Date().getFullYear()} TG1.AI</div>
      </div>
    </footer>
  );
}

/** Simple no-sidebar layout for changelog / legal. */
export function SimpleLayout({ children }: { children: ReactNode }) {
  return (
    <div className="min-h-screen flex flex-col bg-white">
      <SubpageHeader />
      <main className="flex-1">
        <div className="max-w-container mx-auto px-6 py-12 lg:py-16">
          {children}
        </div>
      </main>
      <SubpageFooter />
    </div>
  );
}
