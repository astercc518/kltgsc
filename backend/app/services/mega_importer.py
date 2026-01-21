import os
import logging
import asyncio
import shutil
import re
import subprocess
from mega import Mega
import rarfile
import zipfile
from app.services.tdata_converter import convert_tdata_to_session
from app.services.session_converter import convert_telethon_to_pyrogram

logger = logging.getLogger(__name__)

class MegaImporter:
    def __init__(self, download_dir: str = "temp_downloads"):
        self.mega = Mega()
        try:
            self.m = self.mega.login() # Login anonymous
        except Exception as e:
            logger.warning(f"Mega anonymous login failed: {e}")
            self.m = None
            
        self.download_dir = download_dir
        os.makedirs(download_dir, exist_ok=True)

    def download(self, url: str) -> str:
        """
        下载 Mega 文件
        """
        logger.info(f"Downloading from MEGA: {url}")
        
        # 优先使用 megatools (megadl) 如果可用，因为它更可靠
        try:
            # 检查 megadl 是否可用
            subprocess.run(["megadl", "--version"], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # 使用 megadl 下载
            # megadl --path=download_dir url
            # 注意: megadl 的 --path 如果是目录，必须存在
            
            # 为了准确获取文件名，我们先列出当前目录文件，下载后对比
            before_files = set(os.listdir(self.download_dir))
            
            cmd = ["megadl", "--path", self.download_dir, url]
            # Capture output to debug
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            
            # 查找新文件
            after_files = set(os.listdir(self.download_dir))
            new_files = after_files - before_files
            
            if new_files:
                # 假设只有一个新文件
                filename = list(new_files)[0]
                full_path = os.path.join(self.download_dir, filename)
                if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                    return full_path
            
            # 如果没有检测到新文件（可能是覆盖了？）尝试解析 stdout
            output = result.stderr.decode() # megadl prints to stderr usually
            match = re.search(r"Downloaded\s+(.+)", output)
            if match:
                filename = match.group(1).strip()
                full_path = os.path.join(self.download_dir, filename)
                if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                    return full_path

        except Exception as e:
            logger.warning(f"megadl failed or not installed, falling back to mega.py: {e}")

        # Fallback to mega.py
        if not self.m:
             self.m = self.mega.login()
             
        try:
            filename = self.m.download_url(url, self.download_dir)
            
            full_path = str(filename)
            if not os.path.exists(full_path):
                 joined = os.path.join(self.download_dir, full_path)
                 if os.path.exists(joined):
                     full_path = joined
            
            if os.path.exists(full_path) and os.path.getsize(full_path) > 0:
                return full_path
            else:
                 raise Exception("Downloaded file is empty or missing")

        except Exception as e:
            logger.error(f"Mega download failed: {e}")
            raise e

    def extract(self, file_path: str, extract_to: str):
        """
        解压文件 (支持 zip, rar)
        """
        logger.info(f"Extracting {file_path} to {extract_to}")
        os.makedirs(extract_to, exist_ok=True)
        
        try:
            if file_path.lower().endswith('.rar'):
                # 优先尝试使用 unrar 命令行工具，因为它支持 RAR5
                try:
                    subprocess.run(["unrar", "x", "-y", file_path, extract_to], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
                    return
                except Exception as e:
                    logger.warning(f"unrar command failed, falling back to rarfile: {e}")
                
                with rarfile.RarFile(file_path) as rf:
                    rf.extractall(extract_to)
            elif file_path.lower().endswith('.zip'):
                with zipfile.ZipFile(file_path) as zf:
                    zf.extractall(extract_to)
            else:
                logger.warning(f"Unsupported archive format: {file_path}")
        except Exception as e:
            logger.error(f"Extraction failed: {e}")
            raise e

    async def process_directory(self, directory: str, output_session_dir: str) -> list:
        """
        递归扫描目录，寻找 tdata 并转换
        """
        results = []
        os.makedirs(output_session_dir, exist_ok=True)
        
        # Walk through directory
        for root, dirs, files in os.walk(directory):
            # Check for tdata folder
            if 'tdata' in dirs:
                tdata_path = os.path.join(root, 'tdata')
                
                # 尝试提取手机号
                # 1. 尝试从当前目录名提取
                current_dir_name = os.path.basename(root)
                phone = self._extract_phone(current_dir_name)
                
                # 2. 如果没找到，尝试父目录
                if not phone:
                     parent_dir_name = os.path.basename(os.path.dirname(root))
                     phone = self._extract_phone(parent_dir_name)
                
                # 3. 如果还是没找到，生成一个临时ID
                if not phone:
                    phone = f"imported_{os.urandom(4).hex()}"
                
                # 确保手机号以 + 开头
                if not phone.startswith('+') and phone.isdigit():
                    phone = '+' + phone
                    
                session_name = phone
                output_path_base = os.path.join(output_session_dir, session_name)
                
                logger.info(f"Found tdata at {tdata_path}, converting to {output_path_base}...")
                
                # 1. TData -> Telethon Session
                # convert_tdata_to_session returns path with .session extension
                telethon_session_path = await convert_tdata_to_session(tdata_path, output_path_base, verify=False)
                
                if telethon_session_path and os.path.exists(telethon_session_path):
                    # 2. Telethon Session -> Pyrogram Session
                    # convert_telethon_to_pyrogram modifies the file in place (and backs up old one)
                    if convert_telethon_to_pyrogram(telethon_session_path):
                         logger.info(f"Successfully converted to Pyrogram session: {telethon_session_path}")
                         results.append({
                             "phone": phone,
                             "session_path": telethon_session_path,
                             "original_tdata": tdata_path
                         })
                    else:
                        logger.error(f"Failed to convert Telethon session to Pyrogram: {telethon_session_path}")
                else:
                    logger.error(f"Failed to convert tdata: {tdata_path}")
                    
        return results

    def _extract_phone(self, text: str) -> str:
        if not text:
            return None
        match = re.search(r'\+?\d{7,15}', text)
        if match:
            return match.group(0)
        return None
    
    def cleanup(self, path: str):
        if os.path.exists(path):
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
