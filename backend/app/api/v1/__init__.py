from fastapi import APIRouter, Depends
from app.api.v1.endpoints import (
    accounts, proxies, registration, login, system, tasks, scraping, marketing, 
    warmup, ai, script, ws, crm, logs, monitor, invite, users,
    campaigns, source_groups, funnel_groups, personas, knowledge_bases, workflow
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