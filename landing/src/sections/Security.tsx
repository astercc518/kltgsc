/**
 * Security — 4 enterprise concerns + the AI boundary promise.
 *
 * The "AI never DMs" wall is repeated here on purpose — it's the
 * single most-asked-about safety contract, and it deserves to be in
 * the security section, not just buried in the AI Assistant card.
 */
import { Lock, FileSearch, KeyRound, Wallet, Shield } from 'lucide-react';
import Reveal from '@/components/Reveal';

const pillars = [
  {
    icon: Lock,
    title: 'AES-256 at rest',
    desc: 'Session strings + tdata blobs encrypted with a per-instance KEK before they hit disk. Even with DB access, sessions are useless without the key.',
  },
  {
    icon: FileSearch,
    title: 'Operation audit log',
    desc: 'Every admin action — invoice activation, role change, feature override — written to operation_log with actor + before/after diff. Exportable CSV.',
  },
  {
    icon: KeyRound,
    title: 'SSO + SAML (Pro)',
    desc: 'Bring your IdP. OAuth-style flow against the customer JWT. Per-seat audit trail.',
  },
  {
    icon: Wallet,
    title: 'Self-custody wallet',
    desc: 'USDT goes directly to the customer\'s tenant address. We never custodian funds — refunds, top-ups, and freezes are on-chain only.',
  },
];

export default function Security() {
  return (
    <section className="bg-white">
      <div className="max-w-container mx-auto px-6 py-24 lg:py-28">
        <Reveal>
          <div className="max-w-3xl">
            <div className="inline-flex items-center gap-2 text-eyebrow font-mono text-brand-ink-500 uppercase">
              <span className="h-px w-8 bg-brand-ink-300" />
              Security & compliance
            </div>
            <h2 className="mt-4 font-display text-display-2 text-brand-ink-900">
              Enterprise-grade, from day one.
            </h2>
          </div>
        </Reveal>

        <div className="mt-12 grid md:grid-cols-2 lg:grid-cols-4 gap-5">
          {pillars.map((p, i) => (
            <Reveal key={p.title} delay={i * 80}>
              <div className="h-full p-6 rounded-2xl bg-brand-ink-50 border border-brand-ink-100">
                <p.icon className="w-6 h-6 text-brand-ink-700 mb-4" />
                <h3 className="font-display font-semibold text-brand-ink-900 mb-2">{p.title}</h3>
                <p className="text-sm text-brand-ink-600 leading-relaxed">{p.desc}</p>
              </div>
            </Reveal>
          ))}
        </div>

        {/* The AI boundary wall — repeated promise */}
        <Reveal delay={250}>
          <div className="mt-12 rounded-3xl bg-brand-ink-950 text-white p-8 lg:p-10 flex flex-col lg:flex-row items-start gap-6">
            <div className="shrink-0 w-12 h-12 rounded-xl bg-brand-purple-500/20 inline-flex items-center justify-center">
              <Shield className="w-6 h-6 text-brand-purple-300" />
            </div>
            <div className="flex-1">
              <h3 className="font-display text-2xl font-semibold mb-2">
                Two safety contracts the platform enforces for you.
              </h3>
              <ul className="space-y-3 text-white/70 leading-relaxed">
                <li className="flex gap-3">
                  <span className="font-mono text-brand-purple-300 shrink-0">1.</span>
                  <span>
                    <strong className="text-white">AI replies only in-group, never in DM.</strong>{' '}
                    The reply_mode <code className="font-mono text-xs bg-white/10 px-1.5 py-0.5 rounded">private_dm</code> is hard-rejected at the API layer for customer-owned monitors. Private outreach stays a human decision.
                  </span>
                </li>
                <li className="flex gap-3">
                  <span className="font-mono text-brand-purple-300 shrink-0">2.</span>
                  <span>
                    <strong className="text-white">Tenant isolation at the listener.</strong>{' '}
                    Your monitor rules only fire on TG accounts whose <code className="font-mono text-xs bg-white/10 px-1.5 py-0.5 rounded">customer_id</code> matches yours. Cross-tenant leakage is structurally impossible.
                  </span>
                </li>
              </ul>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
