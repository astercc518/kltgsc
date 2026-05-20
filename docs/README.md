# TG1.AI 文档索引

> 全部项目文档集中于此。根目录 `README.md` 是项目入口，详细资料按下表分组。

## 📘 用户文档

| 文档 | 用途 |
|---|---|
| [user_manual.md](user_manual.md) | **完整使用手册**（Portal / Admin / 销售 / API 集成 4 视角，1400+ 行）|

## 🏗 架构 (`architecture/`)

| 文档 | 用途 |
|---|---|
| [ARCHITECTURE.md](architecture/ARCHITECTURE.md) | 系统架构总览（服务/数据/容器拓扑）|
| [REQUIREMENTS.md](architecture/REQUIREMENTS.md) | 产品需求规格 |
| [MIGRATION_GUIDE.md](architecture/MIGRATION_GUIDE.md) | 数据库迁移与版本升级指引（Alembic）|

## 📋 规划 (`planning/`)

| 文档 | 用途 |
|---|---|
| [STRATEGIC_PLAN.md](planning/STRATEGIC_PLAN.md) | 战略规划与路线图 |
| [DEV_PLAN.md](planning/DEV_PLAN.md) | 工程开发计划 |
| [TASKS.md](planning/TASKS.md) | 任务清单与进度跟踪 |
| [TESTING.md](planning/TESTING.md) | 测试策略 |
| [WEB_ACCEPTANCE_REPORT.md](planning/WEB_ACCEPTANCE_REPORT.md) | Web 端验收报告 |

## 💼 投资人材料 (`investor/`)

中英文双语，每份提供 `.md` / `.html` / `.pdf` 三种格式。

| 文档 | 中文 | 英文 |
|---|---|---|
| **融资计划书** | [FINANCING_PLAN.md](investor/FINANCING_PLAN.md) · [html](investor/FINANCING_PLAN.html) · [pdf](investor/FINANCING_PLAN.pdf) | [FINANCING_PLAN_EN.md](investor/FINANCING_PLAN_EN.md) · [html](investor/FINANCING_PLAN_EN.html) · [pdf](investor/FINANCING_PLAN_EN.pdf) |
| **路演 PITCH** | [PITCH_DECK.md](investor/PITCH_DECK.md) · [html](investor/PITCH_DECK.html) · [pdf](investor/PITCH_DECK.pdf) | [PITCH_DECK_EN.md](investor/PITCH_DECK_EN.md) · [html](investor/PITCH_DECK_EN.html) · [pdf](investor/PITCH_DECK_EN.pdf) |

## 📊 数据资产 (`data/`)

从两个主号（id 81 / 82）采集 + 挖掘出的群组清单与候选清单。

| 文件 | 内容 | 用途 |
|---|---|---|
| [main_account_groups.csv](data/main_account_groups.csv) | 70 个群（去重，含 username/msgs/scraped_by）| Worker 号加群源 |
| [public_group_links.txt](data/public_group_links.txt) | 36 个公开群链接 | 直接喂 `POST /api/v1/scraping/join/batch` |
| [candidate_groups.csv](data/candidate_groups.csv) | 66 个被高频引用的 t.me/X 候选 | 待 resolve 的潜在群 |
| [resolve_results.json](data/resolve_results.json) | 候选 resolve 结果（7 group / 38 channel / 15 user / 6 not_found）| 已识别的频道/群分类 |

## 📝 维护说明

- 修改 `.md` 后用 `git diff` 检查变更
- `investor/*.pdf` 由对应 `.md` 通过 `pandoc` 生成，**不要直接编辑 pdf**
- 数据文件 (`data/*.csv`) 由后端 SQL 导出生成，记录采集时间快照
- 新文档加入时同步更新本索引
