#!/usr/bin/env python3
"""
独立的 TData 转换脚本，在 subprocess 中运行
使用手动方法创建 Telethon session，绕过 opentele 的 LoginFlagInvalid 错误
"""
import os
import sys
import asyncio
import json
import sqlite3

# 设置环境变量
os.environ['QT_QPA_PLATFORM'] = 'offscreen'
os.environ['QT_DEBUG_PLUGINS'] = '0'

# DC IP 地址映射 (production)
DC_IPS = {
    1: '149.154.175.53',
    2: '149.154.167.50', 
    3: '149.154.175.100',
    4: '149.154.167.91',
    5: '91.108.56.130'
}

def create_telethon_session(session_path: str, dc_id: int, auth_key: bytes) -> bool:
    """
    手动创建 Telethon SQLite session 文件
    """
    try:
        if os.path.exists(session_path):
            os.remove(session_path)
        
        dc_ip = DC_IPS.get(dc_id, DC_IPS[1])
        
        conn = sqlite3.connect(session_path)
        c = conn.cursor()
        
        # 创建 Telethon session 表结构 (version 7)
        c.execute('CREATE TABLE version (version INTEGER PRIMARY KEY)')
        c.execute('INSERT INTO version VALUES (7)')
        
        c.execute('''CREATE TABLE sessions (
            dc_id INTEGER PRIMARY KEY,
            server_address TEXT,
            port INTEGER,
            auth_key BLOB,
            takeout_id INTEGER
        )''')
        
        c.execute('''CREATE TABLE entities (
            id INTEGER PRIMARY KEY,
            hash INTEGER NOT NULL,
            username TEXT,
            phone INTEGER,
            name TEXT,
            date INTEGER
        )''')
        
        c.execute('''CREATE TABLE sent_files (
            md5_digest BLOB,
            file_size INTEGER,
            type INTEGER,
            id INTEGER,
            hash INTEGER,
            PRIMARY KEY (md5_digest, file_size, type)
        )''')
        
        c.execute('''CREATE TABLE update_state (
            id INTEGER PRIMARY KEY,
            pts INTEGER,
            qts INTEGER,
            date INTEGER,
            seq INTEGER
        )''')
        
        # 插入 session 数据
        c.execute('INSERT INTO sessions VALUES (?, ?, ?, ?, ?)',
                  (dc_id, dc_ip, 443, auth_key, None))
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Failed to create session: {e}", file=sys.stderr)
        return False

async def verify_session(session_path: str) -> tuple:
    """
    验证 session 是否有效
    返回 (success, phone_number)
    """
    from telethon import TelegramClient
    
    # 使用 Telegram Desktop 的 API
    api_id = 2040
    api_hash = 'b18441a1ff607e10a989891a5462e627'
    
    # 移除 .session 后缀
    session_name = session_path.replace('.session', '')
    
    client = TelegramClient(session_name, api_id, api_hash)
    try:
        await client.connect()
        
        if await client.is_user_authorized():
            me = await client.get_me()
            return True, me.phone
        else:
            return False, None
    except Exception as e:
        print(f"Verification error: {e}", file=sys.stderr)
        return False, None
    finally:
        await client.disconnect()

def main():
    # Usage:
    #   tdata_converter_script.py <tdata_path> <output_path> [--verify]
    if len(sys.argv) not in (3, 4):
        print(json.dumps({"success": False, "error": "Usage: tdata_converter_script.py <tdata_path> <output_path> [--verify]"}))
        sys.exit(1)
    
    tdata_path = sys.argv[1]
    output_path = sys.argv[2]
    verify = len(sys.argv) == 4 and sys.argv[3] == "--verify"
    session_path = f"{output_path}.session"
    
    async def do_convert():
        try:
            from opentele.td import TDesktop
            
            # 加载 TData
            tdesk = TDesktop(tdata_path)
            
            if not tdesk.isLoaded():
                return {"success": False, "error": "TDesktop failed to load"}
            
            if len(tdesk.accounts) == 0:
                return {"success": False, "error": "No accounts found in TData"}
            
            acc = tdesk.accounts[0]
            
            # 获取 authKey
            if not acc.authKey or not hasattr(acc.authKey, 'key'):
                return {"success": False, "error": "No valid authKey found"}
            
            auth_key = acc.authKey.key
            dc_id = acc.MainDcId
            
            if len(auth_key) != 256:
                return {"success": False, "error": f"Invalid authKey length: {len(auth_key)}"}
            
            # 手动创建 session 文件
            if not create_telethon_session(session_path, dc_id, auth_key):
                return {"success": False, "error": "Failed to create session file"}

            # 默认不触碰 Telegram：不做联网验活
            if not verify:
                return {"success": True, "session_file": session_path, "phone": None, "verified": False}

            # 可选：联网验证 session
            success, phone = await verify_session(session_path)
            if success:
                return {"success": True, "session_file": session_path, "phone": phone, "verified": True}
            else:
                # 删除无效的 session 文件
                if os.path.exists(session_path):
                    os.remove(session_path)
                return {"success": False, "error": "Session verification failed - account may be expired or banned"}
                
        except Exception as e:
            import traceback
            return {"success": False, "error": str(e), "traceback": traceback.format_exc()}
    
    try:
        result = asyncio.run(do_convert())
        print(json.dumps(result))
    except Exception as e:
        print(json.dumps({"success": False, "error": f"Script error: {str(e)}"}))
        sys.exit(1)

if __name__ == "__main__":
    main()
