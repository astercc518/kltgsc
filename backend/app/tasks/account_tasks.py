"""
账号相关任务
- 账号状态检查
- MEGA 导入
- 养号汇总
"""
import os
import json
import asyncio
import logging
import tempfile
import zipfile
import shutil
import subprocess
from typing import List, Optional

from sqlmodel import Session, select
from app.core.db import engine
from app.core.celery_app import celery_app
from app.models.account import Account
from app.models.warmup_task import WarmupTask
from app.services.telegram_client import check_account_with_client
from app.services.device_generator import DeviceGenerator

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3)
def check_account_status(self, account_id: int):
    """
    检查单个账号状态
    """
    logger.info(f"Checking account status for ID: {account_id}")
    
    with Session(engine) as session:
        account = session.get(Account, account_id)
        if not account:
            logger.error(f"Account {account_id} not found")
            return {"success": False, "error": "Account not found"}
        
        # Get proxy if bound
        proxy = account.proxy if account.proxy_id else None
        
        # Ensure device fingerprint exists
        if not account.device_model:
            dev_info = DeviceGenerator.generate()
            account.device_model = dev_info["device_model"]
            account.system_version = dev_info["system_version"]
            account.app_version = dev_info["app_version"]
            session.add(account)
            session.commit()
            session.refresh(account)
            logger.info(f"Generated device fingerprint for account {account_id}")
        
        # Create event loop
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        try:
            status, error_msg, last_active, device_info = loop.run_until_complete(
                check_account_with_client(account, proxy, mode="safe")
            )
            
            # Auto-warmup for spam_block accounts
            if status == "spam_block":
                _schedule_auto_warmup(session, account_id, account.phone_number)

            # Update account status
            account.status = status
            if last_active:
                account.last_active = last_active
            if device_info and not account.device_model:
                account.device_model = device_info.get("device_model")
                account.system_version = device_info.get("system_version")
                account.app_version = device_info.get("app_version")
            
            # Release proxy for banned accounts
            if status == "banned" and account.proxy_id:
                logger.info(f"Account {account_id} is banned, releasing proxy")
                account.proxy_id = None
            
            session.add(account)
            session.commit()
            
            return {
                "success": status == "active",
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
            try:
                loop.close()
            except Exception:
                pass


def _schedule_auto_warmup(session: Session, account_id: int, phone_number: str):
    """为受限账号自动调度养号任务"""
    try:
        # Check if already in warmup
        existing_tasks = session.exec(
            select(WarmupTask).where(WarmupTask.status.in_(["pending", "running"]))
        ).all()
        
        for t in existing_tasks:
            try:
                t_ids = json.loads(t.account_ids_json)
                if account_id in t_ids:
                    return  # Already warming up
            except Exception:
                pass
        
        logger.info(f"Auto-starting warmup for restricted account {account_id}")
        new_task = WarmupTask(
            name=f"Auto Warmup - {phone_number}",
            action_type="mixed",
            account_ids_json=json.dumps([account_id]),
            status="pending",
            target_channels="Telegram"
        )
        session.add(new_task)
        session.commit()
        session.refresh(new_task)
        
        # Trigger task
        celery_app.send_task("app.tasks.marketing_tasks.execute_warmup_task", args=[new_task.id])
    except Exception as e:
        logger.error(f"Failed to auto-start warmup for {account_id}: {e}")


@celery_app.task(bind=True, max_retries=2)
def import_mega_accounts(self, mega_url: str, target_channels: str = "kltgsc"):
    """
    从 MEGA 链接导入账号
    """
    logger.info(f"Starting MEGA import from: {mega_url}")
    
    self.update_state(state='PROGRESS', meta={
        'status': 'downloading',
        'message': '正在下载...',
        'url': mega_url
    })
    
    try:
        temp_dir = tempfile.mkdtemp()
        
        try:
            # Download using megadl
            result = subprocess.run(
                ['megadl', '--path', temp_dir, mega_url],
                capture_output=True,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                raise Exception(f"megadl failed: {result.stderr}")
            
            self.update_state(state='PROGRESS', meta={
                'status': 'extracting',
                'message': '正在解压...',
                'url': mega_url
            })
            
            imported_count = 0
            imported_account_ids = []
            errors = []
            
            # Process files
            imported_count, imported_account_ids, errors = _process_downloaded_files(
                temp_dir, self, mega_url
            )
            
            return {
                "success": True,
                "imported_count": imported_count,
                "imported_account_ids": imported_account_ids,
                "errors": errors,
                "url": mega_url
            }
            
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Download timeout", "url": mega_url}
    except FileNotFoundError:
        return {"success": False, "error": "megadl not installed", "url": mega_url}
    except Exception as e:
        logger.error(f"MEGA import failed: {e}")
        return {"success": False, "error": str(e), "url": mega_url}


def _process_downloaded_files(temp_dir: str, task, mega_url: str):
    """处理下载的文件"""
    import re as regex
    
    imported_count = 0
    imported_account_ids = []
    errors = []
    
    def do_import_session(filepath: str, filename: str) -> bool:
        nonlocal imported_count
        task.update_state(state='PROGRESS', meta={
            'status': 'converting',
            'message': f'正在导入 {filename}...',
            'url': mega_url
        })
        
        try:
            phone = os.path.splitext(filename)[0]
            phone = phone.replace('_', '').replace(' ', '')
            if not phone.startswith('+'):
                phone = '+' + phone
            
            sessions_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sessions')
            os.makedirs(sessions_dir, exist_ok=True)
            dest_path = os.path.join(sessions_dir, filename)
            shutil.copy2(filepath, dest_path)
            
            # Encrypt new session file
            try:
                from app.services.session_encryption_service import encrypt_new_session_file
                encrypt_new_session_file(dest_path)
            except Exception as e:
                logger.warning(f"Failed to encrypt session: {e}")
            
            with Session(engine) as db_session:
                existing = db_session.exec(
                    select(Account).where(Account.phone_number == phone)
                ).first()
                
                if existing:
                    errors.append(f"Account {phone} already exists")
                    return False
                
                account = Account(
                    phone_number=phone,
                    status="init",
                    session_file_path=dest_path
                )
                db_session.add(account)
                db_session.commit()
                db_session.refresh(account)
                imported_count += 1
                imported_account_ids.append(account.id)
                return True
        except Exception as e:
            errors.append(f"Failed to import {filename}: {e}")
            return False
    
    # Process all files
    for root, dirs, files in os.walk(temp_dir):
        for f in files:
            filepath = os.path.join(root, f)
            
            if f.endswith('.zip'):
                try:
                    extract_dir = os.path.join(temp_dir, 'extracted')
                    os.makedirs(extract_dir, exist_ok=True)
                    with zipfile.ZipFile(filepath, 'r') as zf:
                        zf.extractall(extract_dir)
                except Exception as e:
                    errors.append(f"Failed to extract {f}: {e}")
                    
            elif f.endswith('.rar'):
                try:
                    extract_dir = os.path.join(temp_dir, 'extracted')
                    os.makedirs(extract_dir, exist_ok=True)
                    subprocess.run(
                        ['unrar', 'x', '-o+', filepath, extract_dir + '/'],
                        capture_output=True,
                        timeout=120
                    )
                except Exception as e:
                    errors.append(f"Failed to extract {f}: {e}")
                    
            elif f.endswith('.session'):
                do_import_session(filepath, f)
    
    # Process extracted files
    extract_dir = os.path.join(temp_dir, 'extracted')
    if os.path.exists(extract_dir):
        # Check for tdata directories
        for root, dirs, files in os.walk(extract_dir):
            if 'tdata' in dirs:
                tdata_path = os.path.join(root, 'tdata')
                parent_name = os.path.basename(root)
                phone = None
                match = regex.search(r'\+?\d{7,15}', parent_name)
                if match:
                    phone = match.group(0)
                if phone and not phone.startswith('+'):
                    phone = '+' + phone
                if not phone:
                    phone = f"imported_{os.urandom(4).hex()}"
                
                _convert_and_import_tdata(
                    tdata_path, phone, imported_account_ids, errors, task, mega_url
                )
        
        # Check for session files
        for root, dirs, files in os.walk(extract_dir):
            for f in files:
                if f.endswith('.session'):
                    filepath = os.path.join(root, f)
                    do_import_session(filepath, f)
    
    return imported_count, imported_account_ids, errors


def _convert_and_import_tdata(tdata_path, phone, imported_account_ids, errors, task, mega_url):
    """转换并导入 tdata"""
    nonlocal_imported_count = [0]
    
    sessions_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sessions')
    os.makedirs(sessions_dir, exist_ok=True)
    output_path_base = os.path.join(sessions_dir, phone)
    
    try:
        from app.services.tdata_converter import convert_tdata_to_session
        from app.services.session_converter import convert_telethon_to_pyrogram
        
        task.update_state(state='PROGRESS', meta={
            'status': 'converting',
            'message': f'正在转换 tdata {phone}...',
            'url': mega_url
        })
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            telethon_session_path = loop.run_until_complete(
                convert_tdata_to_session(tdata_path, output_path_base, verify=False)
            )
        finally:
            loop.close()
        
        if telethon_session_path and os.path.exists(telethon_session_path):
            if convert_telethon_to_pyrogram(telethon_session_path):
                with Session(engine) as db_session:
                    existing = db_session.exec(
                        select(Account).where(Account.phone_number == phone)
                    ).first()
                    
                    if existing:
                        errors.append(f"Account {phone} already exists")
                    else:
                        account = Account(
                            phone_number=phone,
                            status="init",
                            session_file_path=telethon_session_path,
                            tier="tier3",
                            api_id=2040,
                            api_hash="b18441a1ff607e10a989891a5462e627",
                            device_model="Desktop",
                            system_version="Windows 10",
                            app_version="4.16.8 x64"
                        )
                        db_session.add(account)
                        db_session.commit()
                        db_session.refresh(account)
                        
                        from app.services.proxy_assigner import auto_assign_proxy
                        auto_assign_proxy(db_session, account)
                        
                        nonlocal_imported_count[0] += 1
                        imported_account_ids.append(account.id)
            else:
                errors.append(f"Failed to convert Telethon to Pyrogram for {phone}")
        else:
            errors.append(f"Failed to convert tdata for {phone}")
    except Exception as e:
        errors.append(f"tdata conversion error: {e}")


@celery_app.task(bind=True)
def create_warmup_after_imports(
    self,
    task_ids: list,
    target_channels: str = "kltgsc",
    auto_check: bool = False,
    auto_warmup: bool = False,
):
    """
    等待所有导入任务完成后创建养号任务
    """
    import time
    from celery.result import AsyncResult
    
    logger.info(f"Waiting for {len(task_ids)} import tasks...")
    
    all_account_ids = []
    max_wait = 600
    start_time = time.time()
    
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
        
        if pending_tasks:
            time.sleep(2)
    
    if not all_account_ids:
        return {"success": False, "message": "No accounts imported"}
    
    if not auto_check:
        return {
            "success": True,
            "message": "Auto-check disabled",
            "total_imported": len(all_account_ids),
            "active_count": 0,
        }

    logger.info(f"Checking {len(all_account_ids)} imported accounts...")
    
    active_account_ids = []
    with Session(engine) as db_session:
        for account_id in all_account_ids:
            account = db_session.get(Account, account_id)
            if not account:
                continue
            
            proxy = account.proxy if account.proxy_id else None
            
            try:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                try:
                    status, error_msg, last_active, device_info = loop.run_until_complete(
                        check_account_with_client(account, proxy, mode="safe")
                    )
                finally:
                    loop.close()
                
                account.status = status
                if last_active:
                    account.last_active = last_active
                
                if status == "banned" and account.proxy_id:
                    account.proxy_id = None
                
                db_session.add(account)
                db_session.commit()
                
                if status == "active":
                    active_account_ids.append(account_id)
                    
            except Exception as e:
                logger.error(f"Error checking account {account_id}: {e}")
                account.status = "error"
                db_session.add(account)
                db_session.commit()
    
    if not auto_warmup:
        return {
            "success": True,
            "message": "Auto-warmup disabled",
            "total_imported": len(all_account_ids),
            "active_count": len(active_account_ids),
        }

    if not active_account_ids:
        return {
            "success": True,
            "message": "No active accounts to warmup",
            "total_imported": len(all_account_ids),
            "active_count": 0
        }
    
    with Session(engine) as db_session:
        warmup_task = WarmupTask(
            name=f"Auto Warmup - {len(active_account_ids)} accounts",
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
        
        celery_app.send_task("app.tasks.marketing_tasks.execute_warmup_task", args=[warmup_task.id])
        
        return {
            "success": True,
            "warmup_task_id": warmup_task.id,
            "total_imported": len(all_account_ids),
            "active_count": len(active_account_ids)
        }
