import asyncio
import logging
import sys
import os

# Configure paths
current_dir = os.getcwd() # /var/tgsc
backend_dir = os.path.join(current_dir, "backend")

# Switch to backend directory so that 'sessions' workdir in pyrogram works correctly
if os.path.exists(backend_dir):
    os.chdir(backend_dir)
    print(f"Changed working directory to: {os.getcwd()}")

# Add backend directory to sys.path to allow 'from app...' imports if needed
sys.path.insert(0, backend_dir)

from datetime import datetime
from sqlmodel import Session, create_engine, select
from app.models.account import Account
from app.services.telegram_client import check_account_with_client

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Database setup - relative to backend dir now
sqlite_url = "sqlite:///tgsc.db"
engine = create_engine(sqlite_url)

async def verify_single_account(account: Account, session: Session):
    """Verify a single account and update its status."""
    print(f"Checking account {account.phone_number} (ID: {account.id})...")
    
    # Get proxy if associated
    proxy = account.proxy if account.proxy_id else None
    
    # Path handling:
    # The session_file_path in DB is likely /app/sessions/... or backend/sessions/...
    # Since we are now in backend/ dir, we expect sessions in ./sessions/
    # Pyrogram client uses workdir="sessions" and searches for name.session
    # So we just need to make sure the session file exists in ./sessions/
    
    # Check if session exists
    session_name = f"{account.phone_number}.session"
    expected_path = os.path.join("sessions", session_name)
    
    if os.path.exists(expected_path):
        # Update path in object to match reality if needed, though check_account_with_client relies on name mostly if path is provided
        # But check_account_with_client logic:
        # if account.session_file_path and os.path.exists(account.session_file_path):
        #    ...
        #    session_name = ...basename...
        #    Client(..., workdir="sessions")
        
        # So we need account.session_file_path to point to a valid file.
        # Since we are in backend/, expected_path is valid relative path.
        # Let's use absolute path to be safe.
        abs_path = os.path.abspath(expected_path)
        # account.session_file_path = abs_path
        pass
    else:
        print(f"Warning: Session file not found at {expected_path}")
        # If the DB has a path that works (e.g. absolute), check that too
        if account.session_file_path and os.path.exists(account.session_file_path):
            pass # It's fine
        elif account.session_file_path and account.session_file_path.startswith("/app/sessions/"):
             # Try to map
             mapped_name = os.path.basename(account.session_file_path)
             if mapped_name == session_name and os.path.exists(expected_path):
                 # It exists in our local sessions dir, so we can point to it
                 account.session_file_path = os.path.abspath(expected_path)
             else:
                 print(f"Could not find session file for {account.session_file_path}")

    print(f"Using Session File: {account.session_file_path}")

    # Run the check
    status, error_msg, last_active, device_info = await check_account_with_client(account, proxy)
    
    # Update account
    previous_status = account.status
    account.status = status
    if last_active:
        account.last_active = last_active
    
    # Update device info if returned
    if device_info:
        if "device_model" in device_info: account.device_model = device_info["device_model"]
        if "system_version" in device_info: account.system_version = device_info["system_version"]
        if "app_version" in device_info: account.app_version = device_info["app_version"]

    session.add(account)
    session.commit()
    session.refresh(account)
    
    result_msg = f"Result: {status}"
    if error_msg:
        result_msg += f" - {error_msg}"
    
    if previous_status != status:
        result_msg += f" (Changed from {previous_status})"
        
    print(result_msg)
    print("-" * 50)
    return status

async def main():
    print("Starting account verification...")
    
    with Session(engine) as session:
        # Get all accounts or filter as needed
        statement = select(Account)
        accounts = session.exec(statement).all()
        
        print(f"Found {len(accounts)} accounts to verify.")
        
        results = {
            "active": 0,
            "banned": 0,
            "spam_block": 0,
            "flood_wait": 0,
            "session_invalid": 0,
            "error": 0,
            "proxy_error": 0
        }
        
        for account in accounts:
            try:
                status = await verify_single_account(account, session)
                if status in results:
                    results[status] += 1
                else:
                    results["error"] += 1
            except Exception as e:
                print(f"Exception verifying account {account.id}: {e}")
                import traceback
                traceback.print_exc()
                results["error"] += 1
                
        print("\nVerification Summary:")
        for status, count in results.items():
            print(f"{status}: {count}")

if __name__ == "__main__":
    asyncio.run(main())
