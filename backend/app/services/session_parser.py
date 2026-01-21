"""
Session 文件解析服务
从 Pyrogram session 文件名或内容中提取账号信息
"""
import os
import re
from typing import Optional, Tuple
from pathlib import Path

def parse_session_filename(filename: str) -> Optional[str]:
    """
    从 session 文件名中提取手机号
    Pyrogram session 文件名格式通常是: +1234567890.session
    """
    # 移除扩展名
    name_without_ext = os.path.splitext(filename)[0]
    
    # 尝试匹配手机号格式（+数字 或 纯数字）
    # 匹配 +1234567890 或 1234567890 格式
    phone_match = re.match(r'^\+?(\d+)$', name_without_ext)
    if phone_match:
        phone = phone_match.group(1)
        # 如果前面没有 +，添加 +
        if not phone.startswith('+'):
            phone = '+' + phone
        return phone
    
    # 如果文件名就是手机号格式
    if re.match(r'^\+?\d{7,15}$', name_without_ext):
        if not name_without_ext.startswith('+'):
            return '+' + name_without_ext
        return name_without_ext
    
    return None

def extract_phone_from_session_file(file_path: str) -> Optional[str]:
    """
    从 session 文件路径中提取手机号
    优先从文件名提取，如果失败则尝试从文件内容提取
    """
    filename = os.path.basename(file_path)
    
    # 方法1: 从文件名提取
    phone = parse_session_filename(filename)
    if phone:
        return phone
    
    # 方法2: 尝试从文件内容提取（Pyrogram session 文件可能包含手机号信息）
    try:
        with open(file_path, 'rb') as f:
            # 读取文件内容（session 文件是二进制格式）
            content = f.read()
            # 尝试查找手机号模式
            # 注意：这是简化实现，实际 Pyrogram session 文件格式更复杂
            text_content = content.decode('utf-8', errors='ignore')
            phone_match = re.search(r'\+?\d{7,15}', text_content)
            if phone_match:
                phone = phone_match.group(0)
                if not phone.startswith('+'):
                    phone = '+' + phone
                return phone
    except Exception:
        pass
    
    return None

def parse_session_file(file_path: str, filename: str) -> Tuple[Optional[str], dict]:
    """
    解析 session 文件，返回手机号和其他信息
    返回: (phone_number, extra_info)
    """
    phone = extract_phone_from_session_file(file_path)
    
    extra_info = {
        'filename': filename,
        'file_path': file_path,
    }
    
    return phone, extra_info
