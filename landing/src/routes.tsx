/**
 * Landing route table — react-router-dom v6.
 *
 * Pages are lazy-loaded so the initial Home bundle stays small. Routes:
 *   /                      Home (single-page-scroll, 13 sections)
 *   /docs                  Docs index (PR3)
 *   /docs/:slug            One mdx article (PR3)
 *   /changelog             Changelog grouped by month (PR3)
 *   /legal/privacy         Privacy policy (PR3)
 *   /legal/tos             Terms of service (PR3)
 *   *                      404 → redirect to /
 */
import { lazy, Suspense } from 'react';
import { createBrowserRouter, Navigate } from 'react-router-dom';
import App from './App';

const Home      = lazy(() => import('@/pages/Home'));
const DocsIndex = lazy(() => import('@/pages/docs'));
const DocsPage  = lazy(() => import('@/pages/docs/[slug]'));
const Changelog = lazy(() => import('@/pages/Changelog'));
const Privacy   = lazy(() => import('@/pages/legal/Privacy'));
const Terms     = lazy(() => import('@/pages/legal/Terms'));

function PageFallback() {
  return (
    <div className="min-h-screen flex items-center justify-center bg-brand-ink-50">
      <div className="text-brand-ink-400 text-sm tracking-wide animate-pulse-soft">Loading…</div>
    </div>
  );
}

const route = (el: React.ReactNode) => <Suspense fallback={<PageFallback />}>{el}</Suspense>;

export const router = createBrowserRouter([
  {
    element: <App />,
    children: [
      { path: '/',              element: route(<Home />) },
      { path: '/docs',          element: route(<DocsIndex />) },
      { path: '/docs/:slug',    element: route(<DocsPage />) },
      { path: '/changelog',     element: route(<Changelog />) },
      { path: '/legal/privacy', element: route(<Privacy />) },
      { path: '/legal/tos',     element: route(<Terms />) },
      { path: '*',              element: <Navigate to="/" replace /> },
    ],
  },
]);
