/**
 * /docs — index page listing the 4 documentation articles.
 *
 * Uses DocsLayout (with no slug, so no item is highlighted in the
 * sidebar) and renders a card grid as the article content.
 */
import { Link } from 'react-router-dom';
import { ArrowUpRight, BookOpen, Boxes, Code2, CircleDollarSign } from 'lucide-react';
import DocsLayout, { DOC_ORDER } from '@/layouts/DocsLayout';

const ICONS = {
  quickstart: BookOpen,
  modules:    Boxes,
  api:        Code2,
  billing:    CircleDollarSign,
} as const;

export default function DocsIndex() {
  return (
    <DocsLayout>
      <h1>Documentation</h1>
      <p>
        Four short articles. Read them in order if you're new — each builds
        on the previous one. Or jump straight to whichever answers your
        current question.
      </p>

      <div className="not-prose grid sm:grid-cols-2 gap-4 mt-8">
        {DOC_ORDER.map((doc) => {
          const Icon = ICONS[doc.slug];
          return (
            <Link
              key={doc.slug}
              to={`/docs/${doc.slug}`}
              className="group block p-5 rounded-2xl border border-brand-ink-200 hover:border-brand-blue-300 hover:shadow-card-hover transition-all bg-white"
            >
              <div className="flex items-start gap-4">
                <div className="shrink-0 w-10 h-10 rounded-xl bg-brand-blue-50 text-brand-blue-600 inline-flex items-center justify-center">
                  <Icon className="w-5 h-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <h3 className="font-display text-lg font-semibold text-brand-ink-900 mb-1 group-hover:text-brand-blue-700 transition-colors flex items-center gap-1.5">
                    {doc.title}
                    <ArrowUpRight className="w-4 h-4 opacity-0 group-hover:opacity-100 transition-opacity" />
                  </h3>
                  <p className="text-sm text-brand-ink-600 leading-relaxed">
                    {doc.description}
                  </p>
                </div>
              </div>
            </Link>
          );
        })}
      </div>

      <hr />

      <h3>Looking for something else?</h3>
      <ul>
        <li><Link to="/changelog">Changelog</Link> — what shipped each month</li>
        <li><a href="https://t.me/tg1ai_sales" target="_blank" rel="noopener">Talk to sales</a> — for everything you can't find here</li>
        <li><a href="https://github.com/astercc518/kltgsc" target="_blank" rel="noopener">GitHub</a> — open an issue</li>
      </ul>
    </DocsLayout>
  );
}
