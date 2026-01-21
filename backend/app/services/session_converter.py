import sqlite3
import os
import shutil
import logging

logger = logging.getLogger(__name__)

def is_telethon_session(file_path: str) -> bool:
    """检查是否为 Telethon 格式的 Session 文件"""
    conn = None
    try:
        conn = sqlite3.connect(file_path)
        cursor = conn.cursor()
        
        # 首先检查是否为 Pyrogram 格式 (有 peers 表 或 sessions 表包含 test_mode 列)
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='peers'")
        if cursor.fetchone():
            return False  # Pyrogram session has 'peers' table
        
        cursor.execute("PRAGMA table_info(sessions)")
        columns = [col[1] for col in cursor.fetchall()]
        if 'test_mode' in columns:
            return False  # Pyrogram session has 'test_mode' column
        
        # 检查 Telethon 特征
        # Telethon: dc_id, server_address, port, auth_key, takeout_id
        if 'server_address' in columns:
            return True
        
        # Telethon 有 entities 表
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='entities'")
        if cursor.fetchone():
            return True
            
        return False
    except Exception as e:
        logger.error(f"Error checking session type: {e}")
        return False
    finally:
        if conn:
            conn.close()

def convert_telethon_to_pyrogram(file_path: str) -> bool:
    """
    将 Telethon Session 转换为 Pyrogram Session
    原文件会被备份为 .telethon
    """
    if not os.path.exists(file_path):
        return False
        
    try:
        # 1. 读取 Telethon 数据
        conn_tl = sqlite3.connect(file_path)
        cursor_tl = conn_tl.cursor()
        cursor_tl.execute("SELECT dc_id, auth_key FROM sessions")
        row = cursor_tl.fetchone()
        conn_tl.close()
        
        if not row:
            logger.error("No session data found in Telethon file")
            return False
            
        dc_id, auth_key = row
        
        # 2. 备份原文件
        backup_path = file_path + ".telethon"
        shutil.move(file_path, backup_path)
        
        # 3. 创建 Pyrogram Session
        conn_py = sqlite3.connect(file_path)
        cursor_py = conn_py.cursor()
        
        # Pyrogram schema (must match exactly to avoid issues)
        cursor_py.execute("""
        CREATE TABLE sessions
        (
            dc_id     INTEGER PRIMARY KEY,
            api_id    INTEGER,
            test_mode INTEGER,
            auth_key  BLOB,
            date      INTEGER NOT NULL,
            user_id   INTEGER,
            is_bot    INTEGER
        )
        """)
        
        cursor_py.execute("""
        CREATE TABLE peers
        (
            id             INTEGER PRIMARY KEY,
            access_hash    INTEGER,
            type           INTEGER NOT NULL,
            username       TEXT,
            phone_number   TEXT,
            last_update_on INTEGER NOT NULL DEFAULT (CAST(STRFTIME('%s', 'now') AS INTEGER))
        )
        """)
        
        cursor_py.execute("""
        CREATE TABLE version
        (
            number INTEGER PRIMARY KEY
        )
        """)
        
        # Create indexes
        cursor_py.execute("CREATE INDEX idx_peers_id ON peers (id)")
        cursor_py.execute("CREATE INDEX idx_peers_username ON peers (username)")
        cursor_py.execute("CREATE INDEX idx_peers_phone_number ON peers (phone_number)")
        
        # Create trigger for auto-updating last_update_on
        cursor_py.execute("""
        CREATE TRIGGER trg_peers_last_update_on
            AFTER UPDATE
            ON peers
        BEGIN
            UPDATE peers
            SET last_update_on = CAST(STRFTIME('%s', 'now') AS INTEGER)
            WHERE id = NEW.id;
        END
        """)
        
        # 插入版本号 (Pyrogram current storage version is 3)
        cursor_py.execute("INSERT INTO version (number) VALUES (3)")
        
        # 插入数据 (api_id, user_id 暂时填 0，Pyrogram 会在登录后更新)
        # date 必须是有效的 Unix 时间戳，否则 Pyrogram 会报错
        import time
        cursor_py.execute(
            "INSERT INTO sessions (dc_id, api_id, test_mode, auth_key, date, user_id, is_bot) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (dc_id, 0, 0, auth_key, int(time.time()), 0, 0)
        )
        
        conn_py.commit()
        conn_py.close()
        
        logger.info(f"Successfully converted Telethon session: {file_path}")
        return True
        
    except Exception as e:
        logger.error(f"Failed to convert session: {e}")
        # 尝试恢复
        if os.path.exists(file_path + ".telethon"):
            if os.path.exists(file_path):
                os.remove(file_path)
            shutil.move(file_path + ".telethon", file_path)
        return False
