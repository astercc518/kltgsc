"""验证 group_ai_sales_phase1 迁移可正反两向跑通"""
import subprocess
import os
import pytest


def _alembic(*args):
    cwd = os.path.join(os.path.dirname(__file__), "..")
    return subprocess.run(
        ["alembic", *args], cwd=cwd,
        env={**os.environ}, capture_output=True, text=True, check=True,
    )


def test_migration_round_trip():
    """upgrade head -> downgrade -1 -> upgrade head 不报错"""
    db = os.environ.get("DATABASE_URL", "")
    if not db.startswith(("postgresql", "postgres")):
        pytest.skip("requires Postgres DATABASE_URL with pgvector")
    _alembic("upgrade", "head")
    _alembic("downgrade", "-1")
    _alembic("upgrade", "head")
