import os
import shutil
import logging
import subprocess
import sys
from typing import Optional, Dict
from opentele.td import TDesktop
from opentele.api import API
import asyncio

logger = logging.getLogger(__name__)

def is_tdata_session(path: str) -> bool:
    """检查路径是否为 TData 目录"""
    if os.path.isdir(path):
        # Check for typical TData files
        # key_datas is standard in newer tdata
        if os.path.exists(os.path.join(path, "key_datas")):
            return True
        # Older versions might have D877... map files directly
        for f in os.listdir(path):
            if len(f) == 16 and f.isalnum(): # Simple check for map files
                return True
    return False


async def convert_tdata_to_session(tdata_path: str, output_path_base: str, verify: bool = False) -> Optional[str]:
    """
    将 TData 目录转换为 Telethon Session 文件
    使用 tdata_converter_script.py 子进程执行转换
    返回生成的 session 文件路径 (带 .session 扩展名)
    """
    try:
        # Remove .session extension if present (script will add it)
        if output_path_base.endswith('.session'):
            output_path_base = output_path_base[:-8]
        
        session_path = output_path_base + '.session'
        
        # Run the converter script as subprocess to avoid Qt/GUI issues
        script_path = os.path.join(os.path.dirname(__file__), 'tdata_converter_script.py')
        
        logger.info(f"Converting tdata: {tdata_path} -> {session_path}")
        
        cmd = [sys.executable, script_path, tdata_path, output_path_base]
        if verify:
            cmd.append("--verify")

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        if result.returncode != 0:
            logger.error(f"tdata_converter_script failed: {result.stderr}")
            return None
        
        # Parse JSON output
        try:
            output = result.stdout.strip().split('\n')[-1]  # Get last line (JSON result)
            result_data = __import__('json').loads(output)
            if result_data.get('success'):
                return session_path
            else:
                logger.error(f"Conversion failed: {result_data.get('error')}")
                return None
        except Exception as e:
            logger.error(f"Failed to parse converter output: {e}, stdout: {result.stdout}")
            return None
            
    except subprocess.TimeoutExpired:
        logger.error("tdata conversion timed out")
        return None
    except Exception as e:
        logger.error(f"tdata conversion error: {e}")
        return None

async def convert_tdata_to_pyrogram(tdata_path: str, session_file_path: str) -> Optional[Dict]:
    """
    将 TData 目录转换为 Pyrogram Session 文件
    """
    try:
        # Load TData
        tdata = TDesktop(tdata_path)
        
        # Check if loaded successfully
        if not tdata.isLoaded():
            logger.error(f"Failed to load TData from {tdata_path}")
            return None

        # Convert to Pyrogram
        # We assume standard API ID/Hash for initial conversion. 
        # The AuthKey is what matters.
        # Opentele uses a default API ID if not specified.
        
        # ToPyrogram returns a Client object and saves the session file
        client = await tdata.ToPyrogram(session_file_path)
        
        # Extract basic info if possible
        # TDesktop stores config in encrypted maps, opentele handles decryption
        # We can try to peek at client properties but Pyrogram client is fresh
        
        # Return empty dict for device info as we can't easily extract original device params from TData maps
        # without deeper TData parsing which opentele might not expose fully for device params.
        # However, TData represents a "Desktop" session usually.
        
        return {
            "device_model": "Desktop", 
            "system_version": "Windows/Linux", # Generic assumption for TData
            "app_version": "Unknown"
        }

    except Exception as e:
        logger.error(f"TData conversion error: {e}")
        # Cleanup if failed
        if os.path.exists(session_file_path):
            try:
                os.remove(session_file_path)
            except: pass
        return None
