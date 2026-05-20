# 技术架构设计 (Technical Architecture)

## 1. 系统架构图

```mermaid
graph TD
    Client[Web Browser (Frontend)] -->|HTTP/REST| API[FastAPI Backend]
    API -->|CRUD| DB[(SQLite/PostgreSQL)]
    API -->|Task| Queue[Task Queue (Optional for MVP)]
    API -->|Control| TG_Manager[Telegram Client Manager]
    TG_Manager -->|MTProto| TG_Server[Telegram Servers]
    TG_Manager -.->|SOCKS5| Proxy[Proxy Servers]
```

## 2. 技术栈详细选型

### 后端 (Backend)
*   **语言**: Python 3.10+
*   **Web 框架**: **FastAPI**
    *   *理由*: 异步支持友好 (与 Telegram 库完美契合)，自动生成 OpenAPI 文档，开发效率高。
*   **Telegram 协议库**: **Pyrogram**
    *   *理由*: 现代、轻量、异步性能好，API 设计直观。
*   **数据库**: **SQLite** (开发阶段) / **PostgreSQL** (生产环境)
    *   *ORM*: **SQLModel** (结合了 Pydantic 和 SQLAlchemy 的优点)。
*   **异步任务**: Python 原生 `asyncio` (MVP阶段) -> **Celery + Redis** (后期复杂任务)。

### 前端 (Frontend)
*   **框架**: **React 18**
*   **构建工具**: **Vite**
    *   *理由*: 极速启动，开发体验极佳。
*   **UI 组件库**: **Ant Design (antd)**
    *   *理由*: 适合后台管理系统，表格、表单组件丰富。
*   **状态管理**: **Zustand** 或 **TanStack Query** (React Query)。
*   **HTTP 客户端**: **Axios**。

### 部署与环境
*   **Docker**: 容器化部署。
*   **Docker Compose**: 编排前后端服务。

## 3. 目录结构规范

```
/var/tgsc/
├── backend/                # 后端代码
│   ├── app/
│   │   ├── api/            # API 路由定义
│   │   │   └── v1/
│   │   ├── core/           # 核心配置、数据库连接
│   │   ├── models/         # 数据库模型 (SQLModel)
│   │   ├── schemas/        # Pydantic 数据验证模型
│   │   ├── services/       # 业务逻辑 (TG Client 管理)
│   │   └── main.py         # 入口文件
│   ├── sessions/           # 存放 .session 文件
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/               # 前端代码
│   ├── src/
│   │   ├── api/            # API 请求封装
│   │   ├── components/     # 公共组件
│   │   ├── pages/          # 页面组件
│   │   ├── layout/         # 布局组件
│   │   └── App.tsx
│   ├── package.json
│   └── Dockerfile
│
├── docker-compose.yml      # 服务编排
├── ARCHITECTURE.md         # 架构文档
└── DEV_PLAN.md             # 开发计划
```
