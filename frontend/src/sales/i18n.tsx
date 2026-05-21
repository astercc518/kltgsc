/**
 * Lightweight i18n for the sales workbench.
 *
 * No external dep. Two locales (en + zh-CN). Stored in localStorage so the
 * choice persists across reloads. To add a string, put both translations in
 * STRINGS, then call useT() in a component:
 *
 *   const t = useT();
 *   <Button>{t('inbox.refresh')}</Button>
 *
 * Falls back to the English value when a key is missing in zh-CN.
 */
import React, {
  createContext, useCallback, useContext, useEffect, useMemo, useState,
  type ReactNode,
} from 'react';

export type Lang = 'en' | 'zh-CN';
const STORAGE_KEY = 'tg1_sales_lang';
const DEFAULT_LANG: Lang = 'zh-CN';

// All translatable strings live here. Keys are dot-paths grouped by page.
// English value is the source of truth — missing zh-CN entries fall back.
const STRINGS: Record<Lang, Record<string, string>> = {
  'en': {
    // Layout / common
    'app.brand': 'TG1.AI · Sales',
    'app.platform': 'PLATFORM',
    'app.tenant': 'TENANT',
    'nav.inbox': 'Lead Inbox',
    'nav.wallet': 'My Wallet',
    'nav.settings': 'Settings',
    'common.logout': 'Logout',
    'common.refresh': 'Refresh',
    'common.back': 'Back',
    'common.copy': 'Copy',
    'common.copied': 'Copied',
    'common.cancel': 'Cancel',
    'common.confirm': 'Confirm',

    // Inbox
    'inbox.title': 'Lead Inbox',
    'inbox.subtitle': 'Click View to unlock contact info — $0.50 per lead per day. Same-day re-opens are free.',
    'inbox.balance': 'Balance',
    'inbox.stat.total': 'Total',
    'inbox.stat.viewedToday': 'Viewed Today',
    'inbox.stat.replied': 'Replied/Interested',
    'inbox.stat.industries': 'Industries',
    'inbox.filter.industry': 'Industry',
    'inbox.filter.status': 'Status',
    'inbox.filter.search': 'Search masked hints',
    'inbox.empty': 'No leads in your scope',
    'inbox.col.lead': 'Lead',
    'inbox.col.industry': 'Industry',
    'inbox.col.source': 'Source',
    'inbox.col.status': 'Status',
    'inbox.col.views': 'Views',
    'inbox.col.last': 'Last',
    'inbox.action.view': 'View ($0.50)',
    'inbox.action.openFree': 'Open (free)',
    'inbox.phone': 'phone',
    'inbox.lead': 'lead',

    // Lead detail
    'detail.charging': 'Charging wallet and unlocking lead...',
    'detail.insufficientTitle': 'Insufficient balance',
    'detail.insufficientHint': 'Top up your wallet to view this lead.',
    'detail.topupBtn': 'Topup wallet',
    'detail.freeReopen': 'Free re-open',
    'detail.freeReopenDesc': "You've already paid to view this lead today. Balance",
    'detail.chargedTitle': 'Charged',
    'detail.chargedDesc': 'Remaining balance',
    'detail.freeRest': 'This lead is free to re-open today.',
    'detail.viewed': 'viewed',
    'detail.tgId': 'Telegram ID',
    'detail.username': 'Username',
    'detail.phone': 'Phone',
    'detail.tags': 'Tags',
    'detail.notes': 'Notes',
    'detail.noNotes': 'none',
    'detail.bulkBatch': 'Bulk batch',
    'detail.accountId': 'Account ID',
    'detail.created': 'Created',
    'detail.lastInteraction': 'Last interaction',
    'detail.dmHint': 'To message this lead',
    'detail.dmDesc': 'Use the TG account linked to this lead and DM',
    'detail.dmComing': 'Direct in-app messaging is coming in a follow-up.',
    'detail.interactions': 'Recent interactions',
    'detail.them': 'They',
    'detail.us': 'Us',

    // Wallet
    'wallet.title': 'My Wallet',
    'wallet.subtitle': 'Lead views are billed from this wallet (default $0.50/view, $0 for same-day re-views).',
    'wallet.topup': 'Topup',
    'wallet.platformTitle': 'Platform sales wallet',
    'wallet.platformDesc': "Self-topup isn't enabled for platform sales accounts. Ask an admin to credit your viewing budget.",
    'wallet.currentBalance': 'Current balance',
    'wallet.totalCredited': 'Total credited',
    'wallet.totalSpent': 'Total spent',
    'wallet.balance': 'Balance',
    'wallet.txTable': 'Transactions',
    'wallet.txEmpty': 'No transactions yet',
    'wallet.col.type': 'Type',
    'wallet.col.amount': 'Amount',
    'wallet.col.balanceAfter': 'Balance after',
    'wallet.col.desc': 'Description',
    'wallet.col.lead': 'Lead',
    'wallet.col.when': 'When',
    'wallet.modal.title': 'Topup sales wallet',
    'wallet.modal.amount': 'Amount (USD)',
    'wallet.modal.network': 'USDT network',
    'wallet.modal.create': 'Create invoice',
    'wallet.modal.invoiceCreated': 'Invoice #',
    'wallet.modal.invoiceCreated2': ' created',
    'wallet.modal.sendUsdt': 'Send',
    'wallet.modal.on': 'on',
    'wallet.modal.to': 'to:',
    'wallet.modal.bonus': 'bonus on confirmation',
    'wallet.invoiceSuccess': 'Invoice created — send USDT to complete topup',
    'wallet.topupFailed': 'Topup failed',

    // Settings
    'settings.title': 'Settings',
    'settings.subtitle': 'Your identity and preferences.',
    'settings.account': 'Account',
    'settings.email': 'Email',
    'settings.kind': 'Kind',
    'settings.kindPlatform': 'Platform sales',
    'settings.kindTenant': 'Tenant sub-user',
    'settings.tenantId': 'Tenant customer ID',
    'settings.industryFilter': 'Industry filter',
    'settings.industryFilterDesc': 'The lead list auto-filters to your assigned industries. Ask your customer admin (or platform admin) to update this list — coming soon as a self-serve field.',

    // Misc / actions
    'action.cancel': 'Cancel',
    'action.cancelDone': 'Canceled',
    'action.cancelFailed': 'Cancel failed',
  },
  'zh-CN': {
    'app.brand': 'TG1.AI · 销售',
    'app.platform': '平台',
    'app.tenant': '租户',
    'nav.inbox': '线索收件箱',
    'nav.wallet': '我的钱包',
    'nav.settings': '设置',
    'common.logout': '退出',
    'common.refresh': '刷新',
    'common.back': '返回',
    'common.copy': '复制',
    'common.copied': '已复制',
    'common.cancel': '取消',
    'common.confirm': '确定',

    'inbox.title': '线索收件箱',
    'inbox.subtitle': '点击「查看」解锁联系方式 — 每条线索 $0.50 / 每日。同日重复打开免费。',
    'inbox.balance': '余额',
    'inbox.stat.total': '总数',
    'inbox.stat.viewedToday': '今日已查看',
    'inbox.stat.replied': '已回复/有意向',
    'inbox.stat.industries': '业务分类',
    'inbox.filter.industry': '业务',
    'inbox.filter.status': '状态',
    'inbox.filter.search': '搜索线索',
    'inbox.empty': '没有匹配的线索',
    'inbox.col.lead': '线索',
    'inbox.col.industry': '业务',
    'inbox.col.source': '来源',
    'inbox.col.status': '状态',
    'inbox.col.views': '查看次数',
    'inbox.col.last': '最近互动',
    'inbox.action.view': '查看 ($0.50)',
    'inbox.action.openFree': '打开（免费）',
    'inbox.phone': '电话',
    'inbox.lead': '线索',

    'detail.charging': '扣费中并加载线索…',
    'detail.insufficientTitle': '余额不足',
    'detail.insufficientHint': '请先给钱包充值后再查看该线索。',
    'detail.topupBtn': '充值',
    'detail.freeReopen': '今日免费重看',
    'detail.freeReopenDesc': '今日已支付查看此线索。当前余额',
    'detail.chargedTitle': '已扣费',
    'detail.chargedDesc': '剩余余额',
    'detail.freeRest': '今日可免费再次打开本线索。',
    'detail.viewed': '查看次数',
    'detail.tgId': 'Telegram ID',
    'detail.username': '用户名',
    'detail.phone': '电话',
    'detail.tags': '标签',
    'detail.notes': '备注',
    'detail.noNotes': '无',
    'detail.bulkBatch': '群发批次',
    'detail.accountId': '账号 ID',
    'detail.created': '创建时间',
    'detail.lastInteraction': '最近互动',
    'detail.dmHint': '联系该线索',
    'detail.dmDesc': '使用该线索关联的 TG 账号给以下用户发私信',
    'detail.dmComing': '平台内直接私信功能在后续版本上线。',
    'detail.interactions': '历史互动',
    'detail.them': '对方',
    'detail.us': '我方',

    'wallet.title': '我的钱包',
    'wallet.subtitle': '查看线索从此钱包扣费（默认 $0.50/次，同日复看免费）。',
    'wallet.topup': '充值',
    'wallet.platformTitle': '平台销售钱包',
    'wallet.platformDesc': '平台销售账号不支持自助充值。请联系管理员为你的查看预算充值。',
    'wallet.currentBalance': '当前余额',
    'wallet.totalCredited': '累计充值',
    'wallet.totalSpent': '累计消耗',
    'wallet.balance': '余额',
    'wallet.txTable': '流水明细',
    'wallet.txEmpty': '暂无流水',
    'wallet.col.type': '类型',
    'wallet.col.amount': '金额',
    'wallet.col.balanceAfter': '余额',
    'wallet.col.desc': '说明',
    'wallet.col.lead': '线索',
    'wallet.col.when': '时间',
    'wallet.modal.title': '充值销售钱包',
    'wallet.modal.amount': '金额（USD）',
    'wallet.modal.network': 'USDT 网络',
    'wallet.modal.create': '创建账单',
    'wallet.modal.invoiceCreated': '账单 #',
    'wallet.modal.invoiceCreated2': ' 已创建',
    'wallet.modal.sendUsdt': '请转账',
    'wallet.modal.on': '到',
    'wallet.modal.to': '：',
    'wallet.modal.bonus': '到账后追加赠送',
    'wallet.invoiceSuccess': '账单已创建 — 请按地址转账完成充值',
    'wallet.topupFailed': '充值失败',

    'settings.title': '设置',
    'settings.subtitle': '账号信息与偏好。',
    'settings.account': '账号信息',
    'settings.email': '邮箱',
    'settings.kind': '类型',
    'settings.kindPlatform': '平台销售',
    'settings.kindTenant': '租户员工',
    'settings.tenantId': '所属租户 ID',
    'settings.industryFilter': '业务分类过滤',
    'settings.industryFilterDesc': '线索列表会按你设定的业务分类自动过滤。如需修改，请联系所属客户管理员或平台管理员 — 自助配置后续版本上线。',

    'action.cancel': '取消',
    'action.cancelDone': '已取消',
    'action.cancelFailed': '取消失败',
  },
};

interface I18nCtxValue {
  lang: Lang;
  setLang: (l: Lang) => void;
  t: (key: string, fallback?: string) => string;
}

const Ctx = createContext<I18nCtxValue | null>(null);

function readInitialLang(): Lang {
  try {
    const stored = localStorage.getItem(STORAGE_KEY);
    if (stored === 'en' || stored === 'zh-CN') return stored;
  } catch {}
  // Fall back to browser language if Chinese, else English
  if (typeof navigator !== 'undefined') {
    const nav = (navigator.language || '').toLowerCase();
    if (nav.startsWith('zh')) return 'zh-CN';
    if (nav.startsWith('en')) return 'en';
  }
  return DEFAULT_LANG;
}

export const SalesI18nProvider: React.FC<{ children: ReactNode }> = ({ children }) => {
  const [lang, setLangState] = useState<Lang>(() => readInitialLang());

  const setLang = useCallback((l: Lang) => {
    setLangState(l);
    try { localStorage.setItem(STORAGE_KEY, l); } catch {}
  }, []);

  // Sync across tabs: when user flips lang in /sales tab A, tab B picks it up.
  useEffect(() => {
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY && (e.newValue === 'en' || e.newValue === 'zh-CN')) {
        setLangState(e.newValue);
      }
    };
    window.addEventListener('storage', onStorage);
    return () => window.removeEventListener('storage', onStorage);
  }, []);

  const t = useCallback((key: string, fallback?: string) => {
    return STRINGS[lang][key] ?? STRINGS['en'][key] ?? fallback ?? key;
  }, [lang]);

  const value = useMemo(() => ({ lang, setLang, t }), [lang, setLang, t]);
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
};

export function useT() {
  const ctx = useContext(Ctx);
  if (!ctx) {
    // Allow components outside the provider to fall through to English.
    return (key: string, fallback?: string) =>
      STRINGS['en'][key] ?? fallback ?? key;
  }
  return ctx.t;
}

export function useLang() {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useLang must be used inside <SalesI18nProvider>');
  return ctx;
}
