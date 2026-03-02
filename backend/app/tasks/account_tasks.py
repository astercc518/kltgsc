"""
账号相关任务
- 账号状态检查
- MEGA 导入
- 养号汇总
- 头像/资料批量更新
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

from celery.exceptions import SoftTimeLimitExceeded
from sqlmodel import Session, select
from app.core.db import engine
from app.core.celery_app import celery_app
from app.models.account import Account
from app.models.warmup_task import WarmupTask
from app.services.telegram_client import (
    check_account_with_client,
    update_photo_with_client,
    update_profile_with_client,
    update_username_with_client,
    update_2fa_with_client,
)
from app.services.device_generator import DeviceGenerator
from app.services.profile_generator import ProfileGenerator

logger = logging.getLogger(__name__)


@celery_app.task(bind=True, max_retries=3, soft_time_limit=300, time_limit=600)
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
        except SoftTimeLimitExceeded:
            logger.error(f"Account check timed out for account {account_id}")
            account.status = "error"
            session.add(account)
            session.commit()
            return {"success": False, "error": "Task timed out"}
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


@celery_app.task(bind=True, max_retries=2, soft_time_limit=1800, time_limit=3600)
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
            
    except SoftTimeLimitExceeded:
        logger.error(f"MEGA import timed out for URL: {mega_url}")
        return {"success": False, "error": "Import task timed out", "url": mega_url}
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Download timeout", "url": mega_url}
    except FileNotFoundError:
        return {"success": False, "error": "megadl not installed", "url": mega_url}
    except Exception as e:
        logger.error(f"MEGA import failed: {e}")
        return {"success": False, "error": str(e), "url": mega_url}


def _import_session_file(filepath: str, filename: str, imported_account_ids: list, errors: list, task, source_label: str) -> bool:
    """导入单个 session 文件（模块级辅助函数，供 MEGA 导入和 tdata 上传复用）"""
    task.update_state(state='PROGRESS', meta={
        'status': 'converting',
        'message': f'正在导入 {filename}...',
        'source_label': source_label
    })

    try:
        phone = os.path.splitext(filename)[0]
        phone = phone.replace('_', '').replace(' ', '')
        if not phone.startswith('+'):
            phone = '+' + phone

        sessions_dir = os.path.join(os.getcwd(), 'sessions')
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

            # Store relative path (consistent with other endpoints)
            rel_path = os.path.join('sessions', filename)
            account = Account(
                phone_number=phone,
                status="init",
                session_file_path=rel_path
            )
            db_session.add(account)
            db_session.commit()
            db_session.refresh(account)
            imported_account_ids.append(account.id)
            return True
    except Exception as e:
        errors.append(f"Failed to import {filename}: {e}")
        return False


def _process_downloaded_files(temp_dir: str, task, mega_url: str):
    """处理下载的文件"""
    import re as regex

    imported_account_ids = []
    errors = []

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
                _import_session_file(filepath, f, imported_account_ids, errors, task, mega_url)

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
                    _import_session_file(filepath, f, imported_account_ids, errors, task, mega_url)

    imported_count = len(imported_account_ids)
    return imported_count, imported_account_ids, errors


def _convert_and_import_tdata(tdata_path, phone, imported_account_ids, errors, task, source_label):
    """转换并导入 tdata"""
    sessions_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'sessions')
    os.makedirs(sessions_dir, exist_ok=True)
    output_path_base = os.path.join(sessions_dir, phone)

    try:
        from app.services.tdata_converter import convert_tdata_to_session
        from app.services.session_converter import convert_telethon_to_pyrogram

        task.update_state(state='PROGRESS', meta={
            'status': 'converting',
            'message': f'正在转换 tdata {phone}...',
            'source_label': source_label
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
                        # Store relative path (consistent with other endpoints)
                        rel_session_path = os.path.join('sessions', os.path.basename(telethon_session_path))
                        account = Account(
                            phone_number=phone,
                            status="init",
                            session_file_path=rel_session_path,
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

                        imported_account_ids.append(account.id)
            else:
                errors.append(f"Failed to convert Telethon to Pyrogram for {phone}")
        else:
            errors.append(f"Failed to convert tdata for {phone}")
    except Exception as e:
        errors.append(f"tdata conversion error: {e}")


@celery_app.task(bind=True, max_retries=1, soft_time_limit=1800, time_limit=3600)
def import_tdata_archive(self, file_path: str, filename: str):
    """
    从上传的压缩包中导入 tdata 账号
    支持 ZIP/RAR 格式，包含 tdata 目录和散落的 .session 文件
    """
    import re as regex

    logger.info(f"Starting tdata archive import: {filename}")

    self.update_state(state='PROGRESS', meta={
        'status': 'extracting',
        'message': f'正在解压 {filename}...',
        'source_label': filename
    })

    imported_account_ids = []
    errors = []

    try:
        temp_dir = tempfile.mkdtemp()

        try:
            extract_dir = os.path.join(temp_dir, 'extracted')
            os.makedirs(extract_dir, exist_ok=True)

            # Extract archive with Zip Slip protection
            if file_path.lower().endswith('.zip'):
                with zipfile.ZipFile(file_path, 'r') as zf:
                    for member in zf.namelist():
                        member_path = os.path.realpath(os.path.join(extract_dir, member))
                        if not member_path.startswith(os.path.realpath(extract_dir)):
                            raise Exception(f"Zip Slip detected: {member}")
                    zf.extractall(extract_dir)
            elif file_path.lower().endswith('.rar'):
                result = subprocess.run(
                    ['unrar', 'x', '-o+', file_path, extract_dir + '/'],
                    capture_output=True,
                    text=True,
                    timeout=300
                )
                if result.returncode != 0:
                    raise Exception(f"unrar failed: {result.stderr}")
            else:
                raise Exception(f"Unsupported archive format: {filename}")

            self.update_state(state='PROGRESS', meta={
                'status': 'converting',
                'message': f'正在转换 {filename}...',
                'source_label': filename
            })

            # Find and process tdata directories
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
                        tdata_path, phone, imported_account_ids, errors, self, filename
                    )

            # Also check for loose .session files
            for root, dirs, files in os.walk(extract_dir):
                for f in files:
                    if f.endswith('.session'):
                        filepath = os.path.join(root, f)
                        _import_session_file(
                            filepath, f, imported_account_ids, errors, self, filename
                        )

            self.update_state(state='PROGRESS', meta={
                'status': 'saving',
                'message': f'正在保存 {filename}...',
                'source_label': filename
            })

            return {
                "success": True,
                "imported_count": len(imported_account_ids),
                "imported_account_ids": imported_account_ids,
                "errors": errors,
                "filename": filename
            }

        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)
            # Clean up uploaded archive
            try:
                if os.path.exists(file_path):
                    os.remove(file_path)
            except Exception:
                pass

    except SoftTimeLimitExceeded:
        logger.error(f"tdata archive import timed out: {filename}")
        return {"success": False, "error": "Import task timed out", "filename": filename}
    except Exception as e:
        logger.error(f"tdata archive import failed for {filename}: {e}")
        return {"success": False, "error": str(e), "filename": filename}


@celery_app.task(bind=True, soft_time_limit=1800, time_limit=3600)
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
    
    try:
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
    except SoftTimeLimitExceeded:
        logger.error("create_warmup_after_imports timed out while waiting for import tasks")
        return {"success": False, "error": "Task timed out waiting for imports"}

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


# =====================
# 头像 & 资料批量更新
# =====================

@celery_app.task(bind=True, max_retries=1, soft_time_limit=600, time_limit=900)
def update_account_photo_task(self, account_id: int, photo_path: str):
    """更新单个账号头像（上传文件方式）"""
    logger.info(f"Updating photo for account {account_id}")

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        with Session(engine) as session:
            account = session.get(Account, account_id)
            if not account:
                return {"success": False, "account_id": account_id, "error": "Account not found"}

            success, msg = loop.run_until_complete(
                update_photo_with_client(account, photo_path, db_session=session)
            )
            return {"success": success, "account_id": account_id, "message": msg}
    except Exception as e:
        logger.error(f"Photo update failed for account {account_id}: {e}")
        return {"success": False, "account_id": account_id, "error": str(e)}
    finally:
        loop.close()
        # 清理临时文件
        try:
            if os.path.exists(photo_path):
                os.remove(photo_path)
        except Exception:
            pass


@celery_app.task(bind=True, max_retries=1, soft_time_limit=1800, time_limit=3600)
def batch_update_photos_random(self, account_ids: List[int], avatar_style: str = "face"):
    """
    批量为账号设置随机头像

    avatar_style:
      - face: AI 人脸 (thispersondoesnotexist.com)
      - portrait: 肖像照片
      - illustration: 插画风格
      - abstract: 抽象图案
    """
    logger.info(f"Batch random photo update for {len(account_ids)} accounts, style={avatar_style}")

    # 根据风格选择不同的图片源
    style_sources = {
        "face": [
            "https://thispersondoesnotexist.com/",
            "https://loremflickr.com/640/640/face",
        ],
        "portrait": [
            "https://loremflickr.com/640/640/portrait",
            "https://loremflickr.com/640/640/person",
        ],
        "illustration": [
            "https://loremflickr.com/640/640/illustration,avatar",
            "https://loremflickr.com/640/640/cartoon,avatar",
        ],
        "abstract": [
            "https://picsum.photos/640/640",
            "https://loremflickr.com/640/640/abstract,art",
        ],
    }

    import time
    import requests
    import random

    sources = style_sources.get(avatar_style, style_sources["face"])
    results = []
    success_count = 0
    fail_count = 0

    for i, account_id in enumerate(account_ids):
        self.update_state(state='PROGRESS', meta={
            'current': i + 1,
            'total': len(account_ids),
            'success': success_count,
            'fail': fail_count,
            'account_id': account_id,
        })

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with Session(engine) as session:
                account = session.get(Account, account_id)
                if not account:
                    results.append({"account_id": account_id, "success": False, "error": "Not found"})
                    fail_count += 1
                    continue

                if account.status == "banned":
                    results.append({"account_id": account_id, "success": False, "error": "Account banned"})
                    fail_count += 1
                    continue

                # 下载随机头像
                tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                tmp_path = tmp_file.name
                tmp_file.close()

                downloaded = False
                # 随机打乱源顺序，使每个账号获得不同图片
                shuffled_sources = random.sample(sources, len(sources))
                for url in shuffled_sources:
                    try:
                        ts = int(time.time() * 1000) + random.randint(0, 9999)
                        sep = "&" if "?" in url else "?"
                        final_url = f"{url}{sep}t={ts}"
                        resp = requests.get(final_url, timeout=15, headers={
                            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                        })
                        if resp.status_code == 200 and len(resp.content) > 1000:
                            with open(tmp_path, "wb") as f:
                                f.write(resp.content)
                            downloaded = True
                            break
                    except Exception as e:
                        logger.warning(f"Download avatar failed from {url}: {e}")

                if not downloaded:
                    results.append({"account_id": account_id, "success": False, "error": "Failed to download avatar"})
                    fail_count += 1
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass
                    continue

                # 设置头像
                try:
                    success, msg = loop.run_until_complete(
                        update_photo_with_client(account, tmp_path, db_session=session)
                    )
                    results.append({"account_id": account_id, "success": success, "message": msg})
                    if success:
                        success_count += 1
                    else:
                        fail_count += 1
                except Exception as e:
                    results.append({"account_id": account_id, "success": False, "error": str(e)})
                    fail_count += 1
                finally:
                    try:
                        os.remove(tmp_path)
                    except Exception:
                        pass

                # 账号间随机延迟 2-5 秒，避免触发风控
                if i < len(account_ids) - 1:
                    loop.run_until_complete(asyncio.sleep(random.uniform(2, 5)))

        except Exception as e:
            logger.error(f"Error processing account {account_id}: {e}")
            results.append({"account_id": account_id, "success": False, "error": str(e)})
            fail_count += 1
        finally:
            loop.close()

    logger.info(f"Batch photo update done. Success: {success_count}, Fail: {fail_count}")
    return {
        "success": True,
        "total": len(account_ids),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results,
    }


@celery_app.task(bind=True, max_retries=1, soft_time_limit=1800, time_limit=3600)
def batch_auto_update(self, account_ids: List[int], options: dict):
    """
    批量自动更新账号信息
    options: { update_profile, update_photo, update_2fa, update_username, password_2fa, avatar_style }
    """
    logger.info(f"Batch auto-update for {len(account_ids)} accounts, options={options}")

    import random

    update_profile = options.get("update_profile", False)
    update_photo = options.get("update_photo", False)
    update_2fa = options.get("update_2fa", False)
    update_username = options.get("update_username", False)
    password_2fa = options.get("password_2fa")
    avatar_style = options.get("avatar_style", "face")

    results = []
    success_count = 0
    fail_count = 0

    for i, account_id in enumerate(account_ids):
        self.update_state(state='PROGRESS', meta={
            'current': i + 1,
            'total': len(account_ids),
            'success': success_count,
            'fail': fail_count,
            'account_id': account_id,
        })

        account_ok = True
        account_errors = []

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            with Session(engine) as session:
                account = session.get(Account, account_id)
                if not account:
                    results.append({"account_id": account_id, "success": False, "errors": ["Not found"]})
                    fail_count += 1
                    continue

                if account.status == "banned":
                    results.append({"account_id": account_id, "success": False, "errors": ["Account banned"]})
                    fail_count += 1
                    continue

                # 1. 更新资料
                if update_profile:
                    try:
                        name = ProfileGenerator.generate_name()
                        about = ProfileGenerator.generate_about()
                        ok, msg = loop.run_until_complete(
                            update_profile_with_client(
                                account, name["first_name"], name["last_name"], about, db_session=session
                            )
                        )
                        if not ok:
                            account_errors.append(f"Profile: {msg}")
                            account_ok = False
                        else:
                            account.first_name = name["first_name"]
                            account.last_name = name["last_name"]
                            session.add(account)
                            session.commit()
                    except Exception as e:
                        account_errors.append(f"Profile: {e}")
                        account_ok = False

                # 2. 更新头像
                if update_photo:
                    try:
                        tmp_file = tempfile.NamedTemporaryFile(suffix=".jpg", delete=False)
                        tmp_path = tmp_file.name
                        tmp_file.close()

                        downloaded = ProfileGenerator.download_random_avatar(tmp_path)
                        if downloaded:
                            ok, msg = loop.run_until_complete(
                                update_photo_with_client(account, tmp_path, db_session=session)
                            )
                            if not ok:
                                account_errors.append(f"Photo: {msg}")
                                account_ok = False
                        else:
                            account_errors.append("Photo: Failed to download")
                            account_ok = False

                        try:
                            os.remove(tmp_path)
                        except Exception:
                            pass
                    except Exception as e:
                        account_errors.append(f"Photo: {e}")
                        account_ok = False

                # 3. 更新用户名
                if update_username:
                    try:
                        first = getattr(account, 'first_name', None) or "user"
                        last = getattr(account, 'last_name', None) or ""
                        uname = ProfileGenerator.generate_username(first, last)
                        ok, msg = loop.run_until_complete(
                            update_username_with_client(account, uname, db_session=session)
                        )
                        if not ok:
                            account_errors.append(f"Username: {msg}")
                            account_ok = False
                    except Exception as e:
                        account_errors.append(f"Username: {e}")
                        account_ok = False

                # 4. 设置 2FA
                if update_2fa:
                    try:
                        pwd = password_2fa or ProfileGenerator.generate_password()
                        ok, msg = loop.run_until_complete(
                            update_2fa_with_client(account, pwd, db_session=session)
                        )
                        if not ok:
                            account_errors.append(f"2FA: {msg}")
                            account_ok = False
                    except Exception as e:
                        account_errors.append(f"2FA: {e}")
                        account_ok = False

            if account_ok:
                success_count += 1
            else:
                fail_count += 1
            results.append({
                "account_id": account_id,
                "success": account_ok,
                "errors": account_errors if account_errors else None,
            })

            # 账号间随机延迟
            if i < len(account_ids) - 1:
                loop.run_until_complete(asyncio.sleep(random.uniform(2, 5)))

        except Exception as e:
            logger.error(f"Auto-update error for account {account_id}: {e}")
            results.append({"account_id": account_id, "success": False, "errors": [str(e)]})
            fail_count += 1
        finally:
            loop.close()

    logger.info(f"Batch auto-update done. Success: {success_count}, Fail: {fail_count}")
    return {
        "success": True,
        "total": len(account_ids),
        "success_count": success_count,
        "fail_count": fail_count,
        "results": results,
    }


@celery_app.task(bind=True, max_retries=1, soft_time_limit=600, time_limit=900)
def update_single_profile_task(self, account_id: int, first_name: str = None, last_name: str = None, about: str = None, random_mode: bool = False):
    """更新单个账号资料"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        with Session(engine) as session:
            account = session.get(Account, account_id)
            if not account:
                return {"success": False, "account_id": account_id, "error": "Not found"}

            if random_mode:
                name = ProfileGenerator.generate_name()
                first_name = name["first_name"]
                last_name = name["last_name"]
                about = ProfileGenerator.generate_about()

            ok, msg = loop.run_until_complete(
                update_profile_with_client(account, first_name, last_name, about, db_session=session)
            )
            if ok:
                if first_name:
                    account.first_name = first_name
                if last_name:
                    account.last_name = last_name
                session.add(account)
                session.commit()
            return {"success": ok, "account_id": account_id, "message": msg}
    except Exception as e:
        return {"success": False, "account_id": account_id, "error": str(e)}
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=1, soft_time_limit=600, time_limit=900)
def update_single_username_task(self, account_id: int, username: str):
    """更新单个账号用户名"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        with Session(engine) as session:
            account = session.get(Account, account_id)
            if not account:
                return {"success": False, "account_id": account_id, "error": "Not found"}

            ok, msg = loop.run_until_complete(
                update_username_with_client(account, username, db_session=session)
            )
            return {"success": ok, "account_id": account_id, "message": msg}
    except Exception as e:
        return {"success": False, "account_id": account_id, "error": str(e)}
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=1, soft_time_limit=600, time_limit=900)
def update_single_2fa_task(self, account_id: int, password: str, current_password: str = None, hint: str = None):
    """更新单个账号 2FA"""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        with Session(engine) as session:
            account = session.get(Account, account_id)
            if not account:
                return {"success": False, "account_id": account_id, "error": "Not found"}

            ok, msg = loop.run_until_complete(
                update_2fa_with_client(account, password, current_password, hint, db_session=session)
            )
            return {"success": ok, "account_id": account_id, "message": msg}
    except Exception as e:
        return {"success": False, "account_id": account_id, "error": str(e)}
    finally:
        loop.close()
