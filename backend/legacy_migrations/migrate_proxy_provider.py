import sqlite3
import os

DB_PATH = "backend/tgsc.db"

def migrate():
    if not os.path.exists(DB_PATH):
        print(f"Database not found at {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    try:
        # Check if column exists
        cursor.execute("PRAGMA table_info(proxy)")
        columns = [info[1] for info in cursor.fetchall()]
        
        if "provider_type" not in columns:
            print("Adding provider_type column to proxy table...")
            cursor.execute("ALTER TABLE proxy ADD COLUMN provider_type TEXT DEFAULT 'datacenter'")
            conn.commit()
            print("Migration successful")
        else:
            print("Column provider_type already exists")
            
    except Exception as e:
        print(f"Migration failed: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
