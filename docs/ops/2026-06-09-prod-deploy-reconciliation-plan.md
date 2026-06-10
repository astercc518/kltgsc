# 生产上线方案：把 main 新功能合入生产（safety 分支）

日期：2026-06-09　状态：待审 / 待排维护窗口
关联：[[project_prod_deploy_topology]]、[[project_bulk_cold_send_peer_resolution]]、[[project_llm_safety_architecture]]

## 0. 背景一句话

生产实际跑 `feat/llm-safety-stack`（DB 在其头 `c7d8e9f0a1b2`）。本会话的新功能（冷发 peer 解析、按客户群发定价、钱包充值端点+UI、no_handle 提示）都在 `main`。一次误把 backend 切到 main 重启导致短暂宕机，已回滚恢复，DB 未受损。

## 1. 迁移分叉清单（已核实）

| 比较 | 结果 |
|---|---|
| 共同祖先 | `206607a`（Merge landing-demo-modal） |
| main 迁移数 / safety 迁移数 | 25 / 27 |
| **只在 main、不在 safety** | **0 个** |
| **只在 safety、不在 main** | **2 个**：`b6c7d8e9f0a1`(account_delete_cascade)、`c7d8e9f0a1b2`(llm_usage_safety_columns) |

**结论：不是冲突分叉，而是 safety = main 全部迁移 + 2 个线性增量。** 本会话功能**未引入任何迁移**。

两个 safety-only 迁移均为**安全增量**：
- `c7d8e9f0a1b2`：给 `llm_usage` 加 3 列 `moderation_score/block_layer/routed_provider`，**全部 `nullable=True`** → main 代码不写它们也能插入。
- `b6c7d8e9f0a1`：把若干 FK 改 `ON DELETE SET NULL/CASCADE`、`lead.account_id` 放宽为 nullable → 只放松约束，对 main 代码无害。

## 2. 代码合并规模（已核实）

`git merge main → feat/llm-safety-stack` **dry-run 干净，0 冲突文件**，涉及 38 个文件（均为 main 的功能代码）。

## 3. 推荐路径：合并 main → safety，部署 safety

因为合并零冲突、且不引入新迁移，部署后 `alembic upgrade head` 对生产 DB 是 **no-op**（DB 已在头）。既**保留 LLM 安全栈**，又拿到**全部新功能**，风险低。

> 不要反向（把 safety merge 进 main 再部署 main），那会让生产丢掉安全栈。

## 4. Staging 演练（先做，绝不碰生产）

1. **克隆生产 DB 到一次性实例**
   ```bash
   docker exec tgsc_postgres pg_dump -U <user> -d tgsc_prod -Fc -f /tmp/prod.dump
   # 在一次性 PG 容器里 pg_restore 出 tgsc_staging
   ```
2. **建合并分支**（不动 main/safety）
   ```bash
   git worktree add /tmp/tgsc-release -b release/merge-main-into-safety feat/llm-safety-stack
   cd /tmp/tgsc-release && git merge --no-ff main      # 预期 0 冲突
   ```
3. **对 staging 库跑迁移，确认 no-op**
   ```bash
   DATABASE_URL=<staging> alembic current   # 期望 c7d8e9f0a1b2 (head)
   DATABASE_URL=<staging> alembic upgrade head   # 期望 "no-op / already at head"
   ```
4. **起一份 staging 后端 + 前端**，冒烟测试：
   - 安全栈仍工作（L0/L1 过滤、provider 路由、`llm_usage` 写入含新列）。
   - 新功能：开户 / 配价（含群发按客户单价生效）/ 群发冷发 peer 解析 / 钱包充值（GET wallet 200、creditWallet 成功）/ no_handle 提示。
   - `record_usage` 等对 `llm_usage` 的写入正常（验证 nullable 列不报错）。
5. **跑后端测试套件**：`cd backend && python3 -m pytest tests/ -q`（容忍既有环境性失败：reranker .env、account upload、group_ai migration——见记忆）。

## 5. 生产发布（窗口内，演练通过后）

1. **备份生产 DB**：`pg_dump -Fc` 存档 + 记录当前镜像 tag（回滚锚点）。
2. 把 `release/merge-main-into-safety` 合并/快进到生产部署用分支（或直接用该分支）。
3. **重建并重启**（注意：backend/worker 用 dev compose，frontend 用 prod compose）：
   ```bash
   docker compose -f docker-compose.prod.yml build frontend
   docker compose -f docker-compose.prod.yml up -d --no-build frontend
   docker compose -f docker-compose.yml restart backend worker
   ```
4. **验证**：`alembic current` 仍 `c7d8e9f0a1b2`；`/api/v1/...` 真实路由非 502；GET wallet 200；前端「客户运营」全功能可用；安全栈日志正常。

## 6. 回滚预案

- DB 未变（no-op），无需 DB 回滚；如异常：`git checkout feat/llm-safety-stack` → 重启 backend/worker（已验证可恢复）+ 回滚 frontend 镜像。
- 备份 dump 作为最终兜底。

## 7. 收敛技术债（发布后）

- 把生产正式落到一条分支（合并后的 release）；删除并行未合并分支的混乱。
- 把**未跟踪却承重的迁移文件**（如 `41f948211e5f`）正式提交进版本库。
- 统一到单一 compose 文件（现 dev+prod 混用）。
- 清理前端 82 个历史 tsc 报错，恢复 `tsc` 类型门禁（目前 build 已改为只 `vite build`）。
