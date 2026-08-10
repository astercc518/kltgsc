"""CLI wrapper. Run: cd backend && python3 scripts/seed_chitchat_pool.py"""
from sqlmodel import Session
from app.core.database import engine
from app.services.chitchat_pool_seeder import seed_chitchat_pool


if __name__ == "__main__":
    with Session(engine) as session:
        n = seed_chitchat_pool(session=session)
    print(f"Inserted {n} chitchat topics")
