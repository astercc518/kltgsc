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
import { useT } from '@/i18n';

/** Render markdown-lite codespans (`code`) into <code> elements.
 *  Keeps i18n strings plain so they round-trip cleanly through DeepL
 *  yet still get the brand monospace + chip treatment on render. */
function renderAnswer(text: string) {
  const parts = text.split(/(`[^`]+`)/g);
  return parts.map((p, i) =>
    p.startsWith('`') && p.endsWith('`')
      ? <code key={i} className="font-mono text-xs bg-brand-ink-800 text-fg-primary px-1.5 py-0.5 rounded">{p.slice(1, -1)}</code>
      : <span key={i}>{p}</span>,
  );
}

export default function FAQ() {
  const [open, setOpen] = useState<number | null>(0);
  const t = useT();
  const faqs = t.faq.items;

  return (
    <section className="bg-surface-1">
      <div className="max-w-container mx-auto px-6 py-24 lg:py-28">
        <Reveal>
          <div className="max-w-3xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 text-eyebrow font-mono text-fg-muted uppercase">
              <span className="h-px w-8 bg-line-strong" />
              {t.faq.eyebrow}
              <span className="h-px w-8 bg-line-strong" />
            </div>
            <h2 className="mt-4 font-display text-display-2 text-fg-primary">
              {t.faq.title}
            </h2>
          </div>
        </Reveal>

        <Reveal delay={120}>
          <div className="mt-12 max-w-3xl mx-auto rounded-2xl border border-line-subtle bg-brand-ink-900 overflow-hidden divide-y divide-line-subtle">
            {faqs.map((item, i) => {
              const isOpen = open === i;
              const Icon = isOpen ? Minus : Plus;
              return (
                <div key={i}>
                  <button
                    type="button"
                    onClick={() => setOpen(isOpen ? null : i)}
                    className="w-full px-5 py-4 lg:px-6 lg:py-5 flex items-start justify-between gap-4 text-left hover:bg-brand-ink-800 transition-colors"
                    aria-expanded={isOpen}
                  >
                    <span className="font-display font-medium text-fg-primary text-base lg:text-lg">
                      {item.q}
                    </span>
                    <Icon className="w-5 h-5 shrink-0 text-fg-muted mt-0.5" />
                  </button>
                  {isOpen && (
                    <div className="px-5 lg:px-6 pb-5 lg:pb-6 text-fg-secondary leading-relaxed text-[0.95rem]">
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
