import os
import json
import re
import shutil
import logging
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query, Body, Request
from sqlmodel import Session, select, func
from datetime import datetime
from pydantic import BaseModel

from app.core.db import get_session
from app.core import security
from app.models.account import Account, AccountCreate, AccountRead
from app.models.proxy import Proxy
from app.services.proxy_assigner import auto_assign_proxy
from app.services.session_parser import parse_session_file
from app.worker import check_account_status, import_mega_accounts

logger = logging.getLogger(__name__)

router = APIRouter()

class AIConfigUpdate(BaseModel):
    auto_reply: bool = False
    persona_prompt: Optional[str] = None

class ProfileUpdate(BaseModel):
    first_name: Optional[str] = None
    last_name: Optional[str] = None
    bio: Optional[str] = None

class TwoFAUpdate(BaseModel):
    password: Optional[str] = None
    hint: Optional[str] = None
    email: Optional[str] = None

class AutoUpdateOptions(BaseModel):
    update_profile: bool = False
    update_username: bool = False
    update_photo: bool = False
    update_2fa: bool = False

class MegaImportRequest(BaseModel):
    urls: List[str]
    target_channels: Optional[str] = "kltgsc"  # 养号目标频道，逗号分隔
    # 安全默认值：导入后不自动触碰 Telegram
    auto_check: bool = False   # 导入完成后自动验活（低风险验活模式）
    auto_warmup: bool = False  # 导入完成后自动启动养号/热身任务

class RoleTagsUpdate(BaseModel):
    role: Optional[str] = None
    tags: Optional[str] = None
    tier: Optional[str] = None

@router.get("/", response_model=List[AccountRead])
def get_accounts(
    session: Session = Depends(get_session),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    status: Optional[str] = None,
    role: Optional[str] = None
):
    """获取账号列表"""
    try:
        query = select(Account)
        if status:
            query = query.where(Account.status == status)
        if role:
            query = query.where(Account.role == role)
        query = query.offset(skip).limit(limit).order_by(Account.created_at.desc())
        accounts = session.exec(query).all()
        return accounts
    except Exception as e:
        logger.error(f"Error fetching accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/count")
def get_account_count(
    session: Session = Depends(get_session),
    status: Optional[str] = None
):
    """获取账号数量"""
    try:
        query = select(func.count(Account.id))
        if status:
            query = query.where(Account.status == status)
        count = session.exec(query).one()
        return {"total": count, "count": count, "status": status}
    except Exception as e:
        logger.error(f"Error counting accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/{account_id}")
def get_account(
    account_id: int,
    session: Session = Depends(get_session)
):
    """获取单个账号详情"""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    return account

@router.post("/")
def create_account(
    account: AccountCreate,
    session: Session = Depends(get_session)
):
    """创建账号"""
    db_account = Account.model_validate(account)
    session.add(db_account)
    session.commit()
    session.refresh(db_account)
    return db_account

@router.post("/batch/delete")
def delete_accounts_batch(
    account_ids: List[int] = Body(..., embed=True),
    session: Session = Depends(get_session)
):
    """批量删除账号"""
    accounts = session.exec(select(Account).where(Account.id.in_(account_ids))).all()
    deleted_count = 0
    for account in accounts:
        # 删除关联的 session 文件
        if account.session_file_path:
            import os
            try:
                if os.path.exists(account.session_file_path):
                    os.remove(account.session_file_path)
                # 也删除可能存在的 .session.telethon 文件
                telethon_path = account.session_file_path + ".telethon"
                if os.path.exists(telethon_path):
                    os.remove(telethon_path)
            except Exception:
                pass
        session.delete(account)
        deleted_count += 1
    session.commit()
    return {"message": f"已删除 {deleted_count} 个账号", "deleted_count": deleted_count}

@router.delete("/{account_id}")
def delete_account(
    account_id: int,
    session: Session = Depends(get_session)
):
    """删除账号"""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    session.delete(account)
    session.commit()
    return {"message": "Account deleted"}

@router.put("/{account_id}/role")
def update_account_role(
    account_id: int,
    update_data: RoleTagsUpdate,
    session: Session = Depends(get_session)
):
    """更新账号角色、标签和分级"""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    if update_data.role is not None:
        if update_data.role not in ["worker", "master", "support", "sales"]:
            raise HTTPException(status_code=400, detail="Invalid role")
        account.role = update_data.role
    
    if update_data.tags is not None:
        account.tags = update_data.tags

    if update_data.tier is not None:
        if update_data.tier not in ["tier1", "tier2", "tier3"]:
             raise HTTPException(status_code=400, detail="Invalid tier")
        account.tier = update_data.tier
        
    session.add(account)
    session.commit()
    session.refresh(account)
    return account

@router.post("/batch/role")
def update_accounts_role_batch(
    request: dict = Body(...),
    session: Session = Depends(get_session)
):
    """批量更新账号角色"""
    account_ids = request.get("account_ids", [])
    role = request.get("role")
    tags = request.get("tags")
    tier = request.get("tier")
    
    if not account_ids:
        raise HTTPException(status_code=400, detail="account_ids required")
    
    if role and role not in ["worker", "master", "support", "sales"]:
        raise HTTPException(status_code=400, detail="Invalid role")
        
    if tier and tier not in ["tier1", "tier2", "tier3"]:
        raise HTTPException(status_code=400, detail="Invalid tier")
    
    accounts = session.exec(select(Account).where(Account.id.in_(account_ids))).all()
    updated = 0
    for account in accounts:
        if role:
            account.role = role
        if tags is not None:
            account.tags = tags
        if tier:
            account.tier = tier
        session.add(account)
        updated += 1

    session.commit()
    return {"updated": updated}

@router.post("/upload")
async def upload_session(
    request: Request,
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """上传单个 Session 文件"""
    os.makedirs("sessions", exist_ok=True)

    # 安全: 防止路径穿越，仅使用文件名的基本部分
    safe_filename = os.path.basename(file.filename)
    if not safe_filename or safe_filename.startswith('.'):
        raise HTTPException(status_code=400, detail="无效的文件名")
    file_location = os.path.join("sessions", safe_filename)
    # 确认最终路径在 sessions 目录内
    if not os.path.realpath(file_location).startswith(os.path.realpath("sessions")):
        raise HTTPException(status_code=400, detail="非法文件路径")
    with open(file_location, "wb+") as file_object:
        shutil.copyfileobj(file.file, file_object)
    
    parsed_phone, extra_info = parse_session_file(file_location, file.filename)
    
    if not parsed_phone:
        raise HTTPException(status_code=400, detail="无法解析手机号")
    
    # 自动加密 session 文件
    try:
        from app.services.session_encryption_service import encrypt_new_session_file
        encrypt_new_session_file(file_location)
        logger.info(f"Session file encrypted: {file_location}")
    except Exception as e:
        logger.warning(f"Failed to encrypt session file: {e}")
    
    # 检查账号是否已存在
    existing = session.exec(
        select(Account).where(Account.phone_number == parsed_phone)
    ).first()
    
    if existing:
        existing.session_file_path = file_location
        existing.status = "uploaded"
        session.add(existing)
        session.commit()
        return {"message": "账号已更新", "account_id": existing.id, "encrypted": True}
    else:
        account = Account(
            phone_number=parsed_phone,
            session_file_path=file_location,
            session_string="",
            status="uploaded"
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        
        # 自动分配代理
        if not account.proxy_id:
            auto_assign_proxy(session, account)
        
        return {"message": "账号已创建", "account_id": account.id, "encrypted": True}

@router.post("/batch/upload")
def upload_sessions_batch(
    request: Request,
    files: List[UploadFile] = File(...),
    session: Session = Depends(get_session)
):
    """
    批量上传 Session 文件
    支持同时上传同名的 .json 文件以导入 API 信息
    """
    os.makedirs("sessions", exist_ok=True)
    
    results = {
        "created": 0,
        "updated": 0,
        "skipped": 0,
        "errors": []
    }
    
    # 1. 预处理 JSON 文件，建立映射
    json_info_map = {}  # phone -> json_data
    session_files = []
    
    for file in files:
        if file.filename.endswith('.json'):
            try:
                content = json.loads(file.file.read().decode('utf-8'))
                filename_phone = os.path.splitext(file.filename)[0]
                cleaned_phone = re.sub(r'[^\d]', '', filename_phone)
                if cleaned_phone:
                    phone_key = '+' + cleaned_phone
                    json_info_map[phone_key] = content
                if 'phone' in content:
                    inner_phone = str(content['phone'])
                    cleaned_inner = re.sub(r'[^\d]', '', inner_phone)
                    if cleaned_inner:
                        json_info_map['+' + cleaned_inner] = content
            except Exception as e:
                results["errors"].append(f"Failed to parse JSON {file.filename}: {str(e)}")
        elif file.filename.endswith('.session'):
            session_files.append(file)
    
    # 2. 处理 Session 文件
    for file in session_files:
        try:
            file_location = f"sessions/{file.filename}"
            with open(file_location, "wb+") as file_object:
                shutil.copyfileobj(file.file, file_object)
            
            parsed_phone, extra_info = parse_session_file(file_location, file.filename)
            
            if not parsed_phone:
                results["errors"].append(f"{file.filename}: 无法解析手机号")
                results["skipped"] += 1
                continue
            
            account_info = json_info_map.get(parsed_phone)
            
            api_id = None
            api_hash = None
            device_model = None
            system_version = None
            app_version = None
            
            if account_info:
                api_id = account_info.get('app_id')
                api_hash = account_info.get('app_hash')
                device_model = account_info.get('device')
                system_version = account_info.get('sdk')
                app_version = account_info.get('app_version')
            
            existing = session.exec(
                select(Account).where(Account.phone_number == parsed_phone)
            ).first()
            
            if existing:
                existing.session_file_path = file_location
                existing.status = "uploaded"
                if api_id: existing.api_id = api_id
                if api_hash: existing.api_hash = api_hash
                if device_model and not existing.device_model: existing.device_model = device_model
                if system_version and not existing.system_version: existing.system_version = system_version
                if app_version and not existing.app_version: existing.app_version = app_version
                session.add(existing)
                results["updated"] += 1
            else:
                account = Account(
                    phone_number=parsed_phone,
                    session_file_path=file_location,
                    session_string="",
                    status="uploaded",
                    api_id=api_id,
                    api_hash=api_hash,
                    device_model=device_model,
                    system_version=system_version,
                    app_version=app_version
                )
                session.add(account)
                results["created"] += 1
            
            session.commit()
            
            account = session.exec(
                select(Account).where(Account.phone_number == parsed_phone)
            ).first()
            if account and not account.proxy_id:
                auto_assign_proxy(session, account)
            
        except Exception as e:
            session.rollback()
            results["errors"].append(f"{file.filename}: {str(e)}")
            results["skipped"] += 1
    
    security.create_log(
        session, "upload_sessions_batch", "system",
        f"Batch uploaded: {results['created']} created, {results['updated']} updated",
        request.client.host if request.client else "unknown"
    )
    
    return {
        "message": "批量上传完成",
        "created": results["created"],
        "updated": results["updated"],
        "skipped": results["skipped"],
        "errors": results["errors"][:10]
    }

@router.post("/batch/check")
async def check_accounts_batch(
    account_ids: List[int] = Body(..., embed=True),
    session: Session = Depends(get_session)
):
    """批量检查账号状态"""
    tasks = []
    for account_id in account_ids:
        account = session.get(Account, account_id)
        if account:
            task = check_account_status.delay(account_id)
            tasks.append({"account_id": account_id, "task_id": task.id})
    
    return {
        "message": f"已提交 {len(tasks)} 个检查任务",
        "tasks": tasks,
        "account_count": len(tasks)
    }

@router.post("/{account_id}/check")
async def check_single_account(
    account_id: int,
    session: Session = Depends(get_session)
):
    """检查单个账号状态"""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # 异步执行检查任务
    task = check_account_status.delay(account_id)
    
    return {
        "message": "检查任务已提交",
        "task_id": task.id
    }


@router.post("/{account_id}/spambot-check")
async def check_spambot(
    account_id: int,
    session: Session = Depends(get_session)
):
    """
    深度检查账号状态 - 通过向 @SpamBot 发送请求获取详细受限信息
    
    返回信息包括:
    - 是否受限
    - 限制类型 (临时/永久)
    - 预计解除时间 (如果是临时限制)
    """
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    from app.services.telegram_client import check_spambot_status
    
    try:
        result = await check_spambot_status(account, db_session=session)
        
        # 根据结果更新账号状态
        if result.get("is_restricted"):
            if result.get("restriction_type") == "permanent":
                account.status = "banned"
            else:
                account.status = "spam_block"
            account.last_error = result.get("restriction_reason", "SpamBot 检测到限制")
        else:
            # 如果之前是 spam_block 状态，现在解除了
            if account.status == "spam_block":
                account.status = "active"
                account.last_error = None
        
        session.add(account)
        session.commit()
        
        return {
            "account_id": account_id,
            "phone": account.phone_number,
            **result
        }
    except Exception as e:
        logger.error(f"SpamBot check failed for account {account_id}: {e}")
        raise HTTPException(status_code=500, detail=f"检测失败: {str(e)}")


@router.put("/{account_id}/proxy")
def update_account_proxy(
    account_id: int,
    proxy_id: int = Body(..., embed=True),
    session: Session = Depends(get_session)
):
    """更新账号的代理"""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    if proxy_id:
        proxy = session.get(Proxy, proxy_id)
        if not proxy:
            raise HTTPException(status_code=404, detail="Proxy not found")
    
    account.proxy_id = proxy_id
    session.add(account)
    session.commit()
    
    return {"message": "代理已更新"}

class BatchSendMessageRequest(BaseModel):
    account_ids: List[int]
    message: str
    username: str

@router.post("/batch/send_message")
async def send_message_batch(
    request: BatchSendMessageRequest,
    session: Session = Depends(get_session)
):
    """批量发送测试消息"""
    results = []
    
    # 简单的直接发送实现 (同步等待，仅用于测试)
    # 生产环境应该使用 Celery 任务
    from app.services.telegram_client import send_message_with_client
    
    for account_id in request.account_ids:
        account = session.get(Account, account_id)
        if account:
            try:
                # 尝试直接发送
                success, msg = await send_message_with_client(account, request.username, request.message, db_session=session)
                results.append({
                    "account_id": account_id,
                    "status": "success" if success else "failed",
                    "detail": msg
                })
            except Exception as e:
                results.append({
                    "account_id": account_id,
                    "status": "failed", 
                    "detail": str(e)
                })
        else:
             results.append({
                "account_id": account_id,
                "status": "failed",
                "detail": "Account not found"
            })
            
    return {
        "message": f"已处理 {len(results)} 个发送请求",
        "results": results
    }

@router.post("/{account_id}/update_profile")
async def update_account_profile(
    account_id: int,
    data: ProfileUpdate,
    session: Session = Depends(get_session)
):
    """更新账号资料"""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # TODO: 实际调用 Telegram API 更新资料
    return {"message": "资料更新任务已提交", "account_id": account_id}

@router.post("/{account_id}/update_username")
async def update_account_username(
    account_id: int,
    username: str = Body(..., embed=True),
    session: Session = Depends(get_session)
):
    """更新账号用户名"""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # TODO: 实际调用 Telegram API 更新用户名
    return {"message": "用户名更新任务已提交", "account_id": account_id}

@router.post("/{account_id}/update_2fa")
async def update_account_2fa(
    account_id: int,
    data: TwoFAUpdate,
    session: Session = Depends(get_session)
):
    """更新账号 2FA"""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # TODO: 实际调用 Telegram API 更新 2FA
    return {"message": "2FA 更新任务已提交", "account_id": account_id}

@router.post("/{account_id}/update_photo")
async def update_account_photo(
    account_id: int,
    file: UploadFile = File(...),
    session: Session = Depends(get_session)
):
    """更新账号头像"""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # TODO: 实际调用 Telegram API 更新头像
    return {"message": "头像更新任务已提交", "account_id": account_id}

@router.post("/{account_id}/update_photo/random")
async def update_account_photo_random(
    account_id: int,
    session: Session = Depends(get_session)
):
    """使用随机头像更新账号"""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # TODO: 生成随机头像并更新
    return {"message": "随机头像更新任务已提交", "account_id": account_id}

@router.post("/{account_id}/auto_update")
async def auto_update_account(
    account_id: int,
    options: AutoUpdateOptions,
    session: Session = Depends(get_session)
):
    """自动更新账号信息"""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    # TODO: 实际执行自动更新
    return {"message": "自动更新任务已提交", "account_id": account_id, "options": options.dict()}

@router.put("/{account_id}/ai_config")
def update_account_ai_config(
    account_id: int,
    config: AIConfigUpdate,
    session: Session = Depends(get_session)
):
    """更新账号 AI 配置"""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    account.auto_reply = config.auto_reply
    account.persona_prompt = config.persona_prompt
    session.add(account)
    session.commit()
    
    return {"message": "AI 配置已更新"}

@router.post("/import/mega")
async def import_from_mega(
    request: MegaImportRequest,
    session: Session = Depends(get_session)
):
    """从 MEGA 链接导入账号"""
    from app.worker import create_warmup_after_imports
    
    task_ids = []
    urls = []
    for url in request.urls:
        # 传递 target_channels 参数到 worker 任务
        task = import_mega_accounts.delay(url, request.target_channels)
        task_ids.append(task.id)
        urls.append(url)
    
    # 只有在需要自动验活/自动养号时才创建汇总任务
    if task_ids and (request.auto_check or request.auto_warmup):
        warmup_task = create_warmup_after_imports.delay(
            task_ids,
            request.target_channels or "kltgsc",
            request.auto_check,
            request.auto_warmup,
        )
        logger.info(f"Created warmup aggregator task: {warmup_task.id}")
    
    return {
        "message": f"已提交 {len(task_ids)} 个导入任务",
        "task_ids": task_ids,
        "urls": urls
    }


# =====================
# 战斗角色管理
# =====================

class CombatRoleUpdate(BaseModel):
    combat_role: str  # cannon/scout/actor/sniper

class BatchCombatRoleUpdate(BaseModel):
    account_ids: List[int]
    combat_role: str


COMBAT_ROLE_CONFIG = {
    "cannon": {
        "display_name": "炮灰组",
        "description": "廉价弹药，用于高风险群发、拉人",
        "daily_limit": 100,
        "allowed_actions": ["mass_dm", "invite", "spam"]
    },
    "scout": {
        "display_name": "侦察组",
        "description": "情报收集，潜伏采集、监控",
        "daily_limit": 0,
        "allowed_actions": ["scrape", "monitor", "join_group"]
    },
    "actor": {
        "display_name": "演员组",
        "description": "信任铺垫，炒群造势",
        "daily_limit": 50,
        "allowed_actions": ["shill", "script_chat"]
    },
    "sniper": {
        "display_name": "狙击组",
        "description": "精准打击，高价值客户转化",
        "daily_limit": 20,
        "allowed_actions": ["precision_dm"]
    }
}


@router.get("/combat-roles/config")
def get_combat_role_config():
    """获取战斗角色配置"""
    return COMBAT_ROLE_CONFIG


@router.get("/combat-roles/stats")
def get_combat_role_stats(
    session: Session = Depends(get_session)
):
    """获取各角色账号统计"""
    stats = {}
    for role in COMBAT_ROLE_CONFIG.keys():
        total = session.exec(
            select(func.count(Account.id)).where(Account.combat_role == role)
        ).one()
        active = session.exec(
            select(func.count(Account.id)).where(
                Account.combat_role == role,
                Account.status == "active"
            )
        ).one()
        stats[role] = {
            "total": total,
            "active": active,
            "display_name": COMBAT_ROLE_CONFIG[role]["display_name"]
        }
    return stats


@router.put("/{account_id}/combat-role")
def update_account_combat_role(
    account_id: int,
    update: CombatRoleUpdate,
    session: Session = Depends(get_session)
):
    """更新账号战斗角色"""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    if update.combat_role not in COMBAT_ROLE_CONFIG:
        raise HTTPException(status_code=400, detail=f"Invalid combat role. Must be one of: {list(COMBAT_ROLE_CONFIG.keys())}")
    
    old_role = account.combat_role
    account.combat_role = update.combat_role
    session.add(account)
    session.commit()
    
    return {
        "success": True,
        "account_id": account_id,
        "old_role": old_role,
        "new_role": update.combat_role
    }


@router.post("/combat-roles/batch-assign")
def batch_assign_combat_role(
    update: BatchCombatRoleUpdate,
    session: Session = Depends(get_session)
):
    """批量分配战斗角色"""
    if update.combat_role not in COMBAT_ROLE_CONFIG:
        raise HTTPException(status_code=400, detail=f"Invalid combat role")
    
    accounts = session.exec(select(Account).where(Account.id.in_(update.account_ids))).all()
    updated_count = 0
    for account in accounts:
        account.combat_role = update.combat_role
        session.add(account)
        updated_count += 1

    session.commit()
    return {
        "success": True,
        "updated_count": updated_count,
        "combat_role": update.combat_role
    }


@router.get("/by-combat-role/{combat_role}", response_model=List[AccountRead])
def get_accounts_by_combat_role(
    combat_role: str,
    skip: int = 0,
    limit: int = 100,
    status: Optional[str] = None,
    session: Session = Depends(get_session)
):
    """按战斗角色获取账号"""
    if combat_role not in COMBAT_ROLE_CONFIG:
        raise HTTPException(status_code=400, detail=f"Invalid combat role")
    
    query = select(Account).where(Account.combat_role == combat_role)
    if status:
        query = query.where(Account.status == status)
    query = query.offset(skip).limit(limit).order_by(Account.health_score.desc())
    
    return session.exec(query).all()


@router.post("/{account_id}/promote")
def promote_account(
    account_id: int,
    session: Session = Depends(get_session)
):
    """晋升账号角色"""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    promotion_path = ["cannon", "scout", "actor", "sniper"]
    current_idx = promotion_path.index(account.combat_role) if account.combat_role in promotion_path else 0
    
    if current_idx >= len(promotion_path) - 1:
        raise HTTPException(status_code=400, detail="Account is already at highest role")
    
    new_role = promotion_path[current_idx + 1]
    old_role = account.combat_role
    account.combat_role = new_role
    session.add(account)
    session.commit()
    
    return {
        "success": True,
        "account_id": account_id,
        "old_role": old_role,
        "new_role": new_role,
        "message": f"晋升成功: {COMBAT_ROLE_CONFIG[old_role]['display_name']} → {COMBAT_ROLE_CONFIG[new_role]['display_name']}"
    }


@router.post("/{account_id}/demote")
def demote_account(
    account_id: int,
    session: Session = Depends(get_session)
):
    """降级账号角色"""
    account = session.get(Account, account_id)
    if not account:
        raise HTTPException(status_code=404, detail="Account not found")
    
    promotion_path = ["cannon", "scout", "actor", "sniper"]
    current_idx = promotion_path.index(account.combat_role) if account.combat_role in promotion_path else 0
    
    if current_idx <= 0:
        raise HTTPException(status_code=400, detail="Account is already at lowest role")
    
    new_role = promotion_path[current_idx - 1]
    old_role = account.combat_role
    account.combat_role = new_role
    session.add(account)
    session.commit()
    
    return {
        "success": True,
        "account_id": account_id,
        "old_role": old_role,
        "new_role": new_role,
        "message": f"降级完成: {COMBAT_ROLE_CONFIG[old_role]['display_name']} → {COMBAT_ROLE_CONFIG[new_role]['display_name']}"
    }
