# Demo Video Modal — 设计文档

**Date:** 2026-05-25
**Scope:** 落地页 hero 区"看 90 秒 Demo"按钮的目标组件
**Status:** Approved, ready for implementation plan

## 背景

落地页 [HeroDual.tsx](../../../landing/src/sections/HeroDual.tsx) 的 secondary CTA `看 90 秒 Demo` 指向 `LINKS.demoVideo = '#demo-video'`，但页面无任何 `id="demo-video"` 元素，点击毫无反应。注释自承"actual mp4 lands in PR4"。

本设计用一个纯前端 **产品 UI 模拟动画** 取代视频方案，0 额外资产、0 后端依赖、可 i18n。

## 目标

- 用户点击 "看 90 秒 Demo" 弹出全屏 modal，自动播放一段 ~75s 的产品演示动画
- 只讲 AI 助手产品线一个故事：监听目标群 → AI 捕获高意向消息 → 推送到销售 Inbox → 销售接管
- 支持暂停、重播、ESC 关闭、`prefers-reduced-motion`
- 完整支持落地页现有 5 种语言（zh-CN / zh-TW / en / ja / ko）

## 非目标（YAGNI）

- 不做真实 mp4 视频
- 不做进度条拖动 UI（hook 留接口，UI 不出）
- 不做分享、嵌入、跳过到下一幕
- 不持久化播放进度
- 不替代落地页其他 CTA（试用、Telegram 联系销售）

## 故事板

4 幕，总长 75 秒：

| 幕 | 时间 | 内容 |
|---|---|---|
| 1 · 监听就绪 | 0:00 – 0:15 | 左：Telegram 群列表（3 个目标群亮绿点）。右：AI 控制台空状态 "正在监听 3 个群..."。底部 KPI：消息流速 0 → 12 条/分 |
| 2 · 消息流入 | 0:15 – 0:35 | 左侧群里飘入 6-8 条气泡，1-2 条高意向（如 "有人做 USDT 收款吗？"）。普通消息灰显划过；高意向被蓝色扫描线扫过卡住 |
| 3 · AI 评分 | 0:35 – 0:55 | 高意向消息上方弹出评分卡：意向分 92/100、关键词、用户画像、推荐话术。右侧 AI 控制台同步打字机日志 |
| 4 · 推送 Inbox + 销售接管 | 0:55 – 1:15 | 评分卡飞向右侧 Inbox 变 lead 卡片，Inbox +1 红点。销售头像出现，打字 → "您好，看到您在群里问..."。底部 KPI：今日捕获 +1，漏斗动画 |

幕间用进度条平滑过渡，不强切。高意向消息文案需与落地页目标客户场景匹配（USDT / 跨境支付方向），后续可在 `demoScript.ts` 内调整。

## 组件结构

```
landing/src/components/DemoVideoModal/
├─ DemoVideoModal.tsx        # 顶层 modal + 时间轴宿主
├─ demoScript.ts             # mock 数据（消息、时间点、KPI 数值）
├─ useTimeline.ts            # 时间轴 hook
└─ parts/
   ├─ Backdrop.tsx
   ├─ TopBar.tsx
   ├─ LeftPane.tsx           # GroupRail + MessageStream
   ├─ MessageBubble.tsx
   ├─ RightPane.tsx          # ConsoleLog + ScoreCard + InboxList
   ├─ ScoreCard.tsx
   ├─ InboxItem.tsx
   └─ BottomBar.tsx          # ProgressBar + KPI + 控制
```

### 布局

```
DemoVideoModal (fixed inset-0, z-50, backdrop-blur-xl bg-black/70)
├─ Backdrop (click → close)
└─ Panel (max-w-5xl, aspect-video, rounded-2xl, glass-dark)
   ├─ TopBar [标题 · 当前幕标签 · 关闭 ✕]
   ├─ Stage (grid grid-cols-12)
   │  ├─ LeftPane (col-span-7)  — Telegram 模拟
   │  └─ RightPane (col-span-5) — AI 控制台 + Inbox
   └─ BottomBar [ProgressBar · KPI · ⏸ ↻]
```

## 时间轴驱动

`useTimeline(durationMs: number)` hook：

```ts
interface Timeline {
  elapsedMs: number;     // 已播放毫秒
  progress: number;      // 0-1
  act: 1 | 2 | 3 | 4;
  paused: boolean;
  pause(): void;
  resume(): void;
  restart(): void;
}
```

实现要点：
- 内部 `requestAnimationFrame` 驱动 `elapsedMs`
- 暂停时冻结 elapsed，恢复后从冻结点继续
- `elapsedMs >= durationMs` 时自动暂停在末尾（不自动重播）
- 卸载时取消 raf

子组件接收 `elapsedMs`，声明式决定渲染什么（如 `<MessageBubble appearAt={3200} message={...} />`）。

### 不引入新依赖

- 不引入 GSAP / framer-motion timeline / react-spring
- 单元素的 in/out 用现有 `framer-motion` 的 `<motion.div>` + `AnimatePresence`
- 时间轴本身（幕切换、消息出现时机）由 `useTimeline` 自管

## 触发改造

[HeroDual.tsx](../../../landing/src/sections/HeroDual.tsx) 改动：

```diff
- <CTAButton variant="secondary" href={LINKS.demoVideo} ...>
+ <CTAButton variant="secondary" onClick={() => setDemoOpen(true)} href="#" preventDefault ...>
```

`CTAButton` 需要支持 `preventDefault` 属性（或新增 `as="button"` 变体），细节由实施阶段决定。

[links.ts](../../../landing/src/lib/links.ts) 删除 `demoVideo` 项。

## 可访问性

- `role="dialog" aria-modal="true" aria-labelledby="demo-modal-title"`
- 打开时 focus 关闭按钮；关闭时 focus 还给 trigger CTA
- ESC 键关闭
- 打开时锁 body scroll（`document.body.style.overflow = 'hidden'`），关闭恢复
- `prefers-reduced-motion: reduce` 时：
  - 跳过气泡飘入、扫描线、打字机
  - 改为 4 个 tab，每个 tab 展示当幕的最终静态截图
  - 进度条变 tab 切换器

## i18n

落地页用现有 `useT()` 系统，5 种语言。新增 `demo` 命名空间：

```ts
demo: {
  title: 'TG1 AI 助手 · 实时演示',
  acts: { listening, incoming, scoring, handover }, // 4 个幕名
  console: { line1, line2, ... },                   // AI 控制台日志
  salesReply: '您好，看到您在群里问...',
  kpi: { rate, captured, fundnel },
  controls: { pause, resume, restart, close },
  reducedMotionTab: '...',
}
```

**消息气泡内容**（mock 群消息）也走 i18n —— 中文用户看中文消息，英文用户看英文消息。`demoScript.ts` 中的消息字段引用 `t.demo.messages[i]`，时间戳和发送者结构保持语言无关。

## 错误处理

Modal 是纯展示，无外部依赖（不发请求、不读 storage），无需特别 error handling。

唯一边缘：`requestAnimationFrame` 在标签页隐藏时被浏览器节流，恢复时 elapsed 可能跳跃。处理：每帧检查 `delta > 250ms` 视作 tab 隐藏过，冻结时间不计入 elapsed（避免跳幕）。

## 测试策略

- `useTimeline.test.ts` — 时间轴推进、暂停、重播、tab 隐藏边缘
- `DemoVideoModal.test.tsx` — 给定 elapsed=X，断言渲染了第 Y 幕；ESC 关闭；reduced-motion 走 fallback 路径
- 无 e2e（落地页项目目前无 e2e 框架）
- 手测清单：
  - 5 种语言切换显示正确
  - 移动端（< md）布局可读，整段动画不变形
  - Lighthouse a11y 不降分
  - 暂停/重播按钮可工作

## 不在本设计范围内的相关修复

同一轮反馈中用户还报告了两个独立 bug，会一并提交但不在本 spec 范围：

1. **登录按钮无跳转** — `Header.tsx` 用 `<Link to="/login">`（react-router 内部导航），但 `/login` 在 frontend SPA 而非 landing SPA。改为 `<a href="/login">` 让浏览器整页加载，交给 nginx 路由
2. **主菜单文字对比度低** — Header 未滚动时背景透明叠在深色 hero 上，nav 用 `text-brand-ink-700` 深灰几乎不可见。未滚动时切浅色文字，滚动后切回深色

## 实施顺序建议

1. 修两个独立 bug（登录链接 + Header 对比度）—— 30 分钟以内
2. 搭 `useTimeline` + 测试
3. 搭骨架组件（Backdrop / Panel / TopBar / BottomBar / 空 Stage）
4. 逐幕实现（按故事板顺序，每幕能独立看效果）
5. i18n 5 语言文案
6. reduced-motion fallback
7. 集成到 `HeroDual` 触发器
