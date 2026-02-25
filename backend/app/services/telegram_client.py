"""
Telegram 客户端服务
用于初始化和管理 Pyrogram 客户端
"""
import os
import asyncio
import random
import logging
import tempfile
import shutil
from typing import Optional, Tuple, List, Dict, Any, Literal
from datetime import datetime, timedelta
from contextlib import contextmanager
from sqlmodel import Session
from pyrogram import Client, enums
from pyrogram.errors import (
    FloodWait,
    PeerFlood,
    UserBannedInChannel,
    UserDeactivated,
    AuthKeyUnregistered,
    SessionRevoked,
    FloodTestPhoneWait,
    PhoneNumberBanned,
    PhoneNumberInvalid,
    PhoneCodeInvalid,
    PhoneCodeExpired,
    InviteHashExpired,
    InviteHashInvalid
)
from app.models.account import Account
from app.models.proxy import Proxy
from app.services.device_generator import DeviceGenerator
from app.services.session_converter import is_telethon_session, convert_telethon_to_pyrogram
from app.core.exceptions import (
    AccountFloodWaitException,
    AccountBannedException,
    AccountSpamBlockException,
    AccountSessionInvalidException,
    AccountException
)
from app.services.client_pool import client_pool

logger = logging.getLogger(__name__)


@contextmanager
def decrypted_session_file(session_file_path: str):
    """
    上下文管理器：解密 session 文件用于临时使用
    
    如果文件已加密，解密到临时目录
    如果文件未加密，直接返回原路径
    使用完毕后自动清理临时文件
    """
    temp_dir = None
    temp_session_path = None
    
    try:
        # 延迟导入避免循环依赖
        from app.core.encryption import is_session_encrypted, get_encryption_service
        
        if is_session_encrypted(session_file_path):
            # 创建临时目录
            temp_dir = tempfile.mkdtemp(prefix="tgsc_session_")
            
            # 解密到临时文件
            encryption_service = get_encryption_service()
            decrypted_data = encryption_service.decrypt_to_memory(session_file_path)
            
            # 保持原文件名
            original_name = os.path.basename(session_file_path)
            temp_session_path = os.path.join(temp_dir, original_name)
            
            with open(temp_session_path, "wb") as f:
                f.write(decrypted_data)
            
            logger.debug(f"Decrypted session to temp: {temp_session_path}")
            yield temp_session_path, temp_dir
        else:
            # 未加密，直接使用原文件
            yield session_file_path, os.path.dirname(session_file_path)
            
    except ImportError:
        # 如果加密模块不可用，直接使用原文件
        logger.warning("Encryption module not available, using unencrypted session")
        yield session_file_path, os.path.dirname(session_file_path)
        
    finally:
        # 清理临时文件
        if temp_dir and os.path.exists(temp_dir):
            try:
                shutil.rmtree(temp_dir)
                logger.debug(f"Cleaned up temp session dir: {temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to clean up temp dir {temp_dir}: {e}")

def get_proxy_dict(proxy: Optional[Proxy]) -> Optional[dict]:
    """将 Proxy 模型转换为 Pyrogram 可用的代理字典"""
    if not proxy:
        return None
    
    proxy_url = f"{proxy.protocol}://"
    if proxy.username and proxy.password:
        proxy_url += f"{proxy.username}:{proxy.password}@"
    proxy_url += f"{proxy.ip}:{proxy.port}"
    
    return {
        "scheme": proxy.protocol,
        "hostname": proxy.ip,
        "port": proxy.port,
        "username": proxy.username,
        "password": proxy.password,
    }

async def send_message_with_client(account: Account, username: str, message: str, db_session: Optional[Session] = None) -> Tuple[bool, str]:
    """
    使用 Pyrogram 客户端发送消息
    返回: (success, result_message)
    """
    async def try_send(use_ipv6: bool = False):
        client = None
        try:
            # 准备代理配置
            proxy = account.proxy
            proxy_dict = get_proxy_dict(proxy) if proxy else None
            
            # 准备 API 凭证
            # 优先使用数据库中的配置，否则使用默认值
            api_id = account.api_id or 6
            api_hash = account.api_hash or "eb06d4abfb49dc3eeb1aeb98ae0f581e"
            
            # 检查并生成设备指纹 (如果提供了 db_session)
            if db_session and not account.device_model:
                dev_info = DeviceGenerator.generate()
                account.device_model = dev_info["device_model"]
                account.system_version = dev_info["system_version"]
                account.app_version = dev_info["app_version"]
                db_session.add(account)
                db_session.commit()
                db_session.refresh(account)

            # 准备设备指纹
            client_params = {
                "api_id": api_id,
                "api_hash": api_hash,
                "proxy": proxy_dict,
                "device_model": account.device_model,
                "system_version": account.system_version,
                "app_version": account.app_version,
                "lang_code": "en",
                "ipv6": use_ipv6
            }
            
            if account.session_file_path and os.path.exists(account.session_file_path):
                # 确保是 Pyrogram 格式
                if is_telethon_session(account.session_file_path):
                    if not convert_telethon_to_pyrogram(account.session_file_path):
                        return False, "Failed to convert Telethon session"
                
                session_name = os.path.splitext(os.path.basename(account.session_file_path))[0]
                client = Client(
                    name=session_name,
                    workdir="sessions",
                    **client_params
                )
            else:
                return False, "No session file"

            # 连接并发送
            await client.connect()
            
            try:
                # 模拟真人行为
                
                # 1. 随机延迟 (1-3秒)
                await asyncio.sleep(random.uniform(1.0, 3.0))

                # 2. 模拟打字状态 (Typing Action)
                try:
                    await client.send_chat_action(username, enums.ChatAction.TYPING)
                    # 假装打字 2-5 秒
                    await asyncio.sleep(random.uniform(2.0, 5.0)) 
                except Exception:
                    # 某些情况下（如没有权限）可能失败，忽略
                    pass

                sent_msg = await client.send_message(username, message)
                return True, "Message sent"
            finally:
                if client.is_connected:
                    await client.disconnect()
                    
        except FloodWait as e:
            if db_session:
                account.status = "flood_wait"
                account.cooldown_until = datetime.utcnow() + timedelta(seconds=e.value)
                db_session.add(account)
                db_session.commit()
            raise AccountFloodWaitException(e.value)
            
        except (UserBannedInChannel, UserDeactivated, PhoneNumberBanned) as e:
            if db_session:
                account.status = "banned"
                db_session.add(account)
                db_session.commit()
            raise AccountBannedException(str(e))

        except PeerFlood as e:
            if db_session:
                # PeerFlood usually means temporary restriction or spamblock
                account.status = "flood_wait"
                # Default 1 hour for peer flood
                account.cooldown_until = datetime.utcnow() + timedelta(hours=1)
                db_session.add(account)
                db_session.commit()
            raise AccountFloodWaitException(3600, message=f"PeerFlood: {str(e)}")

        except Exception as e:
            error_str = str(e)
            if any(x in error_str for x in ["Connection refused", "0x05", "Network is unreachable", "OSError", "[Errno 111]"]):
                raise e # 抛出异常以触发重试
            return False, f"Failed: {error_str}"
        finally:
            if client and client.is_connected:
                try:
                    await client.stop()
                except Exception:
                    pass

    # 重试逻辑
    try:
        return await try_send(use_ipv6=False)
    except Exception as e:
        error_str = str(e)
        if account.proxy and any(x in error_str for x in ["Connection refused", "0x05", "Network is unreachable", "OSError", "[Errno 111]"]):
            try:
                return await try_send(use_ipv6=True)
            except Exception as e2:
                return False, f"Network failed (IPv4/IPv6): {str(e2)}"
        
        # If it's one of our custom exceptions, re-raise it
        if isinstance(e, AccountException):
            raise e
            
        return False, f"Error: {error_str}"

async def _create_client_and_run(account: Account, operation, *args, db_session: Optional[Session] = None, **kwargs) -> Tuple[bool, Any]:
    """通用客户端执行帮助函数"""
    async def try_op(use_ipv6: bool = False):
        client = None
        try:
            # 准备代理配置
            proxy = account.proxy
            proxy_dict = get_proxy_dict(proxy) if proxy else None
            
            # 准备 API 凭证
            api_id = account.api_id or 6
            api_hash = account.api_hash or "eb06d4abfb49dc3eeb1aeb98ae0f581e"
            
            # 检查并生成设备指纹
            if db_session and not account.device_model:
                dev_info = DeviceGenerator.generate()
                account.device_model = dev_info["device_model"]
                account.system_version = dev_info["system_version"]
                account.app_version = dev_info["app_version"]
                db_session.add(account)
                db_session.commit()
                db_session.refresh(account)

            # 准备设备指纹
            client_params = {
                "api_id": api_id,
                "api_hash": api_hash,
                "proxy": proxy_dict,
                "device_model": account.device_model,
                "system_version": account.system_version,
                "app_version": account.app_version,
                "lang_code": "en",
                "ipv6": use_ipv6
            }
            
            if account.session_file_path and os.path.exists(account.session_file_path):
                if is_telethon_session(account.session_file_path):
                    if not convert_telethon_to_pyrogram(account.session_file_path):
                        return False, "Failed to convert Telethon session"
                
                session_name = os.path.splitext(os.path.basename(account.session_file_path))[0]
                client = Client(
                    name=session_name,
                    workdir="sessions",
                    **client_params
                )
            else:
                return False, "No session file"

            # 连接
            await client.connect()
            try:
                # 执行操作
                result = await operation(client, *args, **kwargs)
                return True, result
            finally:
                if client.is_connected:
                    await client.disconnect()
                    
        except FloodWait as e:
            if db_session:
                account.status = "flood_wait"
                account.cooldown_until = datetime.utcnow() + timedelta(seconds=e.value)
                db_session.add(account)
                db_session.commit()
            raise AccountFloodWaitException(e.value)

        except (UserBannedInChannel, UserDeactivated, PhoneNumberBanned) as e:
            if db_session:
                account.status = "banned"
                db_session.add(account)
                db_session.commit()
            raise AccountBannedException(str(e))
            
        except PeerFlood as e:
            if db_session:
                account.status = "flood_wait"
                account.cooldown_until = datetime.utcnow() + timedelta(hours=1)
                db_session.add(account)
                db_session.commit()
            raise AccountFloodWaitException(3600, message=f"PeerFlood: {str(e)}")

        except Exception as e:
            error_str = str(e)
            if any(x in error_str for x in ["Connection refused", "0x05", "Network is unreachable", "OSError", "[Errno 111]"]):
                raise e # 抛出异常以触发重试
            return False, f"Failed: {error_str}"
        finally:
            if client and client.is_connected:
                try:
                    await client.stop()
                except Exception:
                    pass

    # 重试逻辑
    try:
        return await try_op(use_ipv6=False)
    except Exception as e:
        error_str = str(e)
        if account.proxy and any(x in error_str for x in ["Connection refused", "0x05", "Network is unreachable", "OSError", "[Errno 111]"]):
            try:
                return await try_op(use_ipv6=True)
            except Exception as e2:
                return False, f"Network failed (IPv4/IPv6): {str(e2)}"
        
        if isinstance(e, AccountException):
            raise e
            
        return False, f"Error: {error_str}"

async def update_profile_with_client(account: Account, first_name: Optional[str] = None, last_name: Optional[str] = None, about: Optional[str] = None, db_session: Optional[Session] = None) -> Tuple[bool, str]:
    async def op(client, fname, lname, bio):
        await client.update_profile(first_name=fname, last_name=lname, bio=bio)
        return "Profile updated"
    return await _create_client_and_run(account, op, first_name, last_name, about, db_session=db_session)

async def update_username_with_client(account: Account, username: str, db_session: Optional[Session] = None) -> Tuple[bool, str]:
    async def op(client, uname):
        await client.set_username(uname)
        return "Username updated"
    return await _create_client_and_run(account, op, username, db_session=db_session)

async def update_photo_with_client(account: Account, photo_path: str, db_session: Optional[Session] = None) -> Tuple[bool, str]:
    async def op(client, path):
        await client.set_profile_photo(photo=path)
        return "Profile photo updated"
    return await _create_client_and_run(account, op, photo_path, db_session=db_session)

async def update_2fa_with_client(account: Account, password: str, current_password: Optional[str] = None, hint: Optional[str] = None, db_session: Optional[Session] = None) -> Tuple[bool, str]:
    async def op(client, pwd, cur_pwd, pwd_hint):
        if cur_pwd:
             await client.change_cloud_password(current_password=cur_pwd, new_password=pwd, hint=pwd_hint)
             return "2FA password changed"
        else:
             await client.enable_cloud_password(password=pwd, hint=pwd_hint)
             return "2FA password enabled"
    return await _create_client_and_run(account, op, password, current_password, hint, db_session=db_session)

async def join_group_with_client(account: Account, invite_link: str, db_session: Optional[Session] = None) -> Tuple[bool, str]:
    """加入群组"""
    async def op(client, link):
        try:
            # 处理链接格式
            # Pyrogram join_chat 接受：
            # - username 直接 (如 "kltgsc" 或 "@kltgsc")
            # - 邀请链接 (如 "https://t.me/+xxxxx")
            chat_identifier = link.strip()
            
            # 如果是完整 URL，需要处理
            if chat_identifier.startswith("https://t.me/") or chat_identifier.startswith("http://t.me/"):
                # 检查是否是邀请链接
                if "/+" in chat_identifier or "/joinchat/" in chat_identifier:
                    # 私有邀请链接 - 直接使用
                    pass
                else:
                    # 公开频道 URL 如 https://t.me/kltgsc - 提取用户名
                    chat_identifier = chat_identifier.split("/")[-1]
            elif chat_identifier.startswith("t.me/"):
                if "/+" in chat_identifier or "/joinchat/" in chat_identifier:
                    chat_identifier = "https://" + chat_identifier
                else:
                    chat_identifier = chat_identifier.replace("t.me/", "")
            
            # 移除 @ 前缀（Pyrogram 可以处理带或不带 @）
            if chat_identifier.startswith("@"):
                chat_identifier = chat_identifier[1:]
            
            logger.info(f"Joining chat with identifier: {chat_identifier} (original: {link})")
            
            # 先检查是否已经在群里
            try:
                existing_chat = await client.get_chat(chat_identifier)
                logger.info(f"Already in chat: {existing_chat.title} (ID: {existing_chat.id})")
                return f"Already in group: {existing_chat.title}"
            except Exception as check_e:
                logger.info(f"Not in chat yet, attempting to join... (check error: {check_e})")
            
            result = await client.join_chat(chat_identifier)
            logger.info(f"Join result: {result.title if hasattr(result, 'title') else result}")
            return f"Joined successfully: {result.title if hasattr(result, 'title') else chat_identifier}"
            
        except InviteHashExpired:
            return "Invite link expired"
        except InviteHashInvalid:
            return "Invite link invalid"
        except UserBannedInChannel:
            return "Banned in channel"
        except Exception as e:
            error_str = str(e)
            logger.warning(f"Join chat exception: {error_str}")
            if "USER_ALREADY_PARTICIPANT" in error_str:
                return "Already joined"
            if "INVITE_REQUEST_SENT" in error_str:
                return "Join request sent (pending approval)"
            if "CHANNELS_TOO_MUCH" in error_str:
                return "Too many channels joined"
            if "USERNAME_INVALID" in error_str:
                return f"Invalid username: {link}"
            if "USERNAME_NOT_OCCUPIED" in error_str:
                return f"Username not found: {link}"
            raise e
            
    return await _create_client_and_run(account, op, invite_link, db_session=db_session)

async def scrape_group_members(
    account: Account, 
    group_link: str, 
    limit: int = 100, 
    db_session: Optional[Session] = None,
    filter_config: Optional[Dict[str, bool]] = None
) -> Tuple[bool, List[Dict]]:
    """采集群成员 (支持高质量用户过滤)
    
    Args:
        filter_config: 过滤配置
            - active_only: 仅保留最近一周活跃用户
            - has_photo: 仅保留有头像的用户
            - has_username: 仅保留有用户名的用户
    """
    async def op(client, link, max_limit, filters):
        try:
            # 如果是链接，先加入或获取信息
            if "t.me" in link or link.startswith("@"):
                chat = await client.get_chat(link)
                chat_id = chat.id
            else:
                chat_id = int(link)
        except Exception as e:
            logger.warning(f"Failed to get chat {link}: {e}")
            return []

        members = []
        scanned_count = 0
        # 扫描数量上限设为目标数量的10倍，防止死循环
        max_scan = max_limit * 10
        
        # 不限制 API 返回数量，手动控制过滤后的数量
        async for member in client.get_chat_members(chat_id):
            scanned_count += 1
            if scanned_count > max_scan:
                break
                
            user = member.user
            # 1. 基础过滤：排除机器人和已删除账号
            if user.is_bot or user.is_deleted:
                continue
                
            # 2. 高级过滤
            if filters:
                # 排除无头像用户
                if filters.get('has_photo') and not user.photo:
                    continue
                
                # 排除无用户名用户
                if filters.get('has_username') and not user.username:
                    continue
                    
                # 排除不活跃用户 (排除一个月以上未登录的)
                if filters.get('active_only'):
                    # Pyrogram UserStatus: ONLINE, OFFLINE, RECENTLY, LAST_WEEK, LAST_MONTH, LONG_AGO
                    # 我们保留: ONLINE, RECENTLY, LAST_WEEK (最近7天内活跃)
                    # 排除: LONG_AGO (>1月), LAST_MONTH (>1周)
                    if user.status in [enums.UserStatus.LONG_AGO, enums.UserStatus.LAST_MONTH]:
                        continue
                    if user.status is None:  # 状态隐藏也视为不活跃
                        continue

            members.append({
                "telegram_id": user.id,
                "username": user.username,
                "first_name": user.first_name,
                "last_name": user.last_name,
                "phone": user.phone_number,
                "source_group": link,
                "source_group_id": chat_id
            })
            
            if len(members) >= max_limit:
                break
                
        logger.info(f"Scraped {len(members)} members from {link} (scanned {scanned_count})")
        return members

    return await _create_client_and_run(account, op, group_link, limit, filter_config, db_session=db_session)


async def check_account_with_client(
    account: Account,
    proxy: Optional[Proxy] = None,
    mode: Literal["safe", "full"] = "full",
) -> Tuple[str, Optional[str], Optional[datetime], Optional[dict]]:
    """
    使用 Pyrogram 客户端检查账号状态
    返回: (status, error_message, last_active, device_info)
    """
    client = None
    device_info = {}
    
    try:
        # 准备代理配置
        proxy_dict = get_proxy_dict(proxy) if proxy else None
        
        # 准备 API 凭证（如果账号有的话）
        api_id = account.api_id
        api_hash = account.api_hash
        
        # 如果没有 API 凭证，使用默认值（Telegram Android）
        if not api_id:
            api_id = 6
        if not api_hash:
            api_hash = "eb06d4abfb49dc3eeb1aeb98ae0f581e"
        
        # 准备设备指纹
        if account.device_model:
            device_info = {
                "device_model": account.device_model,
                "system_version": account.system_version,
                "app_version": account.app_version
            }
        else:
            # 如果账号没有设备信息，随机生成一套
            # 注意：在 worker.py 中调用此函数前，应尽量先生成并保存指纹
            # 这里保留生成逻辑作为后备
            device_info = DeviceGenerator.generate()
        
        # 创建客户端
        client_params = {
            "api_id": api_id,
            "api_hash": api_hash,
            "proxy": proxy_dict,
            "device_model": device_info.get("device_model"),
            "system_version": device_info.get("system_version"),
            "app_version": device_info.get("app_version"),
            # 语言代码也可以随机化，这里先固定
            "lang_code": "en" 
        }
        
        if account.session_string:
            # 使用 session string
            client = Client(
                name=f"check_{account.id}",
                session_string=account.session_string,
                in_memory=True,
                **client_params
            )
        elif account.session_file_path and os.path.exists(account.session_file_path):
            # 使用 session 文件
            # 检查是否为 Telethon 格式，如果是则转换
            if is_telethon_session(account.session_file_path):
                if not convert_telethon_to_pyrogram(account.session_file_path):
                    return "error", "Failed to convert Telethon session", None, None
            
            # 从文件路径提取 session name（去掉路径和扩展名）
            session_name = os.path.splitext(os.path.basename(account.session_file_path))[0]
            client = Client(
                name=session_name,
                workdir="sessions",
                **client_params
            )
        else:
            return "error", "No session data available", None, None
        
        # 连接并检查
        # 不使用 start()，因为它会触发交互式登录流程（如果 user_id 为 0）
        await client.connect()
        try:
            me = await client.get_me()
            # 低风险模式：只做最基础的连接验证，避免触发风控
            # - 不给自己发消息
            # - 不做搜索测试
            # 仅靠 connect/get_me 与异常类型来判断可用性
            if mode == "full":
                # 检查账号是否已注销：尝试给自己发消息
                try:
                    test_msg = await client.send_message("me", "TGSC Status Check")
                    await test_msg.delete()
                except Exception as e:
                    error_str = str(e)
                    if "PEER_ID_INVALID" in error_str:
                        # 无法给自己发消息，账号已注销
                        return "banned", "账号已注销: 无法执行任何操作", None, None
                    elif "USER_DEACTIVATED" in error_str or "AUTH_KEY_UNREGISTERED" in error_str:
                        return "banned", f"账号已注销: {error_str}", None, None
                
                # 检查账号是否受限 (Search Ban / Spam Block)
                # 尝试解析一个一定会存在的官方账号，如 @Telegram
                try:
                    await client.get_users("Telegram")
                except Exception as e:
                    error_str = str(e)
                    if "USERNAME_NOT_OCCUPIED" in error_str or "USERNAME_INVALID" in error_str:
                         # 无法解析官方账号，说明被限制了
                         return "spam_block", "账号受限: 无法搜索用户 (Search Ban)", datetime.utcnow(), device_info
                
        finally:
            # 无论成功失败，都要尝试断开
            if client.is_connected:
                await client.disconnect()
        
        # 如果成功连接，且使用了新的设备信息，返回这套信息以便更新到数据库
        
        # 成功（safe 模式只保证“能连 + 能 get_me”，不保证不受限）
        return "active", None, datetime.utcnow(), device_info
        
    except FloodWait as e:
        # 需要等待
        wait_time = e.value
        return "flood_wait", f"FloodWait: 需要等待 {wait_time} 秒", None, None
        
    except PeerFlood as e:
        return "flood_wait", f"PeerFlood: {str(e)}", None, None
        
    except (UserBannedInChannel, UserDeactivated, PhoneNumberBanned) as e:
        return "banned", f"账号被封禁: {str(e)}", None, None
        
    except (AuthKeyUnregistered, SessionRevoked) as e:
        return "session_invalid", f"Session 无效: {str(e)}", None, None
        
    except PhoneNumberInvalid:
        return "error", "手机号无效", None, None
        
    except (PhoneCodeInvalid, PhoneCodeExpired):
        return "error", "验证码错误或过期", None, None
        
    except FloodTestPhoneWait as e:
        return "flood_wait", f"测试手机号需要等待: {str(e)}", None, None
        
    except Exception as e:
        error_msg = str(e)
        # 检查是否是代理相关错误
        if any(x in error_msg.lower() for x in ["proxy", "connection", "eof", "time out", "timed out"]):
            return "proxy_error", f"网络/代理连接失败: {error_msg}", None, None
        return "error", f"未知错误: {error_msg}", None, None
        
    finally:
        # 清理工作已在 try 块中处理，这里不需要重复 stop
        pass


async def check_spambot_status(account: Account, db_session: Optional[Session] = None) -> Dict[str, Any]:
    """
    主动向 @SpamBot 发起查询，获取账号的详细受限状态
    
    Returns:
        {
            "status": "clean" | "restricted" | "error",
            "is_restricted": bool,
            "restriction_type": "none" | "temporary" | "permanent",
            "restriction_reason": str (可选),
            "expires_at": str (可选, 临时限制的解除时间),
            "raw_response": str (SpamBot 的原始回复)
        }
    """
    async def op(client):
        import re
        result = {
            "status": "error",
            "is_restricted": False,
            "restriction_type": "none",
            "raw_response": ""
        }
        
        try:
            # 发送 /start 给 SpamBot
            await client.send_message("SpamBot", "/start")
            await asyncio.sleep(3)  # 等待回复
            
            # 获取最新回复
            async for msg in client.get_chat_history("SpamBot", limit=1):
                text = msg.text or ""
                result["raw_response"] = text[:500]
                
                # 分析回复内容
                text_lower = text.lower()
                
                # 情况 1: 无限制
                if "good news" in text_lower or "no limits" in text_lower or "没有限制" in text_lower:
                    result["status"] = "clean"
                    result["is_restricted"] = False
                    result["restriction_type"] = "none"
                    return result
                
                # 情况 2: 有限制
                result["is_restricted"] = True
                result["status"] = "restricted"
                
                # 判断是永久还是临时
                if "permanently" in text_lower or "永久" in text_lower:
                    result["restriction_type"] = "permanent"
                    result["restriction_reason"] = "账号被永久限制"
                elif "until" in text_lower or "直到" in text_lower:
                    result["restriction_type"] = "temporary"
                    # 尝试提取日期
                    # 常见格式: "until 20 January 2026" 或 "until January 20, 2026"
                    date_match = re.search(r'until\s+(\d{1,2}\s+\w+\s+\d{4}|\w+\s+\d{1,2},?\s+\d{4})', text, re.IGNORECASE)
                    if date_match:
                        result["expires_at"] = date_match.group(1)
                    result["restriction_reason"] = f"临时限制，预计解除时间: {result.get('expires_at', '未知')}"
                else:
                    result["restriction_type"] = "unknown"
                    result["restriction_reason"] = "存在限制，类型未知"
                
                return result
                
        except Exception as e:
            logger.error(f"SpamBot check failed: {e}")
            result["status"] = "error"
            result["error"] = str(e)
            return result
        
        return result
    
    return await _create_client_and_run(account, op, db_session=db_session)


async def report_proxy_issue(session: Session, proxy_id: int, issue_type: str):
    """
    上报代理问题，用于风控
    
    issue_type:
        - 'banned_account': 严重问题，此IP导致封号
        - 'flood_wait': 警告，触发FloodWait
        - 'timeout': 轻微问题，连接超时
    """
    from app.models.proxy import Proxy
    
    proxy = session.get(Proxy, proxy_id)
    if not proxy:
        return
    
    if issue_type == 'banned_account':
        # 严重：此IP可能已被标记，暂停使用
        proxy.status = 'suspicious'
        # 如果有 fail_count 字段，增加计数
        if hasattr(proxy, 'fail_count'):
            proxy.fail_count = (proxy.fail_count or 0) + 10
            if proxy.fail_count >= 30:
                proxy.status = 'blacklisted'
    elif issue_type == 'flood_wait':
        if hasattr(proxy, 'fail_count'):
            proxy.fail_count = (proxy.fail_count or 0) + 1
    elif issue_type == 'timeout':
        if hasattr(proxy, 'fail_count'):
            proxy.fail_count = (proxy.fail_count or 0) + 1
    
    session.add(proxy)
    session.commit()
    logger.info(f"Reported proxy issue: {proxy_id} - {issue_type}")
