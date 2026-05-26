/**
 * FAQ — 8 questions updated to match the actual product.
 *
 * Accordion (one open at a time). Questions chosen to defuse the most
 * common pre-sale objections; answers cite the actual product behavior
 * (wallet auto-pause, AI DM boundary, tenant isolation, etc).
 */
import { useState } from 'react';
import { Plus, Minus } from 'lucide-react';
import Reveal from '@/components/Reveal';
import SectionLabel from '@/components/SectionLabel';
import { useT } from '@/i18n';

/** Render markdown-lite codespans (`code`) into <code> elements.
 *  Keeps i18n strings plain so they round-trip cleanly through DeepL
 *  yet still get the brand monospace + chip treatment on render. */
function renderAnswer(text: string) {
  const parts = text.split(/(`[^`]+`)/g);
  return parts.map((p, i) =>
    p.startsWith('`') && p.endsWith('`')
      ? <code key={i} className="font-mono text-xs bg-brand-ink-100 px-1.5 py-0.5 rounded">{p.slice(1, -1)}</code>
      : <span key={i}>{p}</span>,
  );
}

export default function FAQ() {
  const [open, setOpen] = useState<number | null>(0);
  const t = useT();
  const faqs = t.faq.items;

  return (
    <section className="bg-brand-ink-50">
      <div className="max-w-container mx-auto px-6 py-24 lg:py-28">
        <Reveal>
          <div className="max-w-3xl mx-auto text-center">
            <div className="flex justify-center">
              <SectionLabel number="08" tone="light">{t.faq.eyebrow}</SectionLabel>
            </div>
            <h2 className="mt-5 font-display text-display-2 text-brand-ink-900 tracking-tight text-balance">
              {t.faq.title}
            </h2>
          </div>
        </Reveal>

        <Reveal delay={120}>
          <div className="mt-12 max-w-3xl mx-auto rounded-2xl border border-brand-ink-200 bg-white overflow-hidden divide-y divide-brand-ink-100">
            {faqs.map((item, i) => {
              const isOpen = open === i;
              const Icon = isOpen ? Minus : Plus;
              return (
                <div key={i}>
                  <button
                    type="button"
                    onClick={() => setOpen(isOpen ? null : i)}
                    className="w-full px-5 py-4 lg:px-6 lg:py-5 flex items-start justify-between gap-4 text-left hover:bg-brand-ink-50/50 transition-colors"
                    aria-expanded={isOpen}
                  >
                    <span className="font-display font-medium text-brand-ink-900 text-base lg:text-lg">
                      {item.q}
                    </span>
                    <Icon className="w-5 h-5 shrink-0 text-brand-ink-400 mt-0.5" />
                  </button>
                  {isOpen && (
                    <div className="px-5 lg:px-6 pb-5 lg:pb-6 text-brand-ink-600 leading-relaxed text-[0.95rem]">
                      {renderAnswer(item.a)}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        </Reveal>
      </div>
    </section>
  );
}
