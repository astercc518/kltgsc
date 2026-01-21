
from sqlmodel import Session, create_engine, select
from backend.app.models.account import Account

# Adjust the database URL as needed. Assuming sqlite
sqlite_url = "sqlite:///backend/tgsc.db"
engine = create_engine(sqlite_url)

def check_accounts():
    with Session(engine) as session:
        statement = select(Account).where(Account.id >= 4).where(Account.id <= 10)
        results = session.exec(statement).all()
        
        print(f"Found {len(results)} accounts with ID between 4 and 10.")
        for account in results:
            print(f"ID: {account.id}, Phone: {account.phone_number}, API ID: {account.api_id}, API Hash: {account.api_hash}")

if __name__ == "__main__":
    check_accounts()
