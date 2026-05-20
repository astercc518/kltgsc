/**
 * KLTGSC — Landing page (multilingual).
 * Languages: en, zh-CN, ja, ko, es. Stored in localStorage, auto-detected from navigator.language.
 */

import React, { useEffect, useRef, useState } from 'react';
import type { LucideIcon } from 'lucide-react';
import {
  Box,
  ArrowRight,
  ArrowUpRight,
  Layers,
  Globe2,
  BrainCircuit,
  UserCheck,
  Filter,
  Activity,
  Search,
  MessageSquare,
  Handshake,
  Check,
  Bitcoin,
  Wallet,
  CreditCard,
  Twitter,
  Github,
  Send,
  Sparkles,
  Menu,
  Languages,
  ChevronDown,
  BarChart3,
  Network,
  Lock,
  FileSearch,
  KeyRound,
} from 'lucide-react';
import { LangProvider, useLang, useT, LANGS, type Lang } from './i18n';

const ICON = { strokeWidth: 1.5 } as const;

const Logo: React.FC<{ className?: string }> = ({ className = '' }) => (
  <a href="#" className={`group inline-flex items-center gap-2 ${className}`}>
    <span className="relative inline-flex h-7 w-7 items-center justify-center rounded-lg border border-white/10 bg-white/[0.03]">
      <Box className="h-4 w-4 text-cyan-300" {...ICON} />
      <span className="absolute inset-0 rounded-lg bg-cyan-400/10 blur-md opacity-0 transition group-hover:opacity-100" />
    </span>
    <span className="text-sm font-semibold tracking-tight">
      <span className="bg-gradient-to-r from-zinc-100 to-zinc-400 bg-clip-text text-transparent">
        KLTGSC
      </span>
    </span>
  </a>
);

const LanguageSwitcher: React.FC = () => {
  const { lang, setLang } = useLang();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const current = LANGS.find((l) => l.code === lang) ?? LANGS[0];

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') setOpen(false);
    };
    document.addEventListener('mousedown', onDown);
    document.addEventListener('keydown', onKey);
    return () => {
      document.removeEventListener('mousedown', onDown);
      document.removeEventListener('keydown', onKey);
    };
  }, [open]);

  return (
    <div ref={ref} className="relative">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="inline-flex items-center gap-1.5 rounded-xl border border-white/10 bg-white/[0.02] px-2.5 py-1.5 text-xs text-zinc-300 transition-all hover:border-white/20 hover:bg-white/[0.04] hover:text-zinc-100"
        aria-haspopup="listbox"
        aria-expanded={open}
      >
        <Languages className="h-3.5 w-3.5" {...ICON} />
        <span className="hidden sm:inline">{current.native}</span>
        <ChevronDown
          className={`h-3 w-3 transition-transform ${open ? 'rotate-180' : ''}`}
          {...ICON}
        />
      </button>

      {open && (
        <div
          role="listbox"
          className="absolute right-0 mt-2 w-44 overflow-hidden rounded-xl border border-white/10 bg-zinc-900/95 p-1 shadow-2xl backdrop-blur-xl"
        >
          {LANGS.map((l) => {
            const active = l.code === lang;
            return (
              <button
                key={l.code}
                role="option"
                aria-selected={active}
                onClick={() => {
                  setLang(l.code as Lang);
                  setOpen(false);
                }}
                className={`flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition-colors ${
                  active
                    ? 'bg-white/[0.06] text-zinc-100'
                    : 'text-zinc-400 hover:bg-white/[0.04] hover:text-zinc-100'
                }`}
              >
                <span>{l.native}</span>
                {active && <Check className="h-3.5 w-3.5 text-cyan-300" strokeWidth={2.5} />}
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
};

const Header: React.FC = () => {
  const t = useT();
  const nav = [
    { label: t.nav.product, href: '#product' },
    { label: t.nav.pricing, href: '#pricing' },
    { label: t.nav.docs, href: '#' },
    { label: t.nav.customers, href: '#' },
    { label: t.nav.changelog, href: '#' },
  ];
  return (
    <header className="fixed inset-x-0 top-0 z-50 border-b border-white/5 bg-zinc-950/60 backdrop-blur-xl">
      <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-6">
        <div className="flex items-center gap-10">
          <Logo />
          <nav className="hidden items-center gap-7 md:flex">
            {nav.map((n) => (
              <a
                key={n.label}
                href={n.href}
                className="text-sm text-zinc-400 transition-colors hover:text-zinc-100"
              >
                {n.label}
              </a>
            ))}
          </nav>
        </div>
        <div className="flex items-center gap-2 sm:gap-3">
          <LanguageSwitcher />
          <a
            href="/login"
            className="hidden text-sm text-zinc-400 transition-colors hover:text-zinc-100 sm:inline"
          >
            {t.cta.signIn}
          </a>
          <a
            href="/login"
            className="group inline-flex items-center gap-1.5 rounded-xl bg-gradient-to-b from-cyan-400 to-cyan-500 px-3.5 py-1.5 text-sm font-medium text-zinc-950 shadow-[0_0_40px_-10px_rgba(56,189,248,0.6)] transition-all hover:from-cyan-300 hover:to-cyan-400 hover:shadow-[0_0_50px_-8px_rgba(56,189,248,0.8)]"
          >
            <span className="hidden sm:inline">{t.cta.launchConsole}</span>
            <span className="sm:hidden">→</span>
            <ArrowRight
              className="hidden h-4 w-4 transition-transform group-hover:translate-x-0.5 sm:inline"
              {...ICON}
            />
          </a>
          <button
            className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 text-zinc-300 md:hidden"
            aria-label="Open menu"
          >
            <Menu className="h-5 w-5" {...ICON} />
          </button>
        </div>
      </div>
    </header>
  );
};

const TerminalMock: React.FC = () => (
  <div className="relative mx-auto mt-16 w-full max-w-5xl">
    <div className="absolute -inset-x-20 -inset-y-10 -z-10 bg-gradient-to-r from-cyan-500/10 via-sky-500/10 to-violet-500/10 blur-3xl" />
    <div className="overflow-hidden rounded-2xl border border-white/10 bg-zinc-900/60 shadow-2xl backdrop-blur-xl">
      <div className="flex items-center gap-2 border-b border-white/5 bg-zinc-900/80 px-4 py-3">
        <span className="h-2.5 w-2.5 rounded-full bg-red-500/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-yellow-500/70" />
        <span className="h-2.5 w-2.5 rounded-full bg-emerald-500/70" />
        <span className="ml-3 font-mono text-xs text-zinc-500">~/kltgsc/console</span>
      </div>
      <pre className="overflow-x-auto px-6 py-6 font-mono text-[13px] leading-relaxed text-zinc-300">
        <code>
          <span className="text-zinc-500">$</span>{' '}
          <span className="text-zinc-100">kltgsc</span> deploy{' '}
          <span className="text-cyan-300">--nodes</span>{' '}
          <span className="text-violet-300">1024</span>{' '}
          <span className="text-cyan-300">--persona</span>{' '}
          <span className="text-emerald-300">"fintech-sales"</span>
          {'\n'}
          <span className="text-emerald-400">✔</span> Provisioning{' '}
          <span className="text-cyan-300">1024</span> sessions across{' '}
          <span className="text-cyan-300">12</span> residential subnets
          {'\n'}
          <span className="text-emerald-400">✔</span> Loaded RAG index:{' '}
          <span className="text-violet-300">industry/fintech-en</span>{' '}
          <span className="text-zinc-500">(4,812 vectors)</span>
          {'\n'}
          <span className="text-emerald-400">✔</span> AI persona engine warm{' '}
          <span className="text-zinc-500">→ 312ms avg p50</span>
          {'\n'}
          <span className="text-cyan-300">→</span> Console live at{' '}
          <span className="text-zinc-100 underline decoration-cyan-400/40 underline-offset-4">
            https://app.kltgsc.com
          </span>
          {'\n'}
        </code>
      </pre>
    </div>
  </div>
);

const Hero: React.FC = () => {
  const t = useT();
  return (
    <section className="relative pt-40 pb-20 md:pt-48 md:pb-28">
      <div className="mx-auto max-w-7xl px-6 text-center">
        <a
          href="#"
          className="inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1 text-xs text-zinc-400 backdrop-blur transition hover:border-white/20 hover:text-zinc-100"
        >
          <Sparkles className="h-3.5 w-3.5 text-cyan-300" {...ICON} />
          {t.hero.badge}
          <ArrowUpRight className="h-3.5 w-3.5" {...ICON} />
        </a>

        <h1 className="mx-auto mt-8 max-w-4xl text-5xl font-medium tracking-tight text-zinc-50 sm:text-6xl md:text-7xl">
          {t.hero.titleA}
          <br className="hidden sm:block" />{' '}
          <span className="bg-gradient-to-r from-cyan-300 via-sky-300 to-violet-400 bg-clip-text text-transparent">
            {t.hero.titleB}
          </span>
        </h1>

        <p className="mx-auto mt-7 max-w-2xl text-base leading-relaxed text-zinc-400 sm:text-lg">
          {t.hero.subtitle}
        </p>

        <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
          <a
            href="/login"
            className="group inline-flex items-center gap-2 rounded-xl bg-gradient-to-b from-cyan-400 to-cyan-500 px-5 py-3 text-sm font-medium text-zinc-950 shadow-[0_0_60px_-10px_rgba(56,189,248,0.7)] transition-all hover:-translate-y-0.5 hover:from-cyan-300 hover:to-cyan-400 hover:shadow-[0_0_80px_-8px_rgba(56,189,248,0.9)]"
          >
            {t.cta.launchConsole}
            <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" {...ICON} />
          </a>
          <a
            href="#"
            className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.02] px-5 py-3 text-sm font-medium text-zinc-200 backdrop-blur transition-all hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/[0.04]"
          >
            {t.cta.viewDocs}
          </a>
        </div>

        <TerminalMock />
      </div>
    </section>
  );
};

const TrustBar: React.FC = () => {
  const t = useT();
  const items = [
    { value: '1,000+', label: t.trust.nodes },
    { value: '10M+', label: t.trust.messages },
    { value: '99.99%', label: t.trust.uptime },
    { value: 'USDT', label: t.trust.crypto },
    { value: 'SOC 2', label: t.trust.compliance },
  ];
  return (
    <section className="relative border-y border-white/5 bg-white/[0.01]">
      <div className="mx-auto max-w-7xl px-6 py-12">
        <div className="grid grid-cols-2 gap-y-8 sm:grid-cols-3 md:grid-cols-5 md:divide-x md:divide-white/5">
          {items.map((it, i) => (
            <div
              key={it.label}
              className={`flex flex-col items-center text-center ${i > 0 ? 'md:pl-4' : ''}`}
            >
              <div className="bg-gradient-to-r from-cyan-300 via-sky-300 to-violet-400 bg-clip-text text-3xl font-medium tracking-tight text-transparent">
                {it.value}
              </div>
              <div className="mt-2 text-[10px] uppercase tracking-[0.18em] text-zinc-500">
                {it.label}
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

const NodeMesh: React.FC = () => (
  <svg
    viewBox="0 0 300 160"
    className="absolute bottom-0 right-0 h-40 w-72 opacity-80"
    fill="none"
  >
    <defs>
      <radialGradient id="dot" cx="50%" cy="50%" r="50%">
        <stop offset="0%" stopColor="#67e8f9" stopOpacity="1" />
        <stop offset="100%" stopColor="#67e8f9" stopOpacity="0" />
      </radialGradient>
      <linearGradient id="line" x1="0" x2="1">
        <stop offset="0%" stopColor="#67e8f9" stopOpacity="0.4" />
        <stop offset="100%" stopColor="#a78bfa" stopOpacity="0.1" />
      </linearGradient>
    </defs>
    <g stroke="url(#line)" strokeWidth="1">
      <line x1="40" y1="40" x2="140" y2="80" />
      <line x1="140" y1="80" x2="240" y2="40" />
      <line x1="140" y1="80" x2="80" y2="130" />
      <line x1="140" y1="80" x2="220" y2="130" />
      <line x1="40" y1="40" x2="80" y2="130" />
      <line x1="240" y1="40" x2="220" y2="130" />
    </g>
    {[
      [40, 40],
      [140, 80],
      [240, 40],
      [80, 130],
      [220, 130],
    ].map(([cx, cy], i) => (
      <g key={i}>
        <circle cx={cx} cy={cy} r="14" fill="url(#dot)" />
        <circle cx={cx} cy={cy} r="3" fill="#67e8f9" />
      </g>
    ))}
  </svg>
);

type BentoCard = {
  icon: LucideIcon;
  title: string;
  body: string;
  span: string;
  extra?: React.ReactNode;
};

const BentoCardEl: React.FC<{ card: BentoCard }> = ({ card }) => {
  const Icon = card.icon;
  return (
    <div
      className={`group relative overflow-hidden rounded-3xl border border-white/10 bg-white/[0.02] p-6 transition-all duration-300 hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/[0.04] md:p-8 ${card.span}`}
    >
      <div className="pointer-events-none absolute -top-24 -right-24 h-64 w-64 rounded-full bg-cyan-500/10 blur-3xl transition-opacity duration-500 group-hover:opacity-80" />
      <div className="pointer-events-none absolute -bottom-24 -left-24 h-56 w-56 rounded-full bg-violet-500/[0.06] blur-3xl" />
      <div className="relative flex items-center gap-2">
        <span className="inline-flex h-9 w-9 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03]">
          <Icon className="h-4 w-4 text-zinc-100" strokeWidth={1.5} />
        </span>
      </div>
      <h3 className="relative mt-5 text-lg font-medium tracking-tight text-zinc-100 md:text-xl">
        {card.title}
      </h3>
      <p className="relative mt-2 max-w-md text-sm leading-relaxed text-zinc-400">
        {card.body}
      </p>
      {card.extra}
    </div>
  );
};

const Bento: React.FC = () => {
  const t = useT();
  const cards: BentoCard[] = [
    {
      icon: Layers,
      title: t.features.cards.tdata[0],
      body: t.features.cards.tdata[1],
      span: 'md:col-span-2 md:row-span-2',
      extra: <NodeMesh />,
    },
    {
      icon: Globe2,
      title: t.features.cards.ip[0],
      body: t.features.cards.ip[1],
      span: 'md:col-span-2',
    },
    {
      icon: BrainCircuit,
      title: t.features.cards.rag[0],
      body: t.features.cards.rag[1],
      span: 'md:col-span-2 md:row-span-2',
    },
    {
      icon: UserCheck,
      title: t.features.cards.takeover[0],
      body: t.features.cards.takeover[1],
      span: 'md:col-span-1',
    },
    {
      icon: Filter,
      title: t.features.cards.funnel[0],
      body: t.features.cards.funnel[1],
      span: 'md:col-span-1',
    },
    {
      icon: Activity,
      title: t.features.cards.monitor[0],
      body: t.features.cards.monitor[1],
      span: 'md:col-span-2',
    },
  ];

  return (
    <section id="product" className="relative py-24 md:py-32">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <div className="text-xs uppercase tracking-[0.22em] text-cyan-300/80">
            {t.features.eyebrow}
          </div>
          <h2 className="mt-3 text-3xl font-medium tracking-tight text-zinc-50 sm:text-4xl md:text-5xl">
            {t.features.title}
          </h2>
          <p className="mt-5 text-base leading-relaxed text-zinc-400 sm:text-lg">
            {t.features.subtitle}
          </p>
        </div>

        <div className="mt-14 grid grid-cols-1 gap-4 md:grid-cols-4 md:auto-rows-[12rem]">
          {cards.map((c) => (
            <BentoCardEl key={c.title} card={c} />
          ))}
        </div>
      </div>
    </section>
  );
};

const PipelineNode: React.FC<{
  icon: LucideIcon;
  step: string;
  title: string;
  body: string;
}> = ({ icon: Icon, step, title, body }) => (
  <div className="relative flex flex-1 flex-col items-center text-center">
    <div className="relative">
      <div className="absolute -inset-3 rounded-full bg-cyan-500/20 blur-xl" />
      <div className="relative inline-flex h-16 w-16 items-center justify-center rounded-full border border-white/10 bg-zinc-900/80 backdrop-blur">
        <Icon className="h-6 w-6 text-cyan-300" strokeWidth={1.5} />
      </div>
    </div>
    <div className="mt-5 text-[10px] uppercase tracking-[0.22em] text-zinc-500">{step}</div>
    <h3 className="mt-2 text-lg font-medium tracking-tight text-zinc-100">{title}</h3>
    <p className="mt-2 max-w-xs text-sm leading-relaxed text-zinc-400">{body}</p>
  </div>
);

const Pipeline: React.FC = () => {
  const t = useT();
  const icons: LucideIcon[] = [Search, MessageSquare, Handshake];
  return (
    <section className="relative py-24 md:py-32">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <div className="text-xs uppercase tracking-[0.22em] text-cyan-300/80">
            {t.workflow.eyebrow}
          </div>
          <h2 className="mt-3 text-3xl font-medium tracking-tight text-zinc-50 sm:text-4xl md:text-5xl">
            {t.workflow.titleA}
            <br className="hidden sm:block" />
            <span className="bg-gradient-to-r from-cyan-300 via-sky-300 to-violet-400 bg-clip-text text-transparent">
              {' '}
              {t.workflow.titleB}
            </span>
          </h2>
        </div>

        <div className="relative mt-16">
          <div
            aria-hidden
            className="absolute left-[16%] right-[16%] top-8 hidden h-px bg-gradient-to-r from-white/0 via-white/20 to-white/0 md:block"
          />
          <div className="relative flex flex-col items-stretch justify-between gap-12 md:flex-row md:gap-6">
            {t.workflow.steps.map((s, i) => (
              <PipelineNode
                key={s.label}
                icon={icons[i]}
                step={s.label}
                title={s.title}
                body={s.body}
              />
            ))}
          </div>
        </div>
      </div>
    </section>
  );
};

type Plan = {
  name: string;
  price: string;
  blurb: string;
  features: string[];
  cta: string;
  highlight?: boolean;
};

const PricingCard: React.FC<{ plan: Plan; mostPopular: string }> = ({ plan, mostPopular }) => (
  <div
    className={`relative flex flex-col rounded-3xl border p-8 transition-all duration-300 hover:-translate-y-0.5 ${
      plan.highlight
        ? 'border-cyan-400/30 bg-gradient-to-b from-cyan-500/[0.06] to-transparent'
        : 'border-white/10 bg-white/[0.02] hover:border-white/20 hover:bg-white/[0.04]'
    }`}
  >
    {plan.highlight && (
      <>
        <div className="pointer-events-none absolute -top-px left-12 right-12 h-px bg-gradient-to-r from-cyan-400/0 via-cyan-300 to-cyan-400/0" />
        <span className="absolute -top-3 left-1/2 -translate-x-1/2 whitespace-nowrap rounded-full border border-cyan-400/30 bg-zinc-950 px-3 py-1 text-[10px] uppercase tracking-[0.18em] text-cyan-300">
          {mostPopular}
        </span>
      </>
    )}
    <div className="text-sm font-medium tracking-tight text-zinc-100">{plan.name}</div>
    <div className="mt-4 flex items-baseline gap-1">
      <span className="text-5xl font-medium tracking-tight text-zinc-50">{plan.price}</span>
      <span className="text-sm text-zinc-500">/mo</span>
    </div>
    <p className="mt-3 text-sm leading-relaxed text-zinc-400">{plan.blurb}</p>

    <ul className="mt-8 space-y-3">
      {plan.features.map((f) => (
        <li key={f} className="flex items-start gap-2.5 text-sm text-zinc-300">
          <span className="mt-0.5 inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border border-cyan-400/30 bg-cyan-500/10">
            <Check className="h-2.5 w-2.5 text-cyan-300" strokeWidth={2.5} />
          </span>
          {f}
        </li>
      ))}
    </ul>

    <a
      href="#"
      className={`mt-10 inline-flex items-center justify-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all ${
        plan.highlight
          ? 'bg-gradient-to-b from-cyan-400 to-cyan-500 text-zinc-950 shadow-[0_0_60px_-12px_rgba(56,189,248,0.7)] hover:from-cyan-300 hover:to-cyan-400'
          : 'border border-white/10 bg-white/[0.02] text-zinc-100 hover:border-white/20 hover:bg-white/[0.06]'
      }`}
    >
      {plan.cta}
      <ArrowRight className="h-4 w-4" strokeWidth={1.5} />
    </a>
  </div>
);

const Pricing: React.FC = () => {
  const t = useT();
  const meta = [
    { name: 'Starter', price: '$199' },
    { name: 'Growth', price: '$299', highlight: true },
    { name: 'Scale', price: '$599' },
  ];
  const plans: Plan[] = meta.map((m, i) => ({
    name: m.name,
    price: m.price,
    highlight: m.highlight,
    blurb: t.pricing.plans[i].blurb,
    features: t.pricing.plans[i].features,
    cta: t.pricing.plans[i].cta,
  }));

  return (
    <section id="pricing" className="relative py-24 md:py-32">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <div className="text-xs uppercase tracking-[0.22em] text-cyan-300/80">
            {t.pricing.eyebrow}
          </div>
          <h2 className="mt-3 text-3xl font-medium tracking-tight text-zinc-50 sm:text-4xl md:text-5xl">
            {t.pricing.title}
          </h2>
          <p className="mt-5 text-base leading-relaxed text-zinc-400 sm:text-lg">
            {t.pricing.subtitle}
          </p>
        </div>

        <div className="mt-14 grid grid-cols-1 gap-5 md:grid-cols-3">
          {plans.map((p) => (
            <PricingCard key={p.name} plan={p} mostPopular={t.cta.mostPopular} />
          ))}
        </div>

        <div className="mt-12 flex flex-wrap items-center justify-center gap-x-6 gap-y-3 text-xs text-zinc-500">
          <span className="inline-flex items-center gap-1.5">
            <Bitcoin className="h-3.5 w-3.5 text-zinc-400" strokeWidth={1.5} />
            {t.pricing.badges.crypto}
          </span>
          <span className="text-zinc-700">·</span>
          <span className="inline-flex items-center gap-1.5">
            <Wallet className="h-3.5 w-3.5 text-zinc-400" strokeWidth={1.5} />
            {t.pricing.badges.wallet}
          </span>
          <span className="text-zinc-700">·</span>
          <span className="inline-flex items-center gap-1.5">
            <CreditCard className="h-3.5 w-3.5 text-zinc-400" strokeWidth={1.5} />
            {t.pricing.badges.card}
          </span>
        </div>
      </div>
    </section>
  );
};

const useCaseIcons: LucideIcon[] = [Bitcoin, BarChart3, Network];

const UseCases: React.FC = () => {
  const t = useT();
  return (
    <section className="relative py-24 md:py-28">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <div className="text-xs uppercase tracking-[0.22em] text-cyan-300/80">
            {t.useCases.eyebrow}
          </div>
          <h2 className="mt-3 text-3xl font-medium tracking-tight text-zinc-50 sm:text-4xl md:text-5xl">
            {t.useCases.title}
          </h2>
        </div>
        <div className="mt-14 grid grid-cols-1 gap-5 md:grid-cols-3">
          {t.useCases.cards.map((c, i) => {
            const Icon = useCaseIcons[i];
            return (
              <div
                key={c.title}
                className="group relative overflow-hidden rounded-3xl border border-white/10 bg-white/[0.02] p-8 transition-all duration-300 hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/[0.04]"
              >
                <div className="pointer-events-none absolute -top-24 -right-24 h-56 w-56 rounded-full bg-cyan-500/10 blur-3xl opacity-60 transition-opacity group-hover:opacity-100" />
                <span className="relative inline-flex h-10 w-10 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03]">
                  <Icon className="h-5 w-5 text-cyan-300" strokeWidth={1.5} />
                </span>
                <h3 className="relative mt-6 text-lg font-medium tracking-tight text-zinc-100">
                  {c.title}
                </h3>
                <p className="relative mt-3 text-sm leading-relaxed text-zinc-400">{c.body}</p>
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

const Integrations: React.FC = () => {
  const t = useT();
  return (
    <section className="relative py-24 md:py-28">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <div className="text-xs uppercase tracking-[0.22em] text-cyan-300/80">
            {t.integrations.eyebrow}
          </div>
          <h2 className="mt-3 text-3xl font-medium tracking-tight text-zinc-50 sm:text-4xl md:text-5xl">
            {t.integrations.title}
          </h2>
          <p className="mt-5 text-base leading-relaxed text-zinc-400 sm:text-lg">
            {t.integrations.subtitle}
          </p>
        </div>
        <div className="mt-14 grid grid-cols-2 gap-3 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-6">
          {t.integrations.items.map((it) => (
            <div
              key={it}
              className="group relative flex items-center justify-center gap-2 rounded-2xl border border-white/10 bg-white/[0.02] px-3 py-4 text-sm text-zinc-300 transition-all hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/[0.04]"
            >
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-cyan-400/70 transition-colors group-hover:bg-cyan-300" />
              {it}
            </div>
          ))}
        </div>
      </div>
    </section>
  );
};

const securityIcons: LucideIcon[] = [Lock, FileSearch, KeyRound, Wallet];

const Security: React.FC = () => {
  const t = useT();
  return (
    <section className="relative py-24 md:py-28">
      <div className="mx-auto max-w-7xl px-6">
        <div className="mx-auto max-w-3xl text-center">
          <div className="text-xs uppercase tracking-[0.22em] text-cyan-300/80">
            {t.security.eyebrow}
          </div>
          <h2 className="mt-3 text-3xl font-medium tracking-tight text-zinc-50 sm:text-4xl md:text-5xl">
            {t.security.title}
          </h2>
          <p className="mt-5 text-base leading-relaxed text-zinc-400 sm:text-lg">
            {t.security.subtitle}
          </p>
        </div>
        <div className="mt-14 grid grid-cols-1 gap-4 md:grid-cols-2">
          {t.security.items.map((s, i) => {
            const Icon = securityIcons[i];
            return (
              <div
                key={s.title}
                className="group relative overflow-hidden rounded-3xl border border-white/10 bg-white/[0.02] p-7 transition-all duration-300 hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/[0.04]"
              >
                <div className="pointer-events-none absolute -top-20 -right-20 h-48 w-48 rounded-full bg-cyan-500/[0.07] blur-3xl" />
                <div className="relative flex items-start gap-4">
                  <span className="inline-flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-xl border border-white/10 bg-white/[0.03]">
                    <Icon className="h-5 w-5 text-cyan-300" strokeWidth={1.5} />
                  </span>
                  <div>
                    <h3 className="text-lg font-medium tracking-tight text-zinc-100">{s.title}</h3>
                    <p className="mt-2 text-sm leading-relaxed text-zinc-400">{s.body}</p>
                  </div>
                </div>
              </div>
            );
          })}
        </div>
        <div className="mt-10 text-center text-[11px] uppercase tracking-[0.18em] text-zinc-500">
          {t.security.badges}
        </div>
      </div>
    </section>
  );
};

const FAQ: React.FC = () => {
  const t = useT();
  const [open, setOpen] = useState<number | null>(0);
  return (
    <section className="relative py-24 md:py-28">
      <div className="mx-auto max-w-3xl px-6">
        <div className="text-center">
          <div className="text-xs uppercase tracking-[0.22em] text-cyan-300/80">
            {t.faq.eyebrow}
          </div>
          <h2 className="mt-3 text-3xl font-medium tracking-tight text-zinc-50 sm:text-4xl md:text-5xl">
            {t.faq.title}
          </h2>
        </div>
        <div className="mt-12 divide-y divide-white/5 rounded-3xl border border-white/10 bg-white/[0.02]">
          {t.faq.items.map((item, i) => {
            const isOpen = open === i;
            return (
              <div key={item.q}>
                <button
                  type="button"
                  onClick={() => setOpen(isOpen ? null : i)}
                  className="flex w-full items-center justify-between gap-4 px-6 py-5 text-left transition-colors hover:bg-white/[0.02]"
                  aria-expanded={isOpen}
                >
                  <span className="text-sm font-medium text-zinc-100 sm:text-base">{item.q}</span>
                  <ChevronDown
                    className={`h-4 w-4 flex-shrink-0 text-zinc-400 transition-all ${
                      isOpen ? 'rotate-180 text-cyan-300' : ''
                    }`}
                    strokeWidth={1.5}
                  />
                </button>
                {isOpen && (
                  <div className="px-6 pb-6 text-sm leading-relaxed text-zinc-400">{item.a}</div>
                )}
              </div>
            );
          })}
        </div>
      </div>
    </section>
  );
};

const FinalCTA: React.FC = () => {
  const t = useT();
  return (
    <section className="relative py-24 md:py-32">
      <div className="mx-auto max-w-7xl px-6">
        <div className="relative overflow-hidden rounded-3xl border border-white/10 bg-gradient-to-b from-cyan-500/[0.08] via-zinc-950 to-zinc-950 px-8 py-16 text-center md:px-16 md:py-24">
          <div className="pointer-events-none absolute -top-40 left-1/2 h-[400px] w-[700px] -translate-x-1/2 rounded-full bg-cyan-500/15 blur-[100px]" />
          <div className="pointer-events-none absolute -bottom-40 right-1/4 h-[300px] w-[300px] rounded-full bg-violet-500/10 blur-[100px]" />
          <h2 className="relative text-3xl font-medium tracking-tight text-zinc-50 sm:text-4xl md:text-5xl">
            {t.finalCta.title}
            <br />
            <span className="bg-gradient-to-r from-cyan-300 via-sky-300 to-violet-400 bg-clip-text text-transparent">
              {t.finalCta.titleAccent}
            </span>
          </h2>
          <p className="relative mx-auto mt-6 max-w-xl text-base leading-relaxed text-zinc-400 sm:text-lg">
            {t.finalCta.body}
          </p>
          <div className="relative mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <a
              href="/login"
              className="group inline-flex items-center gap-2 rounded-xl bg-gradient-to-b from-cyan-400 to-cyan-500 px-5 py-3 text-sm font-medium text-zinc-950 shadow-[0_0_60px_-10px_rgba(56,189,248,0.7)] transition-all hover:-translate-y-0.5 hover:from-cyan-300 hover:to-cyan-400 hover:shadow-[0_0_80px_-8px_rgba(56,189,248,0.9)]"
            >
              {t.finalCta.primary}
              <ArrowRight className="h-4 w-4 transition-transform group-hover:translate-x-0.5" strokeWidth={1.5} />
            </a>
            <a
              href="#"
              className="inline-flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.02] px-5 py-3 text-sm font-medium text-zinc-200 backdrop-blur transition-all hover:-translate-y-0.5 hover:border-white/20 hover:bg-white/[0.04]"
            >
              {t.finalCta.secondary}
            </a>
          </div>
        </div>
      </div>
    </section>
  );
};

const Footer: React.FC = () => {
  const t = useT();
  return (
    <footer className="relative border-t border-white/5 bg-zinc-950">
      <div className="mx-auto max-w-7xl px-6 py-16">
        <div className="grid grid-cols-2 gap-10 md:grid-cols-4">
          <div className="col-span-2 md:col-span-1">
            <Logo />
            <p className="mt-4 max-w-xs text-sm leading-relaxed text-zinc-500">
              {t.footer.tagline}
            </p>
            <div className="mt-6 flex items-center gap-3">
              {[Twitter, Github, Send].map((I, idx) => (
                <a
                  key={idx}
                  href="#"
                  className="inline-flex h-9 w-9 items-center justify-center rounded-lg border border-white/10 bg-white/[0.02] text-zinc-400 transition-colors hover:border-white/20 hover:text-zinc-100"
                >
                  <I className="h-4 w-4" strokeWidth={1.5} />
                </a>
              ))}
            </div>
          </div>
          {t.footer.sections.map((c) => (
            <div key={c.title}>
              <div className="text-xs font-medium uppercase tracking-[0.18em] text-zinc-400">
                {c.title}
              </div>
              <ul className="mt-4 space-y-3">
                {c.items.map((i) => (
                  <li key={i}>
                    <a
                      href="#"
                      className="text-sm text-zinc-500 transition-colors hover:text-zinc-100"
                    >
                      {i}
                    </a>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-14 flex flex-col items-start justify-between gap-4 border-t border-white/5 pt-8 text-xs text-zinc-500 md:flex-row md:items-center">
          <div>{t.footer.copyright}</div>
          <div className="text-zinc-600">{t.footer.builtFor}</div>
        </div>
      </div>
    </footer>
  );
};

const Shell: React.FC = () => (
  <div className="min-h-screen bg-zinc-950 font-sans text-zinc-100 antialiased selection:bg-cyan-500/30 selection:text-white">
    <div aria-hidden className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
      <div className="absolute -top-40 left-1/2 h-[600px] w-[1000px] -translate-x-1/2 rounded-full bg-cyan-500/[0.08] blur-[120px]" />
      <div className="absolute top-[35%] -left-40 h-[400px] w-[400px] rounded-full bg-violet-500/[0.08] blur-[120px]" />
      <div className="absolute bottom-[10%] -right-40 h-[400px] w-[400px] rounded-full bg-sky-500/[0.06] blur-[120px]" />
      <div
        className="absolute inset-0 opacity-[0.025]"
        style={{
          backgroundImage:
            'radial-gradient(circle at 1px 1px, white 1px, transparent 0)',
          backgroundSize: '32px 32px',
        }}
      />
    </div>

    <Header />
    <main>
      <Hero />
      <TrustBar />
      <UseCases />
      <Bento />
      <Integrations />
      <Pipeline />
      <Security />
      <Pricing />
      <FAQ />
      <FinalCTA />
    </main>
    <Footer />
  </div>
);

export default function App() {
  return (
    <LangProvider>
      <Shell />
    </LangProvider>
  );
}
