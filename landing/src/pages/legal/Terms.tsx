/** Terms — populated in PR3. */
import { Link } from 'react-router-dom';
import BrandMark from '@/components/BrandMark';

export default function Terms() {
  return (
    <div className="min-h-screen bg-brand-ink-50">
      <div className="max-w-3xl mx-auto px-6 py-24">
        <Link to="/" className="inline-block mb-8"><BrandMark size="sm" /></Link>
        <h1 className="font-display text-display-2 text-brand-ink-900 mb-4">Terms of Service</h1>
        <p className="text-brand-ink-500">Full text lands in PR3. Contact legal@tg1.ai for current terms.</p>
      </div>
    </div>
  );
}
