# pg14 → pgvector/pgvector:pg16 数据迁移指引

## 背景

`docker-compose.prod.yml` 的 db 服务从 `postgres:14-alpine` 升级到 `pgvector/pgvector:pg16`。**Postgres major 版本之间数据卷不兼容**，必须 dump + restore。

## 操作步骤（在服务器上执行，所有命令在 /var/tgsc 目录下）

### 1. 备份（最重要）

```bash
# 1.1 dump 当前数据库（pg14 容器还跑着）
docker exec tgsc_postgres pg_dumpall -U "$POSTGRES_USER" > /var/tgsc/backup_pg14_$(date +%Y%m%d_%H%M%S).sql

# 1.2 也把整个 volume 物理备份一份（保险）
docker run --rm -v tgsc_postgres_data:/data -v /var/tgsc:/backup alpine \
  tar czf /backup/backup_pg14_volume_$(date +%Y%m%d_%H%M%S).tar.gz -C / data
```

确认 dump 文件大小 > 0 且包含 `CREATE DATABASE` 之类的内容：

```bash
ls -lh /var/tgsc/backup_pg14_*.sql
head -50 /var/tgsc/backup_pg14_*.sql
```

### 2. 停服 + 清旧卷

```bash
# 2.1 把所有依赖 db 的服务停掉
docker compose -f docker-compose.prod.yml stop backend worker beat listener db

# 2.2 删除旧 volume（数据已在第 1 步备份）
docker volume rm tgsc_postgres_data
```

### 3. 启动新 pgvector 镜像（空库）

```bash
docker compose -f docker-compose.prod.yml up -d db

# 等到 healthy
docker compose -f docker-compose.prod.yml ps db
```

### 4. 恢复数据

```bash
# 把 dump 文件 cp 进容器再 restore
docker cp /var/tgsc/backup_pg14_*.sql tgsc_postgres:/tmp/restore.sql
docker exec -e PGPASSWORD="$POSTGRES_PASSWORD" tgsc_postgres \
  psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" -f /tmp/restore.sql
```

### 5. 先重建 backend 镜像（装 pgvector / pypdf Python 包）

```bash
# requirements.txt 加了 pgvector / pypdf，必须 rebuild 镜像才会装上
docker compose -f docker-compose.prod.yml build backend worker beat listener
```

### 6. 启动 backend，Alembic 自动跑迁移

```bash
docker compose -f docker-compose.prod.yml up -d backend worker beat listener
docker compose logs -f backend | grep -i alembic
```

Alembic 会按顺序跑 `a7e6c2b9f1a3_add_pgvector_to_kb` → `b4d8e1f2c5a7_add_user_role_and_lead_takeover`：
- `CREATE EXTENSION IF NOT EXISTS vector;`（新镜像自带 pgvector）
- 给 `ai_knowledge_base` 加 embedding/category/parent_doc_id 等字段 + HNSW 索引
- 给 `user` 加 role；给 `lead` 加 assigned_to_user_id / ai_enabled / ai_draft / claimed_at

### 7. 验证

```bash
# 7.1 扩展存在
docker exec tgsc_postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "SELECT extversion FROM pg_extension WHERE extname='vector';"

# 7.2 embedding 列存在
docker exec tgsc_postgres psql -U "$POSTGRES_USER" -d "$POSTGRES_DB" \
  -c "\d ai_knowledge_base"

# 7.3 应用层正常
curl -s http://localhost/api/v1/health || true
```

### 8. backfill 存量 KB embedding

```bash
docker compose exec backend python scripts/backfill_kb_embeddings.py
```

### 9. 创建一个销售账号（admin 登录后调）

```bash
curl -X POST http://localhost/api/v1/users/ \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"username":"sales1","password":"YourStrongPwd123","role":"sales"}'
```

### 步骤序号调整说明
原 step 5/6/7 因新增"重建镜像"步骤，整体下移一位（5→6, 6→7, 7→8/9）。

## 回滚

若任一步失败：
1. 停服 → 删新卷
2. 把 `backup_pg14_volume_*.tar.gz` 解到新建的 `tgsc_postgres_data` 卷
3. 把 `docker-compose.prod.yml` 的镜像改回 `postgres:14-alpine`
4. `docker compose up -d`

## 注意

- 不要试图用 `pg_upgrade` 跨 major 版本就地升级 — pgvector 镜像没装 pg14 二进制
- 1G+ 数据的 dump/restore 用 `pg_dump -Fc -j 4` + `pg_restore -j 4` 更快（这里走 plain dump 是图简单）
- pgvector 扩展从 Alembic 迁移里 `CREATE EXTENSION IF NOT EXISTS vector;` 装；不需要手动装
