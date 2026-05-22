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
import { LINKS } from '@/lib/links';

const faqs = [
  {
    q: 'How do I claim the $20 free trial?',
    a: (
      <>Register at <a className="text-brand-blue-500 underline" href={LINKS.signUp}>/portal/register</a> with a working email — your wallet is credited $20 USDT-equivalent immediately. No card, no chain transfer. Enough to run ~2,000 scrape rows, 200 bulk sends, or 40 AI auto-leads.</>
    ),
  },
  {
    q: 'Will my accounts get banned?',
    a: (
      <>Risk is concentrated in unsolicited DMs. That's why customer-owned monitors can only reply <em>in-group</em>, never auto-DM. Combined with persona warming, daily caps, randomized delays, and FloodWait-aware retries, real-world ban rate on Growth tier is &lt;1%/month — and replacement SLA covers anything beyond.</>
    ),
  },
  {
    q: 'Can I use this from mainland China?',
    a: (
      <>Yes. We give every paid customer access to the per-region proxy pool (residential exits, country-pinned, sticky per-account). Pro tier includes 2 dedicated proxy slots. The console + portal are reachable through the same proxies.</>
    ),
  },
  {
    q: 'How does sales takeover actually work?',
    a: (
      <>Lead enters your sales inbox pre-assigned to whoever owns that TG account. One click marks it claimed (atomic — no double-handoff), AI switches to "draft mode" (suggestions only, no auto-send), and your sales sends the DM manually. Every interaction logged to CRM.</>
    ),
  },
  {
    q: 'What happens if my wallet runs out mid-task?',
    a: (
      <>Tasks transition to <code className="font-mono text-xs bg-brand-ink-100 px-1.5 py-0.5 rounded">paused_no_funds</code>. They don't fail, they don't replay duplicate ops on resume (idempotency keys), and your sales seats still see in-flight leads — they just stop generating new ones until you top up.</>
    ),
  },
  {
    q: 'How is tenant isolation enforced?',
    a: (
      <>Every business table carries a <code className="font-mono text-xs bg-brand-ink-100 px-1.5 py-0.5 rounded">customer_id</code> column with row-level filters at the listener + API + KB retrieval layer. Your monitor rules cannot fire on someone else's accounts; your sales cannot view someone else's leads. Structural, not policy.</>
    ),
  },
  {
    q: 'Do you support card / bank wire payments?',
    a: (
      <>No. We're USDT-only on TRC20 / ERC20 / BEP20. Settlement is on-chain; refunds and credit are transparent. The internal sales playbook explains the regulatory rationale — fewer middlemen, cleaner books for crypto-native customers.</>
    ),
  },
  {
    q: 'Can I self-host or get the source?',
    a: (
      <>Pro tier customers get a read-only repo view + the ability to run the backend in their own VPC (no source license, ops-grade access). Source licensing is available on request for $50k+/yr commitments.</>
    ),
  },
];

export default function FAQ() {
  const [open, setOpen] = useState<number | null>(0);

  return (
    <section className="bg-brand-ink-50">
      <div className="max-w-container mx-auto px-6 py-24 lg:py-28">
        <Reveal>
          <div className="max-w-3xl mx-auto text-center">
            <div className="inline-flex items-center gap-2 text-eyebrow font-mono text-brand-ink-500 uppercase">
              <span className="h-px w-8 bg-brand-ink-300" />
              FAQ
              <span className="h-px w-8 bg-brand-ink-300" />
            </div>
            <h2 className="mt-4 font-display text-display-2 text-brand-ink-900">
              The questions we get most.
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
                      {item.a}
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
