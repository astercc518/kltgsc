/** Changelog — mdx in PR3. Stub for now. */
import { Link } from 'react-router-dom';
import BrandMark from '@/components/BrandMark';

export default function Changelog() {
  return (
    <div className="min-h-screen bg-brand-ink-50">
      <div className="max-w-container mx-auto px-6 py-24">
        <Link to="/" className="inline-block mb-8"><BrandMark size="sm" /></Link>
        <h1 className="font-display text-display-2 text-brand-ink-900 mb-4">Changelog</h1>
        <p className="text-brand-ink-500">Per-month release notes land in PR3.</p>
      </div>
    </div>
  );
}
