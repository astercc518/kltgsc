/**
 * /changelog — most-recent-first list of monthly mdx releases.
 *
 * Each month is its own mdx file under src/content/changelog/. To add
 * a new month: create YYYY-MM.mdx and prepend it to the `MONTHS`
 * array. Articles render inside .prose-tg1 so brand typography is
 * inherited automatically.
 */
import { lazy, Suspense } from 'react';
import { SimpleLayout } from '@/layouts/SubpageChrome';

const M_2026_05 = lazy(() => import('@/content/changelog/2026-05.mdx'));
const M_2026_04 = lazy(() => import('@/content/changelog/2026-04.mdx'));
const M_2026_03 = lazy(() => import('@/content/changelog/2026-03.mdx'));

const MONTHS = [
  { id: '2026-05', label: 'May 2026', Comp: M_2026_05 },
  { id: '2026-04', label: 'April 2026', Comp: M_2026_04 },
  { id: '2026-03', label: 'March 2026', Comp: M_2026_03 },
] as const;

export default function Changelog() {
  return (
    <SimpleLayout>
      <div className="prose-tg1 max-w-none">
        <header className="mb-8">
          <div className="text-eyebrow font-mono text-brand-ink-500 uppercase mb-2">
            Changelog
          </div>
          <h1 className="!mt-0">What shipped, month by month.</h1>
          <p className="text-brand-ink-500">
            Newest first. Each section pairs with the live product — if you
            see a feature here, it's deployed.
          </p>
        </header>

        {MONTHS.map(({ id, label, Comp }) => (
          <section key={id} id={id} className="border-t border-brand-ink-100 pt-12 first:border-0 first:pt-0">
            <div className="text-eyebrow font-mono text-brand-ink-500 uppercase mb-4 not-prose">
              <a href={`#${id}`} className="hover:text-brand-ink-900">
                {label}
              </a>
            </div>
            <Suspense fallback={<p className="text-brand-ink-400">Loading…</p>}>
              <Comp />
            </Suspense>
          </section>
        ))}
      </div>
    </SimpleLayout>
  );
}
