"""
迁移脚本：添加批量拉人功能相关字段
"""
import psycopg2
import os

DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://tgsc:tgsc123@postgres:5432/tgsc")

# 解析连接参数
if DATABASE_URL.startswith("postgresql://"):
    parts = DATABASE_URL.replace("postgresql://", "").split("@")
    user_pass = parts[0].split(":")
    host_db = parts[1].split("/")
    host_port = host_db[0].split(":")
    
    conn_params = {
        "user": user_pass[0],
        "password": user_pass[1],
        "host": host_port[0],
        "port": host_port[1] if len(host_port) > 1 else "5432",
        "database": host_db[1]
    }

def run_migration():
    conn = psycopg2.connect(**conn_params)
    cur = conn.cursor()
    
    print("开始迁移 InviteTask 表...")
    
    # InviteTask 新增字段
    invite_task_columns = [
        ("account_group", "VARCHAR(100)"),
        ("total_count", "INTEGER DEFAULT 0"),
        ("privacy_restricted_count", "INTEGER DEFAULT 0"),
        ("flood_wait_count", "INTEGER DEFAULT 0"),
        ("pending_count", "INTEGER DEFAULT 0"),
        ("max_invites_per_task", "INTEGER DEFAULT 100"),
        ("concurrent_accounts", "INTEGER DEFAULT 1"),
        ("stop_on_flood", "BOOLEAN DEFAULT TRUE"),
        ("filter_tags", "TEXT"),
        ("filter_min_score", "INTEGER"),
        ("filter_funnel_stages", "TEXT"),
        ("exclude_invited", "BOOLEAN DEFAULT TRUE"),
        ("exclude_failed_recently", "BOOLEAN DEFAULT TRUE"),
        ("failed_cooldown_hours", "INTEGER DEFAULT 72"),
        ("scheduled_at", "TIMESTAMP"),
        ("is_recurring", "BOOLEAN DEFAULT FALSE"),
        ("recurring_interval_hours", "INTEGER DEFAULT 24"),
        ("recurring_batch_size", "INTEGER DEFAULT 50"),
        ("started_at", "TIMESTAMP"),
        ("completed_at", "TIMESTAMP"),
        ("last_error", "TEXT"),
    ]
    
    for col_name, col_type in invite_task_columns:
        try:
            cur.execute(f"ALTER TABLE invitetask ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            print(f"  ✓ invitetask.{col_name}")
        except Exception as e:
            print(f"  ✗ invitetask.{col_name}: {e}")
            conn.rollback()
    
    conn.commit()
    
    print("\n开始迁移 TargetUser 表...")
    
    # TargetUser 新增字段
    target_user_columns = [
        ("invite_status", "VARCHAR(50) DEFAULT 'untried'"),
        ("invite_target_group", "VARCHAR(255)"),
        ("invite_account_id", "INTEGER"),
        ("invite_attempted_at", "TIMESTAMP"),
        ("invite_success_at", "TIMESTAMP"),
        ("invite_error_code", "VARCHAR(100)"),
        ("invite_error_message", "TEXT"),
        ("invite_attempt_count", "INTEGER DEFAULT 0"),
    ]
    
    for col_name, col_type in target_user_columns:
        try:
            cur.execute(f"ALTER TABLE targetuser ADD COLUMN IF NOT EXISTS {col_name} {col_type}")
            print(f"  ✓ targetuser.{col_name}")
        except Exception as e:
            print(f"  ✗ targetuser.{col_name}: {e}")
            conn.rollback()
    
    conn.commit()
    
    print("\n创建 InviteLog 表...")
    
    # 创建 InviteLog 表
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS invitelog (
                id SERIAL PRIMARY KEY,
                task_id INTEGER NOT NULL,
                account_id INTEGER NOT NULL,
                target_user_id INTEGER NOT NULL,
                target_telegram_id BIGINT NOT NULL,
                target_username VARCHAR(100),
                target_channel VARCHAR(255) NOT NULL,
                target_channel_id BIGINT,
                status VARCHAR(50) NOT NULL,
                error_code VARCHAR(100),
                error_message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                duration_ms INTEGER,
                account_username VARCHAR(100),
                retry_count INTEGER DEFAULT 0,
                flood_wait_seconds INTEGER
            )
        """)
        print("  ✓ invitelog 表创建成功")
        
        # 创建索引
        cur.execute("CREATE INDEX IF NOT EXISTS ix_invitelog_task_id ON invitelog(task_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_invitelog_account_id ON invitelog(account_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_invitelog_target_user_id ON invitelog(target_user_id)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_invitelog_created_at ON invitelog(created_at)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_invitelog_status ON invitelog(status)")
        cur.execute("CREATE INDEX IF NOT EXISTS ix_invitelog_error_code ON invitelog(error_code)")
        print("  ✓ invitelog 索引创建成功")
        
    except Exception as e:
        print(f"  ✗ invitelog: {e}")
        conn.rollback()
    
    conn.commit()
    
    # 添加索引到新字段
    print("\n创建索引...")
    
    indexes = [
        ("ix_invitetask_status", "invitetask", "status"),
        ("ix_invitetask_account_group", "invitetask", "account_group"),
        ("ix_targetuser_invite_status", "targetuser", "invite_status"),
        ("ix_targetuser_invite_attempted_at", "targetuser", "invite_attempted_at"),
        ("ix_targetuser_invite_account_id", "targetuser", "invite_account_id"),
    ]
    
    for idx_name, table, column in indexes:
        try:
            cur.execute(f"CREATE INDEX IF NOT EXISTS {idx_name} ON {table}({column})")
            print(f"  ✓ {idx_name}")
        except Exception as e:
            print(f"  ✗ {idx_name}: {e}")
            conn.rollback()
    
    conn.commit()
    
    cur.close()
    conn.close()
    
    print("\n迁移完成！")


if __name__ == "__main__":
    run_migration()
