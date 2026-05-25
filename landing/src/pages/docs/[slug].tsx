/**
 * /docs/:slug — render one mdx article via DocsLayout.
 *
 * mdx modules are lazy-loaded so each article ships its own JS chunk;
 * the 4-doc nav lives in `DocsLayout.DOC_ORDER`. An unknown slug just
 * redirects to /docs (index).
 */
import { lazy, Suspense } from 'react';
import { Navigate, useParams } from 'react-router-dom';
import DocsLayout, { DOC_ORDER, type DocSlug } from '@/layouts/DocsLayout';

const DOCS: Record<DocSlug, ReturnType<typeof lazy>> = {
  quickstart: lazy(() => import('@/content/docs/quickstart.mdx')),
  modules:    lazy(() => import('@/content/docs/modules.mdx')),
  api:        lazy(() => import('@/content/docs/api.mdx')),
  billing:    lazy(() => import('@/content/docs/billing.mdx')),
};

const VALID = new Set<DocSlug>(DOC_ORDER.map((d) => d.slug));
const isValid = (s: string | undefined): s is DocSlug =>
  !!s && VALID.has(s as DocSlug);

export default function DocsPage() {
  const { slug } = useParams<{ slug: string }>();
  if (!isValid(slug)) return <Navigate to="/docs" replace />;

  const Mdx = DOCS[slug];
  return (
    <DocsLayout slug={slug}>
      <Suspense fallback={<p className="text-brand-ink-400">Loading article…</p>}>
        <Mdx />
      </Suspense>
    </DocsLayout>
  );
}
