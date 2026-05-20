from fastapi import APIRouter, Depends
from app.api.v1.endpoints import (
    accounts, proxies, registration, login, system, tasks, scraping, marketing,
    warmup, ai, script, ws, crm, logs, monitor, invite, users,
    campaigns, source_groups, funnel_groups, personas, knowledge_bases, workflow,
    monitoring, ai_usage,
    customer_auth, customer_resources, customer_billing, admin_billing,
    webhooks, customer_kb, customer_main_account, admin_dashboard,
    customer_wallet, admin_features, customer_features,
    customer_bulk, admin_bulk,
    unified_auth,
)
from app.api.deps import get_current_user
from app.core.config import settings

router = APIRouter()


@router.get("/")
def read_root():
    return {"message": "Welcome to TGSC API V1"}


# 根据安全模式配置认证依赖
def get_auth_dependencies():
    """根据配置返回认证依赖"""
    if settings.SECURITY_ENABLED:
        return [Depends(get_current_user)]
    return []


# 公开路由 (不需要认证)
router.include_router(login.router, tags=["login"])
# Unified login: single URL for customers + admin (POST /api/v1/auth/login)
router.include_router(unified_auth.router, prefix="/auth", tags=["auth"])

# 受保护路由 (需要认证)
auth_deps = get_auth_dependencies()

router.include_router(
    users.router, 
    prefix="/users", 
    tags=["users"],
    dependencies=auth_deps
)
router.include_router(
    accounts.router, 
    prefix="/accounts", 
    tags=["accounts"],
    dependencies=auth_deps
)
router.include_router(
    proxies.router, 
    prefix="/proxies", 
    tags=["proxies"],
    dependencies=auth_deps
)
router.include_router(
    registration.router, 
    prefix="/registration", 
    tags=["registration"],
    dependencies=auth_deps
)
router.include_router(
    system.router, 
    prefix="/system", 
    tags=["system"],
    dependencies=auth_deps
)
router.include_router(
    tasks.router, 
    prefix="/tasks", 
    tags=["tasks"],
    dependencies=auth_deps
)
router.include_router(
    scraping.router, 
    prefix="/scraping", 
    tags=["scraping"],
    dependencies=auth_deps
)
router.include_router(
    marketing.router, 
    prefix="/marketing", 
    tags=["marketing"],
    dependencies=auth_deps
)
router.include_router(
    warmup.router, 
    prefix="/warmup", 
    tags=["warmup"],
    dependencies=auth_deps
)
router.include_router(
    ai.router,
    prefix="/ai",
    tags=["ai"],
    dependencies=auth_deps
)
router.include_router(
    ai_usage.router,
    prefix="/ai/usage",
    tags=["ai-usage"],
    dependencies=auth_deps,
)
router.include_router(
    script.router, 
    prefix="/scripts", 
    tags=["scripts"],
    dependencies=auth_deps
)
router.include_router(
    ws.router, 
    tags=["websocket"]
)
router.include_router(
    crm.router, 
    prefix="/crm", 
    tags=["crm"],
    dependencies=auth_deps
)
router.include_router(
    logs.router, 
    prefix="/logs", 
    tags=["logs"],
    dependencies=auth_deps
)
router.include_router(
    monitor.router, 
    prefix="/monitors", 
    tags=["monitors"],
    dependencies=auth_deps
)
router.include_router(
    invite.router, 
    prefix="/invites", 
    tags=["invites"],
    dependencies=auth_deps
)

# 战略升级模块
router.include_router(
    campaigns.router, 
    prefix="/campaigns", 
    tags=["campaigns"],
    dependencies=auth_deps
)
router.include_router(
    source_groups.router, 
    prefix="/source-groups", 
    tags=["source-groups"],
    dependencies=auth_deps
)
router.include_router(
    funnel_groups.router, 
    prefix="/funnel-groups", 
    tags=["funnel-groups"],
    dependencies=auth_deps
)
router.include_router(
    personas.router, 
    prefix="/personas", 
    tags=["personas"],
    dependencies=auth_deps
)
router.include_router(
    knowledge_bases.router, 
    prefix="/knowledge-bases", 
    tags=["knowledge-bases"],
    dependencies=auth_deps
)
router.include_router(
    workflow.router,
    prefix="/workflow",
    tags=["workflow"],
    dependencies=auth_deps
)
router.include_router(
    monitoring.router,
    prefix="/monitoring",
    tags=["monitoring"],
    dependencies=auth_deps
)

# ── TG1.AI 客户租户接口（独立鉴权，不走 admin auth_deps）──────────────────
# customer_auth: 注册 / 登录 / me（公开，自身处理鉴权）
# customer_resources: 客户视角的资源列表（依赖 get_current_customer）
router.include_router(
    customer_auth.router,
    prefix="/customer",
    tags=["customer-auth"],
)
router.include_router(
    customer_resources.router,
    prefix="/customer",
    tags=["customer-resources"],
)
router.include_router(
    customer_billing.router,
    prefix="/customer",
    tags=["customer-billing"],
)
# Epic 4.1 — customer KB CRUD + upload (writes; reads still on customer_resources)
router.include_router(
    customer_kb.router,
    prefix="/customer/knowledge-bases",
    tags=["customer-kb"],
)
# Epic 5.0 — customer main account QR login
router.include_router(
    customer_main_account.router,
    prefix="/customer/main-account",
    tags=["customer-main-account"],
)
# Bulk Send W1 — customer wallet (topup / balance / transactions)
router.include_router(
    customer_wallet.router,
    prefix="/customer/wallet",
    tags=["customer-wallet"],
)
# Feature Pack W2 — customer feature visibility + cost estimate + usage
router.include_router(
    customer_features.router,
    prefix="/customer/features",
    tags=["customer-features"],
)
# Bulk Send W2 — customer bulk batches (create draft / list / detail / cancel)
router.include_router(
    customer_bulk.router,
    prefix="/customer/bulk",
    tags=["customer-bulk"],
)
# Bulk Send W5 — admin force-pause / force-cancel + cross-customer batch list
router.include_router(
    admin_bulk.router,
    prefix="/admin/bulk",
    tags=["admin-bulk"],
)
# Epic 6.0 — admin business-ops dashboard
router.include_router(
    admin_dashboard.router,
    prefix="/admin/dashboard",
    tags=["admin-dashboard"],
    dependencies=auth_deps,
)

# ── Admin-facing billing (Epic 2 MVP, requires admin auth) ───────────────
router.include_router(
    admin_billing.router,
    prefix="/admin/billing",
    tags=["admin-billing"],
    dependencies=auth_deps,  # also require admin via get_current_admin
)
# Feature Pack W2 — admin feature management
router.include_router(
    admin_features.router,
    prefix="/admin",
    tags=["admin-features"],
    dependencies=auth_deps,
)

# ── Payment gateway webhooks (Epic 2.5, public, signature-verified) ──────
router.include_router(
    webhooks.router,
    prefix="/webhooks",
    tags=["webhooks"],
)