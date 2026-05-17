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

    def flatten_tdata_for_opentele(path: str) -> str:
        """
        Newer Telegram Desktop (4.x+) stores account data in a hex-named subdir.
        opentele expects everything flat in the root. This function copies
        the subdir contents to root level in a temp directory.
        Returns the flattened path (caller must clean up).
        """
        import re, shutil, tempfile
        HEX_DIR = re.compile(r'^[0-9A-Fa-f]{15,17}$')
        account_subdir = None
        for entry in os.listdir(path):
            full = os.path.join(path, entry)
            if os.path.isdir(full) and HEX_DIR.match(entry):
                sub_files = set(os.listdir(full))
                if any(f in sub_files for f in ('maps', 'map0', 'map1')):
                    account_subdir = full
                    break

        if account_subdir is None:
            return path  # already flat, no temp dir needed

        flat = tempfile.mkdtemp(prefix="tdata_flat_")
        # Copy root-level files (key_datas, settingss, etc.)
        for entry in os.listdir(path):
            src = os.path.join(path, entry)
            if os.path.isfile(src):
                shutil.copy2(src, os.path.join(flat, entry))
        # Copy account subdir files to flat root (don't overwrite root files)
        for entry in os.listdir(account_subdir):
            src = os.path.join(account_subdir, entry)
            dst = os.path.join(flat, entry)
            if os.path.isfile(src) and not os.path.exists(dst):
                shutil.copy2(src, dst)
        print(f"Flattened tdata: {path} -> {flat}, files: {os.listdir(flat)}", file=sys.stderr)
        return flat

    _flat_dir = None

    def extract_auth_from_tdata(path: str):
        """
        直接从 tdata 提取 dc_id + auth_key，兼容新版 Telegram Desktop (4.x+)。
        新版把账号数据放在 hex 命名的子目录下，opentele 的 TDesktop 无法识别。
        返回 (dc_id: int, auth_key: bytes) 或抛出异常。
        """
        import opentele.td.storage as st
        from opentele.td import AuthKey, StorageAccount
        from opentele.td.storage import QByteArray
        import opentele.td.shared as td
        from PyQt5.QtCore import QDataStream, QByteArray as QtBA, QIODevice

        effective = flatten_tdata_for_opentele(path)
        flat_created = effective != path

        try:
            keyData = st.Storage.ReadFile("key_data", effective)
            salt = QByteArray(); keyEncrypted = QByteArray(); infoEncrypted = QByteArray()
            keyData.stream >> salt >> keyEncrypted >> infoEncrypted
            passcodeKey = st.Storage.CreateLocalKey(salt, QByteArray())
            keyInner = st.Storage.DecryptLocal(keyEncrypted, passcodeKey)
            localKey_bytes = keyInner.stream.readRawData(256)
            localKey = AuthKey(localKey_bytes)

            owner_mock = type('M', (), {
                'basePath': effective, 'api': None, 'kPerformanceMode': False,
                'keyFile': 'data',
                'owner': type('O', (), {'kPerformanceMode': False})()
            })()
            sa = StorageAccount(owner_mock, effective, 'data')
            sa.start(localKey)

            file_part = td.Storage.ToFilePart(sa._StorageAccount__dataNameKey)
            mtp = td.Storage.ReadEncryptedFile(file_part, sa._StorageAccount__baseGlobalPath, localKey)
            blockId = mtp.stream.readInt32()
            if blockId != 75:
                raise ValueError(f"Unexpected MTP blockId: {blockId}")
            serialized = QByteArray()
            mtp.stream >> serialized
            raw = bytes(serialized)

            qt_ba = QtBA(raw)
            ds = QDataStream(qt_ba, QIODevice.ReadOnly)
            ds.setVersion(QDataStream.Version.Qt_5_1)
            userId_lo = ds.readInt32()
            mainDcId_lo = ds.readInt32()
            combined = ((userId_lo & 0xFFFFFFFF) << 32) | (mainDcId_lo & 0xFFFFFFFF)
            if combined == 0xFFFFFFFFFFFFFFFF:  # kWideIdsTag
                ds.readUInt64()  # skip userId
                mainDcId = ds.readInt32()
            else:
                mainDcId = mainDcId_lo

            key_count = ds.readInt32()
            auth_key = None
            for _ in range(key_count):
                dc_id = ds.readInt32()
                key_data = ds.readRawData(256)
                if dc_id == mainDcId and auth_key is None:
                    auth_key = key_data

            if auth_key is None or len(auth_key) != 256:
                raise ValueError(f"Auth key not found for mainDcId={mainDcId}")

            return mainDcId, auth_key
        finally:
            if flat_created:
                import shutil as _sh
                _sh.rmtree(effective, ignore_errors=True)

    async def do_convert():
        nonlocal _flat_dir
        try:
            # Direct extraction (supports both old and new tdata format)
            try:
                dc_id, auth_key = extract_auth_from_tdata(tdata_path)
                print(f"Direct extraction OK: dc_id={dc_id}", file=sys.stderr)
            except Exception as e1:
                # Fallback to opentele TDesktop
                print(f"Direct extraction failed ({e1}), fallback to opentele...", file=sys.stderr)
                from opentele.td import TDesktop
                effective_path = flatten_tdata_for_opentele(tdata_path)
                if effective_path != tdata_path:
                    _flat_dir = effective_path
                tdesk = TDesktop(effective_path)
                if not tdesk.isLoaded() or len(tdesk.accounts) == 0:
                    return {"success": False, "error": f"Direct: {e1}; opentele: no accounts loaded"}
                acc = tdesk.accounts[0]
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
    finally:
        if _flat_dir and os.path.isdir(_flat_dir):
            import shutil
            shutil.rmtree(_flat_dir, ignore_errors=True)

if __name__ == "__main__":
    main()
