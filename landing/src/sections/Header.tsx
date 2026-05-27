/**
 * Header — sticky top nav with backdrop-blur once scrolled past hero.
 *
 * Layout:
 *   ┌─ BrandMark ─ nav links (Self-Serve / AI Assistant / Pricing / Docs)
 *   └─                                  LangSwitcher / Sign In / Free Trial
 *
 * Mobile (<md): collapses to BrandMark + hamburger that toggles a
 * full-screen sheet with the same links.
 *
 * Polish notes (2026-05-27 round 6):
 *   - Active-section indicator: nav link gets a 1px gradient underline
 *     when its target section is in the viewport. Tracked via
 *     IntersectionObserver with a -40% bottom rootMargin so a section
 *     "activates" when its top crosses the 60% mark.
 *   - Hover indicator: a fine underline grows in from left on hover
 *     for any non-active link, gives the chrome a "considered" feel.
 *   - Sign-in gets a vertical hairline separator from the nav.
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

/** Section IDs that map to in-page nav anchors */
const TRACKED_SECTION_IDS = ['self-serve', 'ai-assistant', 'pricing'];

export default function Header() {
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [activeId, setActiveId] = useState<string | null>(null);
  const t = useT();

  const navLinks: { label: string; href: string; trackedId: string | null }[] = [
    { label: t.nav.selfServe,   href: '#self-serve',   trackedId: 'self-serve' },
    { label: t.nav.aiAssistant, href: '#ai-assistant', trackedId: 'ai-assistant' },
    { label: t.nav.pricing,     href: '#pricing',      trackedId: 'pricing' },
    { label: t.nav.docs,        href: LINKS.docs,      trackedId: null },
  ];

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 24);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);

  /** Track which tracked section is currently in view. Active = nearest
      to the top of viewport with the title still visible. */
  useEffect(() => {
    const targets = TRACKED_SECTION_IDS
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null);
    if (targets.length === 0) return;

    const onIntersect: IntersectionObserverCallback = (entries) => {
      // Prefer the entry with the largest intersection ratio
      const visible = entries.filter((e) => e.isIntersecting);
      if (visible.length === 0) {
        // Falling through nothing — let the previous active stand until
        // another section enters. Avoids flicker between sections.
        return;
      }
      const top = visible.reduce((a, b) => (a.intersectionRatio > b.intersectionRatio ? a : b));
      setActiveId(top.target.id);
    };

    const observer = new IntersectionObserver(onIntersect, {
      // Section becomes active when its top crosses 25% from the viewport top
      rootMargin: '-25% 0px -55% 0px',
      threshold: [0, 0.25, 0.5, 1],
    });
    targets.forEach((t) => observer.observe(t));
    return () => observer.disconnect();
  }, []);

  return (
    <header
      className={[
        'sticky top-0 z-40 transition-all duration-300 ease-out',
        scrolled
          // Scrolled: refined frosted glass — saturate boost so brand colors stay punchy under blur
          ? 'bg-white/75 [backdrop-filter:saturate(180%)_blur(20px)] border-b border-brand-ink-100/80'
          : 'bg-transparent border-b border-transparent',
      ].join(' ')}
    >
      <div className="max-w-container mx-auto px-6 h-16 flex items-center justify-between gap-4">
        <Link to="/" className="shrink-0">
          <BrandMark size="sm" />
        </Link>

        {/* Desktop nav */}
        <nav
          className={[
            'hidden md:flex items-center gap-1 text-sm transition-colors',
            scrolled ? 'text-brand-ink-700' : 'text-white/75',
          ].join(' ')}
        >
          {navLinks.map((l) => {
            const isActive = l.trackedId !== null && activeId === l.trackedId;
            return (
              <a
                key={l.href}
                href={l.href}
                className={[
                  'group relative px-3 py-2 transition-colors duration-200',
                  scrolled ? 'hover:text-brand-ink-900' : 'hover:text-white',
                  isActive ? (scrolled ? 'text-brand-ink-900' : 'text-white') : '',
                ].join(' ')}
              >
                {l.label}
                {/* Indicator rule: gradient underline grows from left.
                    Active: full width. Hover (non-active): half width.
                    Sits 6px below baseline so it doesn't crowd descenders. */}
                <span
                  aria-hidden
                  className={[
                    'pointer-events-none absolute left-3 right-3 bottom-1 h-px origin-left transition-transform duration-300 ease-out',
                    scrolled
                      ? 'bg-gradient-to-r from-brand-blue-500 via-brand-blue-400 to-brand-purple-500'
                      : 'bg-gradient-to-r from-brand-blue-300 via-white to-brand-purple-200',
                    isActive
                      ? 'scale-x-100'
                      : 'scale-x-0 group-hover:scale-x-50',
                  ].join(' ')}
                />
              </a>
            );
          })}
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <LangSwitcher onDark={!scrolled} />
          {/* Vertical hairline separator — establishes that LangSwitcher
              belongs to chrome cluster, Sign In + CTA belong to action cluster */}
          <span
            aria-hidden
            className={[
              'h-5 w-px transition-colors',
              scrolled ? 'bg-brand-ink-200' : 'bg-white/15',
            ].join(' ')}
          />
          <a
            href={LINKS.signIn}
            className={[
              'text-sm px-3 py-1.5 transition-colors duration-200',
              scrolled
                ? 'text-brand-ink-700 hover:text-brand-ink-900'
                : 'text-white/80 hover:text-white',
            ].join(' ')}
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
          className={[
            'md:hidden p-2 transition-colors',
            scrolled ? 'text-brand-ink-700' : 'text-white/80',
          ].join(' ')}
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
