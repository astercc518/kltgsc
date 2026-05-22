/** Docs index — populated in PR3 with mdx articles. */
import { Link } from 'react-router-dom';
import BrandMark from '@/components/BrandMark';

export default function DocsIndex() {
  return (
    <div className="min-h-screen bg-brand-ink-50">
      <div className="max-w-container mx-auto px-6 py-24">
        <Link to="/" className="inline-block mb-8"><BrandMark size="sm" /></Link>
        <h1 className="font-display text-display-2 text-brand-ink-900 mb-4">Docs</h1>
        <p className="text-brand-ink-500">Coming soon — see <a className="text-brand-blue-500 underline" href="https://github.com/astercc518/kltgsc">GitHub</a> for now.</p>
      </div>
    </div>
  );
}
