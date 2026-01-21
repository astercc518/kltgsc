# TGSC 服务器迁移文档

> 文档版本: 1.0  
> 迁移日期: 2026-01-21  
> 作者: 系统自动生成

---

## 1. 迁移概览

### 1.1 服务器信息

| 项目 | 旧服务器 | 新服务器 |
| :--- | :--- | :--- |
| **IP 地址** | (开发环境) | 104.233.205.1 |
| **SSH 端口** | 22 | 12649 |
| **用户名** | root | root |
| **操作系统** | Ubuntu 22.04 | Ubuntu 22.04 |
| **CPU** | - | Intel Xeon Gold 5122 x 2 (8核16线程) |
| **内存** | - | 64GB DDR4 ECC |
| **硬盘** | - | 1TB NVMe SSD |

### 1.2 架构升级

| 组件 | 迁移前 | 迁移后 |
| :--- | :--- | :--- |
| **数据库** | SQLite | PostgreSQL 14 |
| **缓存** | Redis | Redis 7 (带持久化) |
| **Web服务器** | Nginx | Nginx (Alpine) |
| **后端** | Uvicorn (单进程) | Uvicorn (4 workers) |
| **任务队列** | Celery Worker | Celery Worker (8并发) + Beat |

---

## 2. 环境配置

### 2.1 Docker 容器清单

```
┌─────────────────────────────────────────────────────────────────┐
│                         tgsc_nginx                               │
│                    (Nginx 反向代理)                              │
│                   端口: 80, 443                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          ▼                   ▼                   ▼
┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐
│  tgsc_frontend  │  │  tgsc_backend   │  │  tgsc_worker    │
│   (React UI)    │  │   (FastAPI)     │  │   (Celery)      │
│   端口: 3000    │  │   端口: 8000    │  │   8 并发        │
└─────────────────┘  └─────────────────┘  └─────────────────┘
                              │                   │
                              ▼                   ▼
          ┌───────────────────┴───────────────────┐
          │                                       │
┌─────────────────┐                    ┌─────────────────┐
│  tgsc_postgres  │                    │   tgsc_redis    │
│ (PostgreSQL 14) │                    │   (Redis 7)     │
│   端口: 5432    │                    │   端口: 6379    │
└─────────────────┘                    └─────────────────┘
```

### 2.2 网络配置

- **Docker 网络**: `tgsc_internal` (bridge 模式)
- **对外端口**: 
  - `80` - HTTP
  - `443` - HTTPS (自签名证书)
- **内部通信**: 容器间通过服务名直接访问

### 2.3 数据卷

| 卷名 | 挂载路径 | 用途 |
| :--- | :--- | :--- |
| `postgres_data` | `/var/lib/postgresql/data` | PostgreSQL 数据持久化 |
| `redis_data` | `/data` | Redis 数据持久化 |
| `backend_sessions` | `/app/sessions` | Telegram Session 文件 |

---

## 3. 配置文件说明

### 3.1 主配置文件

| 文件路径 | 用途 |
| :--- | :--- |
| `/var/tgsc/docker-compose.prod.yml` | 生产环境 Docker 编排 |
| `/var/tgsc/nginx.conf` | Nginx 反向代理配置 |
| `/var/tgsc/backend/.env` | 后端环境变量 |
| `/var/tgsc/ssl/server.pem` | SSL 证书 |
| `/var/tgsc/ssl/server.key` | SSL 私钥 |

### 3.2 数据库连接

```
postgresql://tgsc_user:TgSc_Pr0d_2026!@db:5432/tgsc_prod
```

**连接参数**:
- 主机: `db` (Docker 内部) 或 `localhost` (主机)
- 端口: `5432`
- 用户: `tgsc_user`
- 密码: `TgSc_Pr0d_2026!`
- 数据库: `tgsc_prod`

### 3.3 Redis 连接

```
redis://:7z0RvmWuSTPJvJcS4-A4BA@redis:6379/0
```

**连接参数**:
- 主机: `redis` (Docker 内部)
- 端口: `6379`
- 密码: `7z0RvmWuSTPJvJcS4-A4BA`

---

## 4. 访问信息

### 4.1 Web 访问

| 协议 | 地址 | 说明 |
| :--- | :--- | :--- |
| HTTP | http://104.233.205.1 | 标准 HTTP 访问 |
| HTTPS | https://104.233.205.1 | HTTPS (自签名证书) |

### 4.2 管理员账户

| 项目 | 值 |
| :--- | :--- |
| 用户名 | `admin` |
| 密码 | `Admin@Tgsc2026` |

### 4.3 SSH 访问

```bash
ssh -p 12649 root@104.233.205.1
```

---

## 5. 运维指南

### 5.1 常用命令

#### 服务管理

```bash
# 进入项目目录
cd /var/tgsc

# 查看所有容器状态
docker compose -f docker-compose.prod.yml ps

# 启动所有服务
docker compose -f docker-compose.prod.yml up -d

# 停止所有服务
docker compose -f docker-compose.prod.yml down

# 重启所有服务
docker compose -f docker-compose.prod.yml restart

# 重启单个服务
docker compose -f docker-compose.prod.yml restart backend
```

#### 日志查看

```bash
# 查看所有服务日志
docker compose -f docker-compose.prod.yml logs -f

# 查看特定服务日志
docker compose -f docker-compose.prod.yml logs -f backend
docker compose -f docker-compose.prod.yml logs -f worker
docker compose -f docker-compose.prod.yml logs -f nginx

# 查看最近 100 行日志
docker compose -f docker-compose.prod.yml logs --tail 100 backend
```

#### 数据库操作

```bash
# 进入 PostgreSQL 命令行
docker compose -f docker-compose.prod.yml exec db psql -U tgsc_user -d tgsc_prod

# 备份数据库
docker compose -f docker-compose.prod.yml exec db pg_dump -U tgsc_user tgsc_prod > backup_$(date +%Y%m%d).sql

# 恢复数据库
cat backup.sql | docker compose -f docker-compose.prod.yml exec -T db psql -U tgsc_user -d tgsc_prod
```

#### 代码更新

```bash
# 拉取最新代码
cd /var/tgsc
git pull

# 重新构建并启动
docker compose -f docker-compose.prod.yml up -d --build
```

### 5.2 健康检查

```bash
# API 健康检查
curl http://localhost/api/v1/health

# 预期输出
# {"status":"ok","message":"Backend is running"}

# 数据库连接测试
docker compose -f docker-compose.prod.yml exec db pg_isready -U tgsc_user -d tgsc_prod

# Redis 连接测试
docker compose -f docker-compose.prod.yml exec redis redis-cli -a 7z0RvmWuSTPJvJcS4-A4BA ping
```

### 5.3 性能监控

```bash
# 查看容器资源使用
docker stats

# 查看磁盘使用
df -h

# 查看内存使用
free -h

# 查看 CPU 使用
htop
```

---

## 6. 迁移步骤记录

### 6.1 已完成步骤

1. ✅ **环境准备**
   - 在新服务器安装 Docker 和 Git
   - 配置 SSH 自动化访问

2. ✅ **代码部署**
   - 从 GitHub 克隆代码: `https://github.com/astercc518/kltgsc.git`
   - 路径: `/var/tgsc`

3. ✅ **配置文件创建**
   - 创建 `docker-compose.prod.yml` (PostgreSQL + Redis)
   - 创建 `.env` 环境变量文件
   - 创建 `nginx.conf` (适配新服务器 IP)
   - 生成自签名 SSL 证书

4. ✅ **数据迁移**
   - 传输 Telegram Session 文件 (12个账号)
   - 初始化 PostgreSQL 数据库表结构

5. ✅ **服务启动与验证**
   - 启动所有 Docker 容器
   - 验证 API 健康检查
   - 验证登录功能

### 6.2 未迁移数据

| 数据类型 | 原因 | 处理建议 |
| :--- | :--- | :--- |
| 账号信息 | 数据库不兼容 (SQLite → PostgreSQL) | 手动重新录入或编写迁移脚本 |
| 代理配置 | 同上 | 手动重新录入 |
| 监控规则 | 同上 | 手动重新录入 |
| 目标用户 | 同上 | 手动重新录入 |

---

## 7. 故障排除

### 7.1 常见问题

#### 问题 1: 502 Bad Gateway

**症状**: 访问网页时显示 "502 Bad Gateway"

**原因**: Nginx 无法连接到后端服务

**解决方案**:
```bash
# 重启 nginx 刷新 DNS 解析
docker compose -f docker-compose.prod.yml restart nginx

# 检查后端是否运行
docker compose -f docker-compose.prod.yml ps backend
docker compose -f docker-compose.prod.yml logs backend
```

#### 问题 2: Worker 不断重启

**症状**: `tgsc_worker` 容器状态显示 "Restarting"

**原因**: 配置文件缺少必要的环境变量

**解决方案**:
```bash
# 检查日志
docker logs tgsc_worker

# 确保 .env 文件包含所有必要变量
cat /var/tgsc/backend/.env
```

#### 问题 3: 数据库连接失败

**症状**: 后端日志显示 "connection refused" 或 "authentication failed"

**解决方案**:
```bash
# 检查 PostgreSQL 容器状态
docker compose -f docker-compose.prod.yml ps db

# 检查数据库日志
docker compose -f docker-compose.prod.yml logs db

# 验证连接字符串
docker compose -f docker-compose.prod.yml exec backend python -c "from app.core.db import engine; print(engine.url)"
```

#### 问题 4: Session 文件不可用

**症状**: Telegram 账号无法登录，提示需要重新验证

**原因**: Session 文件损坏或路径不正确

**解决方案**:
```bash
# 检查 session 文件
ls -la /var/tgsc/backend/sessions/

# 检查 Docker 卷挂载
docker compose -f docker-compose.prod.yml exec backend ls -la /app/sessions/
```

---

## 8. 安全建议

### 8.1 立即执行

- [ ] **修改默认密码**: 更改 `admin` 账户密码
- [ ] **配置防火墙**: 只开放必要端口 (80, 443, 12649)
- [ ] **更新 SSL 证书**: 替换自签名证书为正式证书

### 8.2 建议执行

- [ ] **启用 fail2ban**: 防止 SSH 暴力破解
- [ ] **配置日志轮转**: 防止日志占满磁盘
- [ ] **设置定时备份**: 每日自动备份数据库

### 8.3 定期维护

- [ ] **每周**: 检查磁盘空间和日志大小
- [ ] **每月**: 更新系统和 Docker 镜像
- [ ] **每季度**: 审查账户权限和安全配置

---

## 9. 附录

### 9.1 目录结构

```
/var/tgsc/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   ├── core/
│   │   ├── models/
│   │   └── services/
│   ├── sessions/          # Telegram Session 文件
│   ├── requirements.txt
│   ├── Dockerfile
│   └── .env               # 环境变量 (敏感)
├── frontend/
│   ├── src/
│   ├── package.json
│   └── Dockerfile
├── ssl/
│   ├── server.pem         # SSL 证书
│   └── server.key         # SSL 私钥 (敏感)
├── docker-compose.yml      # 开发环境配置
├── docker-compose.prod.yml # 生产环境配置
├── nginx.conf             # Nginx 配置
└── .gitignore
```

### 9.2 环境变量清单

| 变量名 | 用途 | 示例值 |
| :--- | :--- | :--- |
| `DATABASE_URL` | 数据库连接 | `postgresql://...` |
| `REDIS_URL` | Redis 连接 | `redis://...` |
| `SECRET_KEY` | JWT 签名密钥 | (64字节随机字符串) |
| `ADMIN_USERNAME` | 管理员用户名 | `admin` |
| `ADMIN_PASSWORD` | 管理员密码 | `Admin@Tgsc2026` |
| `CELERY_BROKER_URL` | Celery 消息队列 | `redis://...` |
| `CELERY_RESULT_BACKEND` | Celery 结果存储 | `redis://...` |

### 9.3 端口映射

| 容器 | 内部端口 | 外部端口 | 用途 |
| :--- | :--- | :--- | :--- |
| nginx | 80 | 80 | HTTP |
| nginx | 443 | 443 | HTTPS |
| frontend | 3000 | - | React 开发服务器 |
| backend | 8000 | - | FastAPI |
| db | 5432 | - | PostgreSQL |
| redis | 6379 | - | Redis |

---

## 10. 联系信息

- **GitHub 仓库**: https://github.com/astercc518/kltgsc
- **问题反馈**: 通过 GitHub Issues 提交

---

*文档生成时间: 2026-01-21 08:45 UTC*
