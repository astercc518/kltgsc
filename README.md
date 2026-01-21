#  Telegram群控平台 (TGSC)

## 项目简介

Telegram 群控平台是一个高度自动化的 Telegram 账号批量管理与自动化操作平台。主要用于社群运营、自动化营销及消息管理。核心目标是支持 **1000+ 账号** 的稳定运行，最大程度减少人工干预，并通过技术手段降低账号风控风险。

## 技术栈

- **后端**: Python 3.10+, FastAPI, SQLModel, Pyrogram, Celery, Redis
- **前端**: React 18, Vite, Ant Design, TypeScript, Zustand
- **数据库**: SQLite (开发) / PostgreSQL (生产)
- **部署**: Docker, Docker Compose

## 项目文档

- [开发计划 (DEV_PLAN.md)](./DEV_PLAN.md) - 9 个开发阶段的详细规划
- [需求分析 (REQUIREMENTS.md)](./REQUIREMENTS.md) - 完整的功能需求说明
- [技术架构 (ARCHITECTURE.md)](./ARCHITECTURE.md) - 系统架构设计
- [开发任务清单 (TASKS.md)](./TASKS.md) - 详细的开发任务和验收标准 ⭐

## 快速开始

### 前置要求

- Docker & Docker Compose
- Python 3.10+ (本地开发)
- Node.js 18+ (本地开发)

### 启动服务

```bash
# 使用 Docker Compose 启动所有服务
docker-compose up -d

# 或分别启动
docker-compose up backend    # 后端服务 (http://localhost:8000)
docker-compose up frontend   # 前端服务 (http://localhost:3000)
docker-compose up redis      # Redis 服务
```

### 本地开发

**后端**:
```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**前端**:
```bash
cd frontend
npm install
npm run dev
```

## 开发阶段

当前阶段: **Stage 9 - 高级转化与增长** ⏳

已完成阶段:
- ✅ **Stage 1** - 基础框架搭建
- ✅ **Stage 2** - 核心资源管理
- ✅ **Stage 3** - 任务调度与并发控制
- ✅ **Stage 4** - 基础采集与营销
- ✅ **Stage 5** - 高级风控与自动化
- ✅ **Stage 6** - AI 智能营销
- ✅ **Stage 7** - CRM 客户管理
- ✅ **Stage 8** - 数据看板与运维

详细任务和验收标准请查看 [TASKS.md](./TASKS.md)

## 功能特性

### 1. 账号全生命周期管理
- **自动注册**: 集成 SMS-Activate 和 IP2World，实现从取号、接码到入库的全自动注册。
- **批量导入**: 支持 Session 文件和 JSON 格式批量导入。
- **状态检活**: 自动检测账号是否存活、被封禁或受限。
- **属性管理**: 批量修改头像、姓名、2FA 密码、用户名。

### 2. 高级代理池系统
- **多源支持**: 支持 API 提取 (IP2World) 和静态代理导入。
- **自动维护**: 自动检测代理连通性，智能轮换失效代理。
- **ISP 绑定**: 注册时自动绑定 ISP 代理，确保 IP 稳定性。

### 3. AI 驱动的高级营销
- **AI 智能炒群**: 多账号配合演戏，AI 自动生成自然对话，制造舆论热度。
- **被动引流**: 关键词监控 + AI 托号介入，引导用户主动私信。
- **AI SDR**: 自动识别客户意图（询价/购买），自动打标并通知真人销售。

### 4. 私域流量构建
- **批量拉人**: 采集精准用户 -> 拉入中转群 -> 内容培育 -> 转化。
- **聚合聊天**: CRM 统一回复，WebSocket 实时推送，不错过任何商机。

## 项目结构

```
/var/tgsc/
├── backend/          # 后端代码
│   ├── app/
│   │   ├── api/      # API 路由
│   │   ├── core/     # 核心配置
│   │   ├── models/   # 数据模型
│   │   ├── services/ # 业务逻辑
│   │   └── main.py   # 入口文件
│   └── sessions/     # Session 文件存储
├── frontend/         # 前端代码
│   └── src/
│       ├── api/      # API 请求封装
│       ├── components/ # 公共组件
│       ├── pages/    # 页面组件
│       └── layout/  # 布局组件
└── docker-compose.yml # 服务编排
```

## 验收标准

每个开发阶段完成后，都需要在 **Web 端进行真实环境验收**。详细验收标准请参考 [TASKS.md](./TASKS.md) 中每个阶段的"验收标准"部分。

## 许可证

[待定]
