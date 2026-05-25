/**
 * /legal/tos — long-form terms of service.
 */
import { lazy, Suspense } from 'react';
import { SimpleLayout } from '@/layouts/SubpageChrome';

const TermsMdx = lazy(() => import('@/content/legal/tos.mdx'));

export default function Terms() {
  return (
    <SimpleLayout>
      <article className="prose-tg1 mx-auto">
        <Suspense fallback={<p className="text-brand-ink-400">Loading…</p>}>
          <TermsMdx />
        </Suspense>
      </article>
    </SimpleLayout>
  );
}
