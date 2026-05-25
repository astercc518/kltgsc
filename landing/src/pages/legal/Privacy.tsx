/**
 * /legal/privacy — long-form privacy policy.
 *
 * Renders the mdx article inside SimpleLayout. .prose-tg1 inherits
 * brand typography; max-w-3xl keeps line length comfortable.
 */
import { lazy, Suspense } from 'react';
import { SimpleLayout } from '@/layouts/SubpageChrome';

const PrivacyMdx = lazy(() => import('@/content/legal/privacy.mdx'));

export default function Privacy() {
  return (
    <SimpleLayout>
      <article className="prose-tg1 mx-auto">
        <Suspense fallback={<p className="text-brand-ink-400">Loading…</p>}>
          <PrivacyMdx />
        </Suspense>
      </article>
    </SimpleLayout>
  );
}
