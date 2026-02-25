"""
Session 文件加密服务
使用 AES-256-GCM 加密 Telegram session 文件
"""
import os
import base64
import hashlib
import logging
from pathlib import Path
from typing import Optional, Tuple
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

# 加密文件标识头
ENCRYPTED_HEADER = b"TGSC_ENC_V1"


class SessionEncryption:
    """Session 文件加密/解密服务"""
    
    def __init__(self, encryption_key: str):
        """
        初始化加密服务
        
        Args:
            encryption_key: 加密密钥 (至少 32 个字符的十六进制字符串)
        """
        if not encryption_key or len(encryption_key) < 32:
            raise ValueError("Encryption key must be at least 32 hex characters")
        
        # 从十六进制字符串派生 256-bit AES 密钥
        self.key = self._derive_key(encryption_key)
    
    def _derive_key(self, password: str, salt: bytes = b"tgsc_session_salt") -> bytes:
        """使用 PBKDF2 从密码派生密钥"""
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,  # 256-bit key for AES-256
            salt=salt,
            iterations=100000,
        )
        return kdf.derive(password.encode())
    
    def encrypt_file(self, file_path: str, output_path: Optional[str] = None) -> str:
        """
        加密 session 文件
        
        Args:
            file_path: 原始文件路径
            output_path: 输出文件路径 (默认覆盖原文件)
            
        Returns:
            加密后的文件路径
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        # 读取原始内容
        with open(file_path, "rb") as f:
            plaintext = f.read()
        
        # 检查是否已加密
        if plaintext.startswith(ENCRYPTED_HEADER):
            logger.info(f"File already encrypted: {file_path}")
            return str(file_path)
        
        # 加密
        encrypted_data = self._encrypt(plaintext)
        
        # 写入
        output = Path(output_path) if output_path else file_path
        with open(output, "wb") as f:
            f.write(ENCRYPTED_HEADER)
            f.write(encrypted_data)
        
        logger.info(f"Encrypted file: {file_path} -> {output}")
        return str(output)
    
    def decrypt_file(self, file_path: str, output_path: Optional[str] = None) -> str:
        """
        解密 session 文件
        
        Args:
            file_path: 加密文件路径
            output_path: 输出文件路径 (默认返回临时文件路径)
            
        Returns:
            解密后的文件路径
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, "rb") as f:
            data = f.read()
        
        # 检查是否是加密文件
        if not data.startswith(ENCRYPTED_HEADER):
            logger.debug(f"File not encrypted, returning as-is: {file_path}")
            return str(file_path)
        
        # 移除头部并解密
        encrypted_data = data[len(ENCRYPTED_HEADER):]
        plaintext = self._decrypt(encrypted_data)
        
        # 写入临时文件或指定路径
        if output_path:
            output = Path(output_path)
        else:
            # 创建临时解密文件
            output = file_path.with_suffix(".session.dec")
        
        with open(output, "wb") as f:
            f.write(plaintext)
        
        logger.debug(f"Decrypted file: {file_path} -> {output}")
        return str(output)
    
    def decrypt_to_memory(self, file_path: str) -> bytes:
        """
        解密文件到内存 (不写入磁盘)
        
        Args:
            file_path: 加密文件路径
            
        Returns:
            解密后的原始字节数据
        """
        file_path = Path(file_path)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        with open(file_path, "rb") as f:
            data = f.read()
        
        if not data.startswith(ENCRYPTED_HEADER):
            return data
        
        encrypted_data = data[len(ENCRYPTED_HEADER):]
        return self._decrypt(encrypted_data)
    
    def is_encrypted(self, file_path: str) -> bool:
        """检查文件是否已加密"""
        try:
            with open(file_path, "rb") as f:
                header = f.read(len(ENCRYPTED_HEADER))
            return header == ENCRYPTED_HEADER
        except Exception:
            return False
    
    def _encrypt(self, plaintext: bytes) -> bytes:
        """AES-256-GCM 加密"""
        # 生成随机 nonce (12 bytes for GCM)
        nonce = os.urandom(12)
        
        aesgcm = AESGCM(self.key)
        ciphertext = aesgcm.encrypt(nonce, plaintext, None)
        
        # 返回 nonce + ciphertext
        return nonce + ciphertext
    
    def _decrypt(self, encrypted_data: bytes) -> bytes:
        """AES-256-GCM 解密"""
        if len(encrypted_data) < 12:
            raise ValueError("Invalid encrypted data: too short")
        
        # 分离 nonce 和 ciphertext
        nonce = encrypted_data[:12]
        ciphertext = encrypted_data[12:]
        
        aesgcm = AESGCM(self.key)
        return aesgcm.decrypt(nonce, ciphertext, None)


# 全局加密服务实例 (延迟初始化)
_encryption_service: Optional[SessionEncryption] = None


def get_encryption_service() -> SessionEncryption:
    """获取全局加密服务实例"""
    global _encryption_service
    
    if _encryption_service is None:
        from app.core.config import settings
        _encryption_service = SessionEncryption(settings.SESSION_ENCRYPTION_KEY)
    
    return _encryption_service


def encrypt_session_file(file_path: str) -> str:
    """便捷函数：加密 session 文件"""
    return get_encryption_service().encrypt_file(file_path)


def decrypt_session_file(file_path: str) -> str:
    """便捷函数：解密 session 文件到临时文件"""
    return get_encryption_service().decrypt_file(file_path)


def is_session_encrypted(file_path: str) -> bool:
    """便捷函数：检查 session 文件是否已加密"""
    return get_encryption_service().is_encrypted(file_path)
