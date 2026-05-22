/**
 * Canonical outbound URLs for the landing site.
 *
 * Anything that goes off-domain (Telegram, GitHub) or off-route (the
 * portal at /portal, the sales-of-record email box) lives here so we
 * can swap them in one place when ops changes a handle / email.
 *
 * Do NOT hardcode these in section files — always import from here.
 */
export const LINKS = {
  // Console — same-origin, picks up unified login flow
  signIn:        '/login',
  signUp:        '/portal/register?ref=landing&trial=20',
  trial:         '/portal/register?ref=landing&trial=20',

  // Sales outreach
  telegramSales: 'https://t.me/tg1ai_sales',
  salesEmail:    'mailto:sales@tg1.ai',

  // Product subroutes (same-origin)
  docs:          '/docs',
  docsQuickstart:'/docs/quickstart',
  docsModules:   '/docs/modules',
  docsApi:       '/docs/api',
  docsBilling:   '/docs/billing',
  changelog:     '/changelog',
  privacy:       '/legal/privacy',
  tos:           '/legal/tos',

  // Social / company
  github:        'https://github.com/astercc518/kltgsc',
  twitter:       'https://x.com/tg1ai',

  // Demo
  demoVideo:     '#demo-video', // anchor — actual mp4 lands in PR4
} as const;
