"""
Migration: Add 2FA (TOTP) columns to user table.

Run from project root:
    python3 backend/migrate_2fa.py

Or from backend dir:
    python3 migrate_2fa.py
"""
import sqlite3
import os


DB_PATH = "backend/tgsc.db"


def migrate():
    target_db_path = DB_PATH
    if not os.path.exists(target_db_path):
        if os.path.exists("tgsc.db"):
            target_db_path = "tgsc.db"
        else:
            print(f"Database {target_db_path} not found.")
            return

    conn = sqlite3.connect(target_db_path)
    cursor = conn.cursor()

    columns = [
        ("totp_secret", "TEXT"),
        ("totp_enabled", "BOOLEAN DEFAULT 0"),
    ]

    for col_name, col_type in columns:
        try:
            cursor.execute(f"ALTER TABLE user ADD COLUMN {col_name} {col_type}")
            print(f"Added column {col_name} to user table")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"Column {col_name} already exists")
            else:
                print(f"Error adding {col_name}: {e}")

    conn.commit()
    conn.close()
    print("Migration complete.")


if __name__ == "__main__":
    migrate()
