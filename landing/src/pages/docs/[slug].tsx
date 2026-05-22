/** Single docs article — mdx in PR3. Stub for now. */
import { Link, useParams } from 'react-router-dom';
import BrandMark from '@/components/BrandMark';

export default function DocsPage() {
  const { slug } = useParams<{ slug: string }>();
  return (
    <div className="min-h-screen bg-brand-ink-50">
      <div className="max-w-container mx-auto px-6 py-24">
        <Link to="/docs" className="inline-block mb-8"><BrandMark size="sm" /></Link>
        <p className="text-brand-ink-500 mb-2 font-mono text-xs uppercase tracking-wider">/ docs / {slug}</p>
        <h1 className="font-display text-display-2 text-brand-ink-900">Article placeholder</h1>
        <p className="text-brand-ink-500 mt-4">Content lands in PR3 (mdx integration).</p>
      </div>
    </div>
  );
}
