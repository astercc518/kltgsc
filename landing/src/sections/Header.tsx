/**
 * Header — sticky top nav with backdrop-blur once scrolled past hero.
 *
 * Layout:
 *   ┌─ BrandMark ─ nav links (Self-Serve / AI Assistant / Pricing / Docs)
 *   └─                                  LangSwitcher / Sign In / Free Trial
 *
 * Mobile (<md): collapses to BrandMark + hamburger that toggles a
 * full-screen sheet with the same links.
 */
import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Menu, X } from 'lucide-react';
import BrandMark from '@/components/BrandMark';
import LangSwitcher from '@/components/LangSwitcher';
import CTAButton from '@/components/CTAButton';
import { LINKS } from '@/lib/links';
import { Events } from '@/lib/analytics';
import { useT } from '@/i18n';

export default function Header() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const t = useT();

  const navLinks = [
    { label: t.nav.selfServe,   href: '#self-serve' },
    { label: t.nav.aiAssistant, href: '#ai-assistant' },
    { label: t.nav.pricing,     href: '#pricing' },
    { label: t.nav.docs,        href: LINKS.docs },
  ];

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  return (
    <header
      className={[
        'sticky top-0 z-40 transition-all duration-200',
        scrolled
          ? 'bg-white/80 backdrop-blur-xl border-b border-brand-ink-100'
          : 'bg-transparent border-b border-transparent',
      ].join(' ')}
    >
      <div className="max-w-container mx-auto px-6 h-16 flex items-center justify-between gap-4">
        <Link to="/" className="shrink-0">
          <BrandMark size="sm" />
        </Link>

        {/* Desktop nav */}
        <nav className="hidden md:flex items-center gap-8 text-sm text-brand-ink-700">
          {navLinks.map((l) => (
            <a key={l.href} href={l.href} className="hover:text-brand-ink-900 transition-colors">
              {l.label}
            </a>
          ))}
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <LangSwitcher />
          <a
            href={LINKS.signIn}
            className="text-sm text-brand-ink-700 hover:text-brand-ink-900 px-3 py-1.5"
          >
            {t.nav.signIn}
          </a>
          <CTAButton
            variant="primary"
            href={LINKS.trial}
            trackEvent={Events.CTA_SIGNUP_CLICK}
            trackProps={{ source: 'header' }}
            className="!px-4 !py-2 !text-sm"
            noIcon
          >
            {t.nav.freeTrial}
          </CTAButton>
        </div>

        {/* Mobile hamburger */}
        <button
          type="button"
          className="md:hidden text-brand-ink-700 p-2"
          onClick={() => setMobileOpen(true)}
          aria-label="Open menu"
        >
          <Menu className="w-6 h-6" />
        </button>
      </div>

      {/* Mobile sheet */}
      {mobileOpen && (
        <div className="md:hidden fixed inset-0 z-50 bg-white">
          <div className="flex items-center justify-between px-6 h-16 border-b border-brand-ink-100">
            <BrandMark size="sm" />
            <button
              type="button"
              onClick={() => setMobileOpen(false)}
              className="text-brand-ink-700 p-2"
              aria-label="Close menu"
            >
              <X className="w-6 h-6" />
            </button>
          </div>
          <nav className="flex flex-col gap-1 px-6 py-6 text-lg">
            {navLinks.map((l) => (
              <a
                key={l.href}
                href={l.href}
                onClick={() => setMobileOpen(false)}
                className="py-3 text-brand-ink-700 hover:text-brand-blue-500"
              >
                {l.label}
              </a>
            ))}
            <a
              href={LINKS.signIn}
              className="py-3 text-brand-ink-700"
            >
              {t.nav.signIn}
            </a>
            <div className="py-4">
              <LangSwitcher />
            </div>
            <CTAButton
              variant="primary"
              href={LINKS.trial}
              trackEvent={Events.CTA_SIGNUP_CLICK}
              trackProps={{ source: 'header_mobile' }}
              noIcon
            >
              {t.nav.freeTrial}
            </CTAButton>
          </nav>
        </div>
      )}
    </header>
  );
}
