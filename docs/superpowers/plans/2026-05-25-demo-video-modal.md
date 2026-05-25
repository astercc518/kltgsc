# Demo Video Modal Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 替换落地页 hero 区"看 90 秒 Demo"按钮的死链锚点，改为弹出一个全屏 modal，自动播放一段 75 秒纯前端产品 UI 模拟动画（4 幕：监听 → 消息流入 → AI 评分 → 推送 Inbox + 销售接管）。一并修复两个独立 bug：登录按钮跨 SPA 跳转、Header 在深色 hero 上文字对比度不足。

**Architecture:** Modal 用 React Portal + framer-motion 入场。时间轴由自写的 `useTimeline` hook 驱动（基于 `requestAnimationFrame`，暴露 `elapsedMs`/`act`/`pause`/`resume`/`restart`）。子组件接收 elapsed，声明式决定渲染。Mock 数据与 i18n 分离。引入 vitest 仅为 hook 测试，UI 部分依赖手测 + 类型检查 + 构建。

**Tech Stack:** React 18, TypeScript 5.6, framer-motion 11, Tailwind 3.4, Vite 5。新增 devDeps：vitest, @testing-library/react, jsdom, @testing-library/jest-dom。

---

## 文件结构

**新增：**
- `landing/src/components/DemoVideoModal/index.tsx` — 顶层 modal，宿主时间轴
- `landing/src/components/DemoVideoModal/useTimeline.ts` — 时间轴 hook
- `landing/src/components/DemoVideoModal/useTimeline.test.ts` — hook 单元测试
- `landing/src/components/DemoVideoModal/demoScript.ts` — mock 时间戳与数据
- `landing/src/components/DemoVideoModal/parts/TopBar.tsx`
- `landing/src/components/DemoVideoModal/parts/BottomBar.tsx`
- `landing/src/components/DemoVideoModal/parts/LeftPane.tsx`
- `landing/src/components/DemoVideoModal/parts/RightPane.tsx`
- `landing/src/components/DemoVideoModal/parts/MessageBubble.tsx`
- `landing/src/components/DemoVideoModal/parts/ScoreCard.tsx`
- `landing/src/components/DemoVideoModal/parts/InboxItem.tsx`
- `landing/src/components/DemoVideoModal/parts/ReducedFallback.tsx`
- `landing/vitest.config.ts`
- `landing/src/test-setup.ts`

**修改：**
- `landing/src/sections/Header.tsx` — 登录改 `<a>`，未滚动时切浅色文字
- `landing/src/sections/HeroDual.tsx` — wire modal trigger + 状态
- `landing/src/lib/links.ts` — 删 `demoVideo`
- `landing/src/i18n.ts` — 新增 `demo` 命名空间（5 语言）
- `landing/package.json` — 新增 vitest 依赖与 test script

---

## Task 0a: 修复登录按钮跨 SPA 跳转

**Why:** 当前 `Header.tsx:65-70` 用 react-router 的 `<Link to="/login">`，是 SPA 内部客户端导航。landing SPA 的 `routes.tsx:44` 没有 `/login` 路由，被 `*` 兜底 `<Navigate to="/" replace />` 又跳回首页。`/login` 在 `nginx.conf:213` 走 `location /` proxy 到 frontend SPA，必须用原生 `<a href>` 触发整页加载。

**Files:**
- Modify: `landing/src/sections/Header.tsx:12,65-70,119-125`

- [ ] **Step 1: 删除 react-router Link 导入，登录改原生 `<a>`**

修改 `landing/src/sections/Header.tsx`：

```diff
-import { Link } from 'react-router-dom';
+import { Link } from 'react-router-dom';
```

保留 `Link`（品牌 logo 还在用），只把登录链接从 `<Link>` 改成 `<a>`：

桌面端 (line 65-70)：

```diff
-          <Link
-            to={LINKS.signIn}
-            className="text-sm text-brand-ink-700 hover:text-brand-ink-900 px-3 py-1.5"
-          >
-            {t.nav.signIn}
-          </Link>
+          <a
+            href={LINKS.signIn}
+            className="text-sm text-brand-ink-700 hover:text-brand-ink-900 px-3 py-1.5"
+          >
+            {t.nav.signIn}
+          </a>
```

移动端 sheet (line 119-125)：

```diff
-            <Link
-              to={LINKS.signIn}
-              onClick={() => setMobileOpen(false)}
-              className="py-3 text-brand-ink-700"
-            >
-              {t.nav.signIn}
-            </Link>
+            <a
+              href={LINKS.signIn}
+              className="py-3 text-brand-ink-700"
+            >
+              {t.nav.signIn}
+            </a>
```

移动端去掉 `onClick={() => setMobileOpen(false)}` —— 原生 `<a>` 整页跳转，sheet 状态会随页面卸载销毁，不需手动关。

- [ ] **Step 2: 手测验证**

```bash
cd /var/tgsc/landing && npm run dev
```

浏览器访问 `http://localhost:5173/`，点击右上角"登录"。**预期：** 浏览器 URL 变 `/login`，整页加载，进入 frontend 的登录页（不再瞬间回到落地页首页）。

- [ ] **Step 3: Commit**

```bash
cd /var/tgsc && git add landing/src/sections/Header.tsx
git commit -m "fix(landing): 登录按钮改原生 <a> 跨 SPA 跳转"
```

---

## Task 0b: 修复 Header 深色背景文字对比度

**Why:** 未滚动时 Header 是 `bg-transparent`，叠在 `HeroDual` 的 `bg-grad-radial-dark` 上。导航文字与"登录"用 `text-brand-ink-700`（深灰），在深色背景上几乎不可见。`LangSwitcher` 已支持 `onDark` prop（line 17, 48-49），Header 只需在未滚动时传过去即可。

**Files:**
- Modify: `landing/src/sections/Header.tsx`

- [ ] **Step 1: 给导航链接、登录链接加 onDark 颜色，给 LangSwitcher 传 onDark**

修改 `landing/src/sections/Header.tsx`：

```diff
         {/* Desktop nav */}
-        <nav className="hidden md:flex items-center gap-8 text-sm text-brand-ink-700">
+        <nav
+          className={[
+            'hidden md:flex items-center gap-8 text-sm transition-colors',
+            scrolled ? 'text-brand-ink-700' : 'text-white/80',
+          ].join(' ')}
+        >
           {navLinks.map((l) => (
-            <a key={l.href} href={l.href} className="hover:text-brand-ink-900 transition-colors">
+            <a
+              key={l.href}
+              href={l.href}
+              className={scrolled ? 'hover:text-brand-ink-900' : 'hover:text-white'}
+            >
               {l.label}
             </a>
           ))}
         </nav>

         <div className="hidden md:flex items-center gap-3">
-          <LangSwitcher />
+          <LangSwitcher onDark={!scrolled} />
           <a
             href={LINKS.signIn}
-            className="text-sm text-brand-ink-700 hover:text-brand-ink-900 px-3 py-1.5"
+            className={[
+              'text-sm px-3 py-1.5 transition-colors',
+              scrolled
+                ? 'text-brand-ink-700 hover:text-brand-ink-900'
+                : 'text-white/80 hover:text-white',
+            ].join(' ')}
           >
             {t.nav.signIn}
           </a>
```

同时移动端汉堡按钮在深色背景上也要变浅色：

```diff
         {/* Mobile hamburger */}
         <button
           type="button"
-          className="md:hidden text-brand-ink-700 p-2"
+          className={[
+            'md:hidden p-2 transition-colors',
+            scrolled ? 'text-brand-ink-700' : 'text-white/80',
+          ].join(' ')}
           onClick={() => setMobileOpen(true)}
           aria-label="Open menu"
         >
           <Menu className="w-6 h-6" />
         </button>
```

移动端 sheet 内部（line 96 起）是 `bg-white` 不透明面板，不受深色背景影响，颜色不动。

- [ ] **Step 2: 类型检查 + 手测**

```bash
cd /var/tgsc/landing && npm run build
```

预期：build 成功。再 `npm run dev`，访问 `/`：

- 首屏（未滚动）：导航文字、登录、LangSwitcher 应清晰可见（白色 80% 透明度）
- 向下滚动 > 24px：Header 出现白色底 + blur，文字切回深灰，仍清晰
- 移动端汉堡同理（首屏白色，滚动后深灰）

- [ ] **Step 3: Commit**

```bash
cd /var/tgsc && git add landing/src/sections/Header.tsx
git commit -m "fix(landing): Header 未滚动时切浅色文字适配深色 hero"
```

---

## Task 1: 引入 vitest 测试基础设施

**Why:** 落地页项目目前无测试框架。`useTimeline` hook 是纯逻辑、易测且关键（时间轴跑错幕就完蛋），引入最小 vitest 配置足以覆盖它。UI 部分依赖手测。

**Files:**
- Modify: `landing/package.json`
- Create: `landing/vitest.config.ts`
- Create: `landing/src/test-setup.ts`

- [ ] **Step 1: 安装依赖**

```bash
cd /var/tgsc/landing && npm install --save-dev vitest@^2.1.0 @testing-library/react@^16.1.0 @testing-library/jest-dom@^6.6.0 jsdom@^25.0.0 @vitest/ui@^2.1.0
```

预期：依赖装入，无 peer-dep warning（React 18 兼容）。

- [ ] **Step 2: 在 package.json 加 test script**

修改 `landing/package.json`，scripts 段加：

```diff
   "scripts": {
     "dev": "vite --host 0.0.0.0 --port 5173",
     "build": "tsc -b && vite build",
-    "preview": "vite preview --host 0.0.0.0 --port 5173"
+    "preview": "vite preview --host 0.0.0.0 --port 5173",
+    "test": "vitest run",
+    "test:watch": "vitest"
   },
```

- [ ] **Step 3: 创建 vitest 配置**

创建 `landing/vitest.config.ts`：

```ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: { '@': path.resolve(__dirname, './src') },
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test-setup.ts'],
    globals: true,
  },
});
```

- [ ] **Step 4: 创建 test-setup**

创建 `landing/src/test-setup.ts`：

```ts
import '@testing-library/jest-dom/vitest';
```

- [ ] **Step 5: 验证测试框架可跑**

创建临时 sanity 文件 `landing/src/test-sanity.test.ts`：

```ts
import { describe, it, expect } from 'vitest';

describe('sanity', () => {
  it('1 + 1 = 2', () => {
    expect(1 + 1).toBe(2);
  });
});
```

运行：

```bash
cd /var/tgsc/landing && npm test
```

预期：`1 passed`。

删除 sanity 文件：

```bash
rm landing/src/test-sanity.test.ts
```

- [ ] **Step 6: Commit**

```bash
cd /var/tgsc && git add landing/package.json landing/package-lock.json landing/vitest.config.ts landing/src/test-setup.ts
git commit -m "chore(landing): add vitest + testing-library for unit tests"
```

---

## Task 2: useTimeline hook (TDD)

**Why:** 时间轴是整个 modal 的引擎。先写测试确认行为，再实现。

**Files:**
- Create: `landing/src/components/DemoVideoModal/useTimeline.ts`
- Create: `landing/src/components/DemoVideoModal/useTimeline.test.ts`

- [ ] **Step 1: 写失败测试**

创建 `landing/src/components/DemoVideoModal/useTimeline.test.ts`：

```ts
import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import { useTimeline } from './useTimeline';

describe('useTimeline', () => {
  let rafCallbacks: Map<number, FrameRequestCallback>;
  let rafId: number;
  let now: number;

  beforeEach(() => {
    rafCallbacks = new Map();
    rafId = 0;
    now = 0;
    vi.stubGlobal('requestAnimationFrame', (cb: FrameRequestCallback) => {
      rafId += 1;
      rafCallbacks.set(rafId, cb);
      return rafId;
    });
    vi.stubGlobal('cancelAnimationFrame', (id: number) => {
      rafCallbacks.delete(id);
    });
    vi.spyOn(performance, 'now').mockImplementation(() => now);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  function tick(ms: number) {
    now += ms;
    const callbacks = Array.from(rafCallbacks.values());
    rafCallbacks.clear();
    act(() => callbacks.forEach((cb) => cb(now)));
  }

  it('starts at elapsedMs=0, act=1, not paused', () => {
    const { result } = renderHook(() => useTimeline(75000));
    expect(result.current.elapsedMs).toBe(0);
    expect(result.current.act).toBe(1);
    expect(result.current.paused).toBe(false);
    expect(result.current.progress).toBe(0);
  });

  it('advances elapsed on each frame', () => {
    const { result } = renderHook(() => useTimeline(75000));
    tick(16);
    expect(result.current.elapsedMs).toBe(16);
    tick(34);
    expect(result.current.elapsedMs).toBe(50);
  });

  it('computes act from act boundaries [0, 15000, 35000, 55000, 75000]', () => {
    const { result } = renderHook(() => useTimeline(75000));
    tick(10000);
    expect(result.current.act).toBe(1);
    tick(10000); // 20000
    expect(result.current.act).toBe(2);
    tick(20000); // 40000
    expect(result.current.act).toBe(3);
    tick(20000); // 60000
    expect(result.current.act).toBe(4);
  });

  it('progress is elapsed/duration clamped 0-1', () => {
    const { result } = renderHook(() => useTimeline(1000));
    tick(500);
    expect(result.current.progress).toBeCloseTo(0.5);
    tick(2000);
    expect(result.current.progress).toBe(1);
  });

  it('pause freezes elapsed, resume continues from frozen point', () => {
    const { result } = renderHook(() => useTimeline(75000));
    tick(1000);
    act(() => result.current.pause());
    tick(500);
    expect(result.current.elapsedMs).toBe(1000);
    expect(result.current.paused).toBe(true);
    act(() => result.current.resume());
    tick(500);
    expect(result.current.elapsedMs).toBe(1500);
  });

  it('restart resets elapsed to 0 and resumes', () => {
    const { result } = renderHook(() => useTimeline(75000));
    tick(20000);
    act(() => result.current.restart());
    expect(result.current.elapsedMs).toBe(0);
    expect(result.current.paused).toBe(false);
    expect(result.current.act).toBe(1);
  });

  it('auto-pauses when reaching duration', () => {
    const { result } = renderHook(() => useTimeline(1000));
    tick(2000);
    expect(result.current.elapsedMs).toBe(1000);
    expect(result.current.paused).toBe(true);
  });

  it('ignores frame deltas > 250ms (tab hidden recovery)', () => {
    const { result } = renderHook(() => useTimeline(75000));
    tick(100);
    expect(result.current.elapsedMs).toBe(100);
    tick(5000); // simulated tab-hidden gap
    expect(result.current.elapsedMs).toBe(100); // frozen, not 5100
  });

  it('cancels raf on unmount', () => {
    const cancelSpy = vi.spyOn(window, 'cancelAnimationFrame');
    const { unmount } = renderHook(() => useTimeline(75000));
    unmount();
    expect(cancelSpy).toHaveBeenCalled();
  });
});
```

- [ ] **Step 2: 运行测试确认失败**

```bash
cd /var/tgsc/landing && npm test -- useTimeline
```

预期：所有测试失败（`useTimeline` 不存在 / cannot find module）。

- [ ] **Step 3: 实现 useTimeline**

创建 `landing/src/components/DemoVideoModal/useTimeline.ts`：

```ts
/**
 * Timeline hook for DemoVideoModal.
 *
 * Drives `elapsedMs` via requestAnimationFrame. Tab-hidden recovery
 * (deltas > 250ms) freezes time instead of jumping. Auto-pauses at
 * duration; restart resets to 0 and resumes.
 */
import { useCallback, useEffect, useRef, useState } from 'react';

/** Boundaries that split the 75s timeline into 4 acts. */
export const ACT_BOUNDARIES = [0, 15000, 35000, 55000, 75000] as const;

export type Act = 1 | 2 | 3 | 4;

export interface Timeline {
  elapsedMs: number;
  progress: number;
  act: Act;
  paused: boolean;
  pause: () => void;
  resume: () => void;
  restart: () => void;
}

const TAB_HIDDEN_THRESHOLD_MS = 250;

function actFromElapsed(elapsed: number): Act {
  if (elapsed < ACT_BOUNDARIES[1]) return 1;
  if (elapsed < ACT_BOUNDARIES[2]) return 2;
  if (elapsed < ACT_BOUNDARIES[3]) return 3;
  return 4;
}

export function useTimeline(durationMs: number): Timeline {
  const [elapsedMs, setElapsedMs] = useState(0);
  const [paused, setPaused] = useState(false);
  const lastTickRef = useRef<number | null>(null);
  const rafRef = useRef<number | null>(null);
  const pausedRef = useRef(false);
  const elapsedRef = useRef(0);

  pausedRef.current = paused;
  elapsedRef.current = elapsedMs;

  useEffect(() => {
    const tick = (ts: number) => {
      if (pausedRef.current) {
        lastTickRef.current = ts;
        rafRef.current = requestAnimationFrame(tick);
        return;
      }
      if (lastTickRef.current === null) {
        lastTickRef.current = ts;
        rafRef.current = requestAnimationFrame(tick);
        return;
      }
      const delta = ts - lastTickRef.current;
      lastTickRef.current = ts;
      if (delta > TAB_HIDDEN_THRESHOLD_MS) {
        rafRef.current = requestAnimationFrame(tick);
        return;
      }
      const next = Math.min(elapsedRef.current + delta, durationMs);
      elapsedRef.current = next;
      setElapsedMs(next);
      if (next >= durationMs) {
        setPaused(true);
      }
      rafRef.current = requestAnimationFrame(tick);
    };
    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
      lastTickRef.current = null;
    };
  }, [durationMs]);

  const pause = useCallback(() => setPaused(true), []);
  const resume = useCallback(() => {
    lastTickRef.current = null; // avoid counting time spent paused
    setPaused(false);
  }, []);
  const restart = useCallback(() => {
    elapsedRef.current = 0;
    lastTickRef.current = null;
    setElapsedMs(0);
    setPaused(false);
  }, []);

  return {
    elapsedMs,
    progress: durationMs > 0 ? Math.min(elapsedMs / durationMs, 1) : 0,
    act: actFromElapsed(elapsedMs),
    paused,
    pause,
    resume,
    restart,
  };
}
```

- [ ] **Step 4: 运行测试确认全部通过**

```bash
cd /var/tgsc/landing && npm test -- useTimeline
```

预期：所有 9 个测试通过。

- [ ] **Step 5: Commit**

```bash
cd /var/tgsc && git add landing/src/components/DemoVideoModal/useTimeline.ts landing/src/components/DemoVideoModal/useTimeline.test.ts
git commit -m "feat(landing/demo): useTimeline hook with raf + tab-hidden recovery"
```

---

## Task 3: i18n demo 命名空间（5 语言）

**Why:** 所有 modal 内可见文案必须 i18n。在 dict 里加 `demo` 段，5 语言各加一份。机翻 ja/ko/es 即可（按 i18n.ts 文件头注释的惯例）。

**Files:**
- Modify: `landing/src/i18n.ts`

- [ ] **Step 1: 在 Dict 类型加 demo 段**

定位 `landing/src/i18n.ts` 中 `export type Dict = {` 块，找到 `hero: { ... }` 段末尾后插入：

```ts
  demo: {
    title: string;
    badge: string;
    acts: { listening: string; incoming: string; scoring: string; handover: string };
    kpi: { rate: string; rateUnit: string; captured: string };
    console: { line1: string; line2: string; line3: string; line4: string };
    score: {
      label: string;
      keywords: string;
      persona: string;
      personaValue: string;
      suggestion: string;
      suggestionValue: string;
    };
    handover: {
      newLead: string;
      salesName: string;
      salesReply: string;
    };
    controls: { pause: string; resume: string; restart: string; close: string };
    reduced: { intro: string; tabPrefix: string };
    messages: {
      /** 8 mock 群消息，索引 0-7。索引 3 和 6 是高意向。 */
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
```

- [ ] **Step 2: 给 en dict 加 demo 段**

定位 en dict（约 line 220+），在 `hero: { ... }` 段末尾后插入：

```ts
  demo: {
    title: 'TG1 AI Assistant · Live Demo',
    badge: 'Listening to 3 groups',
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
      persona: 'Persona',
      personaValue: 'SMB merchant',
      suggestion: 'Suggested opener',
      suggestionValue: 'Hi — saw your question about USDT receiving. We help merchants accept stablecoin without local-bank friction. Want a 2-min walkthrough?',
    },
    handover: {
      newLead: 'New lead',
      salesName: 'Sales · Alex',
      salesReply: 'Hi — saw your question in the group about USDT receiving…',
    },
    controls: {
      pause: 'Pause',
      resume: 'Resume',
      restart: 'Replay',
      close: 'Close demo',
    },
    reduced: {
      intro: 'Animation disabled per your motion preference. Browse the 4 acts:',
      tabPrefix: 'Act',
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
```

- [ ] **Step 3: 给 zh-CN dict 加 demo 段**

定位 zh-CN dict（约 line 536+），同位置插入：

```ts
  demo: {
    title: 'TG1 AI 助手 · 实时演示',
    badge: '正在监听 3 个群',
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
      persona: '用户画像',
      personaValue: '中小商户',
      suggestion: '推荐话术',
      suggestionValue: '您好，看到您在问 USDT 收款。我们帮商户用稳定币收单，不走本地银行。要不要看 2 分钟演示？',
    },
    handover: {
      newLead: '新线索',
      salesName: '销售 · Alex',
      salesReply: '您好，看到您在群里问 USDT 收款……',
    },
    controls: {
      pause: '暂停',
      resume: '继续',
      restart: '重播',
      close: '关闭演示',
    },
    reduced: {
      intro: '已按您的动效偏好关闭动画。逐幕浏览：',
      tabPrefix: '第',
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
```

- [ ] **Step 4: 给 ja / ko / es 加 demo 段（机翻）**

ja dict（约 line 851+）插入：

```ts
  demo: {
    title: 'TG1 AI アシスタント · ライブデモ',
    badge: '3 つのグループを監視中',
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
      persona: 'ペルソナ',
      personaValue: '中小事業者',
      suggestion: '推奨トーク',
      suggestionValue: 'こんにちは。USDT の受け取りについてのご質問を拝見しました。当社は加盟店がステーブルコインで受け取れるよう支援しています。2 分のデモはいかがですか？',
    },
    handover: {
      newLead: '新規リード',
      salesName: '営業 · Alex',
      salesReply: 'こんにちは、グループでの USDT 受け取りに関するご質問を拝見しました…',
    },
    controls: { pause: '一時停止', resume: '再開', restart: '再生', close: 'デモを閉じる' },
    reduced: { intro: 'モーション設定によりアニメーションは無効です。4 幕をご覧ください：', tabPrefix: '第' },
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
```

ko dict（约 line 1108+）插入：

```ts
  demo: {
    title: 'TG1 AI 어시스턴트 · 라이브 데모',
    badge: '3개 그룹 모니터링 중',
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
      persona: '페르소나',
      personaValue: '중소 사업자',
      suggestion: '추천 멘트',
      suggestionValue: '안녕하세요. USDT 수금에 대한 질문을 보았습니다. 저희는 가맹점이 스테이블코인으로 수금할 수 있도록 돕습니다. 2분 데모를 보시겠어요?',
    },
    handover: {
      newLead: '신규 리드',
      salesName: '영업 · Alex',
      salesReply: '안녕하세요, 그룹에서 USDT 수금에 대한 질문을 보았습니다…',
    },
    controls: { pause: '일시정지', resume: '재개', restart: '다시 재생', close: '데모 닫기' },
    reduced: { intro: '모션 설정에 따라 애니메이션이 비활성화되었습니다. 4막을 보세요:', tabPrefix: '제' },
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
```

es dict（约 line 1365+，搜索 `'SSO + exportación de auditoría'` 附近的 hero）插入：

```ts
  demo: {
    title: 'Asistente IA de TG1 · Demo en vivo',
    badge: 'Escuchando 3 grupos',
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
      persona: 'Persona',
      personaValue: 'PYME / comerciante',
      suggestion: 'Apertura sugerida',
      suggestionValue: 'Hola — vi tu pregunta sobre recibir USDT. Ayudamos a comerciantes a aceptar stablecoin sin fricciones bancarias locales. ¿2 minutos de demo?',
    },
    handover: {
      newLead: 'Nuevo lead',
      salesName: 'Ventas · Alex',
      salesReply: 'Hola — vi tu pregunta en el grupo sobre recibir USDT…',
    },
    controls: { pause: 'Pausar', resume: 'Reanudar', restart: 'Reproducir', close: 'Cerrar demo' },
    reduced: { intro: 'Animación desactivada según tu preferencia de movimiento. Explora los 4 actos:', tabPrefix: 'Acto' },
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
```

- [ ] **Step 5: 类型检查**

```bash
cd /var/tgsc/landing && npx tsc -b
```

预期：build 通过，无错误。如果某语言漏 key，编译器会报错——补齐。

- [ ] **Step 6: Commit**

```bash
cd /var/tgsc && git add landing/src/i18n.ts
git commit -m "feat(landing/i18n): add demo namespace × 5 languages"
```

---

## Task 4: demoScript 时间轴脚本

**Why:** 把所有"什么时刻该出现什么"集中在一个数据文件，UI 组件只负责"现在 elapsedMs=X，去 script 找该显示的项"。

**Files:**
- Create: `landing/src/components/DemoVideoModal/demoScript.ts`

- [ ] **Step 1: 创建 demoScript.ts**

```ts
/**
 * Timeline script for DemoVideoModal.
 *
 * Each entry's `appearAt` is the ms offset when it should mount.
 * `highIntent: true` flags messages that get scanned + scored by AI
 * in act 3 — keep this in sync with the act boundaries.
 */
export const DURATION_MS = 75_000;

export interface ScriptedMessage {
  id: string;
  /** ms when bubble starts appearing. */
  appearAt: number;
  groupIdx: 0 | 1 | 2;
  senderKey: 's0' | 's1' | 's2' | 's3' | 's4' | 's5' | 's6' | 's7';
  messageKey: 'm0' | 'm1' | 'm2' | 'm3' | 'm4' | 'm5' | 'm6' | 'm7';
  highIntent?: boolean;
}

/** Messages flow during acts 2-3 (15s - 55s). */
export const SCRIPTED_MESSAGES: ScriptedMessage[] = [
  { id: 'msg-0', appearAt: 15_500, groupIdx: 0, senderKey: 's0', messageKey: 'm0' },
  { id: 'msg-1', appearAt: 17_500, groupIdx: 1, senderKey: 's1', messageKey: 'm1' },
  { id: 'msg-2', appearAt: 20_000, groupIdx: 2, senderKey: 's2', messageKey: 'm2' },
  { id: 'msg-3', appearAt: 23_000, groupIdx: 0, senderKey: 's3', messageKey: 'm3', highIntent: true },
  { id: 'msg-4', appearAt: 26_500, groupIdx: 1, senderKey: 's4', messageKey: 'm4' },
  { id: 'msg-5', appearAt: 28_500, groupIdx: 2, senderKey: 's5', messageKey: 'm5' },
  { id: 'msg-6', appearAt: 31_000, groupIdx: 1, senderKey: 's6', messageKey: 'm6', highIntent: true },
  { id: 'msg-7', appearAt: 33_500, groupIdx: 0, senderKey: 's7', messageKey: 'm7' },
];

export interface ConsoleLine {
  appearAt: number;
  key: 'line1' | 'line2' | 'line3' | 'line4';
}

export const CONSOLE_LINES: ConsoleLine[] = [
  { appearAt: 1_000,  key: 'line1' },
  { appearAt: 3_000,  key: 'line2' },
  { appearAt: 21_000, key: 'line3' },
  { appearAt: 42_000, key: 'line4' },
];

/** When the AI scan line sweeps over high-intent messages (act 3). */
export const SCAN_START_MS = 36_000;
export const SCAN_END_MS = 40_000;
/** When the score card pops up. */
export const SCORE_APPEAR_MS = 40_500;
/** When the score card "flies" into the inbox. */
export const SCORE_FLY_MS = 55_000;
/** When sales avatar + typing reply appears. */
export const SALES_TYPING_MS = 60_000;
/** Acts 2-4 ramp the "msg rate" KPI from 0 → 12. */
export function kpiRate(elapsedMs: number): number {
  if (elapsedMs < 15_000) return 0;
  const t = Math.min((elapsedMs - 15_000) / 20_000, 1);
  return Math.round(t * 12);
}

export function kpiCaptured(elapsedMs: number): number {
  return elapsedMs >= SCORE_FLY_MS ? 1 : 0;
}
```

- [ ] **Step 2: 类型检查**

```bash
cd /var/tgsc/landing && npx tsc -b
```

预期：通过。

- [ ] **Step 3: Commit**

```bash
cd /var/tgsc && git add landing/src/components/DemoVideoModal/demoScript.ts
git commit -m "feat(landing/demo): timeline script (messages, console, scan, KPI)"
```

---

## Task 5: Modal 骨架（Backdrop + Panel + TopBar + 关闭逻辑）

**Why:** 先搭一个能弹出、能关闭、占位空白的 modal，wire 进 HeroDual 验证开/关流程。后续 task 往 Stage 区填内容。

**Files:**
- Create: `landing/src/components/DemoVideoModal/index.tsx`
- Create: `landing/src/components/DemoVideoModal/parts/TopBar.tsx`

- [ ] **Step 1: 创建 TopBar**

`landing/src/components/DemoVideoModal/parts/TopBar.tsx`：

```tsx
import { X } from 'lucide-react';
import { useT } from '@/i18n';
import type { Act } from '../useTimeline';

interface Props {
  act: Act;
  onClose: () => void;
}

const actKey: Record<Act, 'listening' | 'incoming' | 'scoring' | 'handover'> = {
  1: 'listening', 2: 'incoming', 3: 'scoring', 4: 'handover',
};

export default function TopBar({ act, onClose }: Props) {
  const t = useT();
  return (
    <div className="flex items-center justify-between px-5 py-3 border-b border-white/10">
      <div className="flex items-center gap-3 min-w-0">
        <span className="relative flex h-2 w-2 shrink-0">
          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-75" />
          <span className="relative inline-flex h-2 w-2 rounded-full bg-success" />
        </span>
        <h2 id="demo-modal-title" className="font-display text-base md:text-lg font-semibold text-white truncate">
          {t.demo.title}
        </h2>
        <span className="hidden md:inline-flex items-center rounded-full bg-white/10 border border-white/15 px-2.5 py-0.5 text-xs font-mono text-white/70">
          {t.demo.acts[actKey[act]]}
        </span>
      </div>
      <button
        type="button"
        onClick={onClose}
        className="text-white/60 hover:text-white p-1.5 rounded-full hover:bg-white/10 transition-colors"
        aria-label={t.demo.controls.close}
      >
        <X className="w-5 h-5" />
      </button>
    </div>
  );
}
```

- [ ] **Step 2: 创建 modal 主体**

`landing/src/components/DemoVideoModal/index.tsx`：

```tsx
/**
 * DemoVideoModal — full-screen modal that plays a 75s product
 * UI simulation in place of a real demo video.
 *
 * Triggered from HeroDual's secondary CTA. ESC closes. While open,
 * body scroll is locked. Honors prefers-reduced-motion (renders a
 * tabbed static fallback instead of the timeline).
 */
import { useEffect, useRef } from 'react';
import { createPortal } from 'react-dom';
import { AnimatePresence, motion } from 'framer-motion';
import { useTimeline } from './useTimeline';
import { DURATION_MS } from './demoScript';
import TopBar from './parts/TopBar';

interface Props {
  open: boolean;
  onClose: () => void;
}

export default function DemoVideoModal({ open, onClose }: Props) {
  const closeBtnRef = useRef<HTMLButtonElement>(null);
  const timeline = useTimeline(DURATION_MS);

  // Body scroll lock + ESC handler
  useEffect(() => {
    if (!open) return;
    const prevOverflow = document.body.style.overflow;
    document.body.style.overflow = 'hidden';
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    document.addEventListener('keydown', onKey);
    return () => {
      document.body.style.overflow = prevOverflow;
      document.removeEventListener('keydown', onKey);
    };
  }, [open, onClose]);

  // Reset timeline whenever modal re-opens
  useEffect(() => {
    if (open) timeline.restart();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  return createPortal(
    <AnimatePresence>
      {open && (
        <motion.div
          key="demo-modal"
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.2 }}
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/70 backdrop-blur-md p-4"
          onClick={onClose}
          role="dialog"
          aria-modal="true"
          aria-labelledby="demo-modal-title"
        >
          <motion.div
            initial={{ opacity: 0, scale: 0.96, y: 12 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.96, y: 12 }}
            transition={{ duration: 0.25, ease: [0.22, 1, 0.36, 1] }}
            className="relative w-full max-w-5xl aspect-[16/10] rounded-2xl overflow-hidden bg-brand-ink-950 border border-white/10 shadow-2xl flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <TopBar act={timeline.act} onClose={onClose} />
            <div className="flex-1 relative bg-gradient-to-br from-brand-ink-950 to-brand-ink-900 grid grid-cols-12 gap-px">
              {/* LeftPane / RightPane slot in later tasks */}
              <div className="col-span-7 p-4 text-white/30 text-xs font-mono">[left pane — task 7]</div>
              <div className="col-span-5 p-4 text-white/30 text-xs font-mono">[right pane — tasks 8, 9]</div>
            </div>
            {/* BottomBar slot — task 6 */}
            <div className="h-14 border-t border-white/10 px-5 flex items-center text-white/30 text-xs font-mono">
              [bottom bar — task 6] elapsed={Math.round(timeline.elapsedMs)}ms act={timeline.act}
            </div>
            <button ref={closeBtnRef} className="sr-only" tabIndex={-1} aria-hidden />
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>,
    document.body,
  );
}
```

- [ ] **Step 3: 类型检查 + 构建**

```bash
cd /var/tgsc/landing && npm run build
```

预期：构建通过。`brand-ink-950` 颜色如果不存在，先看 `tailwind.config.js` 确认；如果缺，把它改为 `bg-black` 临时代替（也可单独加 950 色阶——这部分由实施者根据现有 tailwind 配置选择，不影响功能）。

- [ ] **Step 4: Commit**

```bash
cd /var/tgsc && git add landing/src/components/DemoVideoModal/index.tsx landing/src/components/DemoVideoModal/parts/TopBar.tsx
git commit -m "feat(landing/demo): modal skeleton (portal, ESC, body lock, TopBar)"
```

---

## Task 6: BottomBar（进度条 + KPI + 控制）

**Files:**
- Create: `landing/src/components/DemoVideoModal/parts/BottomBar.tsx`
- Modify: `landing/src/components/DemoVideoModal/index.tsx`

- [ ] **Step 1: 创建 BottomBar**

`landing/src/components/DemoVideoModal/parts/BottomBar.tsx`：

```tsx
import { Pause, Play, RotateCcw } from 'lucide-react';
import { useT } from '@/i18n';
import { ACT_BOUNDARIES } from '../useTimeline';
import { kpiRate, kpiCaptured, DURATION_MS } from '../demoScript';

interface Props {
  elapsedMs: number;
  paused: boolean;
  onPause: () => void;
  onResume: () => void;
  onRestart: () => void;
}

export default function BottomBar({ elapsedMs, paused, onPause, onResume, onRestart }: Props) {
  const t = useT();
  const rate = kpiRate(elapsedMs);
  const captured = kpiCaptured(elapsedMs);

  return (
    <div className="border-t border-white/10 px-5 py-3 flex items-center gap-5 bg-black/30">
      {/* KPIs */}
      <div className="flex items-center gap-5 text-xs font-mono text-white/70">
        <div>
          <span className="text-white/40">{t.demo.kpi.rate} </span>
          <span className="text-white tabular-nums">{rate}{t.demo.kpi.rateUnit}</span>
        </div>
        <div>
          <span className="text-white/40">{t.demo.kpi.captured} </span>
          <span className="text-white tabular-nums">{captured}</span>
        </div>
      </div>

      {/* Segmented progress (4 acts) */}
      <div className="flex-1 flex items-center gap-1">
        {[0, 1, 2, 3].map((i) => {
          const start = ACT_BOUNDARIES[i];
          const end = ACT_BOUNDARIES[i + 1];
          const segProgress = Math.max(0, Math.min(1, (elapsedMs - start) / (end - start)));
          return (
            <div key={i} className="flex-1 h-1 rounded-full bg-white/10 overflow-hidden">
              <div
                className="h-full bg-gradient-to-r from-brand-blue-500 to-brand-purple-500 transition-[width] duration-100"
                style={{ width: `${segProgress * 100}%` }}
              />
            </div>
          );
        })}
      </div>

      {/* Controls */}
      <div className="flex items-center gap-1">
        {paused ? (
          elapsedMs >= DURATION_MS ? (
            <button
              type="button"
              onClick={onRestart}
              aria-label={t.demo.controls.restart}
              className="p-2 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors"
            >
              <RotateCcw className="w-4 h-4" />
            </button>
          ) : (
            <button
              type="button"
              onClick={onResume}
              aria-label={t.demo.controls.resume}
              className="p-2 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors"
            >
              <Play className="w-4 h-4" />
            </button>
          )
        ) : (
          <button
            type="button"
            onClick={onPause}
            aria-label={t.demo.controls.pause}
            className="p-2 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors"
          >
            <Pause className="w-4 h-4" />
          </button>
        )}
        <button
          type="button"
          onClick={onRestart}
          aria-label={t.demo.controls.restart}
          className="p-2 rounded-full text-white/70 hover:text-white hover:bg-white/10 transition-colors"
        >
          <RotateCcw className="w-4 h-4" />
        </button>
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 把 BottomBar 接到 modal**

修改 `landing/src/components/DemoVideoModal/index.tsx`，去掉占位 div，加 import 和 BottomBar：

```diff
 import TopBar from './parts/TopBar';
+import BottomBar from './parts/BottomBar';
```

替换 BottomBar 占位：

```diff
-            {/* BottomBar slot — task 6 */}
-            <div className="h-14 border-t border-white/10 px-5 flex items-center text-white/30 text-xs font-mono">
-              [bottom bar — task 6] elapsed={Math.round(timeline.elapsedMs)}ms act={timeline.act}
-            </div>
+            <BottomBar
+              elapsedMs={timeline.elapsedMs}
+              paused={timeline.paused}
+              onPause={timeline.pause}
+              onResume={timeline.resume}
+              onRestart={timeline.restart}
+            />
```

- [ ] **Step 3: 构建**

```bash
cd /var/tgsc/landing && npm run build
```

预期：通过。

- [ ] **Step 4: Commit**

```bash
cd /var/tgsc && git add landing/src/components/DemoVideoModal/parts/BottomBar.tsx landing/src/components/DemoVideoModal/index.tsx
git commit -m "feat(landing/demo): BottomBar (segmented progress, KPIs, controls)"
```

---

## Task 7: LeftPane（群列表 + 消息流，幕 1-2）

**Files:**
- Create: `landing/src/components/DemoVideoModal/parts/MessageBubble.tsx`
- Create: `landing/src/components/DemoVideoModal/parts/LeftPane.tsx`
- Modify: `landing/src/components/DemoVideoModal/index.tsx`

- [ ] **Step 1: 创建 MessageBubble**

`landing/src/components/DemoVideoModal/parts/MessageBubble.tsx`：

```tsx
import { motion } from 'framer-motion';
import { useT } from '@/i18n';
import type { ScriptedMessage } from '../demoScript';
import { SCAN_START_MS, SCAN_END_MS, SCORE_APPEAR_MS } from '../demoScript';

interface Props {
  message: ScriptedMessage;
  elapsedMs: number;
}

export default function MessageBubble({ message, elapsedMs }: Props) {
  const t = useT();
  const sender = t.demo.senders[message.senderKey];
  const text = t.demo.messages[message.messageKey];

  const scanning = message.highIntent && elapsedMs >= SCAN_START_MS && elapsedMs < SCAN_END_MS;
  const scored = message.highIntent && elapsedMs >= SCORE_APPEAR_MS;
  const dimmed = !message.highIntent && elapsedMs >= SCAN_START_MS;

  return (
    <motion.div
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: dimmed ? 0.25 : 1, y: 0 }}
      transition={{ duration: 0.35, ease: [0.22, 1, 0.36, 1] }}
      className={[
        'relative rounded-lg px-3 py-2 max-w-[85%] text-sm transition-colors',
        scored ? 'bg-brand-blue-500/10 border border-brand-blue-400/40' : 'bg-white/[0.06] border border-white/10',
      ].join(' ')}
    >
      <div className="flex items-baseline gap-2 mb-0.5">
        <span className="text-xs font-medium text-brand-blue-300">{sender}</span>
      </div>
      <p className="text-white/85 leading-snug">{text}</p>

      {scanning && (
        <motion.div
          initial={{ x: '-100%' }}
          animate={{ x: '100%' }}
          transition={{ duration: 1.2, repeat: Infinity, ease: 'linear' }}
          className="pointer-events-none absolute inset-0 overflow-hidden rounded-lg"
        >
          <div className="h-full w-1/3 bg-gradient-to-r from-transparent via-brand-blue-400/40 to-transparent" />
        </motion.div>
      )}
    </motion.div>
  );
}
```

- [ ] **Step 2: 创建 LeftPane**

`landing/src/components/DemoVideoModal/parts/LeftPane.tsx`：

```tsx
import { motion } from 'framer-motion';
import { Users } from 'lucide-react';
import { useT } from '@/i18n';
import { SCRIPTED_MESSAGES } from '../demoScript';
import MessageBubble from './MessageBubble';

interface Props {
  elapsedMs: number;
}

export default function LeftPane({ elapsedMs }: Props) {
  const t = useT();
  const visibleMessages = SCRIPTED_MESSAGES.filter((m) => elapsedMs >= m.appearAt);

  return (
    <div className="col-span-12 md:col-span-7 flex flex-col bg-brand-ink-950/60 min-h-0">
      {/* Group rail */}
      <div className="flex items-center gap-2 px-4 py-2.5 border-b border-white/10 overflow-x-auto">
        {[0, 1, 2].map((i) => (
          <div
            key={i}
            className="flex items-center gap-2 rounded-full bg-white/[0.04] border border-white/10 px-3 py-1 text-xs text-white/70 shrink-0"
          >
            <span className="relative flex h-1.5 w-1.5">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-success opacity-60" />
              <span className="relative inline-flex h-1.5 w-1.5 rounded-full bg-success" />
            </span>
            <Users className="w-3 h-3" />
            <span>{t.demo.groups[`g${i}` as 'g0' | 'g1' | 'g2']}</span>
          </div>
        ))}
      </div>

      {/* Message stream */}
      <div className="flex-1 px-4 py-3 space-y-2 overflow-y-auto min-h-0">
        {visibleMessages.length === 0 ? (
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 0.5 }}
            className="text-xs font-mono text-white/40"
          >
            {t.demo.badge}…
          </motion.div>
        ) : (
          visibleMessages.map((m) => (
            <MessageBubble key={m.id} message={m} elapsedMs={elapsedMs} />
          ))
        )}
      </div>
    </div>
  );
}
```

- [ ] **Step 3: 接到 modal**

修改 `landing/src/components/DemoVideoModal/index.tsx`：

```diff
 import BottomBar from './parts/BottomBar';
+import LeftPane from './parts/LeftPane';
```

```diff
-              <div className="col-span-7 p-4 text-white/30 text-xs font-mono">[left pane — task 7]</div>
+              <LeftPane elapsedMs={timeline.elapsedMs} />
               <div className="col-span-5 p-4 text-white/30 text-xs font-mono">[right pane — tasks 8, 9]</div>
```

注意：现有 stage 是 `grid-cols-12`；LeftPane 自己 span 7（在 md+），小屏占 12。RightPane 占位也要改成 `md:col-span-5`，先就地修：

```diff
-              <div className="col-span-5 p-4 text-white/30 text-xs font-mono">[right pane — tasks 8, 9]</div>
+              <div className="col-span-12 md:col-span-5 p-4 text-white/30 text-xs font-mono">[right pane — tasks 8, 9]</div>
```

- [ ] **Step 4: 构建**

```bash
cd /var/tgsc/landing && npm run build
```

- [ ] **Step 5: Commit**

```bash
cd /var/tgsc && git add landing/src/components/DemoVideoModal/parts/MessageBubble.tsx landing/src/components/DemoVideoModal/parts/LeftPane.tsx landing/src/components/DemoVideoModal/index.tsx
git commit -m "feat(landing/demo): LeftPane with group rail and scripted message stream"
```

---

## Task 8: RightPane 幕 3（Console + ScoreCard）

**Files:**
- Create: `landing/src/components/DemoVideoModal/parts/ScoreCard.tsx`
- Create: `landing/src/components/DemoVideoModal/parts/RightPane.tsx`
- Modify: `landing/src/components/DemoVideoModal/index.tsx`

- [ ] **Step 1: 创建 ScoreCard**

`landing/src/components/DemoVideoModal/parts/ScoreCard.tsx`：

```tsx
import { motion } from 'framer-motion';
import { Sparkles } from 'lucide-react';
import { useT } from '@/i18n';
import { SCORE_APPEAR_MS, SCORE_FLY_MS } from '../demoScript';

interface Props {
  elapsedMs: number;
}

export default function ScoreCard({ elapsedMs }: Props) {
  const t = useT();
  if (elapsedMs < SCORE_APPEAR_MS) return null;
  const flying = elapsedMs >= SCORE_FLY_MS;

  return (
    <motion.div
      initial={{ opacity: 0, y: 16, scale: 0.96 }}
      animate={
        flying
          ? { opacity: 0, y: -40, scale: 0.7, transition: { duration: 0.5 } }
          : { opacity: 1, y: 0, scale: 1, transition: { duration: 0.35, ease: [0.22, 1, 0.36, 1] } }
      }
      className="rounded-xl border border-brand-blue-400/40 bg-gradient-to-br from-brand-blue-500/15 to-brand-purple-500/10 p-3.5 backdrop-blur-sm"
    >
      <div className="flex items-center justify-between mb-2.5">
        <div className="flex items-center gap-1.5 text-xs font-mono text-brand-blue-300">
          <Sparkles className="w-3 h-3" />
          <span>{t.demo.score.label}</span>
        </div>
        <div className="font-display text-2xl font-bold text-white tabular-nums">92</div>
      </div>
      <dl className="space-y-1.5 text-xs">
        <div className="flex justify-between gap-3">
          <dt className="text-white/50">{t.demo.score.keywords}</dt>
          <dd className="text-white/85 text-right">USDT · cross-border</dd>
        </div>
        <div className="flex justify-between gap-3">
          <dt className="text-white/50">{t.demo.score.persona}</dt>
          <dd className="text-white/85 text-right">{t.demo.score.personaValue}</dd>
        </div>
        <div>
          <dt className="text-white/50 mb-1">{t.demo.score.suggestion}</dt>
          <dd className="text-white/85 leading-snug bg-white/[0.04] rounded-md px-2 py-1.5 border border-white/5">
            {t.demo.score.suggestionValue}
          </dd>
        </div>
      </dl>
    </motion.div>
  );
}
```

- [ ] **Step 2: 创建 RightPane 含 Console + ScoreCard 槽位**

`landing/src/components/DemoVideoModal/parts/RightPane.tsx`：

```tsx
import { motion, AnimatePresence } from 'framer-motion';
import { Terminal } from 'lucide-react';
import { useT } from '@/i18n';
import { CONSOLE_LINES } from '../demoScript';
import ScoreCard from './ScoreCard';

interface Props {
  elapsedMs: number;
}

export default function RightPane({ elapsedMs }: Props) {
  const t = useT();
  const visibleConsole = CONSOLE_LINES.filter((l) => elapsedMs >= l.appearAt);

  return (
    <div className="col-span-12 md:col-span-5 flex flex-col bg-brand-ink-900/80 min-h-0 border-l border-white/5">
      {/* Console */}
      <div className="border-b border-white/10">
        <div className="flex items-center gap-1.5 px-4 py-2 text-xs font-mono text-white/50">
          <Terminal className="w-3 h-3" />
          <span>ai-console</span>
        </div>
        <div className="px-4 pb-3 space-y-1 font-mono text-xs text-white/70 min-h-[5rem]">
          <AnimatePresence initial={false}>
            {visibleConsole.map((line) => (
              <motion.div
                key={line.key}
                initial={{ opacity: 0, x: -8 }}
                animate={{ opacity: 1, x: 0 }}
                transition={{ duration: 0.25 }}
              >
                {t.demo.console[line.key]}
              </motion.div>
            ))}
          </AnimatePresence>
        </div>
      </div>

      {/* Score card area */}
      <div className="p-4 min-h-[12rem]">
        <ScoreCard elapsedMs={elapsedMs} />
      </div>

      {/* Inbox area — filled in Task 9 */}
      <div className="flex-1 px-4 pb-4 text-xs font-mono text-white/30">[inbox — task 9]</div>
    </div>
  );
}
```

- [ ] **Step 3: 接到 modal**

修改 `landing/src/components/DemoVideoModal/index.tsx`：

```diff
 import LeftPane from './parts/LeftPane';
+import RightPane from './parts/RightPane';
```

```diff
               <LeftPane elapsedMs={timeline.elapsedMs} />
-              <div className="col-span-12 md:col-span-5 p-4 text-white/30 text-xs font-mono">[right pane — tasks 8, 9]</div>
+              <RightPane elapsedMs={timeline.elapsedMs} />
```

- [ ] **Step 4: 构建**

```bash
cd /var/tgsc/landing && npm run build
```

- [ ] **Step 5: Commit**

```bash
cd /var/tgsc && git add landing/src/components/DemoVideoModal/parts/ScoreCard.tsx landing/src/components/DemoVideoModal/parts/RightPane.tsx landing/src/components/DemoVideoModal/index.tsx
git commit -m "feat(landing/demo): RightPane with AI console + ScoreCard (act 3)"
```

---

## Task 9: RightPane 幕 4（Inbox + 销售接管）

**Files:**
- Create: `landing/src/components/DemoVideoModal/parts/InboxItem.tsx`
- Modify: `landing/src/components/DemoVideoModal/parts/RightPane.tsx`

- [ ] **Step 1: 创建 InboxItem**

`landing/src/components/DemoVideoModal/parts/InboxItem.tsx`：

```tsx
import { motion } from 'framer-motion';
import { Inbox } from 'lucide-react';
import { useT } from '@/i18n';
import { SCORE_FLY_MS, SALES_TYPING_MS } from '../demoScript';

interface Props {
  elapsedMs: number;
}

export default function InboxItem({ elapsedMs }: Props) {
  const t = useT();
  if (elapsedMs < SCORE_FLY_MS) {
    return (
      <div className="flex items-center gap-2 text-xs font-mono text-white/30">
        <Inbox className="w-3 h-3" />
        <span>inbox · empty</span>
      </div>
    );
  }

  const typing = elapsedMs >= SALES_TYPING_MS;

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-xs font-mono text-white/60">
        <div className="flex items-center gap-1.5">
          <Inbox className="w-3 h-3" />
          <span>inbox</span>
        </div>
        <motion.span
          initial={{ scale: 0.6, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          transition={{ type: 'spring', stiffness: 400, damping: 18 }}
          className="inline-flex items-center justify-center min-w-[1.25rem] h-5 rounded-full bg-brand-blue-500 text-white text-[10px] font-bold px-1.5"
        >
          +1
        </motion.span>
      </div>

      <motion.div
        initial={{ opacity: 0, y: -16, scale: 0.92 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        transition={{ duration: 0.4, ease: [0.22, 1, 0.36, 1] }}
        className="rounded-xl border border-white/10 bg-white/[0.04] p-3"
      >
        <div className="flex items-center justify-between mb-2">
          <span className="text-xs font-medium text-brand-blue-300">{t.demo.senders.s3}</span>
          <span className="text-[10px] font-mono text-brand-blue-400 bg-brand-blue-500/15 border border-brand-blue-400/30 rounded-full px-1.5">
            {t.demo.score.label} 92
          </span>
        </div>
        <p className="text-xs text-white/70 leading-snug mb-3">
          {t.demo.messages.m3}
        </p>

        {typing && (
          <motion.div
            initial={{ opacity: 0, y: 8 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.3 }}
            className="border-t border-white/10 pt-2.5 mt-2.5"
          >
            <div className="flex items-center gap-2 mb-1.5">
              <div className="w-5 h-5 rounded-full bg-gradient-to-br from-brand-blue-500 to-brand-purple-500 grid place-items-center text-[10px] font-bold text-white">A</div>
              <span className="text-xs font-medium text-white/80">{t.demo.handover.salesName}</span>
              <motion.span
                animate={{ opacity: [0.3, 1, 0.3] }}
                transition={{ duration: 1.4, repeat: Infinity }}
                className="text-[10px] font-mono text-white/40"
              >
                typing…
              </motion.span>
            </div>
            <p className="text-xs text-white/70 leading-snug pl-7">
              {t.demo.handover.salesReply}
            </p>
          </motion.div>
        )}
      </motion.div>
    </div>
  );
}
```

- [ ] **Step 2: 替换 RightPane 的 inbox 占位**

修改 `landing/src/components/DemoVideoModal/parts/RightPane.tsx`：

```diff
 import ScoreCard from './ScoreCard';
+import InboxItem from './InboxItem';
```

```diff
-      {/* Inbox area — filled in Task 9 */}
-      <div className="flex-1 px-4 pb-4 text-xs font-mono text-white/30">[inbox — task 9]</div>
+      <div className="flex-1 px-4 pb-4">
+        <InboxItem elapsedMs={elapsedMs} />
+      </div>
```

- [ ] **Step 3: 构建**

```bash
cd /var/tgsc/landing && npm run build
```

- [ ] **Step 4: Commit**

```bash
cd /var/tgsc && git add landing/src/components/DemoVideoModal/parts/InboxItem.tsx landing/src/components/DemoVideoModal/parts/RightPane.tsx
git commit -m "feat(landing/demo): InboxItem with handover typing (act 4)"
```

---

## Task 10: Reduced-motion fallback

**Why:** 用户偏好 `prefers-reduced-motion: reduce` 时，必须给静态替代版本，不能强播动画。Spec 要求 4 个 tab，每个展示该幕最终静态视图。

**Files:**
- Create: `landing/src/components/DemoVideoModal/parts/ReducedFallback.tsx`
- Modify: `landing/src/components/DemoVideoModal/index.tsx`

- [ ] **Step 1: 创建 ReducedFallback**

`landing/src/components/DemoVideoModal/parts/ReducedFallback.tsx`：

```tsx
/**
 * Static, tabbed alternative shown when user prefers reduced motion.
 * Renders the same Left/Right panes but pinned to the end-state of
 * the selected act (no raf, no scan, no flying card).
 */
import { useState } from 'react';
import { useT } from '@/i18n';
import { ACT_BOUNDARIES, type Act } from '../useTimeline';
import LeftPane from './LeftPane';
import RightPane from './RightPane';

const ACT_END_ELAPSED: Record<Act, number> = {
  1: ACT_BOUNDARIES[1] - 1,
  2: ACT_BOUNDARIES[2] - 1,
  3: ACT_BOUNDARIES[3] - 1,
  4: ACT_BOUNDARIES[4] - 1,
};

const ACTS: Act[] = [1, 2, 3, 4];

export default function ReducedFallback() {
  const t = useT();
  const [act, setAct] = useState<Act>(1);
  const elapsed = ACT_END_ELAPSED[act];
  const actKey: Record<Act, 'listening' | 'incoming' | 'scoring' | 'handover'> = {
    1: 'listening', 2: 'incoming', 3: 'scoring', 4: 'handover',
  };

  return (
    <div className="flex flex-col flex-1 min-h-0">
      <div className="px-5 py-2.5 border-b border-white/10 flex items-center gap-1 overflow-x-auto">
        <span className="text-xs text-white/50 mr-2 shrink-0">{t.demo.reduced.intro}</span>
        {ACTS.map((a) => (
          <button
            key={a}
            type="button"
            onClick={() => setAct(a)}
            className={[
              'shrink-0 rounded-full px-3 py-1 text-xs font-mono transition-colors',
              act === a
                ? 'bg-brand-blue-500/20 text-brand-blue-200 border border-brand-blue-400/40'
                : 'text-white/60 hover:text-white border border-transparent hover:bg-white/5',
            ].join(' ')}
          >
            {t.demo.acts[actKey[a]]}
          </button>
        ))}
      </div>
      <div className="flex-1 grid grid-cols-12 gap-px min-h-0">
        <LeftPane elapsedMs={elapsed} />
        <RightPane elapsedMs={elapsed} />
      </div>
    </div>
  );
}
```

- [ ] **Step 2: 在 modal 中检测 reduced-motion，分支渲染**

修改 `landing/src/components/DemoVideoModal/index.tsx`，加 hook：

```diff
-import { useEffect, useRef } from 'react';
+import { useEffect, useRef, useState } from 'react';
```

```diff
 import RightPane from './parts/RightPane';
+import ReducedFallback from './parts/ReducedFallback';
```

在 component 内，把 timeline 和 useEffect 一起加：

```diff
 export default function DemoVideoModal({ open, onClose }: Props) {
   const closeBtnRef = useRef<HTMLButtonElement>(null);
   const timeline = useTimeline(DURATION_MS);
+  const [reducedMotion, setReducedMotion] = useState(false);
+
+  useEffect(() => {
+    const mq = window.matchMedia('(prefers-reduced-motion: reduce)');
+    setReducedMotion(mq.matches);
+    const onChange = (e: MediaQueryListEvent) => setReducedMotion(e.matches);
+    mq.addEventListener('change', onChange);
+    return () => mq.removeEventListener('change', onChange);
+  }, []);
```

把 Stage + BottomBar 分支：

```diff
-            <TopBar act={timeline.act} onClose={onClose} />
-            <div className="flex-1 relative bg-gradient-to-br from-brand-ink-950 to-brand-ink-900 grid grid-cols-12 gap-px">
-              <LeftPane elapsedMs={timeline.elapsedMs} />
-              <RightPane elapsedMs={timeline.elapsedMs} />
-            </div>
-            <BottomBar
-              elapsedMs={timeline.elapsedMs}
-              paused={timeline.paused}
-              onPause={timeline.pause}
-              onResume={timeline.resume}
-              onRestart={timeline.restart}
-            />
+            <TopBar act={timeline.act} onClose={onClose} />
+            {reducedMotion ? (
+              <ReducedFallback />
+            ) : (
+              <>
+                <div className="flex-1 relative bg-gradient-to-br from-brand-ink-950 to-brand-ink-900 grid grid-cols-12 gap-px min-h-0">
+                  <LeftPane elapsedMs={timeline.elapsedMs} />
+                  <RightPane elapsedMs={timeline.elapsedMs} />
+                </div>
+                <BottomBar
+                  elapsedMs={timeline.elapsedMs}
+                  paused={timeline.paused}
+                  onPause={timeline.pause}
+                  onResume={timeline.resume}
+                  onRestart={timeline.restart}
+                />
+              </>
+            )}
```

- [ ] **Step 3: 构建**

```bash
cd /var/tgsc/landing && npm run build
```

- [ ] **Step 4: Commit**

```bash
cd /var/tgsc && git add landing/src/components/DemoVideoModal/parts/ReducedFallback.tsx landing/src/components/DemoVideoModal/index.tsx
git commit -m "feat(landing/demo): reduced-motion tabbed fallback"
```

---

## Task 11: 接入 HeroDual + 删除 demoVideo 链接

**Files:**
- Modify: `landing/src/sections/HeroDual.tsx`
- Modify: `landing/src/lib/links.ts`

- [ ] **Step 1: HeroDual 加 state + Modal**

修改 `landing/src/sections/HeroDual.tsx`，imports：

```diff
 import { motion } from 'framer-motion';
+import { useState } from 'react';
 import { ArrowRight, Sparkles, Package, Bot, Shield } from 'lucide-react';
 import CTAButton from '@/components/CTAButton';
+import DemoVideoModal from '@/components/DemoVideoModal';
 import { LINKS } from '@/lib/links';
 import { Events } from '@/lib/analytics';
 import { useT } from '@/i18n';
```

component body 顶部：

```diff
 export default function HeroDual() {
   const t = useT();
+  const [demoOpen, setDemoOpen] = useState(false);
```

secondary CTA：

```diff
           <CTAButton
             variant="secondary"
-            href={LINKS.demoVideo}
+            href="#"
+            onClick={(e) => {
+              e.preventDefault();
+              setDemoOpen(true);
+            }}
             trackEvent={Events.CTA_DEMO_CLICK}
             trackProps={{ source: 'hero' }}
           >
             {t.hero.ctaSecondary}
           </CTAButton>
```

section 结尾（return 块的最末）加 modal：

```diff
       </div>
     </section>
+      <DemoVideoModal open={demoOpen} onClose={() => setDemoOpen(false)} />
+    </>
   );
 }
```

并把 `return (` 改成 `return (<>` 和最末加 `</>`：

```diff
   return (
-    <section className="relative overflow-hidden">
+    <>
+      <section className="relative overflow-hidden">
```

（即把整个 section 包进 Fragment，section 后面跟 Modal）

- [ ] **Step 2: 删 LINKS.demoVideo**

修改 `landing/src/lib/links.ts`：

```diff
-  // Demo
-  demoVideo:     '#demo-video', // anchor — actual mp4 lands in PR4
 } as const;
```

- [ ] **Step 3: 构建 + 全量类型检查**

```bash
cd /var/tgsc/landing && npm run build
```

预期：通过。若有别处引用 `LINKS.demoVideo`，编译器会报；用 grep 搜索：

```bash
grep -rn "demoVideo\|demo-video" /var/tgsc/landing/src/
```

预期：只剩 `links.ts` 不再出现，其他文件无引用。

- [ ] **Step 4: 手测**

```bash
cd /var/tgsc/landing && npm run dev
```

浏览器：
1. 点击 hero "看 90 秒 Demo" → modal 出现，开始播放
2. 按 ESC → 关闭
3. 再次点击 → 重新从头播
4. 点关闭按钮 → 关闭
5. 点黑色背景 → 关闭
6. 等到 75s 末尾 → 自动暂停，按↻可重播
7. 中途点暂停 → 冻结，按播放继续
8. 切换语言（zh/en/ja/ko/es）再开 modal → 文案随语言切换
9. 浏览器 DevTools → Rendering → "Emulate CSS prefers-reduced-motion: reduce" → 关 modal 重开 → 看到 tabbed 静态版

- [ ] **Step 5: Commit**

```bash
cd /var/tgsc && git add landing/src/sections/HeroDual.tsx landing/src/lib/links.ts
git commit -m "feat(landing): wire DemoVideoModal into hero CTA, drop dead demoVideo link"
```

---

## Task 12: 全量验证 + 推送

- [ ] **Step 1: 跑全部测试 + 构建**

```bash
cd /var/tgsc/landing && npm test && npm run build
```

预期：测试全过、build 成功。

- [ ] **Step 2: git status 检查**

```bash
cd /var/tgsc && git status && git log --oneline main..HEAD
```

预期：工作树干净，commit 链：
- `fix(landing): 登录按钮改原生 <a> 跨 SPA 跳转`
- `fix(landing): Header 未滚动时切浅色文字适配深色 hero`
- `chore(landing): add vitest + testing-library for unit tests`
- `feat(landing/demo): useTimeline hook ...`
- `feat(landing/i18n): add demo namespace × 5 languages`
- `feat(landing/demo): timeline script ...`
- `feat(landing/demo): modal skeleton ...`
- `feat(landing/demo): BottomBar ...`
- `feat(landing/demo): LeftPane ...`
- `feat(landing/demo): RightPane with AI console + ScoreCard ...`
- `feat(landing/demo): InboxItem with handover typing ...`
- `feat(landing/demo): reduced-motion tabbed fallback`
- `feat(landing): wire DemoVideoModal into hero CTA ...`

- [ ] **Step 3: 推送到 main**

```bash
cd /var/tgsc && git push origin main
```

预期：推送成功。

---

## 验证清单（实施者完成后自检）

- [ ] 登录按钮（桌面 + 移动）能跳到 `/login` 进入 frontend SPA
- [ ] Hero 区首屏导航文字（按量自助 / AI 助手 / 定价 / 文档 / 登录 / 简体中文）清晰可读
- [ ] 滚动 > 24px Header 切白底，文字深灰仍清晰
- [ ] 点击"看 90 秒 Demo" → modal 弹出 + 自动播放
- [ ] ESC / 点背景 / 点 ✕ 三种关闭方式都生效
- [ ] 暂停 / 继续 / 重播按钮可工作
- [ ] 75 秒末尾自动暂停，重播按钮可重新播放
- [ ] 4 幕进度条逐段填满
- [ ] 高意向消息（msg-3, msg-6）被扫描线高亮 → 弹评分卡 → 飞入 inbox → 销售头像 typing 回复
- [ ] 普通消息变灰
- [ ] KPI 数值（消息流速 0→12，今日捕获 0→1）随时间增长
- [ ] 切换 5 种语言，modal 内文案全部跟随
- [ ] `prefers-reduced-motion: reduce` 时显示 4-tab 静态版
- [ ] 移动端（窄屏）布局可用：左右盘叠成上下
- [ ] body scroll 在 modal 打开时锁定，关闭后恢复
- [ ] `npm test` 全过、`npm run build` 成功

---

## Self-Review 记录

- **Spec coverage:** 故事板 4 幕 → Tasks 7-9；时间轴 hook → Task 2；i18n 5 语言 → Task 3；reduced-motion → Task 10；触发改造 → Task 11；测试策略中 useTimeline 单测 → Task 2；两个独立 bug → Tasks 0a/0b。Spec 提到的 "PR4 才上视频"已被本 plan 完整替代。
- **Placeholder scan:** 已通查，无 TBD/TODO；UI 测试明确改为依赖手测清单（Task 11 Step 4 + 12 验证清单），不留"add tests"空头。
- **Type consistency:** `Timeline` 接口、`Act` 类型、`ACT_BOUNDARIES`、`SCRIPTED_MESSAGES` 字段名在所有引用 task 中一致；i18n `demo.messages.m0-m7`、`demo.senders.s0-s7`、`demo.groups.g0-g2` 在 Dict 类型、5 个 dict、demoScript、MessageBubble、InboxItem 间命名一致。
- **Tailwind 风险点：** `brand-ink-950` 在 Task 5 Step 3 提示实施者按现有 `tailwind.config.js` 决定是用现有色阶还是替换为 `bg-black`——不阻塞功能。
