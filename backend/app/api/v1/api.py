from fastapi import APIRouter, Depends
from app.api.deps import get_current_user
from app.api.v1.endpoints import (
    login, users, accounts, proxies, system, tasks,
    scraping, marketing, ai, script, ws, crm, logs, warmup, monitor, invite,
    campaigns, source_groups, funnel_groups, personas, knowledge_bases, workflow,
    registration
)

api_router = APIRouter()

api_router.include_router(login.router, tags=["login"])
api_router.include_router(users.router, prefix="/users", tags=["users"], dependencies=[Depends(get_current_user)])
api_router.include_router(accounts.router, prefix="/accounts", tags=["accounts"], dependencies=[Depends(get_current_user)])
api_router.include_router(proxies.router, prefix="/proxies", tags=["proxies"], dependencies=[Depends(get_current_user)])
api_router.include_router(system.router, prefix="/system", tags=["system"], dependencies=[Depends(get_current_user)])
api_router.include_router(tasks.router, prefix="/tasks", tags=["tasks"], dependencies=[Depends(get_current_user)])
api_router.include_router(scraping.router, prefix="/scraping", tags=["scraping"], dependencies=[Depends(get_current_user)])
api_router.include_router(marketing.router, prefix="/marketing", tags=["marketing"], dependencies=[Depends(get_current_user)])
api_router.include_router(ai.router, prefix="/ai", tags=["ai"], dependencies=[Depends(get_current_user)])
api_router.include_router(script.router, prefix="/scripts", tags=["scripts"], dependencies=[Depends(get_current_user)])
api_router.include_router(ws.router, tags=["websocket"])
api_router.include_router(crm.router, prefix="/crm", tags=["crm"], dependencies=[Depends(get_current_user)])
api_router.include_router(logs.router, prefix="/logs", tags=["logs"], dependencies=[Depends(get_current_user)])
api_router.include_router(warmup.router, prefix="/warmup", tags=["warmup"], dependencies=[Depends(get_current_user)])
api_router.include_router(monitor.router, prefix="/monitors", tags=["monitors"], dependencies=[Depends(get_current_user)])
api_router.include_router(invite.router, prefix="/invites", tags=["invites"], dependencies=[Depends(get_current_user)])

# 战略升级模块
api_router.include_router(campaigns.router, prefix="/campaigns", tags=["campaigns"], dependencies=[Depends(get_current_user)])
api_router.include_router(source_groups.router, prefix="/source-groups", tags=["source-groups"], dependencies=[Depends(get_current_user)])
api_router.include_router(funnel_groups.router, prefix="/funnel-groups", tags=["funnel-groups"], dependencies=[Depends(get_current_user)])
api_router.include_router(personas.router, prefix="/personas", tags=["personas"], dependencies=[Depends(get_current_user)])
api_router.include_router(knowledge_bases.router, prefix="/knowledge-bases", tags=["knowledge-bases"], dependencies=[Depends(get_current_user)])
api_router.include_router(workflow.router, prefix="/workflow", tags=["workflow"], dependencies=[Depends(get_current_user)])
api_router.include_router(registration.router, prefix="/registration", tags=["registration"], dependencies=[Depends(get_current_user)])