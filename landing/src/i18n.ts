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
    liveBadge: string;         // "1,247 AI monitor rules running right now"
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
    tableAdminNote: string;     // "Admin can override any line per-customer for volume deals. See billing docs."
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
    liveBadge: '1,247 AI monitor rules running right now',
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
    tableAdminNote: 'Admin can override any line per-customer for volume deals. See billing docs.',
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
    liveBadge: '此刻有 1,247 条 AI 监听规则正在运行',
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
    tableAdminNote: '大客户可向 admin 申请单价覆盖，详见 billing 文档。',
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
    liveBadge: '現在 1,247 件の AI モニターが稼働中',
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
    tableAdminNote: '大口取引は管理者が顧客ごとに単価を上書きできます。billing ドキュメントを参照。',
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
    liveBadge: '지금 1,247개의 AI 모니터가 가동 중',
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
    tableAdminNote: '대량 거래는 관리자가 고객별로 단가를 재정의할 수 있습니다. billing 문서 참조.',
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
    liveBadge: '1,247 reglas de monitor IA activas ahora mismo',
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
    tableAdminNote: 'Para grandes volúmenes, el admin puede sobrescribir cualquier línea por cliente. Ver docs de billing.',
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
