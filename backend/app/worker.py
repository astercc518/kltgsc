import random
import asyncio
import logging
import os
import tempfile
import zipfile
import shutil
from typing import List, Optional, Dict
from sqlmodel import Session, select
from app.core.db import engine
from sqlmodel import Session as DBSession
from app.core.celery_app import celery_app
from app.models.account import Account
from app.models.target_user import TargetUser
from app.models.send_task import SendTask, SendRecord
from app.services.telegram_client import send_message_with_client, check_account_with_client
from app.core.concurrency import get_redis_semaphore

logger = logging.getLogger(__name__)

# --- Re-defined task with actual logic ---

@celery_app.task(bind=True)
def execute_send_task(self, task_id: int, account_ids: List[int], target_user_ids: List[int]):
    """
    Execute marketing send task
    """
    logger.info(f"Starting Send Task {task_id} with {len(account_ids)} accounts for {len(target_user_ids)} targets")
    
    semaphore = get_redis_semaphore(limit=5) # Or use env var
    
    with Session(engine) as session:
        task = session.get(SendTask, task_id)
        if not task:
            logger.error(f"Task {task_id} not found")
            return
            
        task.status = "running"
        session.add(task)
        session.commit()
        
        # Simple distribution logic: Round Robin
        account_pool = session.exec(select(Account).where(Account.id.in_(account_ids))).all()
        target_pool = session.exec(select(TargetUser).where(TargetUser.id.in_(target_user_ids))).all()
        
        if not account_pool:
            task.status = "failed"
            session.add(task)
            session.commit()
            return
            
        # Async execution context
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        async def process_batch():
            acc_idx = 0
            for target in target_pool:
                # Check task status (pause/cancel check)
                session.refresh(task)
                if task.status != "running":
                    break
                    
                account = account_pool[acc_idx % len(account_pool)]
                acc_idx += 1
                
                # Wait for random delay
                delay = random.randint(task.min_delay, task.max_delay)
                logger.info(f"Waiting {delay}s before sending to {target.telegram_id}")
                await asyncio.sleep(delay)
                
                try:
                    # Concurrency control
                    with semaphore.acquire_lock():
                        # Determine username or user_id
                        target_identifier = target.username or target.telegram_id
                        success, msg = await send_message_with_client(
                            account, 
                            target_identifier, 
                            task.message_content, 
                            db_session=session
                        )
                        
                        # Record result
                        record = SendRecord(
                            task_id=task.id,
                            account_id=account.id,
                            target_user_id=target.id,
                            status="success" if success else "failed",
                            error_message=msg if not success else None
                        )
                        session.add(record)
                        
                        if success:
                            task.success_count += 1
                        else:
                            task.fail_count += 1
                            
                        session.add(task)
                        session.commit()
                        
                except Exception as e:
                    logger.error(f"Error sending to {target.telegram_id}: {e}")
                    task.fail_count += 1
                    session.add(task)
                    session.commit()
                    
        # Run the batch
        loop.run_until_complete(process_batch())
        
        # Finalize
        session.refresh(task)
        if task.status == "running":
            task.status = "completed"
            session.add(task)
            session.commit()
            
    logger.info(f"Task {task_id} finished")


@celery_app.task(bind=True)
def check_account_status(self, account_id: int):
    """
    Check single account status by verifying Telegram connection
    """
    logger.info(f"Checking account status for ID: {account_id}")
    
    with Session(engine) as session:
        account = session.get(Account, account_id)
        if not account:
            logger.error(f"Account {account_id} not found")
            return {"success": False, "error": "Account not found"}
        
        # Get proxy if bound
        proxy = account.proxy if account.proxy_id else None
        
        # Ensure device fingerprint exists BEFORE connection attempt
        if not account.device_model:
            from app.services.device_generator import DeviceGenerator
            dev_info = DeviceGenerator.generate()
            account.device_model = dev_info["device_model"]
            account.system_version = dev_info["system_version"]
            account.app_version = dev_info["app_version"]
            session.add(account)
            session.commit()
            session.refresh(account)
            logger.info(f"Generated permanent device fingerprint for account {account_id}: {account.device_model}")
        
        # Always create a new event loop for Celery tasks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            status, error_msg, last_active, device_info = loop.run_until_complete(
                # 默认使用低风险验活：只 connect/get_me，不发消息、不做搜索测试
                check_account_with_client(account, proxy, mode="safe")
            )
            
            # Auto-warmup for spam_block accounts
            if status == "spam_block":
                try:
                    from app.models.warmup_task import WarmupTask
                    import json
                    
                    # Check if already in warmup
                    existing_tasks = session.exec(select(WarmupTask).where(WarmupTask.status.in_(["pending", "running"]))).all()
                    already_warming = False
                    for t in existing_tasks:
                        try:
                            t_ids = json.loads(t.account_ids_json)
                            if account_id in t_ids:
                                already_warming = True
                                break
                        except: pass
                    
                    if not already_warming:
                        logger.info(f"Auto-starting warmup for restricted account {account_id}")
                        new_task = WarmupTask(
                            name=f"Auto Warmup - {account.phone_number}",
                            action_type="mixed",
                            account_ids_json=json.dumps([account_id]),
                            status="pending",
                            target_channels="Telegram" 
                        )
                        session.add(new_task)
                        session.commit()
                        session.refresh(new_task)
                        
                        # Trigger task
                        celery_app.send_task("app.worker.execute_warmup_task", args=[new_task.id])
                except Exception as e:
                    logger.error(f"Failed to auto-start warmup for {account_id}: {e}")

            # Update account status
            account.status = status
            if last_active:
                account.last_active = last_active
            if device_info and not account.device_model:
                account.device_model = device_info.get("device_model")
                account.system_version = device_info.get("system_version")
                account.app_version = device_info.get("app_version")
            
            # 已封禁账号自动解除代理绑定
            if status == "banned" and account.proxy_id:
                logger.info(f"Account {account_id} is banned, releasing proxy {account.proxy_id}")
                account.proxy_id = None
            
            session.add(account)
            session.commit()
            
            success = status == "active"
            return {
                "success": success,
                "status": status,
                "message": error_msg if error_msg else "OK",
                "account_id": account_id
            }
        except Exception as e:
            logger.error(f"Error checking account {account_id}: {e}")
            account.status = "error"
            session.add(account)
            session.commit()
            return {"success": False, "error": str(e)}
        finally:
            # Properly close the event loop
            try:
                loop.close()
            except:
                pass


@celery_app.task(bind=True)
def import_mega_accounts(self, mega_url: str, target_channels: str = "kltgsc"):
    """
    Import accounts from MEGA link (download, extract, convert sessions)
    This is a placeholder - actual MEGA download requires megatools installed
    target_channels: 养号目标频道，逗号分隔
    """
    logger.info(f"Starting MEGA import from: {mega_url}")
    
    self.update_state(state='PROGRESS', meta={'status': 'downloading', 'message': '正在下载...', 'url': mega_url})
    
    import subprocess
    
    try:
        # Create temp directory
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Try megadl first (megatools package)
            result = subprocess.run(
                ['megadl', '--path', temp_dir, mega_url],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            
            if result.returncode != 0:
                raise Exception(f"megadl failed: {result.stderr}")
            
            # List all files in temp_dir after download
            all_files_after_download = []
            for root, dirs, files in os.walk(temp_dir):
                for f in files:
                    all_files_after_download.append(os.path.join(root, f))
            
            self.update_state(state='PROGRESS', meta={'status': 'extracting', 'message': '正在解压...', 'url': mega_url})
            
            # Find and extract zip files
            imported_count = 0
            imported_account_ids = []  # 记录本次导入的账号ID
            errors = []
            
            # Helper to import a session file
            def do_import_session(filepath: str, filename: str) -> bool:
                nonlocal imported_count
                self.update_state(state='PROGRESS', meta={'status': 'converting', 'message': f'正在导入 {filename}...', 'url': mega_url})
                try:
                    # Extract phone number from filename
                    phone = os.path.splitext(filename)[0]
                    # Clean up phone number
                    phone = phone.replace('_', '').replace(' ', '')
                    if not phone.startswith('+'):
                        phone = '+' + phone
                    
                    # Copy session file to sessions directory
                    # Fix path to be within /app (shared volume) instead of root /sessions
                    sessions_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sessions')
                    os.makedirs(sessions_dir, exist_ok=True)
                    dest_path = os.path.join(sessions_dir, filename)
                    shutil.copy2(filepath, dest_path)
                    
                    # Create account in database
                    with Session(engine) as db_session:
                        # Check if account already exists
                        existing = db_session.exec(
                            select(Account).where(Account.phone_number == phone)
                        ).first()
                        
                        if existing:
                            errors.append(f"Account {phone} already exists")
                            return False
                        
                        account = Account(
                            phone_number=phone,
                            status="init",  # 导入完成但尚未触碰 Telegram
                            session_file_path=dest_path
                        )
                        db_session.add(account)
                        db_session.commit()
                        db_session.refresh(account)
                        imported_count += 1
                        imported_account_ids.append(account.id)  # 记录账号ID
                        return True
                except Exception as e:
                    errors.append(f"Failed to import {filename}: {e}")
                    return False
            
            for root, dirs, files in os.walk(temp_dir):
                for f in files:
                    filepath = os.path.join(root, f)
                    
                    # Handle zip files
                    if f.endswith('.zip'):
                        try:
                            extract_dir = os.path.join(temp_dir, 'extracted')
                            os.makedirs(extract_dir, exist_ok=True)
                            with zipfile.ZipFile(filepath, 'r') as zf:
                                namelist = zf.namelist()
                                zf.extractall(extract_dir)
                        except Exception as e:
                            errors.append(f"Failed to extract {f}: {e}")
                    
                    # Handle RAR files
                    elif f.endswith('.rar'):
                        try:
                            extract_dir = os.path.join(temp_dir, 'extracted')
                            os.makedirs(extract_dir, exist_ok=True)
                            # Use unrar command to extract
                            rar_result = subprocess.run(
                                ['unrar', 'x', '-o+', filepath, extract_dir + '/'],
                                capture_output=True,
                                text=True,
                                timeout=120
                            )
                            if rar_result.returncode != 0:
                                errors.append(f"Failed to extract {f}: {rar_result.stderr}")
                        except FileNotFoundError:
                            errors.append(f"unrar not installed, cannot extract {f}")
                        except Exception as e:
                            errors.append(f"Failed to extract {f}: {e}")
                    
                    # Handle session files directly
                    elif f.endswith('.session'):
                        do_import_session(filepath, f)
                    else:
                        # Skip other file types
                        pass
            
            # Process extracted files
            extract_dir = os.path.join(temp_dir, 'extracted')
            if os.path.exists(extract_dir):
                extracted_files = []
                for root, dirs, files in os.walk(extract_dir):
                    for f in files:
                        extracted_files.append(os.path.join(root, f))
                
                # First check for tdata directories
                for root, dirs, files in os.walk(extract_dir):
                    if 'tdata' in dirs:
                        tdata_path = os.path.join(root, 'tdata')
                        
                        # Extract phone from parent directory name
                        parent_name = os.path.basename(root)
                        phone = None
                        import re as regex
                        match = regex.search(r'\+?\d{7,15}', parent_name)
                        if match:
                            phone = match.group(0)
                        if phone and not phone.startswith('+'):
                            phone = '+' + phone
                        if not phone:
                            phone = f"imported_{os.urandom(4).hex()}"
                        
                        
                        # Convert tdata to session
                        # Fix path to be within /app (shared volume) instead of root /sessions
                        # __file__ is /app/app/worker.py
                        # dirname -> /app/app
                        # dirname -> /app
                        sessions_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sessions')
                        os.makedirs(sessions_dir, exist_ok=True)
                        output_path_base = os.path.join(sessions_dir, phone)
                        
                        try:
                            from app.services.tdata_converter import convert_tdata_to_session
                            from app.services.session_converter import convert_telethon_to_pyrogram
                            
                            self.update_state(state='PROGRESS', meta={'status': 'converting', 'message': f'正在转换 tdata {phone}...', 'url': mega_url})
                            
                            # Run async conversion in sync context
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                            try:
                                telethon_session_path = loop.run_until_complete(
                                    convert_tdata_to_session(tdata_path, output_path_base, verify=False)
                                )
                            finally:
                                loop.close()
                            
                            
                            if telethon_session_path and os.path.exists(telethon_session_path):
                                # Convert Telethon to Pyrogram
                                if convert_telethon_to_pyrogram(telethon_session_path):
                                    
                                    # Create account in database
                                    with Session(engine) as db_session:
                                        existing = db_session.exec(
                                            select(Account).where(Account.phone_number == phone)
                                        ).first()
                                        
                                        if existing:
                                            errors.append(f"Account {phone} already exists")
                                        else:
                                            # [Security Patch] Use TDesktop official keys and device info
                                            # to match the origin of tdata sessions.
                                            account = Account(
                                                phone_number=phone,
                                                status="init", # Imported but do not touch Telegram by default
                                                session_file_path=telethon_session_path,
                                                tier="tier3",    # Default to lowest tier
                                                
                                                # TDesktop Official API Credentials
                                                api_id=2040,
                                                api_hash="b18441a1ff607e10a989891a5462e627",
                                                
                                                # TDesktop Device Fingerprint
                                                device_model="Desktop",
                                                system_version="Windows 10", 
                                                app_version="4.16.8 x64"
                                            )
                                            db_session.add(account)
                                            db_session.commit()
                                            db_session.refresh(account)
                                            
                                            # Auto assign proxy
                                            from app.services.proxy_assigner import auto_assign_proxy
                                            if auto_assign_proxy(db_session, account):
                                                pass  # Proxy assigned successfully
                                            else:
                                                pass  # No proxy available
                                                
                                            imported_count += 1
                                            imported_account_ids.append(account.id)  # 记录账号ID
                                else:
                                    errors.append(f"Failed to convert Telethon to Pyrogram for {phone}")
                            else:
                                errors.append(f"Failed to convert tdata for {phone}")
                        except Exception as e:
                            errors.append(f"tdata conversion error: {e}")
                
                # Then check for .session files directly
                for root, dirs, files in os.walk(extract_dir):
                    for f in files:
                        if f.endswith('.session'):
                            filepath = os.path.join(root, f)
                            do_import_session(filepath, f)
            
            
            # 返回导入的账号ID列表，由汇总任务统一创建养号任务
            
            return {
                "success": True,
                "imported_count": imported_count,
                "imported_account_ids": imported_account_ids,  # 返回导入的账号ID
                "errors": errors,
                "url": mega_url
            }
            
        finally:
            # Cleanup
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Download timeout", "url": mega_url}
    except FileNotFoundError:
        return {"success": False, "error": "megadl not installed. Please install megatools.", "url": mega_url}
    except Exception as e:
        logger.error(f"MEGA import failed: {e}")
        return {"success": False, "error": str(e), "url": mega_url}


@celery_app.task(bind=True)
def create_warmup_after_imports(
    self,
    task_ids: list,
    target_channels: str = "kltgsc",
    auto_check: bool = False,
    auto_warmup: bool = False,
):
    """
    等待所有导入任务完成后：
    1. 先检测所有导入的账号状态
    2. 只有活跃账号才创建养号任务
    """
    import time
    from celery.result import AsyncResult
    from app.models.warmup_task import WarmupTask
    from app.services.telegram_client import check_account_with_client
    import json
    
    logger.info(f"Waiting for {len(task_ids)} import tasks to complete...")
    
    all_account_ids = []
    max_wait = 600  # 最多等待10分钟
    start_time = time.time()
    
    # 等待所有任务完成
    pending_tasks = set(task_ids)
    while pending_tasks and (time.time() - start_time) < max_wait:
        for task_id in list(pending_tasks):
            result = AsyncResult(task_id, app=celery_app)
            if result.ready():
                pending_tasks.discard(task_id)
                if result.successful():
                    task_result = result.result
                    if task_result and task_result.get("imported_account_ids"):
                        all_account_ids.extend(task_result["imported_account_ids"])
                        logger.info(f"Task {task_id} completed, imported {len(task_result['imported_account_ids'])} accounts")
        
        if pending_tasks:
            time.sleep(2)
    
    if not all_account_ids:
        logger.warning("No accounts imported from any task")
        return {"success": False, "message": "No accounts imported"}
    
    if not auto_check:
        logger.info("Auto-check disabled for this import batch; skipping status checks and warmup creation.")
        return {
            "success": True,
            "message": "Auto-check disabled; imported accounts will not be checked or warmed up automatically.",
            "total_imported": len(all_account_ids),
            "active_count": 0,
        }

    logger.info(f"Starting status check for {len(all_account_ids)} imported accounts (safe mode)...")
    
    # 检测所有导入的账号状态
    active_account_ids = []
    with Session(engine) as db_session:
        for account_id in all_account_ids:
            account = db_session.get(Account, account_id)
            if not account:
                continue
            
            proxy = account.proxy if account.proxy_id else None
            
            try:
                # 使用事件循环检测账号
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    status, error_msg, last_active, device_info = loop.run_until_complete(
                        check_account_with_client(account, proxy, mode="safe")
                    )
                finally:
                    loop.close()
                
                # 更新账号状态
                account.status = status
                if last_active:
                    account.last_active = last_active
                
                # 已封禁账号解除代理
                if status == "banned" and account.proxy_id:
                    logger.info(f"Account {account_id} is banned, releasing proxy")
                    account.proxy_id = None
                
                db_session.add(account)
                db_session.commit()
                
                logger.info(f"Account {account.phone_number}: {status}")
                
                # 只有活跃账号才加入养号列表
                if status == "active":
                    active_account_ids.append(account_id)
                    
            except Exception as e:
                logger.error(f"Error checking account {account_id}: {e}")
                account.status = "error"
                db_session.add(account)
                db_session.commit()
    
    logger.info(f"Check complete: {len(active_account_ids)} active out of {len(all_account_ids)} total")
    
    if not auto_warmup:
        logger.info("Auto-warmup disabled for this import batch; skipping warmup task creation.")
        return {
            "success": True,
            "message": "Auto-warmup disabled; accounts checked but warmup not started.",
            "total_imported": len(all_account_ids),
            "active_count": len(active_account_ids),
        }

    if not active_account_ids:
        logger.warning("No active accounts found, skipping warmup task creation")
        return {
            "success": True,
            "message": "No active accounts to warmup",
            "total_imported": len(all_account_ids),
            "active_count": 0
        }
    
    # 只为活跃账号创建养号任务
    with Session(engine) as db_session:
        warmup_task = WarmupTask(
            name=f"Auto Warmup - {len(active_account_ids)} active accounts",
            action_type="mixed",
            account_ids_json=json.dumps(active_account_ids),
            status="pending",
            target_channels=target_channels,
            min_delay=30,
            max_delay=120,
            duration_minutes=60
        )
        db_session.add(warmup_task)
        db_session.commit()
        db_session.refresh(warmup_task)
        
        # 触发养号任务
        celery_app.send_task("app.worker.execute_warmup_task", args=[warmup_task.id])
        logger.info(f"Created warmup task {warmup_task.id} for {len(active_account_ids)} active accounts")
        
        return {
            "success": True,
            "warmup_task_id": warmup_task.id,
            "total_imported": len(all_account_ids),
            "active_count": len(active_account_ids)
        }


@celery_app.task(bind=True)
def execute_warmup_task(self, warmup_task_id: int):
    """
    Execute account warmup task - performs various actions to warm up accounts
    """
    from app.services.warmup_service import WarmupService
    
    logger.info(f"Starting warmup task {warmup_task_id}")
    
    with Session(engine) as session:
        service = WarmupService(session)
        
        # Always create a new event loop for Celery tasks
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
            
        try:
            loop.run_until_complete(service.run_task(warmup_task_id))
            return {"success": True, "task_id": warmup_task_id}
        except Exception as e:
            logger.error(f"Warmup task {warmup_task_id} failed: {e}")
            return {"success": False, "error": str(e)}
        finally:
            loop.close()


@celery_app.task(bind=True)
def check_auto_reply_task(self, account_id: int):
    """
    Check and process auto-replies for an account
    """
    logger.info(f"Checking auto-replies for account {account_id}")
    
    with Session(engine) as session:
        account = session.get(Account, account_id)
        if not account:
            return {"success": False, "error": "Account not found"}
        
        if not account.auto_reply:
            return {"success": False, "error": "Auto-reply not enabled"}
        
        # Placeholder: actual implementation would fetch unread messages
        # and generate AI responses using LLMService
        try:
            logger.info(f"Auto-reply check completed for account {account_id}")
            return {
                "success": True,
                "account_id": account_id,
                "message": "Auto-reply check completed"
            }
        except Exception as e:
            logger.error(f"Auto-reply error for account {account_id}: {e}")
            return {"success": False, "error": str(e)}


@celery_app.task(bind=True)
def execute_script_task(self, script_task_id: int):
    """
    Execute a script task - sends scripted messages in a group
    """
    import json
    from app.models.script import Script, ScriptTask
    
    logger.info(f"Starting script task {script_task_id}")
    
    with Session(engine) as session:
        task = session.get(ScriptTask, script_task_id)
        if not task:
            return {"success": False, "error": "Task not found"}
        
        task.status = "running"
        session.add(task)
        session.commit()
        
        try:
            script = session.get(Script, task.script_id)
            if not script:
                task.status = "failed"
                session.add(task)
                session.commit()
                return {"success": False, "error": "Script not found"}
            
            # Placeholder for actual script execution
            logger.info(f"Executing script {script.id} for task {script_task_id}")
            
            task.status = "completed"
            session.add(task)
            session.commit()
            
            return {"success": True, "task_id": script_task_id}
            
        except Exception as e:
            logger.error(f"Script task {script_task_id} failed: {e}")
            task.status = "failed"
            session.add(task)
            session.commit()
            return {"success": False, "error": str(e)}


@celery_app.task(bind=True)
def check_proxies_batch_task(self, proxy_ids: List[int]):
    """
    Check multiple proxies in batch
    """
    from app.models.proxy import Proxy
    from app.services.proxy_checker import check_proxy_connectivity
    
    logger.info(f"Checking {len(proxy_ids)} proxies")
    
    results = {"success": 0, "failed": 0, "errors": []}
    
    with Session(engine) as session:
        for proxy_id in proxy_ids:
            proxy = session.get(Proxy, proxy_id)
            if not proxy:
                results["errors"].append(f"Proxy {proxy_id} not found")
                results["failed"] += 1
                continue
            
            try:
                # 使用完整检测服务 (不强制 fetch_details 以加快批量速度，或者可选开启)
                # 这里我们开启 fetch_details=True 以支持批量识别，但要注意 ip-api.com 的速率限制
                # 简单起见，我们在批量时关闭详情查询，以免被封，或者加延时
                # 决策：批量暂不自动识别 ISP 类型，仅检测连通性，避免 API 限流。
                # 如果用户需要识别，建议单个点击或小批量。
                # 或者，我们可以每隔 2 秒请求一次。
                
                # 既然用户问的是“导入的代理能否自动识别”，通常意味着大批量。
                # 我们可以尝试 fetch_details=True 但加上 sleep。
                import time
                time.sleep(1.5) # 限制速率 (60s / 45reqs ~= 1.33s)
                
                is_alive, error_msg, details = check_proxy_connectivity(proxy, fetch_details=True)
                
                from datetime import datetime
                proxy.last_checked = datetime.utcnow()
                
                if is_alive:
                    proxy.status = "active"
                    proxy.fail_count = 0
                    results["success"] += 1
                    
                    if details:
                        if details.get('country'):
                            proxy.country = details.get('country')
                        
                        hosting = details.get('hosting', False)
                        isp = details.get('isp', '')
                        if hosting:
                            proxy.provider_type = "datacenter"
                        elif isp:
                            proxy.provider_type = "isp"
                            
                else:
                    proxy.status = "dead"
                    proxy.fail_count = (proxy.fail_count or 0) + 1
                    results["failed"] += 1
                
                session.add(proxy)
                session.commit()
                
            except Exception as e:
                logger.error(f"Error checking proxy {proxy_id}: {e}")
                proxy.status = "dead"
                proxy.fail_count = (proxy.fail_count or 0) + 1
                session.add(proxy)
                session.commit()
                results["failed"] += 1
                results["errors"].append(str(e))
    
    return results

@celery_app.task(bind=True)
def execute_shill_conversation(self, hit_id: int, script_id: int, role_account_ids: Dict[str, int]):
    """
    Execute a shill conversation based on a keyword hit
    """
    from app.services.shill_dispatcher import run_shill_conversation
    
    logger.info(f"Starting shill conversation task for Hit {hit_id}")
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
    try:
        loop.run_until_complete(run_shill_conversation(hit_id, script_id, role_account_ids))
        return {"success": True, "hit_id": hit_id}
    except Exception as e:
        logger.error(f"Shill conversation failed: {e}")
        return {"success": False, "error": str(e)}

from app.worker_invite import execute_invite_task

@celery_app.task(bind=True)
def join_groups_batch_task(self, account_ids: List[int], group_links: List[str], scraping_task_id: int = None):
    """
    批量加入群组 - 多个账号加入多个群组
    分配策略：轮流使用账号加入群组，避免单个账号频繁操作
    """
    from app.services.telegram_client import join_group_with_client
    from app.models.scraping_task import ScrapingTask
    from datetime import datetime
    import random
    import time
    import json
    
    logger.info(f"Starting batch join: {len(account_ids)} accounts, {len(group_links)} groups, task_id={scraping_task_id}")
    
    db_session = DBSession(engine)
    results = {
        "success": [],
        "failed": [],
        "total_accounts": len(account_ids),
        "total_groups": len(group_links)
    }
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        # 获取所有账号
        accounts = []
        for aid in account_ids:
            account = db_session.get(Account, aid)
            if account and account.status == 'active':
                accounts.append(account)
        
        if not accounts:
            logger.warning("No valid accounts for batch join")
            # 更新任务状态
            if scraping_task_id:
                task = db_session.get(ScrapingTask, scraping_task_id)
                if task:
                    task.status = "failed"
                    task.error_message = "No valid accounts"
                    task.completed_at = datetime.utcnow()
                    db_session.add(task)
                    db_session.commit()
            return results
        
        # 每个账号都尝试加入每个群组
        for group_link in group_links:
            for account in accounts:
                try:
                    logger.info(f"Account {account.phone_number} joining {group_link}")
                    
                    # 使用闭包捕获当前 account 和 group_link
                    current_account = account
                    current_link = group_link
                    
                    async def do_join():
                        return await join_group_with_client(current_account, current_link, db_session=db_session)
                    
                    success, msg = loop.run_until_complete(do_join())
                    
                    if success:
                        results["success"].append({
                            "account": account.phone_number,
                            "group": group_link,
                            "message": msg
                        })
                        logger.info(f"Account {account.phone_number} joined {group_link} successfully")
                    else:
                        # 如果是"已经是成员"，也算成功
                        if "ALREADY" in msg.upper() or "已经" in msg or "already" in msg.lower():
                            results["success"].append({
                                "account": account.phone_number,
                                "group": group_link,
                                "message": "已是成员"
                            })
                            logger.info(f"Account {account.phone_number} already in {group_link}")
                        else:
                            results["failed"].append({
                                "account": account.phone_number,
                                "group": group_link,
                                "error": msg
                            })
                            logger.warning(f"Account {account.phone_number} failed to join {group_link}: {msg}")
                        
                except Exception as e:
                    error_str = str(e)
                    # 如果是"已经是成员"，也算成功
                    if "USER_ALREADY_PARTICIPANT" in error_str:
                        results["success"].append({
                            "account": account.phone_number,
                            "group": group_link,
                            "message": "已是成员"
                        })
                        logger.info(f"Account {account.phone_number} already in {group_link}")
                    else:
                        results["failed"].append({
                            "account": account.phone_number,
                            "group": group_link,
                            "error": error_str
                        })
                        logger.error(f"Exception: Account {account.phone_number} joining {group_link}: {e}")
                
                # 每个账号操作后随机延迟 2-5 秒
                delay = random.uniform(2, 5)
                time.sleep(delay)
            
            # 随机延迟 3-8 秒，避免触发风控
            delay = random.uniform(3, 8)
            time.sleep(delay)
        
        logger.info(f"Batch join completed: {len(results['success'])} success, {len(results['failed'])} failed")
        
        # 更新任务状态
        if scraping_task_id:
            task = db_session.get(ScrapingTask, scraping_task_id)
            if task:
                task.status = "completed"
                task.success_count = len(results['success'])
                task.fail_count = len(results['failed'])
                task.result_json = json.dumps(results)
                task.completed_at = datetime.utcnow()
                db_session.add(task)
                db_session.commit()
        
        return results
        
    except Exception as e:
        logger.error(f"Batch join task failed: {e}")
        # 更新任务状态为失败
        if scraping_task_id:
            try:
                task = db_session.get(ScrapingTask, scraping_task_id)
                if task:
                    task.status = "failed"
                    task.error_message = str(e)
                    task.result_json = json.dumps(results)
                    task.completed_at = datetime.utcnow()
                    db_session.add(task)
                    db_session.commit()
            except:
                pass
        return {"error": str(e), **results}
    finally:
        db_session.close()

@celery_app.task(bind=True)
def scrape_members_batch_task(self, account_ids: List[int], group_links: List[str], limit: int = 100, scraping_task_id: int = None, filter_config: dict = None):
    """
    批量采集群成员 - 多个账号采集多个群组 (支持高质量用户过滤)
    
    Args:
        filter_config: 过滤配置
            - active_only: 仅保留最近一周活跃用户
            - has_photo: 仅保留有头像的用户
            - has_username: 仅保留有用户名的用户
    """
    from app.services.telegram_client import scrape_group_members
    from app.models.scraping_task import ScrapingTask
    from datetime import datetime
    import random
    import time
    import json
    
    logger.info(f"Starting batch scrape: {len(account_ids)} accounts, {len(group_links)} groups, limit={limit}, filters={filter_config}")
    
    db_session = DBSession(engine)
    results = {
        "success": [],
        "failed": [],
        "total_scraped": 0,
        "new_users": 0,
        "filter_config": filter_config
    }
    
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    
    try:
        # 获取有效账号
        accounts = []
        for aid in account_ids:
            account = db_session.get(Account, aid)
            if account and account.status == 'active':
                accounts.append(account)
        
        if not accounts:
            logger.warning("No valid accounts for batch scrape")
            if scraping_task_id:
                task = db_session.get(ScrapingTask, scraping_task_id)
                if task:
                    task.status = "failed"
                    task.error_message = "No valid accounts"
                    task.completed_at = datetime.utcnow()
                    db_session.add(task)
                    db_session.commit()
            return results

        # 轮询分配账号采集
        for i, group_link in enumerate(group_links):
            account = accounts[i % len(accounts)]
            
            try:
                logger.info(f"Account {account.phone_number} scraping {group_link}")
                
                current_account = account
                current_link = group_link
                
                async def do_scrape():
                    return await scrape_group_members(
                        current_account, 
                        current_link, 
                        limit, 
                        db_session=db_session, 
                        filter_config=filter_config
                    )
                
                success, members = loop.run_until_complete(do_scrape())
                
                if success:
                    # 保存采集到的用户
                    saved_count = 0
                    for m in members:
                        exists = db_session.exec(select(TargetUser).where(TargetUser.telegram_id == m["telegram_id"])).first()
                        if not exists:
                            user = TargetUser(**m)
                            db_session.add(user)
                            saved_count += 1
                    
                    db_session.commit()
                    
                    results["success"].append({
                        "account": account.phone_number,
                        "group": group_link,
                        "count": len(members),
                        "new": saved_count
                    })
                    results["total_scraped"] += len(members)
                    results["new_users"] += saved_count
                    
                    logger.info(f"Scraped {len(members)} members from {group_link} (New: {saved_count})")
                else:
                    error_msg = members if isinstance(members, str) else "Unknown error"
                    results["failed"].append({
                        "account": account.phone_number,
                        "group": group_link,
                        "error": error_msg
                    })
                    logger.warning(f"Failed to scrape {group_link}: {error_msg}")
                    
            except Exception as e:
                logger.error(f"Exception scraping {group_link}: {e}")
                results["failed"].append({
                    "account": account.phone_number,
                    "group": group_link,
                    "error": str(e)
                })
            
            # 随机延迟防止风控
            time.sleep(random.uniform(5, 15))
            
        # 更新任务状态
        if scraping_task_id:
            task = db_session.get(ScrapingTask, scraping_task_id)
            if task:
                task.status = "completed"
                task.success_count = results["total_scraped"]
                task.fail_count = len(results["failed"])
                task.result_json = json.dumps(results)
                task.completed_at = datetime.utcnow()
                db_session.add(task)
                db_session.commit()
        
        logger.info(f"Batch scrape completed: {results['total_scraped']} scraped, {results['new_users']} new")
        return results
        
    except Exception as e:
        logger.error(f"Batch scrape task failed: {e}")
        if scraping_task_id:
            try:
                task = db_session.get(ScrapingTask, scraping_task_id)
                if task:
                    task.status = "failed"
                    task.error_message = str(e)
                    task.result_json = json.dumps(results)
                    task.completed_at = datetime.utcnow()
                    db_session.add(task)
                    db_session.commit()
            except:
                pass
        return {"error": str(e), **results}
    finally:
        db_session.close()


# Re-export for celery autodiscover
__all__ = [
    "execute_send_task", 
    "check_account_status", 
    "import_mega_accounts",
    "create_warmup_after_imports",
    "execute_warmup_task",
    "check_auto_reply_task",
    "execute_script_task",
    "check_proxies_batch_task",
    "execute_shill_conversation",
    "execute_invite_task",
    "join_groups_batch_task",
    "scrape_members_batch_task"
]
