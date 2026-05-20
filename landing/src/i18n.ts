import React, {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from 'react';

export type Lang = 'en' | 'zh-CN' | 'ja' | 'ko' | 'es';

export const LANGS: { code: Lang; native: string; english: string }[] = [
  { code: 'en', native: 'English', english: 'English' },
  { code: 'zh-CN', native: '简体中文', english: 'Chinese (Simplified)' },
  { code: 'ja', native: '日本語', english: 'Japanese' },
  { code: 'ko', native: '한국어', english: 'Korean' },
  { code: 'es', native: 'Español', english: 'Spanish' },
];

export type Dict = {
  nav: { product: string; pricing: string; docs: string; customers: string; changelog: string };
  cta: { signIn: string; launchConsole: string; viewDocs: string; mostPopular: string };
  hero: { badge: string; titleA: string; titleB: string; subtitle: string };
  trust: { nodes: string; messages: string; uptime: string; crypto: string; compliance: string };
  features: {
    eyebrow: string;
    title: string;
    subtitle: string;
    cards: {
      tdata: [string, string];
      ip: [string, string];
      rag: [string, string];
      takeover: [string, string];
      funnel: [string, string];
      monitor: [string, string];
    };
  };
  workflow: {
    eyebrow: string;
    titleA: string;
    titleB: string;
    steps: Array<{ label: string; title: string; body: string }>;
  };
  pricing: {
    eyebrow: string;
    title: string;
    subtitle: string;
    plans: Array<{ blurb: string; features: string[]; cta: string }>;
    badges: { crypto: string; wallet: string; card: string };
  };
  useCases: {
    eyebrow: string;
    title: string;
    cards: Array<{ title: string; body: string }>;
  };
  integrations: {
    eyebrow: string;
    title: string;
    subtitle: string;
    items: string[];
  };
  security: {
    eyebrow: string;
    title: string;
    subtitle: string;
    items: Array<{ title: string; body: string }>;
    badges: string;
  };
  faq: {
    eyebrow: string;
    title: string;
    items: Array<{ q: string; a: string }>;
  };
  finalCta: {
    title: string;
    titleAccent: string;
    body: string;
    primary: string;
    secondary: string;
  };
  footer: {
    tagline: string;
    sections: Array<{ title: string; items: string[] }>;
    copyright: string;
    builtFor: string;
  };
};

const en: Dict = {
  nav: { product: 'Product', pricing: 'Pricing', docs: 'Docs', customers: 'Customers', changelog: 'Changelog' },
  cta: { signIn: 'Sign in', launchConsole: 'Launch Console', viewDocs: 'View Documentation', mostPopular: 'Most popular' },
  hero: {
    badge: "What's new · Epic 6 — Operator Dashboard",
    titleA: 'Telegram growth,',
    titleB: 'industrialized.',
    subtitle:
      'KLTGSC is the enterprise Telegram automation OS. Orchestrate thousands of accounts, AI conversations and conversion handover — from one console.',
  },
  trust: {
    nodes: 'Account nodes',
    messages: 'Messages / day',
    uptime: 'Session uptime',
    crypto: 'Crypto-native billing',
    compliance: 'Compliance ready',
  },
  features: {
    eyebrow: 'Features',
    title: 'Built for industrial-scale Telegram operations.',
    subtitle: 'Six primitives that turn a folder of TData into a self-running revenue engine.',
    cards: {
      tdata: [
        'TData / Session orchestration at scale',
        'Bring your own TData. We rotate, warm, and shard 10,000+ sessions across isolated workers with zero supervision.',
      ],
      ip: [
        'Residential IP isolation per node',
        'Sticky residential exits, country-pinned, never reused. Burn one — the rest stay clean.',
      ],
      rag: [
        'RAG knowledge base + AI persona engine',
        'Drop in product docs, transcripts, and FAQs. The persona engine cites the right answer in the right voice — across 40+ languages.',
      ],
      takeover: [
        'Lead takeover',
        'Hand off hot leads to a human seller mid-conversation. No copy-paste, no context loss.',
      ],
      funnel: [
        'Conversion funnel',
        'Visual stage tracking from cold reach to revenue. Drop-off alerts fire to Slack.',
      ],
      monitor: [
        'Real-time risk & health monitor',
        'Per-session reputation, FloodWait curves, ban prediction. See trouble before it spreads.',
      ],
    },
  },
  workflow: {
    eyebrow: 'Workflow',
    titleA: 'From cold lead to closed deal —',
    titleB: 'one autonomous loop.',
    steps: [
      { label: 'Step 01', title: 'Lead Capture', body: 'Scrape sources, dedupe, score. Streamed into a unified pool.' },
      { label: 'Step 02', title: 'AI Outreach', body: 'Personalised first touch in seconds — backed by your RAG knowledge.' },
      { label: 'Step 03', title: 'Conversion Handover', body: 'Hot lead → human seller, fully briefed, with conversation context.' },
    ],
  },
  pricing: {
    eyebrow: 'Pricing',
    title: 'Simple, account-first pricing.',
    subtitle: 'Pay in USDT, USDC or card. Annual saves 20%. No per-message fees, ever.',
    plans: [
      {
        blurb: 'For solo operators validating a new market.',
        features: ['Up to 50 accounts', '1 RAG knowledge base', 'AI persona engine', 'Email support'],
        cta: 'Start with Starter',
      },
      {
        blurb: 'For teams running real conversion pipelines.',
        features: ['Up to 200 accounts', '5 RAG knowledge bases', 'Lead takeover & handover', 'Priority routing', 'Slack alerting'],
        cta: 'Start with Growth',
      },
      {
        blurb: 'For matrix operators running thousand-account fleets.',
        features: ['Up to 1,000 accounts', 'Unlimited knowledge bases', 'Dedicated success engineer', '99.99% SLA', 'SSO & audit logs'],
        cta: 'Talk to sales',
      },
    ],
    badges: { crypto: 'USDT · USDC · BTC', wallet: 'Self-custody wallet', card: 'Card (Stripe-ready)' },
  },
  useCases: {
    eyebrow: 'Use cases',
    title: 'Built for the teams that ship at Telegram scale.',
    cards: [
      {
        title: 'Crypto & Web3 GTM',
        body: 'DEX launches, IDO airdrops, validator referral pushes — fluent, on-brand and auditable across every campaign.',
      },
      {
        title: 'Fintech & forex outbound',
        body: 'Compliant first-touch motions for regulated products. Personalised, never spammy — and the audit trail is automatic.',
      },
      {
        title: 'Affiliate & traffic networks',
        body: 'Orchestrate sub-affiliate fleets without losing per-source visibility. Pay out in crypto, settle in seconds.',
      },
    ],
  },
  integrations: {
    eyebrow: 'Integrations',
    title: 'Connects to the stack you already run.',
    subtitle: 'Native integrations for messaging, payments, observability and CRM. Webhooks if it is not on the list.',
    items: ['Telegram MTProto', 'Slack', 'Discord', 'USDT (TRC20)', 'USDC', 'Bitcoin', 'Stripe', 'Webhooks', 'Notion', 'Linear', 'Datadog', 'Zapier'],
  },
  security: {
    eyebrow: 'Security & Compliance',
    title: 'Enterprise-grade. From day one.',
    subtitle: 'We treat your TData like an HSM key. Because it kind of is.',
    items: [
      { title: 'Encryption at rest', body: 'AES-256 for sessions, secrets and TData blobs. Per-tenant key derivation, never reused across customers.' },
      { title: 'Full audit log', body: 'Every action is journaled with actor, IP and timestamp. Exportable for SOC 2 and internal review.' },
      { title: 'SSO / SAML ready', body: 'Bring your IdP — Okta, Azure AD, Google Workspace. SAML 2.0 on Growth and above.' },
      { title: 'Self-custody wallet', body: 'Crypto payments settle directly to your wallet. We never hold customer funds.' },
    ],
    badges: 'SOC 2 Type I — in progress · GDPR · ISO 27001 — roadmap',
  },
  faq: {
    eyebrow: 'FAQ',
    title: 'Frequently asked.',
    items: [
      { q: 'Do you provide accounts or TData?', a: 'No. You bring your own TData; we orchestrate. Most enterprise customers source TData from vetted suppliers under their own legal scrutiny.' },
      { q: 'What happens when an account gets restricted?', a: 'Our real-time monitor detects FloodWait and ban risk per session, isolates the affected account and triggers your alerting (Slack / webhook). The rest of the fleet stays running.' },
      { q: 'Can the AI sound like a real human?', a: 'The persona engine is grounded on your knowledge base and a tone calibration step. We support 40+ languages. Most customers cannot tell their own AI replies apart in blind A/B tests.' },
      { q: 'How does Lead Takeover work?', a: 'When a lead crosses a hot threshold (intent score, keyword match or manual flag) the conversation thread is mirrored to a human seller portal — full context, no copy-paste.' },
      { q: 'Is the underlying messaging compliant?', a: 'Our infrastructure follows the published Telegram rate limits and ToS. Compliance with local marketing law (CAN-SPAM, GDPR, etc.) is your responsibility — we expose the controls you need.' },
      { q: 'What currencies do you accept?', a: 'USDT (TRC20/ERC20), USDC, BTC and major fiat via Stripe. Annual contracts settle in either.' },
      { q: 'Can I self-host?', a: 'Yes for Scale customers. We ship Docker images, Terraform modules and a runbook. The average deploy is under two hours on a single EC2 instance.' },
      { q: 'How fast can I get started?', a: 'MVP onboarding in under 24 hours: bring TData, paste your industry docs, pick a persona. We help drive the first campaign with you.' },
    ],
  },
  finalCta: {
    title: 'Stop firefighting Telegram bans.',
    titleAccent: 'Start shipping revenue.',
    body: 'Two clicks to a working pilot — bring your TData, we take it from there.',
    primary: 'Launch Console',
    secondary: 'Talk to an engineer',
  },
  footer: {
    tagline: 'The enterprise Telegram automation OS. Built for operators who scale.',
    sections: [
      { title: 'Product', items: ['Features', 'Pricing', 'Changelog', 'Status'] },
      { title: 'Resources', items: ['Docs', 'API reference', 'Guides', 'Customers'] },
      { title: 'Company', items: ['About', 'Careers', 'Contact', 'Legal'] },
    ],
    copyright: '© 2026 KLTGSC. All rights reserved.',
    builtFor: 'Built for operators who scale.',
  },
};

const zhCN: Dict = {
  nav: { product: '产品', pricing: '定价', docs: '文档', customers: '客户', changelog: '更新日志' },
  cta: { signIn: '登录', launchConsole: '进入控制台', viewDocs: '查看文档', mostPopular: '最受欢迎' },
  hero: {
    badge: '新版发布 · Epic 6 — 运营仪表盘',
    titleA: 'Telegram 增长，',
    titleB: '工业级。',
    subtitle:
      'KLTGSC 是面向出海团队的 Telegram 自动化操作系统，在同一个控制台编排上千账号、AI 对话与销售接管。',
  },
  trust: {
    nodes: '账号节点',
    messages: '日均消息',
    uptime: '会话在线',
    crypto: '加密原生计费',
    compliance: '合规就绪',
  },
  features: {
    eyebrow: '功能',
    title: '为工业级 Telegram 运营而生。',
    subtitle: '六个核心组件，把一个 TData 目录变成自运转的收入引擎。',
    cards: {
      tdata: [
        '大规模 TData / Session 编排',
        '你只需上传 TData。我们自动轮换、养号、跨隔离 Worker 分片调度 10,000+ Session，无需人工值守。',
      ],
      ip: [
        '每节点独立住宅 IP',
        '粘性住宅出口、国家定向、永不复用。封一个，其余依然干净。',
      ],
      rag: [
        'RAG 行业知识库 + AI 人设引擎',
        '导入产品文档、聊天记录与 FAQ。人设引擎用对的语气说对的话——支持 40+ 种语言。',
      ],
      takeover: [
        '销售接管',
        '热线索可在对话中无缝交接给人工销售，无需复制粘贴、不丢上下文。',
      ],
      funnel: [
        '转化漏斗',
        '从冷触达到成交的可视化阶段追踪。流失实时推 Slack 告警。',
      ],
      monitor: [
        '实时风险与健康监控',
        '逐会话健康分、FloodWait 曲线、封号预测，问题扩散前先看到。',
      ],
    },
  },
  workflow: {
    eyebrow: '工作流',
    titleA: '从冷线索到成交闭环 ——',
    titleB: '一条自驱动管线。',
    steps: [
      { label: '步骤 01', title: '线索采集', body: '多源抓取、去重、打分，统一进入线索池。' },
      { label: '步骤 02', title: 'AI 触达', body: '秒级个性化首触，背后是你的 RAG 知识库。' },
      { label: '步骤 03', title: '销售接管', body: '热线索一键交给人工销售，对话上下文同步过去。' },
    ],
  },
  pricing: {
    eyebrow: '定价',
    title: '极简、按账号计费。',
    subtitle: 'USDT、USDC 或信用卡支付。年付立省 20%，从不按条收费。',
    plans: [
      {
        blurb: '适合验证新市场的独立运营者。',
        features: ['50 个账号上限', '1 个 RAG 知识库', 'AI 人设引擎', '邮件支持'],
        cta: '选择 Starter',
      },
      {
        blurb: '适合跑真正转化管线的团队。',
        features: ['200 个账号上限', '5 个 RAG 知识库', '销售接管', '优先路由', 'Slack 告警'],
        cta: '选择 Growth',
      },
      {
        blurb: '适合千账号矩阵运营方。',
        features: ['1,000 个账号上限', '无限知识库', '专属客户成功工程师', '99.99% SLA', 'SSO 与审计日志'],
        cta: '联系销售',
      },
    ],
    badges: { crypto: 'USDT · USDC · BTC', wallet: '自托管钱包', card: '信用卡（Stripe 支持）' },
  },
  useCases: {
    eyebrow: '应用场景',
    title: '为 Telegram 规模化运营的团队而生。',
    cards: [
      { title: '加密 / Web3 GTM', body: 'DEX 上线、IDO 空投、节点推介 —— 每一次活动都流畅、贴合品牌、可审计。' },
      { title: '金融科技 / 外汇出海', body: '受监管产品的合规首触动作。个性化但绝不骚扰，审计轨迹自动归档。' },
      { title: '联盟营销 / 流量网络', body: '编排子代理矩阵，不丢失每个流量来源的可见性。加密支付，秒结。' },
    ],
  },
  integrations: {
    eyebrow: '集成',
    title: '接入你已经在用的技术栈。',
    subtitle: '消息、支付、可观测性、CRM 的原生集成。不在列表里？Webhook 兜底。',
    items: ['Telegram MTProto', 'Slack', 'Discord', 'USDT (TRC20)', 'USDC', 'Bitcoin', 'Stripe', 'Webhooks', 'Notion', 'Linear', 'Datadog', 'Zapier'],
  },
  security: {
    eyebrow: '安全 / 合规',
    title: '企业级。从第一天起。',
    subtitle: '我们把你的 TData 当 HSM 密钥对待——因为它差不多就是。',
    items: [
      { title: '静态加密', body: '会话、密钥、TData 全部 AES-256。每租户独立密钥派生，从不跨客户复用。' },
      { title: '全量审计日志', body: '每一次操作都记录操作人、IP、时间戳。可导出供 SOC 2 与内部审计使用。' },
      { title: 'SSO / SAML 就绪', body: '自带 IdP —— Okta、Azure AD、Google Workspace 都支持。SAML 2.0 从 Growth 起。' },
      { title: '自托管钱包', body: '加密支付直接结算到你的钱包。我们从不托管客户资金。' },
    ],
    badges: 'SOC 2 Type I —— 进行中 · GDPR · ISO 27001 —— 路线图',
  },
  faq: {
    eyebrow: '常见问题',
    title: '你大概想问的。',
    items: [
      { q: '你们提供账号或 TData 吗？', a: '不提供。客户自带 TData，我们负责编排。大多数企业客户从经过法务审核的供应商处采购 TData。' },
      { q: '账号被限制后会怎样？', a: '实时监控按会话识别 FloodWait 与封号风险，自动隔离受影响账号，触发你的告警（Slack / Webhook）。其余矩阵照常运行。' },
      { q: 'AI 能说得像真人吗？', a: '人设引擎基于你的知识库 + 一道语气校准。支持 40+ 种语言。盲测里大多数客户分不出自己的 AI 回复和真人。' },
      { q: '销售接管怎么工作？', a: '线索越过"热"阈值（意图分、关键词命中、手动标记）后，对话流自动镜像到人工销售的接管台 —— 完整上下文，无需复制粘贴。' },
      { q: '你们的消息发送是否合规？', a: '我们的基础设施遵循 Telegram 公开的速率限制与 ToS。本地营销法（CAN-SPAM、GDPR 等）合规由客户负责，我们提供你需要的控制项。' },
      { q: '你们接受哪些支付货币？', a: 'USDT（TRC20/ERC20）、USDC、BTC，以及通过 Stripe 接收主要法币。年付合同任选其一结算。' },
      { q: '可以私有化部署吗？', a: 'Scale 档支持。我们提供 Docker 镜像、Terraform 模块与 runbook。单台 EC2 平均 2 小时内完成部署。' },
      { q: '多久能上线？', a: 'MVP 上线 24 小时内：上传 TData、粘贴行业文档、选择人设。我们陪你跑完第一个活动。' },
    ],
  },
  finalCta: {
    title: '别再当 Telegram 封号救火队。',
    titleAccent: '开始稳定产收入。',
    body: '两次点击就能跑通试点 —— 你带 TData，剩下交给我们。',
    primary: '进入控制台',
    secondary: '找工程师聊聊',
  },
  footer: {
    tagline: '面向出海团队的 Telegram 自动化操作系统。为规模化运营者而造。',
    sections: [
      { title: '产品', items: ['功能', '定价', '更新日志', '服务状态'] },
      { title: '资源', items: ['文档', 'API', '使用指南', '客户案例'] },
      { title: '公司', items: ['关于我们', '招聘', '联系我们', '法律条款'] },
    ],
    copyright: '© 2026 KLTGSC. 版权所有。',
    builtFor: '为规模化运营者而造。',
  },
};

const ja: Dict = {
  nav: { product: 'プロダクト', pricing: '料金', docs: 'ドキュメント', customers: '導入事例', changelog: '更新履歴' },
  cta: { signIn: 'ログイン', launchConsole: 'コンソールを開く', viewDocs: 'ドキュメントを見る', mostPopular: '一番人気' },
  hero: {
    badge: '新着 · Epic 6 — オペレーションダッシュボード',
    titleA: 'Telegram グロース、',
    titleB: '産業化。',
    subtitle:
      'KLTGSC は法人向け Telegram 自動化 OS です。数千のアカウント、AI 会話、商談引き継ぎを、ひとつのコンソールで指揮します。',
  },
  trust: {
    nodes: 'アカウントノード',
    messages: '1日あたりメッセージ',
    uptime: 'セッション稼働率',
    crypto: '暗号通貨ネイティブ決済',
    compliance: 'コンプライアンス対応',
  },
  features: {
    eyebrow: '機能',
    title: '産業規模の Telegram 運用のために。',
    subtitle: 'TData フォルダを自律収益エンジンへ変える 6 つのプリミティブ。',
    cards: {
      tdata: [
        'TData / セッションの大規模オーケストレーション',
        'TData を読み込むだけ。10,000 以上のセッションを隔離ワーカー間でローテーション・ウォームアップ・シャーディングし、運用は完全自動。',
      ],
      ip: [
        'ノードごとの住宅 IP 隔離',
        'スティッキーな住宅プロキシ、国別固定、再利用なし。1 つ焼かれても他は無事。',
      ],
      rag: [
        'RAG 知識ベース + AI ペルソナエンジン',
        '製品ドキュメント、会話記録、FAQ を投入。ペルソナエンジンが正しい声色で正しい答えを引用 — 40 以上の言語に対応。',
      ],
      takeover: [
        'リード引き継ぎ',
        'ホットリードを会話の途中で人間営業へ。コピペ不要、文脈ロスなし。',
      ],
      funnel: [
        'コンバージョンファネル',
        'コールドリーチから成約までの段階を可視化。離脱は Slack に即通知。',
      ],
      monitor: [
        'リアルタイム リスク & ヘルス モニタ',
        'セッション別レピュテーション、FloodWait カーブ、BAN 予測。問題が広がる前に察知。',
      ],
    },
  },
  workflow: {
    eyebrow: 'ワークフロー',
    titleA: 'コールドリードから成約まで —',
    titleB: 'ひとつの自律ループ。',
    steps: [
      { label: 'ステップ 01', title: 'リード収集', body: 'ソースをスクレイプし、重複排除、スコアリング。統合プールへ流し込み。' },
      { label: 'ステップ 02', title: 'AI アウトリーチ', body: '数秒でパーソナライズされた初回接触 — あなたの RAG 知識を背景に。' },
      { label: 'ステップ 03', title: '商談引き継ぎ', body: 'ホットリード → 人間営業へ。会話の文脈をすべて引き継いで。' },
    ],
  },
  pricing: {
    eyebrow: '料金',
    title: 'シンプル、アカウント単位の料金。',
    subtitle: 'USDT・USDC・カードで決済。年払いで 20% 割引。メッセージ単価は永遠にゼロ。',
    plans: [
      {
        blurb: '新市場を検証する個人オペレーター向け。',
        features: ['アカウント 50 まで', 'RAG 知識ベース 1', 'AI ペルソナエンジン', 'メールサポート'],
        cta: 'Starter で始める',
      },
      {
        blurb: '本格的なコンバージョンパイプラインを動かすチーム向け。',
        features: ['アカウント 200 まで', 'RAG 知識ベース 5', 'リード引き継ぎ', '優先ルーティング', 'Slack 通知'],
        cta: 'Growth で始める',
      },
      {
        blurb: '千アカウント規模のマトリクス運用者向け。',
        features: ['アカウント 1,000 まで', '知識ベース 無制限', '専任カスタマーサクセスエンジニア', '99.99% SLA', 'SSO と監査ログ'],
        cta: 'セールスに問い合わせる',
      },
    ],
    badges: { crypto: 'USDT · USDC · BTC', wallet: 'セルフカストディウォレット', card: 'カード（Stripe 対応）' },
  },
  useCases: {
    eyebrow: 'ユースケース',
    title: 'Telegram 規模で動くチームのために。',
    cards: [
      { title: '暗号 / Web3 GTM', body: 'DEX ローンチ、IDO エアドロップ、バリデーター紹介 — すべてのキャンペーンが流暢、ブランドに沿い、監査可能。' },
      { title: 'フィンテック / FX アウトバウンド', body: '規制対象プロダクトのコンプライアントなファーストタッチ。パーソナライズされていてもスパムではなく、監査ログは自動取得。' },
      { title: 'アフィリエイト / トラフィックネットワーク', body: 'サブアフィリエイト艦隊を、ソース別の可視性を失わずに編成。クリプト支払い、秒単位で精算。' },
    ],
  },
  integrations: {
    eyebrow: '統合',
    title: 'あなたが既に運用しているスタックに繋がる。',
    subtitle: 'メッセージング、決済、観測、CRM へのネイティブ統合。リストにない？Webhook が補完します。',
    items: ['Telegram MTProto', 'Slack', 'Discord', 'USDT (TRC20)', 'USDC', 'Bitcoin', 'Stripe', 'Webhooks', 'Notion', 'Linear', 'Datadog', 'Zapier'],
  },
  security: {
    eyebrow: 'セキュリティ / コンプライアンス',
    title: 'エンタープライズ級。初日から。',
    subtitle: 'あなたの TData は HSM キーのように扱います。実際そのようなものなので。',
    items: [
      { title: '保存時暗号化', body: 'セッション、シークレット、TData ブロブはすべて AES-256。テナント単位の鍵導出、顧客間で再利用しません。' },
      { title: '完全な監査ログ', body: 'すべての操作にアクター、IP、タイムスタンプを記録。SOC 2 と内部レビュー向けにエクスポート可能。' },
      { title: 'SSO / SAML 対応', body: 'IdP をお持ち込みください — Okta、Azure AD、Google Workspace。SAML 2.0 は Growth 以上で利用可能。' },
      { title: 'セルフカストディウォレット', body: '暗号通貨決済は直接あなたのウォレットへ。我々は顧客資金を保管しません。' },
    ],
    badges: 'SOC 2 Type I — 進行中 · GDPR · ISO 27001 — ロードマップ',
  },
  faq: {
    eyebrow: 'FAQ',
    title: 'よくある質問。',
    items: [
      { q: 'アカウントや TData は提供されますか？', a: 'いいえ。お客様が TData を持ち込み、我々がオーケストレーションします。大半のエンタープライズ顧客は法務審査済みのサプライヤーから TData を調達します。' },
      { q: 'アカウントが制限されたらどうなりますか？', a: 'リアルタイムモニターがセッション単位で FloodWait と BAN リスクを検出し、該当アカウントを隔離、アラート（Slack / Webhook）を発火します。残りの艦隊は通常運用を継続します。' },
      { q: 'AI は本当に人間のように話せますか？', a: 'ペルソナエンジンはあなたの知識ベースとトーンキャリブレーションを基盤にしています。40 以上の言語に対応。盲検 A/B テストで大半の顧客は自分の AI 返信を見分けられません。' },
      { q: 'リード引き継ぎはどう動きますか？', a: 'リードが「ホット」閾値（意図スコア、キーワード一致、手動フラグ）を超えると、会話スレッドが人間営業のポータルへミラーリング — 完全な文脈付き、コピー＆ペースト不要。' },
      { q: 'メッセージング自体はコンプライアントですか？', a: '我々のインフラは Telegram の公開レート制限と ToS に従います。各国の広告関連法（CAN-SPAM、GDPR 等）の遵守はお客様の責任ですが、必要な制御は提供します。' },
      { q: 'どの通貨を受け付けますか？', a: 'USDT（TRC20/ERC20）、USDC、BTC、および Stripe 経由の主要法定通貨。年間契約はいずれでも決済可能。' },
      { q: 'セルフホストできますか？', a: 'Scale プランで可能です。Docker イメージ、Terraform モジュール、ランブックを提供。単一 EC2 インスタンスへの平均デプロイは 2 時間以内。' },
      { q: 'どのくらいで立ち上げられますか？', a: 'MVP オンボーディングは 24 時間以内：TData を持ち込み、業界ドキュメントを貼り付け、ペルソナを選択。最初のキャンペーンを我々が伴走します。' },
    ],
  },
  finalCta: {
    title: 'Telegram BAN の火消しはもうやめよう。',
    titleAccent: '売上を出荷しよう。',
    body: 'クリック 2 回で稼働するパイロットへ — あなたが TData を持ち込めば、あとは我々が引き継ぎます。',
    primary: 'コンソールを開く',
    secondary: 'エンジニアに相談する',
  },
  footer: {
    tagline: '法人向け Telegram 自動化 OS。スケールするオペレーターのために。',
    sections: [
      { title: 'プロダクト', items: ['機能', '料金', '更新履歴', '稼働状況'] },
      { title: 'リソース', items: ['ドキュメント', 'API リファレンス', 'ガイド', '導入事例'] },
      { title: '会社', items: ['会社情報', '採用', 'お問い合わせ', '法務'] },
    ],
    copyright: '© 2026 KLTGSC. All rights reserved.',
    builtFor: 'スケールするオペレーターのために。',
  },
};

const ko: Dict = {
  nav: { product: '제품', pricing: '가격', docs: '문서', customers: '고객사', changelog: '업데이트' },
  cta: { signIn: '로그인', launchConsole: '콘솔 열기', viewDocs: '문서 보기', mostPopular: '가장 인기' },
  hero: {
    badge: '새 소식 · Epic 6 — 운영 대시보드',
    titleA: 'Telegram 그로스,',
    titleB: '산업화하다.',
    subtitle:
      'KLTGSC는 엔터프라이즈 Telegram 자동화 OS입니다. 수천 개의 계정, AI 대화, 영업 인계까지 하나의 콘솔에서 통합 운영합니다.',
  },
  trust: {
    nodes: '계정 노드',
    messages: '일일 메시지',
    uptime: '세션 가동률',
    crypto: '암호화폐 네이티브 결제',
    compliance: '컴플라이언스 준비',
  },
  features: {
    eyebrow: '기능',
    title: '산업 규모 Telegram 운영을 위해 설계.',
    subtitle: 'TData 폴더를 자율 수익 엔진으로 바꾸는 6가지 핵심 모듈.',
    cards: {
      tdata: [
        '대규모 TData / 세션 오케스트레이션',
        'TData만 가져오세요. 10,000개 이상 세션을 격리 워커 간에 회전, 워밍업, 샤딩 — 감독 없이 자동으로.',
      ],
      ip: [
        '노드별 가정용 IP 격리',
        '스티키 주거용 출구, 국가 고정, 재사용 없음. 하나 차단되어도 나머지는 그대로 깨끗.',
      ],
      rag: [
        'RAG 지식 베이스 + AI 페르소나 엔진',
        '제품 문서, 대화 로그, FAQ를 넣으세요. 페르소나 엔진이 올바른 어조로 올바른 답을 — 40개 이상 언어로.',
      ],
      takeover: [
        '리드 인계',
        '대화 중 핫리드를 즉시 사람 영업에게 인계. 복사 붙여넣기도, 컨텍스트 손실도 없습니다.',
      ],
      funnel: [
        '전환 퍼널',
        '콜드 아웃리치부터 매출까지 단계별 시각화. 이탈은 Slack으로 즉시 알림.',
      ],
      monitor: [
        '실시간 리스크 & 헬스 모니터',
        '세션별 평판, FloodWait 곡선, 차단 예측 — 문제가 퍼지기 전에 발견.',
      ],
    },
  },
  workflow: {
    eyebrow: '워크플로',
    titleA: '콜드 리드에서 성사까지 —',
    titleB: '하나의 자율 루프.',
    steps: [
      { label: '단계 01', title: '리드 수집', body: '소스 스크래핑, 중복 제거, 점수 매기기. 통합 풀로 스트리밍.' },
      { label: '단계 02', title: 'AI 아웃리치', body: '초 단위 개인화 첫 접촉 — 당신의 RAG 지식이 받쳐줍니다.' },
      { label: '단계 03', title: '영업 인계', body: '핫리드 → 사람 영업, 대화 컨텍스트까지 완전 인계.' },
    ],
  },
  pricing: {
    eyebrow: '가격',
    title: '심플한 계정 단위 가격.',
    subtitle: 'USDT, USDC 또는 카드 결제. 연간 결제 시 20% 할인. 메시지당 요금은 영원히 없음.',
    plans: [
      {
        blurb: '새 시장을 검증하는 1인 운영자용.',
        features: ['계정 최대 50', 'RAG 지식 베이스 1', 'AI 페르소나 엔진', '이메일 지원'],
        cta: 'Starter 시작',
      },
      {
        blurb: '실제 전환 파이프라인을 운영하는 팀용.',
        features: ['계정 최대 200', 'RAG 지식 베이스 5', '리드 인계', '우선 라우팅', 'Slack 알림'],
        cta: 'Growth 시작',
      },
      {
        blurb: '수천 계정 매트릭스 운영자용.',
        features: ['계정 최대 1,000', '무제한 지식 베이스', '전담 성공 엔지니어', '99.99% SLA', 'SSO 및 감사 로그'],
        cta: '영업팀 문의',
      },
    ],
    badges: { crypto: 'USDT · USDC · BTC', wallet: '셀프 커스터디 지갑', card: '카드 (Stripe 지원)' },
  },
  useCases: {
    eyebrow: '사용 사례',
    title: 'Telegram 규모로 출시하는 팀을 위해.',
    cards: [
      { title: '암호화폐 / Web3 GTM', body: 'DEX 출시, IDO 에어드롭, 밸리데이터 추천 — 모든 캠페인이 유창하고, 브랜드에 부합하며, 감사 가능합니다.' },
      { title: '핀테크 / 외환 아웃바운드', body: '규제 대상 제품의 컴플라이언트 첫 접촉. 개인화되어 있되 스팸이 아니며 감사 추적은 자동 생성.' },
      { title: '어필리에이트 / 트래픽 네트워크', body: '소스별 가시성을 잃지 않고 서브 어필리에이트 함대를 운영. 암호화폐로 지급, 초 단위 정산.' },
    ],
  },
  integrations: {
    eyebrow: '통합',
    title: '이미 운영 중인 스택에 연결합니다.',
    subtitle: '메시징, 결제, 옵저버빌리티, CRM 네이티브 통합. 목록에 없으면 Webhook 으로 처리.',
    items: ['Telegram MTProto', 'Slack', 'Discord', 'USDT (TRC20)', 'USDC', 'Bitcoin', 'Stripe', 'Webhooks', 'Notion', 'Linear', 'Datadog', 'Zapier'],
  },
  security: {
    eyebrow: '보안 / 컴플라이언스',
    title: '엔터프라이즈급. 첫날부터.',
    subtitle: '우리는 당신의 TData를 HSM 키처럼 다룹니다. 사실 거의 그런 셈이니까요.',
    items: [
      { title: '저장 시 암호화', body: '세션, 시크릿, TData 블롭 모두 AES-256. 테넌트별 키 파생, 고객 간 재사용 없음.' },
      { title: '전체 감사 로그', body: '모든 작업에 액터, IP, 타임스탬프 기록. SOC 2 와 내부 검토용으로 내보낼 수 있음.' },
      { title: 'SSO / SAML 지원', body: '자체 IdP — Okta, Azure AD, Google Workspace. SAML 2.0 은 Growth 이상.' },
      { title: '셀프 커스터디 지갑', body: '암호화폐 결제는 직접 당신의 지갑으로 정산. 우리는 고객 자금을 보유하지 않습니다.' },
    ],
    badges: 'SOC 2 Type I — 진행 중 · GDPR · ISO 27001 — 로드맵',
  },
  faq: {
    eyebrow: 'FAQ',
    title: '자주 묻는 질문.',
    items: [
      { q: '계정이나 TData를 제공하나요?', a: '아니요. 고객이 TData를 가져오고 우리는 오케스트레이션합니다. 대부분의 엔터프라이즈 고객은 법무 검토를 거친 공급업체에서 TData를 조달합니다.' },
      { q: '계정이 제한되면 어떻게 되나요?', a: '실시간 모니터가 세션별로 FloodWait 와 차단 위험을 감지하고, 해당 계정을 격리하며, 알림(Slack / Webhook)을 발화합니다. 나머지 함대는 정상 운영.' },
      { q: 'AI가 정말 사람처럼 말할 수 있나요?', a: '페르소나 엔진은 당신의 지식 베이스와 톤 캘리브레이션을 기반으로 합니다. 40개 이상 언어 지원. 블라인드 A/B 테스트에서 대부분의 고객은 자신의 AI 답변을 구별하지 못합니다.' },
      { q: '리드 인계는 어떻게 작동하나요?', a: '리드가 핫 임계값(의도 점수, 키워드 일치, 수동 플래그)을 넘으면 대화 스레드가 사람 영업 포털로 미러링됩니다 — 완전한 컨텍스트, 복사 붙여넣기 없이.' },
      { q: '메시징 자체가 컴플라이언트한가요?', a: '우리의 인프라는 Telegram 의 공개 속도 제한과 ToS 를 따릅니다. 현지 마케팅 법(CAN-SPAM, GDPR 등) 준수는 고객 책임이지만, 필요한 제어 장치를 제공합니다.' },
      { q: '어떤 통화를 받나요?', a: 'USDT(TRC20/ERC20), USDC, BTC 그리고 Stripe 를 통한 주요 법정 통화. 연간 계약은 어느 쪽으로든 정산 가능.' },
      { q: '자체 호스팅이 가능한가요?', a: 'Scale 고객은 가능합니다. Docker 이미지, Terraform 모듈, 런북을 제공. 단일 EC2 인스턴스 평균 배포 시간은 2시간 이하.' },
      { q: '얼마나 빨리 시작할 수 있나요?', a: 'MVP 온보딩은 24시간 이내: TData 가져오기, 업계 문서 붙여넣기, 페르소나 선택. 첫 캠페인은 함께 진행합니다.' },
    ],
  },
  finalCta: {
    title: 'Telegram 차단 진화에 시간을 쓰지 마세요.',
    titleAccent: '매출을 출하하세요.',
    body: '두 번의 클릭으로 작동하는 파일럿 — TData만 가져오시면 나머지는 우리가 맡습니다.',
    primary: '콘솔 열기',
    secondary: '엔지니어와 이야기',
  },
  footer: {
    tagline: '엔터프라이즈 Telegram 자동화 OS. 스케일하는 운영자를 위해.',
    sections: [
      { title: '제품', items: ['기능', '가격', '업데이트', '서비스 상태'] },
      { title: '리소스', items: ['문서', 'API 레퍼런스', '가이드', '고객사'] },
      { title: '회사', items: ['소개', '채용', '문의', '법률'] },
    ],
    copyright: '© 2026 KLTGSC. 모든 권리 보유.',
    builtFor: '스케일하는 운영자를 위해.',
  },
};

const es: Dict = {
  nav: { product: 'Producto', pricing: 'Precios', docs: 'Docs', customers: 'Clientes', changelog: 'Novedades' },
  cta: { signIn: 'Iniciar sesión', launchConsole: 'Abrir consola', viewDocs: 'Ver documentación', mostPopular: 'Más popular' },
  hero: {
    badge: 'Novedad · Epic 6 — Panel de operador',
    titleA: 'Crecimiento en Telegram,',
    titleB: 'industrializado.',
    subtitle:
      'KLTGSC es el sistema operativo empresarial de automatización de Telegram. Orquesta miles de cuentas, conversaciones con IA y traspasos de venta — desde una sola consola.',
  },
  trust: {
    nodes: 'Cuentas activas',
    messages: 'Mensajes / día',
    uptime: 'Disponibilidad de sesión',
    crypto: 'Pagos cripto nativos',
    compliance: 'Listo para cumplimiento',
  },
  features: {
    eyebrow: 'Funcionalidades',
    title: 'Diseñado para operaciones de Telegram a escala industrial.',
    subtitle: 'Seis primitivas que convierten una carpeta de TData en un motor de ingresos autónomo.',
    cards: {
      tdata: [
        'Orquestación de TData / sesiones a escala',
        'Trae tu propio TData. Nosotros rotamos, calentamos y dividimos más de 10 000 sesiones entre workers aislados — sin supervisión.',
      ],
      ip: [
        'Aislamiento de IP residencial por nodo',
        'Salidas residenciales fijas, ancladas por país, nunca reutilizadas. Si una se quema, el resto sigue limpio.',
      ],
      rag: [
        'Base de conocimiento RAG + motor de persona IA',
        'Carga tu documentación, transcripciones y FAQ. El motor de persona cita la respuesta correcta con el tono correcto — en más de 40 idiomas.',
      ],
      takeover: [
        'Traspaso de leads',
        'Pasa leads calientes a un vendedor humano en mitad de la conversación. Sin copiar y pegar, sin perder contexto.',
      ],
      funnel: [
        'Embudo de conversión',
        'Seguimiento visual de cada etapa, desde el alcance frío hasta los ingresos. Las fugas disparan alertas a Slack.',
      ],
      monitor: [
        'Monitor de riesgo y salud en tiempo real',
        'Reputación por sesión, curvas de FloodWait, predicción de baneo. Detecta problemas antes de que se propaguen.',
      ],
    },
  },
  workflow: {
    eyebrow: 'Flujo de trabajo',
    titleA: 'Del lead frío al cierre —',
    titleB: 'un solo bucle autónomo.',
    steps: [
      { label: 'Paso 01', title: 'Captura de leads', body: 'Scraping de fuentes, deduplicación y puntuación. Todo entra en un pool unificado.' },
      { label: 'Paso 02', title: 'Alcance con IA', body: 'Primer contacto personalizado en segundos — respaldado por tu RAG.' },
      { label: 'Paso 03', title: 'Traspaso a venta', body: 'Lead caliente → vendedor humano, con todo el contexto de la conversación.' },
    ],
  },
  pricing: {
    eyebrow: 'Precios',
    title: 'Precios simples, por cuenta.',
    subtitle: 'Paga con USDT, USDC o tarjeta. Anual ahorra 20%. Nunca cobramos por mensaje.',
    plans: [
      {
        blurb: 'Para operadores en solitario validando un nuevo mercado.',
        features: ['Hasta 50 cuentas', '1 base de conocimiento RAG', 'Motor de persona IA', 'Soporte por email'],
        cta: 'Empezar con Starter',
      },
      {
        blurb: 'Para equipos con pipelines reales de conversión.',
        features: ['Hasta 200 cuentas', '5 bases de conocimiento RAG', 'Traspaso de leads', 'Enrutamiento prioritario', 'Alertas en Slack'],
        cta: 'Empezar con Growth',
      },
      {
        blurb: 'Para operadores de flotas de mil cuentas.',
        features: ['Hasta 1 000 cuentas', 'Bases de conocimiento ilimitadas', 'Ingeniero de éxito dedicado', 'SLA 99,99%', 'SSO y registros de auditoría'],
        cta: 'Habla con ventas',
      },
    ],
    badges: { crypto: 'USDT · USDC · BTC', wallet: 'Wallet auto-custodia', card: 'Tarjeta (Stripe-ready)' },
  },
  useCases: {
    eyebrow: 'Casos de uso',
    title: 'Diseñado para los equipos que envían a escala Telegram.',
    cards: [
      { title: 'GTM cripto / Web3', body: 'Lanzamientos DEX, airdrops de IDO, referidos de validadores — fluido, alineado con la marca y auditable en cada campaña.' },
      { title: 'Fintech / forex outbound', body: 'Primeros contactos compliant para productos regulados. Personalizado, nunca spam, con rastro de auditoría automático.' },
      { title: 'Afiliación / redes de tráfico', body: 'Orquesta flotas de sub-afiliados sin perder visibilidad por fuente. Paga en cripto, liquida en segundos.' },
    ],
  },
  integrations: {
    eyebrow: 'Integraciones',
    title: 'Se conecta al stack que ya tienes.',
    subtitle: 'Integraciones nativas para mensajería, pagos, observabilidad y CRM. ¿No está en la lista? Webhook al rescate.',
    items: ['Telegram MTProto', 'Slack', 'Discord', 'USDT (TRC20)', 'USDC', 'Bitcoin', 'Stripe', 'Webhooks', 'Notion', 'Linear', 'Datadog', 'Zapier'],
  },
  security: {
    eyebrow: 'Seguridad y cumplimiento',
    title: 'Nivel empresarial. Desde el primer día.',
    subtitle: 'Tratamos tu TData como una clave de HSM. Porque básicamente lo es.',
    items: [
      { title: 'Cifrado en reposo', body: 'AES-256 para sesiones, secretos y blobs de TData. Derivación de clave por inquilino, nunca reutilizada entre clientes.' },
      { title: 'Registro de auditoría completo', body: 'Cada acción queda registrada con actor, IP y marca temporal. Exportable para SOC 2 y revisión interna.' },
      { title: 'SSO / SAML listo', body: 'Trae tu IdP — Okta, Azure AD, Google Workspace. SAML 2.0 desde Growth en adelante.' },
      { title: 'Wallet auto-custodia', body: 'Los pagos cripto se liquidan directamente a tu wallet. Nunca custodiamos fondos del cliente.' },
    ],
    badges: 'SOC 2 Type I — en progreso · GDPR · ISO 27001 — roadmap',
  },
  faq: {
    eyebrow: 'FAQ',
    title: 'Preguntas frecuentes.',
    items: [
      { q: '¿Proveéis cuentas o TData?', a: 'No. El cliente trae su TData; nosotros orquestamos. La mayoría de los clientes enterprise obtienen TData de proveedores ya validados bajo su propio escrutinio legal.' },
      { q: '¿Qué pasa cuando una cuenta es restringida?', a: 'Nuestro monitor en tiempo real detecta FloodWait y riesgo de baneo por sesión, aísla la cuenta afectada y dispara tu alerta (Slack / webhook). El resto de la flota sigue corriendo.' },
      { q: '¿La IA puede sonar humana?', a: 'El motor de persona se apoya en tu base de conocimiento y un paso de calibración de tono. Más de 40 idiomas. En tests A/B ciegos, la mayoría de clientes no distingue sus propias respuestas de IA.' },
      { q: '¿Cómo funciona el traspaso de leads?', a: 'Cuando un lead cruza un umbral caliente (puntuación de intención, palabra clave o etiqueta manual) la conversación se refleja en el portal del vendedor humano — con contexto completo, sin copiar y pegar.' },
      { q: '¿La mensajería subyacente es compliant?', a: 'Nuestra infraestructura sigue los límites publicados y los ToS de Telegram. El cumplimiento de la ley local de marketing (CAN-SPAM, GDPR, etc.) es tu responsabilidad — exponemos los controles necesarios.' },
      { q: '¿Qué monedas aceptáis?', a: 'USDT (TRC20/ERC20), USDC, BTC y las principales fiat vía Stripe. Los contratos anuales se liquidan en cualquiera.' },
      { q: '¿Puedo auto-hospedarlo?', a: 'Sí, para clientes Scale. Entregamos imágenes Docker, módulos Terraform y un runbook. El despliegue medio es bajo dos horas en una sola EC2.' },
      { q: '¿Cuánto tarda empezar?', a: 'Onboarding MVP en menos de 24 horas: trae TData, pega tu documentación de industria, elige una persona. Te acompañamos en la primera campaña.' },
    ],
  },
  finalCta: {
    title: 'Deja de apagar incendios con baneos de Telegram.',
    titleAccent: 'Empieza a enviar ingresos.',
    body: 'Dos clics para un piloto funcionando — trae tu TData, nosotros nos encargamos del resto.',
    primary: 'Abrir consola',
    secondary: 'Hablar con un ingeniero',
  },
  footer: {
    tagline: 'El SO empresarial de automatización de Telegram. Hecho para operadores que escalan.',
    sections: [
      { title: 'Producto', items: ['Funciones', 'Precios', 'Novedades', 'Estado'] },
      { title: 'Recursos', items: ['Docs', 'Referencia API', 'Guías', 'Clientes'] },
      { title: 'Empresa', items: ['Nosotros', 'Empleo', 'Contacto', 'Legal'] },
    ],
    copyright: '© 2026 KLTGSC. Todos los derechos reservados.',
    builtFor: 'Hecho para operadores que escalan.',
  },
};

export const DICTS: Record<Lang, Dict> = { en, 'zh-CN': zhCN, ja, ko, es };

const STORAGE_KEY = 'kltgsc.lang';

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
