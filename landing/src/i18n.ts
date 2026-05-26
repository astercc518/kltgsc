/**
 * TG1.AI landing i18n.
 *
 * 5 languages. en + zh-CN are hand-written; ja / ko / es are
 * machine-translated and marked at the top of each dict so future
 * human reviewers know what's locked in.
 *
 * PR4 covers the 5 highest-impact sections (Header / HeroDual /
 * Pricing / FinalCTA / Footer). Other 8 sections still hard-code
 * English in their .tsx file — see plan §PR5 for the rest.
 *
 * Adding a key:
 *   1. add to the Dict type below
 *   2. add the en string
 *   3. add the zh-CN string
 *   4. add ja/ko/es (machine OK)
 *   5. consume via useT().section.field in your component
 *
 * Storage key changed from `kltgsc.lang` → `tg1.lang`. Old visitors
 * lose their language preference exactly once (acceptable churn).
 */
import React, {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from 'react';

export type Lang = 'en' | 'zh-CN' | 'ja' | 'ko' | 'es';

export const LANGS: { code: Lang; native: string; english: string }[] = [
  { code: 'en',    native: 'English',   english: 'English' },
  { code: 'zh-CN', native: '简体中文',   english: 'Chinese (Simplified)' },
  { code: 'ja',    native: '日本語',     english: 'Japanese' },
  { code: 'ko',    native: '한국어',     english: 'Korean' },
  { code: 'es',    native: 'Español',   english: 'Spanish' },
];

// ── Dict shape ───────────────────────────────────────────────────────────

export type Dict = {
  meta: {
    titleSuffix: string;       // " — Telegram Growth, On Autopilot"
    description: string;       // SEO meta description
  };
  nav: {
    selfServe: string;
    aiAssistant: string;
    pricing: string;
    docs: string;
    signIn: string;
    freeTrial: string;
  };
  hero: {
    titlePart1: string;        // "Two ways to grow"
    titlePart2: string;        // "on Telegram"
    subtitle: string;
    subtitleQuiet: string;     // "One platform, one account pool, one wallet."
    ctaPrimary: string;        // "Free $20 Trial"
    ctaSecondary: string;      // "Watch 90s Demo"
    ctaTertiary: string;       // "Talk on Telegram"
    selfServe: {
      tag: string;             // "Self-Serve"
      title: string;           // "Pay-as-you-go bulk ops"
      blurb: string;
      bullets: { label: string; price: string }[];
      fit: string;             // "Best for: in-house SDR tooling"
      see: string;             // "See details"
    };
    aiAssistant: {
      tag: string;
      title: string;
      blurb: string;
      bullets: { label: string; price: string }[];
      fit: string;
      safetyNote: string;      // "AI never auto-DMs users — that decision stays with your sales"
      see: string;
    };
  };
  pricing: {
    eyebrow: string;
    titlePart1: string;        // "Subscription unlocks the platform."
    titlePart2: string;        // "Wallet meters the ops."
    subtitle: string;
    plans: {
      starter:  { ctaLabel: string; features: string[]; quotaLines: string[] };
      growth:   { ctaLabel: string; features: string[]; quotaLines: string[] };
      pro:      { ctaLabel: string; features: string[]; quotaLines: string[] };
    };
    mostPopular: string;
    perMonthUsdt: string;       // "/ month · USDT"
    tableTitle: string;         // "Full unit price table"
    tableSubtitle: string;
    tableHeaders: {
      product: string;
      action:  string;
      unit:    string;
      price:   string;
    };
    tableAdminNote: {
      before: string;            // "Admin can override any line per-customer for volume deals. See "
      linkLabel: string;         // "billing docs"
      after: string;             // "."
    };
  };
  finalCta: {
    titlePart1: string;        // "Stop firefighting bans."
    titlePart2: string;        // "Start shipping revenue."
    subtitle: string;
  };
  footer: {
    tagline: string;            // "Telegram growth, on autopilot. Built for operators who scale."
    statusLabel: string;        // "Status"
    statusValue: string;        // "All systems normal"
    columns: {
      product:  string;
      company:  string;
    };
    links: {
      selfServe:   string;
      aiAssistant: string;
      pricing:     string;
      docs:        string;
      changelog:   string;
      talkToSales: string;
      privacy:     string;
      terms:       string;
    };
    copyright:        string;   // "© {year} TG1.AI — All rights reserved."
    notAffiliated:    string;   // "Built for the Telegram economy. Not affiliated with Telegram FZ-LLC."
  };
  trustBar: {
    accounts: string;        // "accounts per tenant"
    shards:   string;        // "listener shards (prod)"
    rag:      string;        // "Vertex Gemini RAG"
    uptime:   string;        // "session uptime"
    networks: string;        // "TRC20 · ERC20 · BEP20"
  };
  selfServe: {
    eyebrow: string;         // "Self-Serve — Pay as you go"
    titleA: string;          // "Three Telegram ops, three flat per-unit prices."
    titleB: string;          // "No subscription needed."
    subtitle: string;
    triplet: Array<{ badge: string; title: string; description: string }>;
    flowTitle: string;
    flowSteps: Array<{ title: string; desc: string }>;
    stripQuestion: string;
    stripQuiet: string;
    stripCta: string;
  };
  aiAssistant: {
    eyebrow: string;
    titleA: string;
    titleB: string;
    subtitle: string;
    steps: Array<{ title: string; desc: string }>;
    safetyTitle: string;
    safetyDesc: string;
    safetyWhy: string;
    safetyLink: string;
    stripText: string;
    stripQuiet: string;
    stripSeePlans: string;
    stripAskSales: string;
  };
  howItWorks: {
    eyebrowPrefix: string;   // "How it works ·" — number rendered separately
    titleA: string;          // "From cold lead to closed deal,"
    titleB: string;          // "one autonomous loop."
    steps: Array<{ title: string; blurb: string }>;
  };
  pricingCalc: {
    eyebrow: string;
    title: string;
    subtitle: string;
    leadsLabel: string;
    sendsLabel: string;
    leadsSuffix: string;     // " leads"
    sendsSuffix: string;     // " msgs"
    walletCostHeader: string;
    aiRepliesLine: string;
    aiLeadsLine: string;
    bulkSendLine: string;
    totalLabel: string;
    bestBadge: string;
    subPlanLabel: string;    // "sub" word
    walletPlanLabel: string; // "wallet" word
    perMo: string;           // "/mo"
  };
  useCases: {
    eyebrow: string;
    title: string;
    cards: Array<{ title: string; blurb: string; metric: string; sub: string }>;
  };
  security: {
    eyebrow: string;
    title: string;
    pillars: Array<{ title: string; desc: string }>;
    contractTitle: string;
    contract1: string;
    contract2: string;
  };
  faq: {
    eyebrow: string;
    title: string;
    items: Array<{ q: string; a: string }>;
  };
  demo: {
    title: string;
    badge: string;
    consoleLabel: string;
    inbox: { label: string; empty: string };
    acts: { listening: string; incoming: string; scoring: string; handover: string };
    kpi: { rate: string; rateUnit: string; captured: string };
    console: { line1: string; line2: string; line3: string; line4: string };
    score: {
      label: string;
      keywords: string;
      keywordsValue: string;
      persona: string;
      personaValue: string;
      suggestion: string;
      suggestionValue: string;
    };
    handover: {
      salesName: string;
      salesReply: string;
      typing: string;
    };
    controls: { pause: string; resume: string; restart: string; close: string };
    reduced: { intro: string };
    messages: {
      m0: string; m1: string; m2: string; m3: string;
      m4: string; m5: string; m6: string; m7: string;
    };
    senders: {
      s0: string; s1: string; s2: string; s3: string;
      s4: string; s5: string; s6: string; s7: string;
    };
    groups: {
      g0: string; g1: string; g2: string;
    };
  };
};

// ── en ───────────────────────────────────────────────────────────────────

const en: Dict = {
  meta: {
    titleSuffix: 'TG1.AI — Telegram Growth, On Autopilot',
    description:
      'Telegram marketing automation: pay-as-you-go scrape / bulk send / invite + AI marketing assistant that listens to your target groups and pushes leads to sales. USDT billing. 1000+ accounts per tenant.',
  },
  nav: {
    selfServe: 'Self-Serve',
    aiAssistant: 'AI Assistant',
    pricing: 'Pricing',
    docs: 'Docs',
    signIn: 'Sign In',
    freeTrial: 'Free $20 Trial',
  },
  hero: {
    titlePart1: 'Two ways to grow',
    titlePart2: 'on Telegram',
    subtitle:
      'Pay-as-you-go scraping & bulk send + an AI marketing assistant that listens to your target groups and pushes high-intent leads to your inbox.',
    subtitleQuiet: 'One platform, one account pool, one wallet.',
    ctaPrimary:   'Free $20 Trial',
    ctaSecondary: 'Watch 90s Demo',
    ctaTertiary:  'Talk on Telegram',
    selfServe: {
      tag:   'Self-Serve',
      title: 'Pay-as-you-go bulk ops',
      blurb: 'Scrape, send, invite — three core actions, billed per unit, prepaid with USDT.',
      bullets: [
        { label: 'Group scrape', price: '$0.01 / member' },
        { label: 'Bulk send',    price: '$0.10 / message' },
        { label: 'Bulk invite',  price: '$0.05 / invite' },
      ],
      fit: 'Best for: in-house SDR tooling',
      see: 'See details',
    },
    aiAssistant: {
      tag:   'AI Marketing Assistant',
      title: 'Subscription that hires itself',
      blurb: 'Your TG accounts listen 24/7. AI replies in group on intent hits, pushes leads to your sales inbox.',
      bullets: [
        { label: 'Listens to', price: 'your target groups' },
        { label: 'Replies in', price: 'group (not DM)' },
        { label: 'Hands off',  price: 'to your humans' },
      ],
      fit: 'Best for: replacing an SDR / BDR team',
      safetyNote: 'AI never auto-DMs users — that decision stays with your sales',
      see: 'See details',
    },
  },
  demo: {
    title: 'TG1 AI Assistant · Live Demo',
    badge: 'Listening to 3 groups',
    consoleLabel: 'ai-console',
    inbox: { label: 'inbox', empty: 'inbox · empty' },
    acts: {
      listening: '1/4 · Listening',
      incoming: '2/4 · Incoming',
      scoring: '3/4 · AI Scoring',
      handover: '4/4 · Handover',
    },
    kpi: {
      rate: 'Msg rate',
      rateUnit: '/min',
      captured: 'Captured today',
    },
    console: {
      line1: '[00:01] connecting to 3 target groups...',
      line2: '[00:03] all listeners online',
      line3: '[00:21] intent classifier loaded (zh+en)',
      line4: '[00:42] high-intent match → score 92, pushing to inbox',
    },
    score: {
      label: 'Intent score',
      keywords: 'Keywords',
      keywordsValue: 'USDT · cross-border',
      persona: 'Persona',
      personaValue: 'SMB merchant',
      suggestion: 'Suggested opener',
      suggestionValue: 'Hi — saw your question about USDT receiving. We help merchants accept stablecoin without local-bank friction. Want a 2-min walkthrough?',
    },
    handover: {
      salesName: 'Sales · Alex',
      salesReply: 'Hi — saw your question in the group about USDT receiving…',
      typing: 'typing…',
    },
    controls: {
      pause: 'Pause',
      resume: 'Resume',
      restart: 'Replay',
      close: 'Close demo',
    },
    reduced: {
      intro: 'Animation disabled per your motion preference. Browse the 4 acts:',
    },
    messages: {
      m0: 'morning everyone, anyone here run a TG channel for crypto?',
      m1: 'lol that airdrop was a scam, lost 50 usdt',
      m2: 'mods can we get the pinned message updated?',
      m3: 'anyone using USDT to receive payments from overseas clients? bank is killing me',
      m4: 'gm',
      m5: 'check out my channel: @somespammer',
      m6: 'need a Telegram group blasting tool, paid is fine — any recommendations?',
      m7: 'thx for the alpha yesterday',
    },
    senders: {
      s0: 'jake_w', s1: 'crypto_sam', s2: 'mira', s3: 'marco_smb',
      s4: 'dexter', s5: 'spam_bot', s6: 'lei_growth', s7: 'anon',
    },
    groups: {
      g0: 'Cross-border Payments',
      g1: 'TG Growth Operators',
      g2: 'SMB Founders',
    },
  },
  pricing: {
    eyebrow: 'Pricing',
    titlePart1: 'Subscription unlocks the platform.',
    titlePart2: 'Wallet meters the ops.',
    subtitle:
      'Both products billed in USDT. Subscription is the recurring infrastructure cost (accounts, groups, tokens, seats). Bulk ops + AI replies are pay-as-you-go on top.',
    plans: {
      starter: {
        ctaLabel: 'Start with Starter',
        features: [
          'AI marketing assistant included',
          'Customer KB upload + RAG',
          'Wallet pay-as-you-go ops',
          'USDT-only billing',
          'Email support, 24h SLA',
        ],
        quotaLines: ['3 TG accounts', '500 target groups', '2M LLM tokens / mo', '1 sales seat'],
      },
      growth: {
        ctaLabel: 'Pick Growth',
        features: [
          'Everything in Starter',
          'Priority listener shard',
          'Lead pre-assign + claim race-safe',
          'Auto-pause + low-balance Slack alerts',
          'Email + Telegram support, 12h SLA',
        ],
        quotaLines: ['5 TG accounts', '1,000 target groups', '5M LLM tokens / mo', '3 sales seats'],
      },
      pro: {
        ctaLabel: 'Go Pro',
        features: [
          'Everything in Growth',
          'Dedicated success engineer',
          'SSO + audit log export',
          'Custom feature pricing',
          '99.9% SLA, 4h response',
        ],
        quotaLines: ['10 TG accounts', '3,000 target groups', '15M LLM tokens / mo', '10 sales seats'],
      },
    },
    mostPopular:   'Most Popular',
    perMonthUsdt:  '/ month · USDT',
    tableTitle:    'Full unit price table',
    tableSubtitle: 'Every wallet-charged action, single source of truth.',
    tableHeaders: {
      product: 'Product',
      action:  'Action',
      unit:    'Billed as',
      price:   'Default',
    },
    tableAdminNote: {
      before: 'Admin can override any line per-customer for volume deals. See ',
      linkLabel: 'billing docs',
      after: '.',
    },
  },
  finalCta: {
    titlePart1: 'Stop firefighting bans.',
    titlePart2: 'Start shipping revenue.',
    subtitle:
      '$20 free credit, 24 hours to first leads. Onboard in your own time, talk to a human only when you want to.',
  },
  footer: {
    tagline: 'Telegram growth, on autopilot. Built for operators who scale.',
    statusLabel: 'Status',
    statusValue: 'All systems normal',
    columns: {
      product: 'Product',
      company: 'Company',
    },
    links: {
      selfServe:   'Self-Serve',
      aiAssistant: 'AI Assistant',
      pricing:     'Pricing',
      docs:        'Docs',
      changelog:   'Changelog',
      talkToSales: 'Talk to sales',
      privacy:     'Privacy',
      terms:       'Terms',
    },
    copyright:     '© {year} TG1.AI — All rights reserved.',
    notAffiliated: 'Built for the Telegram economy. Not affiliated with Telegram FZ-LLC.',
  },
  trustBar: {
    accounts: 'accounts per tenant',
    shards:   'listener shards (prod)',
    rag:      'Vertex Gemini RAG',
    uptime:   'session uptime',
    networks: 'TRC20 · ERC20 · BEP20',
  },
  selfServe: {
    eyebrow: 'Self-Serve — Pay as you go',
    titleA: 'Three Telegram ops, three flat per-unit prices.',
    titleB: 'No subscription needed.',
    subtitle:
      "Top up your USDT wallet, run scrape / send / invite. Any leftover credit rolls forward, and the platform auto-pauses tasks when your balance dips below the operation cost — you can't accidentally over-spend.",
    triplet: [
      {
        badge: '$0.01 / member',
        title: 'Group scrape',
        description:
          'Pull member lists from any group your account can see. Filter by activity, language, or join-date before exporting. Each scraped member deducts $0.01 — failed rows are not charged.',
      },
      {
        badge: '$0.10 / message',
        title: 'Bulk send',
        description:
          'Schedule a campaign across hundreds of accounts. Template variants prevent flag detection; the dispatcher respects per-account daily limits. You pay only for deliveries that get a 200 OK.',
      },
      {
        badge: '$0.05 / invite',
        title: 'Bulk invite',
        description:
          'Pull users into your community group from a scraped list. Auto-pauses if Telegram throttles your accounts; resumes when the cooldown clears. Each invite attempt — success or fail — is metered.',
      },
    ],
    flowTitle: 'How the wallet works',
    flowSteps: [
      { title: 'Top up',     desc: 'Transfer USDT to your tenant address. Auto-credited on chain confirmation.' },
      { title: 'Run task',   desc: 'Each action deducts at the published per-unit price. Receipts in wallet history.' },
      { title: 'Auto-pause', desc: 'If balance < next-op cost, task pauses with `paused_no_funds` — no surprise overage.' },
      { title: 'Resume',     desc: 'Top up again. Tasks pick up where they left off — no replay risk via idempotency keys.' },
    ],
    stripQuestion: 'Want to see the full unit price table?',
    stripQuiet:    'Includes scrape / send / invite tiering above 50k volume.',
    stripCta:      'See pricing',
  },
  aiAssistant: {
    eyebrow:  'AI Marketing Assistant — Subscription',
    titleA:   'An SDR / BDR team that ships in 24 hours.',
    titleB:   'Half-automatic by design.',
    subtitle:
      'Configure a monitor rule once. AI handles first-touch in the group — friendly, on-brand, contextual — and routes high-intent leads to a human inbox. You decide who gets the DM.',
    steps: [
      { title: 'Listen',     desc: 'Your TG accounts sit in your target groups 24/7. The listener fans out across 5 prod shards, ~200 accounts each.' },
      { title: 'Recognize',  desc: 'Two-stage match: keyword pre-filter (fast) → Vertex Gemini semantic judge (precise). Cosine-rerank via BGE cross-encoder for the win.' },
      { title: 'Engage',     desc: 'On intent hit, AI posts a contextual reply IN the source group. Personas come from your KB, with sales-line stripping so it never looks like a billboard.' },
      { title: 'Push',       desc: 'A Lead row materialises — pre-assigned to the salesperson who owns that TG account, source-group attribution intact.' },
      { title: 'Takeover',   desc: 'Sales clicks once: AI drops to "draft mode" (suggestions only), conversation is theirs. Atomic claim, no double-handoff.' },
      { title: 'CRM sink',   desc: 'Unconverted leads land in CRM with industry tag + interaction history — your sales team has tomorrow\'s call list before they wake up.' },
    ],
    safetyTitle: 'AI never auto-DMs your prospects.',
    safetyDesc:
      'The reply layer is half-automatic on purpose. AI posts in the source group where everyone can see — that\'s social proof. Private outreach stays a human decision; your sales clicks "claim", AI switches to draft suggestions, the DM is yours to send.',
    safetyWhy:
      'Why? Ban risk is concentrated in unsolicited DMs, not in-group replies. We keep your accounts alive by design.',
    safetyLink:  'Read the safety doc →',
    stripText:   'Activate the assistant on any paid plan.',
    stripQuiet:  'Sub gates access; wallet meters each AI reply ($0.05) + lead ($0.50).',
    stripSeePlans: 'See plans',
    stripAskSales: 'Ask sales',
  },
  howItWorks: {
    eyebrowPrefix: 'How it works ·',
    titleA: 'From cold lead to closed deal,',
    titleB: 'one autonomous loop.',
    steps: [
      { title: 'Activate a plan',     blurb: 'USDT → Subscription active → 3/5/10 accounts auto-assigned + AI marketing feature unlocked.' },
      { title: 'Upload your KB',      blurb: 'PDF / markdown / chat history → Gemini embedding → pgvector index. Cited automatically in replies.' },
      { title: 'Configure a monitor', blurb: 'Pick keywords + target groups + persona. Active mode = AI replies in group; private DM is locked off.' },
      { title: 'AI engages in group', blurb: 'Listener fires → semantic judge confirms → AI posts a contextual reply with KB-cited details.' },
      { title: 'Lead lands in inbox', blurb: 'Captured user → pre-assigned to your sales seat → atomic claim, no double-handoff.' },
      { title: 'Sales closes',        blurb: 'One-click takeover. AI switches to draft mode, sales takes the DM, conversation logged to CRM.' },
    ],
  },
  pricingCalc: {
    eyebrow:  'Calculator',
    title:    'Estimate your monthly bill',
    subtitle:
      "Drag the sliders to your expected volume. We'll show you the cheapest plan + what your wallet will spend on top.",
    leadsLabel: 'AI auto-leads per month',
    sendsLabel: 'Bulk-send messages per month',
    leadsSuffix: ' leads',
    sendsSuffix: ' msgs',
    walletCostHeader: 'Variable wallet cost · estimate',
    aiRepliesLine: 'AI replies (~3 per lead)',
    aiLeadsLine:   'AI auto-leads',
    bulkSendLine:  'Bulk send',
    totalLabel:    'Total wallet spend / mo',
    bestBadge:     'Best',
    subPlanLabel:  'sub',
    walletPlanLabel: 'wallet',
    perMo:         '/mo',
  },
  useCases: {
    eyebrow: 'Use cases',
    title:   'Built for the teams that ship at Telegram scale.',
    cards: [
      {
        title:  'Crypto & Web3 GTM',
        blurb:
          'IDO launches, airdrop campaigns, exchange referrals. AI listens across 30+ trader chats, posts contextual replies on "looking for X exchange" type intent, hands off conversion talk to your sales seat.',
        metric: '~$0.50 per qualified lead',
        sub:    'vs. $40 ICP CPL on paid social',
      },
      {
        title:  'Fintech & forex outbound',
        blurb:
          'Compliance-friendly first-touch: AI replies in-group with publicly visible language, never DMs first. Your licensed sales rep does the regulated conversation manually.',
        metric: '50× cheaper than offshore SDRs',
        sub:    'with a paper trail per interaction',
      },
      {
        title:  'Cross-border e-com & MCN',
        blurb:
          'Scrape competitor community members (per-MB billing). Run bulk send campaigns to high-overlap segments. AI assistant catches replies and triages to your team.',
        metric: '3 ops, one wallet',
        sub:    'scrape · send · invite — all USDT-metered',
      },
    ],
  },
  security: {
    eyebrow: 'Security & compliance',
    title:   'Enterprise-grade, from day one.',
    pillars: [
      { title: 'AES-256 at rest',      desc: 'Session strings + tdata blobs encrypted with a per-instance KEK before they hit disk. Even with DB access, sessions are useless without the key.' },
      { title: 'Operation audit log',  desc: 'Every admin action — invoice activation, role change, feature override — written to operation_log with actor + before/after diff. Exportable CSV.' },
      { title: 'SSO + SAML (Pro)',     desc: 'Bring your IdP. OAuth-style flow against the customer JWT. Per-seat audit trail.' },
      { title: 'Self-custody wallet',  desc: 'USDT goes directly to the customer\'s tenant address. We never custodian funds — refunds, top-ups, and freezes are on-chain only.' },
    ],
    contractTitle: 'Two safety contracts the platform enforces for you.',
    contract1:
      'AI replies only in-group, never in DM. The reply_mode `private_dm` is hard-rejected at the API layer for customer-owned monitors. Private outreach stays a human decision.',
    contract2:
      'Tenant isolation at the listener. Your monitor rules only fire on TG accounts whose `customer_id` matches yours. Cross-tenant leakage is structurally impossible.',
  },
  faq: {
    eyebrow: 'FAQ',
    title:   'The questions we get most.',
    items: [
      {
        q: 'How do I claim the $20 free trial?',
        a: 'Register at /portal/register with a working email — your wallet is credited $20 USDT-equivalent immediately. No card, no chain transfer. Enough to run ~2,000 scrape rows, 200 bulk sends, or 40 AI auto-leads.',
      },
      {
        q: 'Will my accounts get banned?',
        a: 'Risk is concentrated in unsolicited DMs. That\'s why customer-owned monitors can only reply in-group, never auto-DM. Combined with persona warming, daily caps, randomized delays, and FloodWait-aware retries, real-world ban rate on Growth tier is under 1%/month — and replacement SLA covers anything beyond.',
      },
      {
        q: 'Can I use this from mainland China?',
        a: 'Yes. We give every paid customer access to the per-region proxy pool (residential exits, country-pinned, sticky per-account). Pro tier includes 2 dedicated proxy slots. The console + portal are reachable through the same proxies.',
      },
      {
        q: 'How does sales takeover actually work?',
        a: 'Lead enters your sales inbox pre-assigned to whoever owns that TG account. One click marks it claimed (atomic — no double-handoff), AI switches to "draft mode" (suggestions only, no auto-send), and your sales sends the DM manually. Every interaction logged to CRM.',
      },
      {
        q: 'What happens if my wallet runs out mid-task?',
        a: 'Tasks transition to `paused_no_funds`. They don\'t fail, they don\'t replay duplicate ops on resume (idempotency keys), and your sales seats still see in-flight leads — they just stop generating new ones until you top up.',
      },
      {
        q: 'How is tenant isolation enforced?',
        a: 'Every business table carries a `customer_id` column with row-level filters at the listener + API + KB retrieval layer. Your monitor rules cannot fire on someone else\'s accounts; your sales cannot view someone else\'s leads. Structural, not policy.',
      },
      {
        q: 'Do you support card / bank wire payments?',
        a: "No. We're USDT-only on TRC20 / ERC20 / BEP20. Settlement is on-chain; refunds and credit are transparent. Fewer middlemen, cleaner books for crypto-native customers.",
      },
      {
        q: 'Can I self-host or get the source?',
        a: 'Pro tier customers get a read-only repo view + the ability to run the backend in their own VPC (no source license, ops-grade access). Source licensing is available on request for $50k+/yr commitments.',
      },
    ],
  },
};

// ── zh-CN (hand-written) ─────────────────────────────────────────────────

const zhCN: Dict = {
  meta: {
    titleSuffix: 'TG1.AI — Telegram 营销自动化平台',
    description:
      '双轨产品：按量计费的群采集/群发/拉群 + 7×24 AI 营销助手监听你的目标群并将高意向线索推送给你的销售。USDT 计价，单租户支持 1000+ 账号。',
  },
  nav: {
    selfServe: '按量自助',
    aiAssistant: 'AI 助手',
    pricing: '定价',
    docs: '文档',
    signIn: '登录',
    freeTrial: '免费试用 $20',
  },
  hero: {
    titlePart1: 'Telegram 营销的两种',
    titlePart2: '打开方式',
    subtitle:
      '按量自助的群采集与群发 + AI 营销助手 7×24 监听目标群，把高意向线索直接推到你的销售 inbox。',
    subtitleQuiet: '一个平台，一套账号池，一份钱包。',
    ctaPrimary:   '免费试用 $20',
    ctaSecondary: '看 90 秒 Demo',
    ctaTertiary:  'Telegram 联系销售',
    selfServe: {
      tag:   '按量自助',
      title: '按量计费三件套',
      blurb: '群采集、群发、拉群 —— 三个核心动作，按条计费，USDT 预充值。',
      bullets: [
        { label: '群采集', price: '$0.01 / 人' },
        { label: '群发',   price: '$0.10 / 条' },
        { label: '群拉',   price: '$0.05 / 次' },
      ],
      fit: '适合：自建 SDR 工具链',
      see: '查看详情',
    },
    aiAssistant: {
      tag:   'AI 营销助手',
      title: '订阅会员，AI 替你打头阵',
      blurb: '你的 TG 号 7×24 监听目标群。AI 命中关键词后在群内回话，并把高意向用户线索推送到销售 inbox。',
      bullets: [
        { label: '监听', price: '你指定的目标群' },
        { label: '回复', price: '仅群内，不私聊' },
        { label: '交接', price: '由你的销售人工接管' },
      ],
      fit: '适合：替代 SDR / BDR 团队',
      safetyNote: 'AI 永远不会自动私聊用户 —— 是否 DM 由你的销售人工决定',
      see: '查看详情',
    },
  },
  demo: {
    title: 'TG1 AI 助手 · 实时演示',
    badge: '正在监听 3 个群',
    consoleLabel: 'AI 控制台',
    inbox: { label: '收件箱', empty: '收件箱 · 空' },
    acts: {
      listening: '1/4 · 监听就绪',
      incoming: '2/4 · 消息流入',
      scoring: '3/4 · AI 评分',
      handover: '4/4 · 销售接管',
    },
    kpi: {
      rate: '消息流速',
      rateUnit: ' 条/分',
      captured: '今日捕获',
    },
    console: {
      line1: '[00:01] 连接 3 个目标群...',
      line2: '[00:03] 监听器全部在线',
      line3: '[00:21] 意向分类器已加载（中/英）',
      line4: '[00:42] 命中高意向 → 评分 92，推送到 inbox',
    },
    score: {
      label: '意向分',
      keywords: '关键词',
      keywordsValue: 'USDT · 跨境支付',
      persona: '用户画像',
      personaValue: '中小商户',
      suggestion: '推荐话术',
      suggestionValue: '您好，看到您在问 USDT 收款。我们帮商户用稳定币收单，不走本地银行。要不要看 2 分钟演示？',
    },
    handover: {
      salesName: '销售 · Alex',
      salesReply: '您好，看到您在群里问 USDT 收款……',
      typing: '输入中…',
    },
    controls: {
      pause: '暂停',
      resume: '继续',
      restart: '重播',
      close: '关闭演示',
    },
    reduced: {
      intro: '已按您的动效偏好关闭动画。逐幕浏览：',
    },
    messages: {
      m0: '早上好各位，有人这边做加密相关的 TG 频道吗',
      m1: '昨天那个空投就是骗局，亏了 50u',
      m2: '管理员能更新一下置顶信息吗',
      m3: '有人在用 USDT 收海外客户款吗？银行卡得我太难受了',
      m4: 'gm',
      m5: '看看我的频道：@somespammer',
      m6: '想找个 TG 群发工具，付费也行——有推荐吗',
      m7: '感谢昨天的 alpha',
    },
    senders: {
      s0: '杰克', s1: 'crypto_sam', s2: 'mira', s3: '马可',
      s4: 'dexter', s5: 'spam_bot', s6: '雷增长', s7: 'anon',
    },
    groups: {
      g0: '跨境支付交流',
      g1: 'TG 增长运营',
      g2: '中小商户',
    },
  },
  pricing: {
    eyebrow: '定价',
    titlePart1: '订阅决定能力上限。',
    titlePart2: '钱包按操作计量。',
    subtitle:
      '两个产品都以 USDT 计价。订阅是固定的基础设施成本（账号 / 群组 / Token / 坐席），群发与 AI 回话按量从钱包扣。',
    plans: {
      starter: {
        ctaLabel: '选择 Starter',
        features: [
          '含 AI 营销助手',
          '客户 KB 上传 + RAG 检索',
          '钱包按量操作',
          '仅支持 USDT 计价',
          '邮件支持，24 小时响应',
        ],
        quotaLines: ['3 个 TG 账号', '500 个目标群', '每月 2M LLM Token', '1 个销售坐席'],
      },
      growth: {
        ctaLabel: '推荐 Growth',
        features: [
          '包含 Starter 全部功能',
          '优先 listener 分片',
          '线索预分配 + 原子认领',
          '余额不足自动暂停 + Slack 报警',
          '邮件 + Telegram 支持，12 小时响应',
        ],
        quotaLines: ['5 个 TG 账号', '1,000 个目标群', '每月 5M LLM Token', '3 个销售坐席'],
      },
      pro: {
        ctaLabel: '升级 Pro',
        features: [
          '包含 Growth 全部功能',
          '专属客户成功工程师',
          'SSO + 审计日志导出',
          '可定制单价',
          '99.9% SLA，4 小时响应',
        ],
        quotaLines: ['10 个 TG 账号', '3,000 个目标群', '每月 15M LLM Token', '10 个销售坐席'],
      },
    },
    mostPopular:   '最受欢迎',
    perMonthUsdt:  ' / 月 · USDT',
    tableTitle:    '完整单价表',
    tableSubtitle: '所有钱包扣费动作的唯一真相来源。',
    tableHeaders: {
      product: '产品',
      action:  '动作',
      unit:    '计费方式',
      price:   '默认单价',
    },
    tableAdminNote: {
      before: '大客户可向 admin 申请单价覆盖，详见 ',
      linkLabel: 'billing 文档',
      after: '。',
    },
  },
  finalCta: {
    titlePart1: '停止跟封号救火。',
    titlePart2: '开始稳定出营收。',
    subtitle:
      '$20 免费额度，24 小时内拉出第一批线索。按自己节奏 onboard，需要时再找人。',
  },
  footer: {
    tagline: 'Telegram 营销自动化平台。为规模化运营者打造。',
    statusLabel: '系统状态',
    statusValue: '一切正常',
    columns: {
      product: '产品',
      company: '公司',
    },
    links: {
      selfServe:   '按量自助',
      aiAssistant: 'AI 助手',
      pricing:     '定价',
      docs:        '文档',
      changelog:   '更新日志',
      talkToSales: '联系销售',
      privacy:     '隐私政策',
      terms:       '服务条款',
    },
    copyright:     '© {year} TG1.AI — 保留所有权利。',
    notAffiliated: '为 Telegram 经济而建。与 Telegram FZ-LLC 无关联。',
  },
  trustBar: {
    accounts: '每租户账号上限',
    shards:   '生产环境 listener 分片',
    rag:      'Vertex Gemini RAG',
    uptime:   '会话可用率',
    networks: 'TRC20 · ERC20 · BEP20',
  },
  selfServe: {
    eyebrow: '按量自助 — Pay as you go',
    titleA: '三个 Telegram 动作，三个固定单价。',
    titleB: '无需订阅。',
    subtitle:
      'USDT 钱包充值后跑采集 / 群发 / 拉群。余额自动累积，余额不足时任务自动暂停 —— 永远不会意外超支。',
    triplet: [
      {
        badge: '$0.01 / 人',
        title: '群采集',
        description:
          '从你的账号能看到的任意群导出成员名单。可按活跃度、语言、加入时间过滤。每条入库扣 $0.01，失败行不扣费。',
      },
      {
        badge: '$0.10 / 条',
        title: '群发',
        description:
          '跨数百账号编排批次。模板变体规避风控；调度器尊重每账号日上限。仅成功送达计费。',
      },
      {
        badge: '$0.05 / 次',
        title: '群拉',
        description:
          '从采集名单拉人进你的社区群。账号触发 Telegram 限流时自动暂停，冷却结束自动恢复。每次邀请——成功或失败——都计量。',
      },
    ],
    flowTitle: '钱包工作流',
    flowSteps: [
      { title: '充值',     desc: 'USDT 转入你的租户地址。链上确认后自动入账。' },
      { title: '执行',     desc: '每个动作按公开单价扣费。完整流水在钱包历史中。' },
      { title: '自动暂停', desc: '余额不足下一动作所需时，任务状态切到 `paused_no_funds` —— 无意外超支。' },
      { title: '恢复',     desc: '再次充值。任务从中断点继续 —— 幂等键防止重放重复扣费。' },
    ],
    stripQuestion: '想看完整单价表？',
    stripQuiet:    '包含 5 万量级以上采集 / 群发 / 拉群的阶梯单价。',
    stripCta:      '查看定价',
  },
  aiAssistant: {
    eyebrow:  'AI 营销助手 — 订阅',
    titleA:   '24 小时上线的 SDR / BDR 团队。',
    titleB:   '设计上就是半自动的。',
    subtitle:
      '配置一次 monitor 规则。AI 在群里完成首次接触 —— 友好、品牌一致、契合上下文 —— 并把高意向线索送入人工 inbox。是否 DM 由你的销售决定。',
    steps: [
      { title: '监听', desc: '你的 TG 号 7×24 蹲在目标群里。listener 跨 5 个生产分片扇出，每片 ~200 个账号。' },
      { title: '识别', desc: '两阶段匹配：关键词预过滤（快） → Vertex Gemini 语义判定（准）。BGE cross-encoder 重排提升 Top-K 命中率。' },
      { title: '回话', desc: '命中后 AI 在源群内主动回话。人设来自你的 KB，自动剥离销售话术 —— 看起来不像广告牌。' },
      { title: '推送', desc: '系统落 Lead 行 —— 预分配给拥有该 TG 账号的销售，群源属性完整保留。' },
      { title: '接管', desc: '销售一键认领：AI 切换到"草稿模式"（仅建议、不发送），会话归销售。原子认领，无双重接管。' },
      { title: 'CRM', desc: '未转化线索落 CRM，含行业标签 + 完整交互历史 —— 明天的销售跟进名单提前就绪。' },
    ],
    safetyTitle: 'AI 永远不会自动私聊你的潜客。',
    safetyDesc:
      '回话层故意做成半自动。AI 在源群里发言，所有人都能看见 —— 这就是社交证明。私下接触保持人工决策；销售点击"认领"后 AI 转草稿建议，DM 由你来发。',
    safetyWhy:
      '为什么？封号风险集中在未经请求的 DM，不在群内回复。我们用设计让你的账号活下来。',
    safetyLink:  '阅读安全文档 →',
    stripText:   '任何付费档位均含 AI 助手。',
    stripQuiet:  '订阅控制能否开通；钱包按 AI 回话（$0.05）+ 线索（$0.50）逐条扣费。',
    stripSeePlans: '查看档位',
    stripAskSales: '咨询销售',
  },
  howItWorks: {
    eyebrowPrefix: '工作流程 ·',
    titleA: '从冷线索到成交，',
    titleB: '一个自闭环。',
    steps: [
      { title: '激活套餐',   blurb: 'USDT 付款 → 订阅生效 → 自动分配 3 / 5 / 10 个账号 + 开通 AI 营销助手。' },
      { title: '上传 KB',    blurb: 'PDF / Markdown / 聊天历史 → Gemini embedding → pgvector 索引。AI 回复自动引用。' },
      { title: '配置监听',   blurb: '关键词 + 目标群 + 人设。主动模式 = AI 群内回话；私聊模式被硬锁。' },
      { title: 'AI 群内回话', blurb: 'listener 触发 → 语义判定通过 → AI 发出含 KB 细节的上下文回复。' },
      { title: '线索入 inbox', blurb: '命中用户 → 预分配给销售坐席 → 原子认领，无重复处理。' },
      { title: '销售成交',   blurb: '一键接管。AI 切草稿模式，销售人工发 DM，会话自动归档到 CRM。' },
    ],
  },
  pricingCalc: {
    eyebrow:  '价格计算器',
    title:    '估算你的月度账单',
    subtitle:
      '拖动滑块到你预期的量，即可看到最便宜的套餐 + 钱包额外开销。',
    leadsLabel: '每月 AI 自动线索数',
    sendsLabel: '每月群发条数',
    leadsSuffix: ' 条线索',
    sendsSuffix: ' 条消息',
    walletCostHeader: '可变钱包开销 · 估算',
    aiRepliesLine: 'AI 回话（每条 lead 约 3 次）',
    aiLeadsLine:   'AI 自动线索',
    bulkSendLine:  '群发',
    totalLabel:    '每月钱包总开销',
    bestBadge:     '最优',
    subPlanLabel:  '订阅',
    walletPlanLabel: '钱包',
    perMo:         '/月',
  },
  useCases: {
    eyebrow: '使用场景',
    title:   '为 Telegram 规模化运营的团队打造。',
    cards: [
      {
        title:  'Crypto / Web3 GTM',
        blurb:
          'IDO 发行、空投活动、交易所推广。AI 监听 30+ 交易员群，针对"找 X 交易所"这类意向主动回话，转化对话交给你的销售坐席。',
        metric: '合格线索 ~$0.50 / 条',
        sub:    '对比付费社交 $40 CPL',
      },
      {
        title:  '金融科技 / 外汇出海',
        blurb:
          '合规友好的首次接触：AI 在群内用公开可见的话术回话，绝不主动 DM。受牌的销售人工进行合规话术。',
        metric: '相比海外 SDR 便宜 50×',
        sub:    '每次互动都有完整审计记录',
      },
      {
        title:  '跨境电商 / MCN',
        blurb:
          '采集竞品社区成员（按 MB 计费）。对高重叠人群跑群发战役。AI 助手接收回复并分诊给团队。',
        metric: '三个动作，一个钱包',
        sub:    '采集 · 群发 · 拉群 —— 全 USDT 计量',
      },
    ],
  },
  security: {
    eyebrow: '安全与合规',
    title:   '企业级 —— 从第一天起。',
    pillars: [
      { title: 'AES-256 静态加密',  desc: 'Session 字符串 + tdata 在落盘前使用 per-instance KEK 加密。即使数据库被访问，session 也无法使用。' },
      { title: '操作审计日志',      desc: '每个 admin 动作 —— 发票激活、角色变更、特性覆盖 —— 都写入 operation_log，含操作人 + 前后 diff。可导出 CSV。' },
      { title: 'SSO + SAML（Pro）', desc: '接入你的 IdP。OAuth 风格的客户 JWT 流程。坐席级审计追踪。' },
      { title: '自托管钱包',        desc: 'USDT 直接到客户的租户地址。我们从不托管资金 —— 退款、充值、冻结全部链上完成。' },
    ],
    contractTitle: '平台为你强制执行两条安全契约。',
    contract1:
      'AI 仅在群内回复，绝不 DM。客户自配 monitor 的 reply_mode `private_dm` 在 API 层被硬拒。私下接触保持人工决策。',
    contract2:
      'Listener 层租户隔离。你的 monitor 规则只在 `customer_id` 匹配你的 TG 账号上触发。跨租户串台在结构上不可能。',
  },
  faq: {
    eyebrow: '常见问题',
    title:   '我们被问得最多的几个。',
    items: [
      {
        q: '$20 免费试用怎么领？',
        a: '用工作邮箱在 /portal/register 注册即可 —— 钱包立即入账 $20 USDT 等值。无需信用卡，无需链上转账。够跑 ~2000 条采集、200 条群发、或 40 条 AI 自动线索。',
      },
      {
        q: '我的账号会被封吗？',
        a: '风险集中在未经请求的 DM。所以客户自配 monitor 只能群内回复、永不自动 DM。配合人设养号、日上限、随机延迟、FloodWait 重试，Growth 档实际封号率低于 1%/月 —— 超出部分由替换 SLA 兜底。',
      },
      {
        q: '中国大陆能用吗？',
        a: '能。每个付费客户都接入按地区的代理池（住宅出口、按国家粘性、每账号专属）。Pro 档含 2 个独占代理槽位。Console + Portal 通过相同代理可达。',
      },
      {
        q: '销售接管具体怎么工作？',
        a: 'Lead 进入 inbox 时已预分配给拥有该 TG 账号的销售。一键标记认领（原子操作，杜绝双重接管），AI 切到"草稿模式"（仅建议，不自动发送），销售人工发 DM。每次交互都记录到 CRM。',
      },
      {
        q: '任务跑一半钱包没钱了会怎样？',
        a: '任务切到 `paused_no_funds` 状态。不会失败，恢复时不会重复执行（幂等键），销售看到的飞行中线索仍在 —— 只是不再产生新线索，直到充值。',
      },
      {
        q: '租户隔离怎么保证？',
        a: '每张业务表都带 `customer_id` 列，在 listener + API + KB 检索层都强制行级过滤。你的 monitor 规则不会在别人的账号上触发；你的销售看不到别人的 lead。结构层面的隔离，不是政策层面。',
      },
      {
        q: '支持信用卡 / 银行转账吗？',
        a: '不支持。我们仅接受 USDT，三链可选：TRC20 / ERC20 / BEP20。结算全部链上完成；退款和充值透明。中间环节少，对加密原生客户的账目更干净。',
      },
      {
        q: '可以自托管或拿源码吗？',
        a: 'Pro 档客户可拿到只读 repo 访问 + 在自己 VPC 里跑后端的权限（不含源码许可，运维级访问）。源码授权按 $50k+/年承诺额按需洽谈。',
      },
    ],
  },
};

// ── ja (machine-translated 2026-05-25, needs human review) ───────────────

const ja: Dict = {
  meta: {
    titleSuffix: 'TG1.AI — Telegramの成長を自動操縦に',
    description:
      'Telegram マーケティング自動化：従量課金のスクレイピング / 一括送信 / 招待 + ターゲットグループを聴くAIマーケティングアシスタントが、高意向リードを営業に届けます。USDT 決済。テナント当たり 1,000+ アカウント。',
  },
  nav: {
    selfServe: 'セルフサービス',
    aiAssistant: 'AI アシスタント',
    pricing: '料金',
    docs: 'ドキュメント',
    signIn: 'ログイン',
    freeTrial: '$20 無料トライアル',
  },
  hero: {
    titlePart1: 'Telegram で成長する',
    titlePart2: '2 つの方法',
    subtitle:
      '従量課金型のスクレイピング & 一括送信 + AI マーケティングアシスタントがターゲットグループを聴き、高意向リードを受信箱に届けます。',
    subtitleQuiet: '1 つのプラットフォーム、1 つのアカウントプール、1 つのウォレット。',
    ctaPrimary:   '$20 無料トライアル',
    ctaSecondary: '90 秒デモを見る',
    ctaTertiary:  'Telegram で相談',
    selfServe: {
      tag:   'セルフサービス',
      title: '従量課金の一括オペレーション',
      blurb: 'スクレイプ、送信、招待 — 3 つのコアアクションを単価制で、USDT 前払いで。',
      bullets: [
        { label: 'グループスクレイプ', price: '$0.01 / メンバー' },
        { label: '一括送信',           price: '$0.10 / メッセージ' },
        { label: '一括招待',           price: '$0.05 / 招待' },
      ],
      fit: '向いている：自社 SDR ツールの構築',
      see: '詳細を見る',
    },
    aiAssistant: {
      tag:   'AI マーケティングアシスタント',
      title: '自分で雇われるサブスクリプション',
      blurb: 'TG アカウントが 24/7 聴き続けます。AI は意図ヒット時にグループ内で返信し、リードを営業の受信箱に届けます。',
      bullets: [
        { label: '聴く対象',   price: 'あなたのターゲットグループ' },
        { label: '返信先',     price: 'グループ（DM ではない）' },
        { label: '引き継ぎ先', price: 'あなたの担当者' },
      ],
      fit: '向いている：SDR / BDR チームの代替',
      safetyNote: 'AI が自動で DM することはありません — 判断は営業に残ります',
      see: '詳細を見る',
    },
  },
  demo: {
    title: 'TG1 AI アシスタント · ライブデモ',
    badge: '3 つのグループを監視中',
    consoleLabel: 'AI コンソール',
    inbox: { label: '受信箱', empty: '受信箱 · 空' },
    acts: {
      listening: '1/4 · 監視中',
      incoming: '2/4 · 受信',
      scoring: '3/4 · AI 採点',
      handover: '4/4 · 引き継ぎ',
    },
    kpi: { rate: 'メッセージ速度', rateUnit: ' 件/分', captured: '本日の獲得' },
    console: {
      line1: '[00:01] 3 つのターゲットグループに接続中...',
      line2: '[00:03] すべてのリスナーがオンライン',
      line3: '[00:21] 意図分類器をロードしました（中/英）',
      line4: '[00:42] 高意向マッチ → スコア 92、inbox に送信',
    },
    score: {
      label: '意向スコア',
      keywords: 'キーワード',
      keywordsValue: 'USDT · クロスボーダー',
      persona: 'ペルソナ',
      personaValue: '中小事業者',
      suggestion: '推奨トーク',
      suggestionValue: 'こんにちは。USDT の受け取りについてのご質問を拝見しました。当社は加盟店がステーブルコインで受け取れるよう支援しています。2 分のデモはいかがですか？',
    },
    handover: {
      salesName: '営業 · Alex',
      salesReply: 'こんにちは、グループでの USDT 受け取りに関するご質問を拝見しました…',
      typing: '入力中…',
    },
    controls: { pause: '一時停止', resume: '再開', restart: '再生', close: 'デモを閉じる' },
    reduced: { intro: 'モーション設定によりアニメーションは無効です。4 幕をご覧ください：' },
    messages: {
      m0: 'おはよう、ここで暗号系の TG チャンネルやってる人いる？',
      m1: '昨日のエアドロップは詐欺だった、50u 損した',
      m2: 'モデレーター、ピン留めメッセージを更新してもらえる？',
      m3: '海外クライアントから USDT で受け取ってる人いる？銀行が辛すぎる',
      m4: 'gm',
      m5: '私のチャンネル：@somespammer',
      m6: 'TG グループ一括送信ツール探してます、有料 OK——おすすめある？',
      m7: '昨日のアルファ感謝',
    },
    senders: {
      s0: 'jake_w', s1: 'crypto_sam', s2: 'mira', s3: 'marco_smb',
      s4: 'dexter', s5: 'spam_bot', s6: 'lei_growth', s7: 'anon',
    },
    groups: { g0: 'クロスボーダー決済', g1: 'TG 成長運用', g2: '中小事業者' },
  },
  pricing: {
    eyebrow: '料金',
    titlePart1: 'サブスクリプションがプラットフォームを開錠。',
    titlePart2: 'ウォレットがオペレーションを計量。',
    subtitle:
      '両プロダクトとも USDT 決済。サブスクリプションは固定の基盤コスト（アカウント / グループ / トークン / 席）、一括操作と AI 返信は上乗せの従量制。',
    plans: {
      starter: {
        ctaLabel: 'Starter で始める',
        features: [
          'AI マーケティングアシスタント込み',
          '顧客 KB アップロード + RAG',
          'ウォレット従量操作',
          'USDT 専用決済',
          'メールサポート、24 時間 SLA',
        ],
        quotaLines: ['3 TG アカウント', '500 ターゲットグループ', '月 200 万 LLM トークン', '営業席 1'],
      },
      growth: {
        ctaLabel: 'Growth を選ぶ',
        features: [
          'Starter のすべて',
          '優先 listener シャード',
          'リードの事前割当 + 原子的クレーム',
          '残高低下自動停止 + Slack 通知',
          'メール + Telegram サポート、12 時間 SLA',
        ],
        quotaLines: ['5 TG アカウント', '1,000 ターゲットグループ', '月 500 万 LLM トークン', '営業席 3'],
      },
      pro: {
        ctaLabel: 'Pro へ',
        features: [
          'Growth のすべて',
          '専任カスタマーサクセスエンジニア',
          'SSO + 監査ログのエクスポート',
          '機能ごとのカスタム価格',
          '99.9% SLA、4 時間対応',
        ],
        quotaLines: ['10 TG アカウント', '3,000 ターゲットグループ', '月 1,500 万 LLM トークン', '営業席 10'],
      },
    },
    mostPopular:   '人気',
    perMonthUsdt:  ' / 月 · USDT',
    tableTitle:    '単価表',
    tableSubtitle: 'ウォレット課金対象アクションの単一情報源。',
    tableHeaders: {
      product: '製品',
      action:  'アクション',
      unit:    '課金単位',
      price:   'デフォルト',
    },
    tableAdminNote: {
      before: '大口取引は管理者が顧客ごとに単価を上書きできます。',
      linkLabel: 'billing ドキュメント',
      after: 'を参照。',
    },
  },
  finalCta: {
    titlePart1: 'BAN との戦いをやめよう。',
    titlePart2: '収益を出し続けよう。',
    subtitle:
      '$20 無料クレジット、24 時間で最初のリード。自分のペースでオンボード、必要なときだけ人と話す。',
  },
  footer: {
    tagline: 'Telegram の成長を自動操縦に。スケールするオペレーターのために。',
    statusLabel: 'ステータス',
    statusValue: 'すべて正常',
    columns: {
      product: '製品',
      company: '会社',
    },
    links: {
      selfServe:   'セルフサービス',
      aiAssistant: 'AI アシスタント',
      pricing:     '料金',
      docs:        'ドキュメント',
      changelog:   '更新履歴',
      talkToSales: '営業に相談',
      privacy:     'プライバシー',
      terms:       '利用規約',
    },
    copyright:     '© {year} TG1.AI — All rights reserved.',
    notAffiliated: 'Telegram 経済のために構築。Telegram FZ-LLC とは無関係。',
  },
  trustBar: {
    accounts: 'テナント当たりアカウント',
    shards:   '本番 listener シャード',
    rag:      'Vertex Gemini RAG',
    uptime:   'セッション稼働率',
    networks: 'TRC20 · ERC20 · BEP20',
  },
  selfServe: {
    eyebrow: 'セルフサービス — 従量課金',
    titleA: '3 つの Telegram オペレーション、3 つの単価。',
    titleB: 'サブスクリプション不要。',
    subtitle:
      'USDT でウォレットをチャージし、スクレイプ / 送信 / 招待を実行。残高は繰り越し、残高が次のアクションコスト未満になると自動停止 — 意図せず使い過ぎることはありません。',
    triplet: [
      { badge: '$0.01 / メンバー', title: 'グループスクレイプ', description: 'あなたのアカウントが見えるグループのメンバーリストを取得。アクティビティ、言語、参加日でフィルタ。1 メンバーあたり $0.01、失敗行は無料。' },
      { badge: '$0.10 / メッセージ', title: '一括送信', description: '数百アカウントにわたるキャンペーンをスケジュール。テンプレートのバリエーションで検出を回避。アカウント単位の日次上限を尊重。配信成功時のみ課金。' },
      { badge: '$0.05 / 招待', title: '一括招待', description: 'スクレイプ済みリストからユーザーをコミュニティグループに引き込み。Telegram がスロットルしたら自動停止、クールダウン後に再開。各招待試行ごとに計量。' },
    ],
    flowTitle: 'ウォレットの仕組み',
    flowSteps: [
      { title: 'チャージ',     desc: 'テナントアドレスに USDT を送金。チェーン確認後に自動入金。' },
      { title: '実行',         desc: '各アクションが公示単価で控除。レシートはウォレット履歴に。' },
      { title: '自動停止',     desc: '残高が次のオペコスト未満になるとタスクは `paused_no_funds` に。サプライズの超過なし。' },
      { title: '再開',         desc: '再チャージで中断したところから再開 — 冪等キーで重複実行なし。' },
    ],
    stripQuestion: '完全な単価表を見たい？',
    stripQuiet:    '5 万ボリューム以上のスクレイプ / 送信 / 招待の階層単価を含みます。',
    stripCta:      '料金を見る',
  },
  aiAssistant: {
    eyebrow:  'AI マーケティングアシスタント — サブスクリプション',
    titleA:   '24 時間で立ち上がる SDR / BDR チーム。',
    titleB:   '設計から半自動。',
    subtitle:
      'モニタールールを一度設定すれば、AI がグループでの初回タッチを処理 — 親しみやすく、ブランドに沿い、文脈に合わせて — そして高意向リードを人間の受信箱に。誰に DM するかはあなたが決めます。',
    steps: [
      { title: '聴く',       desc: 'TG アカウントがターゲットグループに 24/7 待機。listener は本番 5 シャード、各 ~200 アカウントに分散。' },
      { title: '認識',       desc: '二段階マッチ：キーワード事前フィルター（高速）→ Vertex Gemini セマンティック判定（精密）。BGE クロスエンコーダで再順位付け。' },
      { title: '関与',       desc: '意図ヒット時、AI はソースグループ内に文脈に沿った返信を投稿。ペルソナは KB から、営業臭は除去。' },
      { title: 'プッシュ',   desc: 'Lead 行が生成 — その TG アカウントの担当者に事前割り当て、ソースグループ属性は保持。' },
      { title: '引き継ぎ',   desc: '営業がワンクリック：AI は「ドラフトモード」に降格（提案のみ）、会話は営業のもの。アトミックなクレーム、二重引き継ぎなし。' },
      { title: 'CRM へ',     desc: '未転換リードは業界タグ + 全交互履歴と共に CRM へ — 営業チームは翌日の対応リストを朝に持って起きる。' },
    ],
    safetyTitle: 'AI が見込み客に自動で DM することは絶対にありません。',
    safetyDesc:
      '返信レイヤーは意図的に半自動。AI はソースグループで投稿し、誰もが見える — それが社会的証明。プライベートなアウトリーチは人間の判断のまま；営業が「クレーム」をクリックすれば AI はドラフト提案に切り替わり、DM はあなたが送る。',
    safetyWhy:
      'なぜ？BAN リスクは無許可 DM に集中、グループ内返信ではない。設計でアカウントを生かす。',
    safetyLink:  '安全文書を読む →',
    stripText:   '有料プランで AI アシスタントを有効化。',
    stripQuiet:  'サブスクリプションがアクセス制御；ウォレットが AI 返信（$0.05）+ リード（$0.50）を計量。',
    stripSeePlans: 'プランを見る',
    stripAskSales: '営業に質問',
  },
  howItWorks: {
    eyebrowPrefix: '仕組み ·',
    titleA: 'コールドリードから成約まで、',
    titleB: '一つの自律ループ。',
    steps: [
      { title: 'プラン有効化',           blurb: 'USDT → サブスクリプション有効 → 3/5/10 アカウント自動割当 + AI マーケティング有効化。' },
      { title: 'KB アップロード',        blurb: 'PDF / マークダウン / チャット履歴 → Gemini 埋め込み → pgvector インデックス。返信で自動引用。' },
      { title: 'モニター設定',           blurb: 'キーワード + ターゲットグループ + ペルソナを選択。アクティブモード = AI がグループで返信；プライベート DM はロック。' },
      { title: 'AI がグループで関与',     blurb: 'listener 発火 → セマンティック判定 → KB 引用付きの文脈に沿った返信を投稿。' },
      { title: 'リードが受信箱に',       blurb: '捕捉ユーザー → 営業席に事前割当 → アトミッククレーム、二重引き継ぎなし。' },
      { title: '営業が成約',             blurb: 'ワンクリックで引き継ぎ。AI はドラフトモードに、営業が DM を送り、会話は CRM に。' },
    ],
  },
  pricingCalc: {
    eyebrow:  '計算機',
    title:    '月額を見積もる',
    subtitle: 'スライダーをドラッグして予想ボリュームを設定。最も安いプラン + ウォレットの追加コストを表示します。',
    leadsLabel: '月間 AI 自動リード',
    sendsLabel: '月間一括送信メッセージ',
    leadsSuffix: ' リード',
    sendsSuffix: ' メッセージ',
    walletCostHeader: '可変ウォレットコスト · 見積',
    aiRepliesLine: 'AI 返信（リード当たり ~3）',
    aiLeadsLine:   'AI 自動リード',
    bulkSendLine:  '一括送信',
    totalLabel:    '月間ウォレット支出',
    bestBadge:     '最適',
    subPlanLabel:  'サブ',
    walletPlanLabel: 'ウォレット',
    perMo:         '/月',
  },
  useCases: {
    eyebrow: 'ユースケース',
    title:   'Telegram スケールで出荷するチームのために。',
    cards: [
      { title: 'Crypto / Web3 GTM',         blurb: 'IDO ローンチ、エアドロップキャンペーン、取引所紹介。AI が 30+ トレーダーチャットを聴き、「X 取引所を探してる」系の意図に文脈付き返信を投稿、変換会話は営業席に引き継ぐ。', metric: 'クオリファイドリード ~$0.50', sub: '対 有料ソーシャル $40 CPL' },
      { title: 'フィンテック・FX アウトバウンド', blurb: 'コンプライアンスフレンドリーな初回タッチ：AI は公開可能な文言でグループ内に返信、最初に DM しない。ライセンス持ち営業が規制対象会話を手動で行う。', metric: 'オフショア SDR より 50× 安い', sub: '各インタラクションに監査証跡' },
      { title: '越境 EC・MCN',              blurb: '競合コミュニティのメンバーをスクレイプ（MB 課金）。重複度の高いセグメントに一括送信。AI アシスタントが返信を捕捉してチームにトリアージ。', metric: '3 つのオペ、1 つのウォレット', sub: 'スクレイプ · 送信 · 招待 — すべて USDT 計量' },
    ],
  },
  security: {
    eyebrow: 'セキュリティとコンプライアンス',
    title:   '初日からエンタープライズグレード。',
    pillars: [
      { title: '静的 AES-256 暗号化',       desc: 'セッション文字列 + tdata はディスクに書く前にインスタンス毎の KEK で暗号化。DB アクセスがあってもセッションは使えない。' },
      { title: 'オペレーション監査ログ',     desc: '管理者の各アクション — インボイス有効化、ロール変更、機能上書き — を operation_log に actor + 前後 diff 付きで記録。CSV エクスポート可。' },
      { title: 'SSO + SAML（Pro）',         desc: 'あなたの IdP を持ち込む。顧客 JWT に対する OAuth スタイルのフロー。座席毎の監査トレイル。' },
      { title: 'セルフカストディウォレット', desc: 'USDT はテナントアドレスに直接。資金は預からない — 返金、チャージ、凍結はすべてオンチェーンのみ。' },
    ],
    contractTitle: 'プラットフォームが強制する 2 つの安全契約。',
    contract1:
      'AI はグループ内のみで返信、DM は決してしない。顧客所有モニターの reply_mode `private_dm` は API レイヤーでハード拒否。プライベートアウトリーチは人間の判断のまま。',
    contract2:
      'リスナーでのテナント分離。あなたのモニタールールは `customer_id` が一致する TG アカウントでのみ発火。テナント間のリークは構造的に不可能。',
  },
  faq: {
    eyebrow: 'FAQ',
    title:   'よく聞かれる質問。',
    items: [
      { q: '$20 無料トライアルを取得するには？', a: '/portal/register で動作するメールで登録 — ウォレットに $20 USDT 相当が即座に入金。カードもチェーン送金も不要。約 2,000 行のスクレイプ、200 件の一括送信、または 40 件の AI 自動リードに相当。' },
      { q: 'アカウントは BAN されますか？',      a: 'リスクは無許可 DM に集中。顧客所有モニターはグループ内返信のみ、自動 DM は不可。ペルソナウォームアップ、日次上限、ランダム遅延、FloodWait 認識リトライと組み合わせ、Growth プランの実 BAN 率は月 1% 未満。それを超える場合は交換 SLA でカバー。' },
      { q: '中国本土から使えますか？',           a: 'はい。すべての有料顧客に地域別プロキシプール（住宅出口、国別ピン留め、アカウント毎スティッキー）へのアクセスを提供。Pro プランは 2 専用プロキシスロット込み。Console + Portal は同じプロキシ経由で到達可能。' },
      { q: '営業の引き継ぎは実際どう動きますか？', a: 'リードはその TG アカウントの担当者に事前割り当て済みで営業の inbox に到着。ワンクリックでクレーム（アトミック — 二重引き継ぎなし）、AI は「ドラフトモード」（提案のみ、自動送信なし）に切り替わり、営業が DM を手動で送信。各インタラクションは CRM に記録。' },
      { q: 'タスク中にウォレットが切れたら？',   a: 'タスクは `paused_no_funds` に移行。失敗せず、再開時に重複実行せず（冪等キー）、営業席は飛行中のリードを引き続き表示 — チャージするまで新規生成のみ停止。' },
      { q: 'テナント分離はどう保証されますか？', a: 'すべての業務テーブルが `customer_id` カラムを持ち、listener + API + KB 検索の全層で行レベルフィルタが強制。あなたのモニタールールは他者のアカウントで発火できず、あなたの営業は他者のリードを閲覧できない。構造的、ポリシー的ではない。' },
      { q: 'カードや銀行振込はサポート？',       a: 'いいえ。USDT 専用、3 ネットワーク：TRC20 / ERC20 / BEP20。決済はオンチェーン、返金とクレジットは透明。中間業者を減らし、クリプトネイティブ顧客の帳簿をきれいに。' },
      { q: 'セルフホストまたはソースは入手可？', a: 'Pro プラン顧客は読み取り専用 repo アクセス + 自社 VPC でのバックエンド実行権を取得（ソースライセンスなし、オペグレードアクセス）。ソースライセンスは年間 $50k+ コミットメントで個別対応。' },
    ],
  },
};

// ── ko (machine-translated 2026-05-25, needs human review) ───────────────

const ko: Dict = {
  meta: {
    titleSuffix: 'TG1.AI — 텔레그램 성장을 자율 주행으로',
    description:
      '텔레그램 마케팅 자동화: 종량제 스크래핑 / 대량 전송 / 초대 + 타깃 그룹을 듣고 고의향 리드를 영업에게 전달하는 AI 마케팅 어시스턴트. USDT 결제. 테넌트당 1,000+ 계정.',
  },
  nav: {
    selfServe: '셀프 서비스',
    aiAssistant: 'AI 어시스턴트',
    pricing: '요금제',
    docs: '문서',
    signIn: '로그인',
    freeTrial: '$20 무료 체험',
  },
  hero: {
    titlePart1: '텔레그램에서 성장하는',
    titlePart2: '두 가지 방법',
    subtitle:
      '종량제 스크래핑 & 대량 전송 + 타깃 그룹을 듣고 고의향 리드를 받은편지함으로 전달하는 AI 마케팅 어시스턴트.',
    subtitleQuiet: '하나의 플랫폼, 하나의 계정 풀, 하나의 지갑.',
    ctaPrimary:   '$20 무료 체험',
    ctaSecondary: '90초 데모 보기',
    ctaTertiary:  'Telegram에서 영업 상담',
    selfServe: {
      tag:   '셀프 서비스',
      title: '종량제 대량 운영',
      blurb: '스크랩, 전송, 초대 — 세 가지 핵심 액션을 단가별로, USDT 선결제로.',
      bullets: [
        { label: '그룹 스크랩', price: '$0.01 / 멤버' },
        { label: '대량 전송',   price: '$0.10 / 메시지' },
        { label: '대량 초대',   price: '$0.05 / 초대' },
      ],
      fit: '추천: 사내 SDR 도구 구축',
      see: '자세히 보기',
    },
    aiAssistant: {
      tag:   'AI 마케팅 어시스턴트',
      title: '스스로 일하는 구독',
      blurb: 'TG 계정이 24/7 듣습니다. AI는 의도 일치 시 그룹에 답글하고, 리드를 영업 받은편지함으로 보냅니다.',
      bullets: [
        { label: '듣는 곳',   price: '당신이 지정한 타깃 그룹' },
        { label: '답글 위치', price: '그룹 (DM 아님)' },
        { label: '이관 대상', price: '담당자' },
      ],
      fit: '추천: SDR / BDR 팀 대체',
      safetyNote: 'AI는 사용자에게 자동 DM을 보내지 않습니다 — 그 결정은 영업의 몫입니다',
      see: '자세히 보기',
    },
  },
  demo: {
    title: 'TG1 AI 어시스턴트 · 라이브 데모',
    badge: '3개 그룹 모니터링 중',
    consoleLabel: 'AI 콘솔',
    inbox: { label: '받은편지함', empty: '받은편지함 · 비어있음' },
    acts: {
      listening: '1/4 · 모니터링',
      incoming: '2/4 · 수신',
      scoring: '3/4 · AI 채점',
      handover: '4/4 · 인계',
    },
    kpi: { rate: '메시지 속도', rateUnit: ' 건/분', captured: '오늘 확보' },
    console: {
      line1: '[00:01] 3개 대상 그룹에 연결 중...',
      line2: '[00:03] 모든 리스너 온라인',
      line3: '[00:21] 의도 분류기 로드됨 (중/영)',
      line4: '[00:42] 고의향 매치 → 점수 92, inbox로 전송',
    },
    score: {
      label: '의향 점수',
      keywords: '키워드',
      keywordsValue: 'USDT · 국경 간 결제',
      persona: '페르소나',
      personaValue: '중소 사업자',
      suggestion: '추천 멘트',
      suggestionValue: '안녕하세요. USDT 수금에 대한 질문을 보았습니다. 저희는 가맹점이 스테이블코인으로 수금할 수 있도록 돕습니다. 2분 데모를 보시겠어요?',
    },
    handover: {
      salesName: '영업 · Alex',
      salesReply: '안녕하세요, 그룹에서 USDT 수금에 대한 질문을 보았습니다…',
      typing: '입력 중…',
    },
    controls: { pause: '일시정지', resume: '재개', restart: '다시 재생', close: '데모 닫기' },
    reduced: { intro: '모션 설정에 따라 애니메이션이 비활성화되었습니다. 4막을 보세요:' },
    messages: {
      m0: '안녕하세요, 여기 암호 관련 TG 채널 운영하는 분 있나요?',
      m1: '어제 그 에어드롭 사기였어요, 50u 잃었어요',
      m2: '모더레이터, 고정 메시지 업데이트 가능할까요?',
      m3: '해외 고객에게 USDT로 수금하시는 분 있나요? 은행이 너무 힘드네요',
      m4: 'gm',
      m5: '제 채널 보세요: @somespammer',
      m6: 'TG 그룹 발송 도구 찾고 있어요, 유료 OK——추천 있나요?',
      m7: '어제 알파 감사',
    },
    senders: {
      s0: 'jake_w', s1: 'crypto_sam', s2: 'mira', s3: 'marco_smb',
      s4: 'dexter', s5: 'spam_bot', s6: 'lei_growth', s7: 'anon',
    },
    groups: { g0: '국경 간 결제', g1: 'TG 성장 운영', g2: '중소 사업자' },
  },
  pricing: {
    eyebrow: '요금제',
    titlePart1: '구독이 플랫폼을 열어줍니다.',
    titlePart2: '지갑이 운영을 계량합니다.',
    subtitle:
      '두 제품 모두 USDT로 청구. 구독은 고정 인프라 비용 (계정 / 그룹 / 토큰 / 좌석), 대량 작업과 AI 답글은 그 위에서 종량제로.',
    plans: {
      starter: {
        ctaLabel: 'Starter 시작',
        features: [
          'AI 마케팅 어시스턴트 포함',
          '고객 KB 업로드 + RAG',
          '지갑 종량 운영',
          'USDT 전용 청구',
          '이메일 지원, 24시간 SLA',
        ],
        quotaLines: ['TG 계정 3', '타깃 그룹 500', '월 LLM 토큰 200만', '영업 좌석 1'],
      },
      growth: {
        ctaLabel: 'Growth 선택',
        features: [
          'Starter의 모든 기능',
          '우선 listener 샤드',
          '리드 사전 할당 + 원자적 클레임',
          '잔액 부족 자동 정지 + Slack 알림',
          '이메일 + Telegram 지원, 12시간 SLA',
        ],
        quotaLines: ['TG 계정 5', '타깃 그룹 1,000', '월 LLM 토큰 500만', '영업 좌석 3'],
      },
      pro: {
        ctaLabel: 'Pro로',
        features: [
          'Growth의 모든 기능',
          '전담 고객 성공 엔지니어',
          'SSO + 감사 로그 내보내기',
          '기능별 맞춤 가격',
          '99.9% SLA, 4시간 응답',
        ],
        quotaLines: ['TG 계정 10', '타깃 그룹 3,000', '월 LLM 토큰 1,500만', '영업 좌석 10'],
      },
    },
    mostPopular:   '인기',
    perMonthUsdt:  ' / 월 · USDT',
    tableTitle:    '전체 단가표',
    tableSubtitle: '지갑에서 청구되는 모든 액션의 단일 정보원.',
    tableHeaders: {
      product: '제품',
      action:  '액션',
      unit:    '청구 단위',
      price:   '기본',
    },
    tableAdminNote: {
      before: '대량 거래는 관리자가 고객별로 단가를 재정의할 수 있습니다. ',
      linkLabel: 'billing 문서',
      after: ' 참조.',
    },
  },
  finalCta: {
    titlePart1: '계정 차단과의 싸움을 멈추세요.',
    titlePart2: '매출을 안정적으로 만드세요.',
    subtitle:
      '$20 무료 크레딧, 24시간 내 첫 리드. 자신의 속도로 온보드, 필요할 때만 사람과 대화.',
  },
  footer: {
    tagline: 'Telegram 성장을 자율 주행으로. 스케일하는 운영자를 위해.',
    statusLabel: '상태',
    statusValue: '모든 시스템 정상',
    columns: {
      product: '제품',
      company: '회사',
    },
    links: {
      selfServe:   '셀프 서비스',
      aiAssistant: 'AI 어시스턴트',
      pricing:     '요금제',
      docs:        '문서',
      changelog:   '변경 로그',
      talkToSales: '영업 상담',
      privacy:     '개인정보',
      terms:       '약관',
    },
    copyright:     '© {year} TG1.AI — All rights reserved.',
    notAffiliated: 'Telegram 경제를 위해 구축. Telegram FZ-LLC와 무관.',
  },
  trustBar: {
    accounts: '테넌트당 계정',
    shards:   '프로덕션 listener 샤드',
    rag:      'Vertex Gemini RAG',
    uptime:   '세션 가동률',
    networks: 'TRC20 · ERC20 · BEP20',
  },
  selfServe: {
    eyebrow: '셀프 서비스 — 종량제',
    titleA: '세 가지 텔레그램 작업, 세 가지 고정 단가.',
    titleB: '구독 불필요.',
    subtitle:
      'USDT 지갑을 충전하고 스크랩 / 전송 / 초대를 실행합니다. 잔여 크레딧은 이월되며, 잔액이 다음 작업 비용 미만으로 떨어지면 자동 일시정지 — 실수로 과지출하지 않습니다.',
    triplet: [
      { badge: '$0.01 / 멤버', title: '그룹 스크랩', description: '계정이 볼 수 있는 그룹에서 멤버 목록을 추출. 활동성/언어/가입일 필터. 1 멤버당 $0.01, 실패 행은 무료.' },
      { badge: '$0.10 / 메시지', title: '대량 전송', description: '수백 계정에 걸친 캠페인 스케줄. 템플릿 변형으로 탐지 회피. 계정별 일일 한도 준수. 200 OK 받은 전송만 청구.' },
      { badge: '$0.05 / 초대', title: '대량 초대', description: '스크랩된 목록에서 사용자를 커뮤니티 그룹으로 유입. 텔레그램 스로틀 시 자동 일시정지, 쿨다운 후 재개. 각 초대 시도 단위 계량.' },
    ],
    flowTitle: '지갑 작동 방식',
    flowSteps: [
      { title: '충전',     desc: '테넌트 주소로 USDT 전송. 체인 확인 후 자동 입금.' },
      { title: '실행',     desc: '각 액션이 공시 단가로 차감. 영수증은 지갑 이력에.' },
      { title: '자동 정지', desc: '잔액 < 다음 작업 비용일 때 작업이 `paused_no_funds`로 — 예상 외 초과 없음.' },
      { title: '재개',     desc: '재충전. 작업은 중단점부터 재개 — 멱등 키로 재실행 위험 없음.' },
    ],
    stripQuestion: '전체 단가표를 보고 싶나요?',
    stripQuiet:    '5만 이상 볼륨의 스크랩 / 전송 / 초대 계층 단가 포함.',
    stripCta:      '가격 보기',
  },
  aiAssistant: {
    eyebrow:  'AI 마케팅 어시스턴트 — 구독',
    titleA:   '24시간 안에 출시되는 SDR / BDR 팀.',
    titleB:   '설계부터 반자동.',
    subtitle:
      '모니터 규칙을 한 번 설정하세요. AI가 그룹에서 첫 접촉을 처리 — 친근하고, 브랜드 일관, 맥락 적합 — 그리고 고의향 리드를 사람 받은편지함으로 라우팅. DM 여부는 당신이 결정.',
    steps: [
      { title: '듣기',     desc: 'TG 계정이 타깃 그룹에 24/7 상주. listener는 프로덕션 5 샤드에 분산, 각 ~200 계정.' },
      { title: '인식',     desc: '2단계 매칭: 키워드 사전 필터(빠름) → Vertex Gemini 의미 판단(정밀). BGE 크로스 인코더 재순위.' },
      { title: '참여',     desc: '의도 일치 시 AI가 소스 그룹에 맥락 답변 게시. 페르소나는 KB에서, 영업 라인은 제거.' },
      { title: '푸시',     desc: 'Lead 행이 생성 — 해당 TG 계정 담당자에게 사전 할당, 소스 그룹 속성 유지.' },
      { title: '인계',     desc: '영업이 한 번 클릭: AI는 "드래프트 모드"로 강등(제안만), 대화는 영업의 것. 원자적 클레임, 이중 인계 없음.' },
      { title: 'CRM',      desc: '미전환 리드는 산업 태그 + 전체 상호작용 이력과 함께 CRM에 — 영업 팀은 아침에 일어나 그날의 통화 목록을 갖습니다.' },
    ],
    safetyTitle: 'AI는 결코 잠재 고객에게 자동 DM을 보내지 않습니다.',
    safetyDesc:
      '답변 레이어는 의도적으로 반자동. AI는 모두가 볼 수 있는 소스 그룹에 게시 — 그게 사회적 증거. 비공개 접촉은 사람의 판단으로 남음; 영업이 "클레임"을 클릭하면 AI는 드래프트 제안으로 전환, DM은 당신이 보내는 것.',
    safetyWhy:
      '왜? 차단 위험은 무허가 DM에 집중, 그룹 내 답변이 아님. 우리는 설계로 계정을 살립니다.',
    safetyLink:  '안전 문서 읽기 →',
    stripText:   '유료 플랜에서 어시스턴트를 활성화.',
    stripQuiet:  '구독이 액세스를 제어; 지갑이 AI 답변($0.05) + 리드($0.50)를 계량.',
    stripSeePlans: '플랜 보기',
    stripAskSales: '영업 문의',
  },
  howItWorks: {
    eyebrowPrefix: '작동 방식 ·',
    titleA: '콜드 리드에서 거래 마감까지,',
    titleB: '하나의 자율 루프.',
    steps: [
      { title: '플랜 활성화',         blurb: 'USDT → 구독 활성 → 3/5/10 계정 자동 할당 + AI 마케팅 기능 잠금 해제.' },
      { title: 'KB 업로드',           blurb: 'PDF / 마크다운 / 채팅 이력 → Gemini 임베딩 → pgvector 인덱스. 답변에서 자동 인용.' },
      { title: '모니터 구성',         blurb: '키워드 + 타깃 그룹 + 페르소나 선택. 활성 모드 = AI 그룹 답변; 비공개 DM은 잠금.' },
      { title: 'AI 그룹 참여',        blurb: 'listener 발사 → 의미 판단 통과 → KB 인용 세부사항이 포함된 맥락 답변 게시.' },
      { title: '리드가 받은편지함으로', blurb: '캡처 사용자 → 영업 좌석에 사전 할당 → 원자적 클레임, 이중 인계 없음.' },
      { title: '영업 마감',           blurb: '원클릭 인계. AI는 드래프트 모드로 전환, 영업이 DM 전송, 대화는 CRM에 기록.' },
    ],
  },
  pricingCalc: {
    eyebrow:  '계산기',
    title:    '월별 청구 추정',
    subtitle: '슬라이더를 예상 볼륨으로 드래그하세요. 가장 저렴한 플랜과 지갑이 추가로 지출할 금액을 보여드립니다.',
    leadsLabel: '월간 AI 자동 리드',
    sendsLabel: '월간 대량 전송 메시지',
    leadsSuffix: ' 리드',
    sendsSuffix: ' 메시지',
    walletCostHeader: '가변 지갑 비용 · 추정',
    aiRepliesLine: 'AI 답변(리드당 ~3)',
    aiLeadsLine:   'AI 자동 리드',
    bulkSendLine:  '대량 전송',
    totalLabel:    '월간 지갑 지출 총액',
    bestBadge:     '최적',
    subPlanLabel:  '구독',
    walletPlanLabel: '지갑',
    perMo:         '/월',
  },
  useCases: {
    eyebrow: '사용 사례',
    title:   '텔레그램 규모로 출시하는 팀을 위해 구축.',
    cards: [
      { title: 'Crypto & Web3 GTM',           blurb: 'IDO 출시, 에어드롭 캠페인, 거래소 추천. AI가 30+ 트레이더 채팅을 듣고 "X 거래소 찾는중" 류 의도에 맥락 답변, 전환 대화는 영업 좌석으로 인계.', metric: '적격 리드당 ~$0.50', sub: '유료 소셜 $40 CPL 대비' },
      { title: '핀테크·외환 아웃바운드',         blurb: '컴플라이언스 친화적 첫 접촉: AI는 공개 가능한 언어로 그룹 내 답변, 결코 먼저 DM하지 않음. 면허 보유 영업이 규제 대화를 수동으로 진행.', metric: '오프쇼어 SDR 대비 50× 저렴', sub: '상호작용별 감사 추적 포함' },
      { title: '국경 간 이커머스 & MCN',        blurb: '경쟁사 커뮤니티 멤버 스크랩(MB당 청구). 중첩도 높은 세그먼트에 대량 전송 캠페인. AI 어시스턴트가 답변을 캐치해 팀에 트리아지.', metric: '3 작업, 1 지갑', sub: '스크랩 · 전송 · 초대 — 모두 USDT 계량' },
    ],
  },
  security: {
    eyebrow: '보안 및 컴플라이언스',
    title:   '첫날부터 엔터프라이즈급.',
    pillars: [
      { title: '저장 시 AES-256',         desc: '세션 문자열 + tdata 블롭이 디스크에 닿기 전 인스턴스별 KEK로 암호화. DB 접근이 있어도 세션은 키 없이 무용지물.' },
      { title: '작업 감사 로그',           desc: '모든 관리자 액션 — 인보이스 활성화, 역할 변경, 기능 오버라이드 — 가 operation_log에 actor + 전후 diff와 함께 기록. CSV 내보내기.' },
      { title: 'SSO + SAML(Pro)',         desc: '당신의 IdP를 가져오세요. 고객 JWT에 대한 OAuth 스타일 흐름. 좌석별 감사 추적.' },
      { title: '자체 수탁 지갑',           desc: 'USDT는 고객의 테넌트 주소로 직접. 자금은 위탁 보관하지 않음 — 환불, 충전, 동결은 모두 온체인.' },
    ],
    contractTitle: '플랫폼이 강제하는 2가지 안전 계약.',
    contract1:
      'AI는 그룹 내에서만 답변, DM은 절대 안 함. 고객 소유 모니터의 reply_mode `private_dm`은 API 레이어에서 하드 거부. 비공개 접촉은 사람의 결정으로 남음.',
    contract2:
      'Listener에서의 테넌트 격리. 모니터 규칙은 `customer_id`가 일치하는 TG 계정에서만 발사. 테넌트 간 누출은 구조적으로 불가능.',
  },
  faq: {
    eyebrow: 'FAQ',
    title:   '가장 자주 받는 질문.',
    items: [
      { q: '$20 무료 체험은 어떻게 청구하나요?', a: '/portal/register에서 작동하는 이메일로 등록 — 지갑에 $20 USDT 상당이 즉시 입금. 카드 불필요, 체인 전송 불필요. ~2,000 스크랩 행, 200 대량 전송, 또는 40 AI 자동 리드 실행 가능.' },
      { q: '계정이 차단되나요?',                a: '위험은 무허가 DM에 집중. 그래서 고객 소유 모니터는 그룹 내 답변만, 자동 DM 안 됨. 페르소나 워밍, 일일 한도, 무작위 지연, FloodWait 인식 재시도와 결합, Growth 티어 실제 차단율은 월 1% 미만 — 그 이상은 교체 SLA가 커버.' },
      { q: '중국 본토에서 사용 가능?',           a: '예. 모든 유료 고객에게 지역별 프록시 풀(주거 출구, 국가 고정, 계정별 스티키) 접근 제공. Pro 티어는 2 전용 프록시 슬롯 포함. Console + Portal은 동일 프록시로 접근 가능.' },
      { q: '영업 인계는 실제로 어떻게 작동?',    a: '리드가 해당 TG 계정 소유자에게 사전 할당되어 영업 받은편지함에 도착. 원클릭으로 클레임(원자적 — 이중 인계 없음), AI는 "드래프트 모드"(제안만, 자동 전송 없음)로 전환, 영업이 DM을 수동으로 전송. 모든 상호작용은 CRM에 기록.' },
      { q: '작업 중 지갑이 소진되면 어떻게?',    a: '작업은 `paused_no_funds`로 전환. 실패하지 않고, 재개 시 중복 작업 없음(멱등 키), 영업 좌석은 진행 중 리드를 계속 봄 — 충전할 때까지 새 리드 생성만 중지.' },
      { q: '테넌트 격리는 어떻게 보장?',         a: '모든 비즈니스 테이블에 `customer_id` 컬럼이 있고 listener + API + KB 검색 레이어에서 행 단위 필터 강제. 모니터 규칙은 타인의 계정에서 발사할 수 없고, 영업은 타인의 리드를 볼 수 없음. 구조적, 정책적이 아님.' },
      { q: '카드/은행 송금을 지원하나요?',       a: '아니요. USDT 전용, 3 네트워크: TRC20 / ERC20 / BEP20. 결제는 온체인, 환불과 크레딧 투명. 중개자가 적고 크립토 네이티브 고객의 장부가 깔끔.' },
      { q: '셀프 호스트 또는 소스 입수 가능?',   a: 'Pro 티어 고객은 읽기 전용 repo 액세스 + 자체 VPC에서 백엔드 실행 권한 획득(소스 라이선스 없음, 운영 등급 액세스). 소스 라이선스는 연 $50k+ 약정 시 요청 시 제공.' },
    ],
  },
};

// ── es (machine-translated 2026-05-25, needs human review) ───────────────

const es: Dict = {
  meta: {
    titleSuffix: 'TG1.AI — Crecimiento de Telegram, en piloto automático',
    description:
      'Automatización de marketing en Telegram: scraping / envío masivo / invitaciones por uso + un asistente de marketing IA que escucha tus grupos objetivo y envía leads al equipo de ventas. Facturación en USDT. 1000+ cuentas por inquilino.',
  },
  nav: {
    selfServe: 'Autoservicio',
    aiAssistant: 'Asistente IA',
    pricing: 'Precios',
    docs: 'Docs',
    signIn: 'Iniciar sesión',
    freeTrial: 'Prueba $20',
  },
  hero: {
    titlePart1: 'Dos formas de crecer',
    titlePart2: 'en Telegram',
    subtitle:
      'Scraping y envío masivo por uso + un asistente de marketing IA que escucha tus grupos objetivo y envía leads de alta intención a tu bandeja.',
    subtitleQuiet: 'Una plataforma, un pool de cuentas, una billetera.',
    ctaPrimary:   'Prueba $20',
    ctaSecondary: 'Ver demo de 90s',
    ctaTertiary:  'Hablar por Telegram',
    selfServe: {
      tag:   'Autoservicio',
      title: 'Operaciones masivas por uso',
      blurb: 'Scrap, envío, invitación — tres acciones núcleo, facturadas por unidad, prepagadas con USDT.',
      bullets: [
        { label: 'Scrap de grupo',  price: '$0.01 / miembro' },
        { label: 'Envío masivo',    price: '$0.10 / mensaje' },
        { label: 'Invitación masiva', price: '$0.05 / invitación' },
      ],
      fit: 'Ideal para: herramientas de SDR internas',
      see: 'Ver detalles',
    },
    aiAssistant: {
      tag:   'Asistente de marketing IA',
      title: 'Una suscripción que se contrata sola',
      blurb: 'Tus cuentas TG escuchan 24/7. La IA responde en grupo en aciertos de intención y envía leads a la bandeja de ventas.',
      bullets: [
        { label: 'Escucha',     price: 'tus grupos objetivo' },
        { label: 'Responde en', price: 'el grupo (no DM)' },
        { label: 'Entrega a',   price: 'tu personal' },
      ],
      fit: 'Ideal para: reemplazar un equipo SDR / BDR',
      safetyNote: 'La IA nunca envía DM automáticos — esa decisión queda en tu equipo de ventas',
      see: 'Ver detalles',
    },
  },
  demo: {
    title: 'Asistente IA de TG1 · Demo en vivo',
    badge: 'Escuchando 3 grupos',
    consoleLabel: 'consola IA',
    inbox: { label: 'bandeja', empty: 'bandeja · vacía' },
    acts: {
      listening: '1/4 · Escuchando',
      incoming: '2/4 · Entrante',
      scoring: '3/4 · Puntuación IA',
      handover: '4/4 · Traspaso',
    },
    kpi: { rate: 'Velocidad', rateUnit: '/min', captured: 'Capturados hoy' },
    console: {
      line1: '[00:01] conectando a 3 grupos objetivo...',
      line2: '[00:03] todos los escuchas en línea',
      line3: '[00:21] clasificador de intención cargado (zh+en)',
      line4: '[00:42] coincidencia de alta intención → puntuación 92, enviando a inbox',
    },
    score: {
      label: 'Puntuación de intención',
      keywords: 'Palabras clave',
      keywordsValue: 'USDT · transfronterizo',
      persona: 'Persona',
      personaValue: 'PYME / comerciante',
      suggestion: 'Apertura sugerida',
      suggestionValue: 'Hola — vi tu pregunta sobre recibir USDT. Ayudamos a comerciantes a aceptar stablecoin sin fricciones bancarias locales. ¿2 minutos de demo?',
    },
    handover: {
      salesName: 'Ventas · Alex',
      salesReply: 'Hola — vi tu pregunta en el grupo sobre recibir USDT…',
      typing: 'escribiendo…',
    },
    controls: { pause: 'Pausar', resume: 'Reanudar', restart: 'Reproducir', close: 'Cerrar demo' },
    reduced: { intro: 'Animación desactivada según tu preferencia de movimiento. Explora los 4 actos:' },
    messages: {
      m0: 'buenas, ¿alguien aquí lleva un canal TG de cripto?',
      m1: 'el airdrop de ayer era una estafa, perdí 50 usdt',
      m2: 'mods, ¿pueden actualizar el mensaje fijado?',
      m3: '¿alguien recibe pagos USDT de clientes en el extranjero? el banco me está matando',
      m4: 'gm',
      m5: 'mira mi canal: @somespammer',
      m6: 'busco herramienta de envío masivo TG, de pago OK — ¿recomendaciones?',
      m7: 'gracias por el alpha de ayer',
    },
    senders: {
      s0: 'jake_w', s1: 'crypto_sam', s2: 'mira', s3: 'marco_smb',
      s4: 'dexter', s5: 'spam_bot', s6: 'lei_growth', s7: 'anon',
    },
    groups: { g0: 'Pagos transfronterizos', g1: 'Operadores TG', g2: 'Fundadores PYME' },
  },
  pricing: {
    eyebrow: 'Precios',
    titlePart1: 'La suscripción habilita la plataforma.',
    titlePart2: 'La billetera mide las operaciones.',
    subtitle:
      'Ambos productos facturados en USDT. La suscripción es el costo de infraestructura recurrente (cuentas, grupos, tokens, asientos). Operaciones masivas y respuestas IA son pago por uso encima.',
    plans: {
      starter: {
        ctaLabel: 'Empezar con Starter',
        features: [
          'Asistente de marketing IA incluido',
          'Subida de KB + RAG',
          'Operaciones por uso con billetera',
          'Facturación solo en USDT',
          'Soporte por email, SLA 24h',
        ],
        quotaLines: ['3 cuentas TG', '500 grupos objetivo', '2M tokens LLM / mes', '1 asiento ventas'],
      },
      growth: {
        ctaLabel: 'Elegir Growth',
        features: [
          'Todo lo de Starter',
          'Listener shard prioritario',
          'Preasignación de leads + claim atómico',
          'Auto-pausa + alertas de saldo bajo en Slack',
          'Soporte email + Telegram, SLA 12h',
        ],
        quotaLines: ['5 cuentas TG', '1,000 grupos objetivo', '5M tokens LLM / mes', '3 asientos ventas'],
      },
      pro: {
        ctaLabel: 'Ir a Pro',
        features: [
          'Todo lo de Growth',
          'Ingeniero de éxito dedicado',
          'SSO + exportación de auditoría',
          'Precios personalizados por feature',
          'SLA 99.9%, respuesta 4h',
        ],
        quotaLines: ['10 cuentas TG', '3,000 grupos objetivo', '15M tokens LLM / mes', '10 asientos ventas'],
      },
    },
    mostPopular:   'Más popular',
    perMonthUsdt:  ' / mes · USDT',
    tableTitle:    'Tabla completa de precios unitarios',
    tableSubtitle: 'Cada acción facturada a billetera, una sola fuente de verdad.',
    tableHeaders: {
      product: 'Producto',
      action:  'Acción',
      unit:    'Unidad',
      price:   'Por defecto',
    },
    tableAdminNote: {
      before: 'Para grandes volúmenes, el admin puede sobrescribir cualquier línea por cliente. Ver ',
      linkLabel: 'docs de billing',
      after: '.',
    },
  },
  finalCta: {
    titlePart1: 'Deja de apagar incendios de bans.',
    titlePart2: 'Empieza a generar ingresos.',
    subtitle:
      '$20 de crédito gratis, 24 horas para los primeros leads. Onboarding a tu ritmo, habla con un humano solo cuando quieras.',
  },
  footer: {
    tagline: 'Crecimiento de Telegram en piloto automático. Hecho para operadores que escalan.',
    statusLabel: 'Estado',
    statusValue: 'Todos los sistemas operativos',
    columns: {
      product: 'Producto',
      company: 'Compañía',
    },
    links: {
      selfServe:   'Autoservicio',
      aiAssistant: 'Asistente IA',
      pricing:     'Precios',
      docs:        'Docs',
      changelog:   'Changelog',
      talkToSales: 'Hablar con ventas',
      privacy:     'Privacidad',
      terms:       'Términos',
    },
    copyright:     '© {year} TG1.AI — Todos los derechos reservados.',
    notAffiliated: 'Hecho para la economía de Telegram. No afiliado con Telegram FZ-LLC.',
  },
  trustBar: {
    accounts: 'cuentas por inquilino',
    shards:   'shards de listener (prod)',
    rag:      'Vertex Gemini RAG',
    uptime:   'uptime de sesión',
    networks: 'TRC20 · ERC20 · BEP20',
  },
  selfServe: {
    eyebrow: 'Autoservicio — Pago por uso',
    titleA: 'Tres operaciones Telegram, tres precios unitarios fijos.',
    titleB: 'Sin suscripción necesaria.',
    subtitle:
      'Recarga tu billetera USDT, ejecuta scrap / envío / invitación. El crédito sobrante se conserva, y la plataforma auto-pausa tareas cuando tu saldo baja del costo de la operación — no puedes gastar de más por accidente.',
    triplet: [
      { badge: '$0.01 / miembro', title: 'Scrap de grupo', description: 'Extrae listas de miembros de cualquier grupo visible para tu cuenta. Filtra por actividad, idioma o fecha de unión. Cada miembro extraído descuenta $0.01 — filas fallidas no se cobran.' },
      { badge: '$0.10 / mensaje', title: 'Envío masivo', description: 'Programa una campaña a través de cientos de cuentas. Variantes de plantilla evitan detección; el dispatcher respeta límites diarios por cuenta. Solo pagas entregas con 200 OK.' },
      { badge: '$0.05 / invitación', title: 'Invitación masiva', description: 'Trae usuarios a tu grupo comunitario desde una lista scraped. Auto-pausa si Telegram limita tus cuentas; se reanuda al pasar el cooldown. Cada intento — éxito o fallo — se mide.' },
    ],
    flowTitle: 'Cómo funciona la billetera',
    flowSteps: [
      { title: 'Recargar',      desc: 'Transfiere USDT a la dirección de tu inquilino. Auto-acreditado en confirmación de cadena.' },
      { title: 'Ejecutar',      desc: 'Cada acción descuenta al precio unitario publicado. Recibos en el historial de billetera.' },
      { title: 'Auto-pausa',    desc: 'Si saldo < costo próxima op, tarea pausa con `paused_no_funds` — sin excedentes sorpresa.' },
      { title: 'Reanudar',      desc: 'Recarga de nuevo. Las tareas retoman donde quedaron — sin riesgo de replay vía claves de idempotencia.' },
    ],
    stripQuestion: '¿Quieres ver la tabla completa de precios unitarios?',
    stripQuiet:    'Incluye escalonamiento de scrap / envío / invitación sobre 50k volumen.',
    stripCta:      'Ver precios',
  },
  aiAssistant: {
    eyebrow:  'Asistente de marketing IA — Suscripción',
    titleA:   'Un equipo SDR / BDR que arranca en 24 horas.',
    titleB:   'Semi-automático por diseño.',
    subtitle:
      'Configura una regla de monitor una vez. La IA maneja el primer contacto en el grupo — amigable, on-brand, contextual — y enruta leads de alta intención a una bandeja humana. Tú decides quién recibe el DM.',
    steps: [
      { title: 'Escuchar',  desc: 'Tus cuentas TG se sientan en tus grupos objetivo 24/7. El listener se distribuye en 5 shards prod, ~200 cuentas cada uno.' },
      { title: 'Reconocer', desc: 'Match en dos etapas: pre-filtro de keyword (rápido) → juez semántico Vertex Gemini (preciso). Re-ranking coseno vía BGE cross-encoder.' },
      { title: 'Engagar',   desc: 'En hit de intención, la IA publica una respuesta contextual EN el grupo fuente. Los personas vienen de tu KB, con eliminación de líneas de venta para no parecer un cartel.' },
      { title: 'Push',      desc: 'Una fila Lead se materializa — pre-asignada al vendedor que posee esa cuenta TG, atribución de grupo fuente intacta.' },
      { title: 'Takeover',  desc: 'El vendedor hace un clic: IA cae a "modo borrador" (solo sugerencias), la conversación es suya. Claim atómico, sin doble handoff.' },
      { title: 'CRM',       desc: 'Leads no convertidos aterrizan en CRM con tag de industria + historial de interacción — tu equipo de ventas tiene la lista de llamadas de mañana antes de despertar.' },
    ],
    safetyTitle: 'La IA nunca envía DM automático a tus prospectos.',
    safetyDesc:
      'La capa de respuesta es semi-automática a propósito. La IA publica en el grupo fuente donde todos pueden ver — eso es prueba social. El outreach privado queda como decisión humana; tu vendedor hace clic en "claim", IA cambia a sugerencias borrador, el DM lo envías tú.',
    safetyWhy:
      '¿Por qué? El riesgo de baneo se concentra en DMs no solicitados, no en respuestas en grupo. Mantenemos tus cuentas vivas por diseño.',
    safetyLink:  'Leer el doc de seguridad →',
    stripText:   'Activa el asistente en cualquier plan pagado.',
    stripQuiet:  'La suscripción otorga acceso; la billetera mide cada respuesta IA ($0.05) + lead ($0.50).',
    stripSeePlans: 'Ver planes',
    stripAskSales: 'Preguntar a ventas',
  },
  howItWorks: {
    eyebrowPrefix: 'Cómo funciona ·',
    titleA: 'De lead frío a deal cerrado,',
    titleB: 'un loop autónomo.',
    steps: [
      { title: 'Activar un plan',         blurb: 'USDT → Suscripción activa → 3/5/10 cuentas auto-asignadas + feature de marketing IA desbloqueado.' },
      { title: 'Subir tu KB',             blurb: 'PDF / markdown / historial de chat → embedding Gemini → índice pgvector. Citado automáticamente en respuestas.' },
      { title: 'Configurar un monitor',   blurb: 'Elige keywords + grupos objetivo + persona. Modo activo = IA responde en grupo; DM privado está bloqueado.' },
      { title: 'IA engage en grupo',      blurb: 'Listener dispara → juez semántico confirma → IA publica respuesta contextual con detalles citados del KB.' },
      { title: 'Lead aterriza en bandeja', blurb: 'Usuario capturado → pre-asignado a tu asiento de ventas → claim atómico, sin doble handoff.' },
      { title: 'Ventas cierra',           blurb: 'Takeover en un clic. IA cambia a modo borrador, ventas toma el DM, conversación loggeada al CRM.' },
    ],
  },
  pricingCalc: {
    eyebrow:  'Calculadora',
    title:    'Estima tu factura mensual',
    subtitle: 'Arrastra los sliders a tu volumen esperado. Te mostraremos el plan más barato + lo que tu billetera gastará encima.',
    leadsLabel: 'Leads IA auto por mes',
    sendsLabel: 'Mensajes envío masivo por mes',
    leadsSuffix: ' leads',
    sendsSuffix: ' mensajes',
    walletCostHeader: 'Costo variable de billetera · estimación',
    aiRepliesLine: 'Respuestas IA (~3 por lead)',
    aiLeadsLine:   'Leads IA auto',
    bulkSendLine:  'Envío masivo',
    totalLabel:    'Gasto total de billetera / mes',
    bestBadge:     'Mejor',
    subPlanLabel:  'sub',
    walletPlanLabel: 'billetera',
    perMo:         '/mes',
  },
  useCases: {
    eyebrow: 'Casos de uso',
    title:   'Hecho para los equipos que envían a escala Telegram.',
    cards: [
      { title: 'GTM de Crypto & Web3',         blurb: 'Lanzamientos IDO, campañas de airdrop, referidos de exchange. La IA escucha 30+ chats de traders, publica respuestas contextuales en intención tipo "busco X exchange", entrega la conversación de conversión a tu asiento de ventas.', metric: '~$0.50 por lead calificado', sub: 'vs. $40 CPL en social pagado' },
      { title: 'Fintech & forex outbound',      blurb: 'Primer contacto compliance-friendly: la IA responde en grupo con lenguaje públicamente visible, nunca DMea primero. Tu rep con licencia hace la conversación regulada manualmente.', metric: '50× más barato que SDRs offshore', sub: 'con rastro auditable por interacción' },
      { title: 'E-com transfronterizo & MCN',   blurb: 'Scrap miembros de comunidad competidora (facturación por MB). Corre campañas de envío masivo a segmentos de alto solapamiento. El asistente IA captura respuestas y las triage a tu equipo.', metric: '3 ops, una billetera', sub: 'scrap · envío · invitación — todo medido en USDT' },
    ],
  },
  security: {
    eyebrow: 'Seguridad y cumplimiento',
    title:   'Grado enterprise, desde el día uno.',
    pillars: [
      { title: 'AES-256 en reposo',        desc: 'Strings de sesión + blobs tdata cifrados con KEK por instancia antes de llegar al disco. Incluso con acceso DB, las sesiones son inútiles sin la clave.' },
      { title: 'Log de auditoría de ops',   desc: 'Cada acción de admin — activación de invoice, cambio de rol, override de feature — escrita a operation_log con actor + diff antes/después. Exportable a CSV.' },
      { title: 'SSO + SAML (Pro)',         desc: 'Trae tu IdP. Flujo OAuth-style contra el JWT del cliente. Audit trail por asiento.' },
      { title: 'Billetera self-custody',    desc: 'USDT va directamente a la dirección del inquilino. Nunca custodiamos fondos — reembolsos, recargas y freezes son solo on-chain.' },
    ],
    contractTitle: 'Dos contratos de seguridad que la plataforma hace cumplir por ti.',
    contract1:
      'IA responde solo en grupo, nunca en DM. El reply_mode `private_dm` es rechazado duro en la capa API para monitores de cliente. El outreach privado queda como decisión humana.',
    contract2:
      'Aislamiento de tenant en el listener. Tus reglas de monitor solo disparan en cuentas TG cuyo `customer_id` coincide. La fuga entre tenants es estructuralmente imposible.',
  },
  faq: {
    eyebrow: 'FAQ',
    title:   'Las preguntas que más recibimos.',
    items: [
      { q: '¿Cómo reclamo la prueba gratuita de $20?', a: 'Regístrate en /portal/register con un email funcional — tu billetera se acredita con $20 USDT equivalente inmediatamente. Sin tarjeta, sin transferencia de cadena. Suficiente para ~2,000 filas de scrap, 200 envíos masivos, o 40 leads IA auto.' },
      { q: '¿Mis cuentas serán baneadas?',             a: 'El riesgo se concentra en DMs no solicitados. Por eso los monitores de cliente solo responden en grupo, nunca auto-DM. Combinado con warming de persona, caps diarios, retrasos aleatorios y reintentos conscientes de FloodWait, la tasa de baneo real en Growth es <1%/mes — y el SLA de reemplazo cubre cualquier cosa más allá.' },
      { q: '¿Puedo usar esto desde China continental?', a: 'Sí. Damos a cada cliente pagado acceso al pool de proxies por región (salidas residenciales, fijadas por país, sticky por cuenta). Pro incluye 2 slots de proxy dedicado. El console + portal son alcanzables a través de los mismos proxies.' },
      { q: '¿Cómo funciona el takeover de ventas?',     a: 'El lead entra a la bandeja de ventas pre-asignado a quien posee esa cuenta TG. Un clic marca como reclamado (atómico — sin doble handoff), IA cambia a "modo borrador" (solo sugerencias, sin envío automático), y tus ventas envían el DM manualmente. Cada interacción loggeada al CRM.' },
      { q: '¿Qué pasa si mi billetera se acaba a mitad?', a: 'Las tareas transicionan a `paused_no_funds`. No fallan, no replayan ops duplicadas en resume (claves de idempotencia), y tus asientos de ventas siguen viendo leads en vuelo — solo dejan de generar nuevos hasta que recargues.' },
      { q: '¿Cómo se hace cumplir el aislamiento de tenant?', a: 'Cada tabla de negocio carga una columna `customer_id` con filtros row-level en las capas listener + API + KB retrieval. Tus reglas de monitor no pueden disparar en cuentas de otro; tus ventas no pueden ver leads de otro. Estructural, no de política.' },
      { q: '¿Soportan pagos con tarjeta/transferencia?',  a: 'No. Solo USDT en TRC20 / ERC20 / BEP20. Liquidación on-chain; reembolsos y crédito transparentes. Menos intermediarios, libros más limpios para clientes crypto-nativos.' },
      { q: '¿Puedo self-host o obtener el código?',       a: 'Clientes Pro obtienen acceso de lectura al repo + capacidad de correr el backend en su propio VPC (sin licencia de código, acceso ops-grade). Licencia de código disponible a pedido para compromisos de $50k+/año.' },
    ],
  },
};

// ── Registry + provider ─────────────────────────────────────────────────

export const DICTS: Record<Lang, Dict> = { en, 'zh-CN': zhCN, ja, ko, es };

const STORAGE_KEY = 'tg1.lang';

function detectLang(): Lang {
  if (typeof window === 'undefined') return 'en';
  const saved = window.localStorage.getItem(STORAGE_KEY) as Lang | null;
  if (saved && DICTS[saved]) return saved;
  const nav = (window.navigator.language || 'en').toLowerCase();
  if (nav.startsWith('zh')) return 'zh-CN';
  if (nav.startsWith('ja')) return 'ja';
  if (nav.startsWith('ko')) return 'ko';
  if (nav.startsWith('es')) return 'es';
  return 'en';
}

type Ctx = { lang: Lang; setLang: (l: Lang) => void; t: Dict };
const LangContext = createContext<Ctx | null>(null);

export const LangProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<Lang>('en');

  useEffect(() => {
    const initial = detectLang();
    setLangState(initial);
  }, []);

  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.lang = lang;
      // Update <title> + <meta description> dynamically so SEO bots that
      // honour client-side updates (Googlebot does) see the localized
      // strings.
      const t = DICTS[lang];
      document.title = t.meta.titleSuffix;
      const desc = document.querySelector('meta[name="description"]');
      if (desc) desc.setAttribute('content', t.meta.description);
    }
  }, [lang]);

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try {
      window.localStorage.setItem(STORAGE_KEY, l);
    } catch {
      /* ignore */
    }
  }, []);

  const value = useMemo<Ctx>(() => ({ lang, setLang, t: DICTS[lang] }), [lang, setLang]);
  return React.createElement(LangContext.Provider, { value }, children);
};

export function useLang(): Ctx {
  const ctx = useContext(LangContext);
  if (!ctx) throw new Error('useLang must be used within <LangProvider>');
  return ctx;
}

export function useT(): Dict {
  return useLang().t;
}
