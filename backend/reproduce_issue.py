import sys
import os
from fastapi import HTTPException
from sqlmodel import Session, select
from app.core.db import engine
from app.api.v1.endpoints.accounts import get_accounts

# Ensure we can import from app
sys.path.append(os.getcwd())

def reproduce_locally():
    print("Attempting to reproduce 500 error locally...")
    try:
        with Session(engine) as session:
            # Mocking parameters
            skip = 0
            limit = 20
            status = None
            role = None
            
            print("Calling get_accounts...")
            accounts = get_accounts(session=session, skip=skip, limit=limit, status=status, role=role)
            print(f"Success! Retrieved {len(accounts)} accounts.")
            for acc in accounts:
                print(f"ID: {acc.id}, Phone: {acc.phone_number}, Tier: {acc.tier}")
                
    except HTTPException as e:
        print(f"Caught HTTPException: {e.detail}")
    except Exception as e:
        print(f"Caught unexpected Exception: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    reproduce_locally()
