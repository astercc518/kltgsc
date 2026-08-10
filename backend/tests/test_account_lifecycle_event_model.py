import os
import pytest


def test_model_importable():
    from app.models.account_lifecycle_event import AccountLifecycleEvent
    assert AccountLifecycleEvent.__tablename__ == "account_lifecycle_events"


def test_migration_round_trip():
    """upgrade head -> downgrade -1 -> upgrade head"""
    db = os.environ.get("DATABASE_URL", "")
    if not db.startswith(("postgresql", "postgres")):
        pytest.skip("requires Postgres")
    import subprocess
    cwd = os.path.join(os.path.dirname(__file__), "..")
    subprocess.run(["alembic", "upgrade", "head"], cwd=cwd, check=True)
    subprocess.run(["alembic", "downgrade", "-1"], cwd=cwd, check=True)
    subprocess.run(["alembic", "upgrade", "head"], cwd=cwd, check=True)
