from fastapi import APIRouter, Depends
from app.api.v1.endpoints import accounts, proxies, registration, login, system, tasks, scraping, marketing, warmup, ai, script, ws, crm, logs, monitor, invite
from app.api.deps import get_current_user

router = APIRouter()

@router.get("/")
def read_root():
    return {"message": "Welcome to TGSC API V1"}

# Note: Authentication temporarily disabled for development. Enable in production.
router.include_router(login.router, tags=["login"])
router.include_router(accounts.router, prefix="/accounts", tags=["accounts"])
router.include_router(proxies.router, prefix="/proxies", tags=["proxies"])
router.include_router(registration.router, prefix="/registration", tags=["registration"])
router.include_router(system.router, prefix="/system", tags=["system"])
router.include_router(tasks.router, prefix="/tasks", tags=["tasks"])
router.include_router(scraping.router, prefix="/scraping", tags=["scraping"])
router.include_router(marketing.router, prefix="/marketing", tags=["marketing"])
router.include_router(warmup.router, prefix="/warmup", tags=["warmup"])
router.include_router(ai.router, prefix="/ai", tags=["ai"])
router.include_router(script.router, prefix="/scripts", tags=["scripts"])
router.include_router(ws.router, tags=["websocket"])
router.include_router(crm.router, prefix="/crm", tags=["crm"])
router.include_router(logs.router, prefix="/logs", tags=["logs"])
router.include_router(monitor.router, prefix="/monitors", tags=["monitors"])
router.include_router(invite.router, prefix="/invites", tags=["invites"])