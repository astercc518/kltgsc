import sqlite3
import os

db_path = "backend/tgsc.db"

def migrate_accounts():
    target_db_path = db_path
    if not os.path.exists(target_db_path):
        # Try relative path if running from backend dir
        if os.path.exists("tgsc.db"):
            target_db_path = "tgsc.db"
        else:
            print(f"Database {target_db_path} not found.")
            return

    conn = sqlite3.connect(target_db_path)
    cursor = conn.cursor()
    
    columns = [
        ("role", "TEXT DEFAULT 'worker'"),
        ("tags", "TEXT")
    ]
    
    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE account ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name} to account table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists")
            else:
                print(f"Error adding {col_name}: {e}")
                
    conn.commit()
    conn.close()

if __name__ == "__main__":
    migrate_accounts()
