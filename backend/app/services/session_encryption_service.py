"""
Session 加密管理服务
提供批量加密/解密 session 文件的功能
"""
import os
import logging
from pathlib import Path
from typing import List, Dict, Optional
from sqlmodel import Session, select
from app.models.account import Account
from app.core.encryption import get_encryption_service, is_session_encrypted, encrypt_session_file

logger = logging.getLogger(__name__)


class SessionEncryptionService:
    """Session 文件加密管理服务"""
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self.encryption_service = get_encryption_service()
    
    def encrypt_all_sessions(self, sessions_dir: str = "sessions") -> Dict[str, any]:
        """
        加密所有未加密的 session 文件
        
        Returns:
            统计信息 {encrypted: int, already_encrypted: int, failed: int, errors: list}
        """
        result = {
            "encrypted": 0,
            "already_encrypted": 0,
            "failed": 0,
            "errors": []
        }
        
        sessions_path = Path(sessions_dir)
        if not sessions_path.exists():
            logger.warning(f"Sessions directory not found: {sessions_dir}")
            return result
        
        # 遍历所有 .session 文件
        for session_file in sessions_path.glob("*.session"):
            try:
                if is_session_encrypted(str(session_file)):
                    result["already_encrypted"] += 1
                    logger.debug(f"Already encrypted: {session_file}")
                else:
                    encrypt_session_file(str(session_file))
                    result["encrypted"] += 1
                    logger.info(f"Encrypted: {session_file}")
            except Exception as e:
                result["failed"] += 1
                result["errors"].append(f"{session_file}: {str(e)}")
                logger.error(f"Failed to encrypt {session_file}: {e}")
        
        return result
    
    def encrypt_account_sessions(self, account_ids: Optional[List[int]] = None) -> Dict[str, any]:
        """
        加密指定账号的 session 文件
        
        Args:
            account_ids: 要加密的账号 ID 列表，None 表示所有账号
            
        Returns:
            统计信息
        """
        result = {
            "encrypted": 0,
            "already_encrypted": 0,
            "failed": 0,
            "not_found": 0,
            "errors": []
        }
        
        # 获取账号列表
        if account_ids:
            accounts = self.db_session.exec(
                select(Account).where(Account.id.in_(account_ids))
            ).all()
        else:
            accounts = self.db_session.exec(select(Account)).all()
        
        for account in accounts:
            if not account.session_file_path:
                continue
                
            if not os.path.exists(account.session_file_path):
                result["not_found"] += 1
                continue
            
            try:
                if is_session_encrypted(account.session_file_path):
                    result["already_encrypted"] += 1
                else:
                    encrypt_session_file(account.session_file_path)
                    result["encrypted"] += 1
                    logger.info(f"Encrypted session for account {account.id}: {account.phone_number}")
            except Exception as e:
                result["failed"] += 1
                result["errors"].append(f"Account {account.id}: {str(e)}")
                logger.error(f"Failed to encrypt session for account {account.id}: {e}")
        
        return result
    
    def get_encryption_status(self) -> Dict[str, any]:
        """
        获取所有账号的 session 加密状态
        
        Returns:
            统计信息
        """
        result = {
            "total": 0,
            "encrypted": 0,
            "unencrypted": 0,
            "no_session": 0,
            "file_missing": 0
        }
        
        accounts = self.db_session.exec(select(Account)).all()
        result["total"] = len(accounts)
        
        for account in accounts:
            if not account.session_file_path:
                result["no_session"] += 1
            elif not os.path.exists(account.session_file_path):
                result["file_missing"] += 1
            elif is_session_encrypted(account.session_file_path):
                result["encrypted"] += 1
            else:
                result["unencrypted"] += 1
        
        return result


def encrypt_new_session_file(file_path: str) -> str:
    """
    加密新导入的 session 文件
    
    Args:
        file_path: session 文件路径
        
    Returns:
        加密后的文件路径
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Session file not found: {file_path}")
    
    if is_session_encrypted(file_path):
        logger.debug(f"Session already encrypted: {file_path}")
        return file_path
    
    return encrypt_session_file(file_path)
