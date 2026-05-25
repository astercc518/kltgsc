/**
 * DocsLayout — header + left-sidebar nav + right-content for /docs pages.
 *
 * Sidebar lists every doc article; the active slug is highlighted.
 * On mobile (<lg), sidebar collapses to a top dropdown.
 *
 * Doc content goes inside <article className="prose-tg1"> so it inherits
 * brand typography from prose.css. Below the article, a prev/next
 * footer wires up navigation through the ordered doc list.
 */
import { Link, useLocation } from 'react-router-dom';
import { ArrowLeft, ArrowRight } from 'lucide-react';
import { SubpageHeader, SubpageFooter } from './SubpageChrome';
import type { ReactNode } from 'react';

export type DocSlug = 'quickstart' | 'modules' | 'api' | 'billing';

export type DocMeta = {
  slug: DocSlug;
  title: string;
  description: string;
};

export const DOC_ORDER: DocMeta[] = [
  { slug: 'quickstart', title: 'Quickstart',        description: 'From sign-up to first lead in 15 minutes.' },
  { slug: 'modules',    title: 'Module dictionary', description: 'TEN · BIL · ALC · KBA · LED · OPS — the 6 platform modules.' },
  { slug: 'api',        title: 'API examples',      description: 'Sample curl calls for the most-asked endpoints.' },
  { slug: 'billing',    title: 'Billing rules',     description: 'Subscription + wallet, half-automatic AI, paused_no_funds.' },
];

export default function DocsLayout({ children, slug }: { children: ReactNode; slug?: DocSlug }) {
  const location = useLocation();
  const active = slug ?? (DOC_ORDER.find((d) => location.pathname.endsWith(d.slug))?.slug);

  const idx = DOC_ORDER.findIndex((d) => d.slug === active);
  const prev = idx > 0 ? DOC_ORDER[idx - 1] : null;
  const next = idx >= 0 && idx < DOC_ORDER.length - 1 ? DOC_ORDER[idx + 1] : null;

  return (
    <div className="min-h-screen flex flex-col bg-white">
      <SubpageHeader />
      <main className="flex-1">
        <div className="max-w-container mx-auto px-6 py-10 lg:py-14 grid lg:grid-cols-[220px_1fr] gap-10">
          {/* Sidebar (desktop) / dropdown (mobile) */}
          <aside className="hidden lg:block">
            <div className="sticky top-24">
              <div className="text-eyebrow font-mono text-brand-ink-500 uppercase mb-3">
                Docs
              </div>
              <nav className="space-y-1">
                {DOC_ORDER.map((doc) => {
                  const isActive = doc.slug === active;
                  return (
                    <Link
                      key={doc.slug}
                      to={`/docs/${doc.slug}`}
                      className={[
                        'block px-3 py-2 rounded-lg text-sm transition-colors',
                        isActive
                          ? 'bg-brand-blue-50 text-brand-blue-700 font-medium'
                          : 'text-brand-ink-600 hover:bg-brand-ink-50 hover:text-brand-ink-900',
                      ].join(' ')}
                    >
                      {doc.title}
                    </Link>
                  );
                })}
              </nav>
              <div className="mt-8 rounded-xl border border-brand-ink-100 bg-brand-ink-50 p-4 text-xs text-brand-ink-500">
                Found an error?{' '}
                <a href="https://github.com/astercc518/kltgsc/issues" target="_blank" rel="noopener" className="text-brand-blue-600 underline underline-offset-2">
                  Open an issue
                </a>
                .
              </div>
            </div>
          </aside>

          {/* Mobile dropdown */}
          <div className="lg:hidden">
            <label className="text-eyebrow font-mono text-brand-ink-500 uppercase block mb-2">
              Docs section
            </label>
            <select
              className="w-full rounded-lg border border-brand-ink-200 px-3 py-2 text-sm font-medium text-brand-ink-900"
              value={active ?? ''}
              onChange={(e) => {
                window.location.assign(`/docs/${e.target.value}`);
              }}
            >
              {DOC_ORDER.map((doc) => (
                <option key={doc.slug} value={doc.slug}>
                  {doc.title}
                </option>
              ))}
            </select>
          </div>

          {/* Content */}
          <div className="min-w-0">
            <article className="prose-tg1">
              {children}
            </article>

            {(prev || next) && (
              <nav className="mt-16 pt-8 border-t border-brand-ink-100 grid sm:grid-cols-2 gap-4">
                {prev ? (
                  <Link to={`/docs/${prev.slug}`} className="group p-4 rounded-xl border border-brand-ink-100 hover:border-brand-ink-300 transition-colors">
                    <div className="flex items-center gap-2 text-eyebrow font-mono text-brand-ink-500 uppercase mb-1">
                      <ArrowLeft className="w-3 h-3" /> Previous
                    </div>
                    <div className="font-display font-semibold text-brand-ink-900 group-hover:text-brand-blue-600">
                      {prev.title}
                    </div>
                  </Link>
                ) : (
                  <div />
                )}
                {next && (
                  <Link to={`/docs/${next.slug}`} className="group p-4 rounded-xl border border-brand-ink-100 hover:border-brand-ink-300 transition-colors text-right">
                    <div className="flex items-center justify-end gap-2 text-eyebrow font-mono text-brand-ink-500 uppercase mb-1">
                      Next <ArrowRight className="w-3 h-3" />
                    </div>
                    <div className="font-display font-semibold text-brand-ink-900 group-hover:text-brand-blue-600">
                      {next.title}
                    </div>
                  </Link>
                )}
              </nav>
            )}
          </div>
        </div>
      </main>
      <SubpageFooter />
    </div>
  );
}
