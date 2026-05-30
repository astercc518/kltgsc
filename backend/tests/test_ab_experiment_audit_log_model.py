"""Tests for ABExperimentAuditLog model (Phase 6 Task 1)."""
import os
import pytest


def test_model_importable():
    from app.models.ab_experiment_audit_log import ABExperimentAuditLog
    assert ABExperimentAuditLog.__tablename__ == "ab_experiment_audit_log"


def test_migration_round_trip():
    db = os.environ.get("DATABASE_URL", "")
    if not db.startswith(("postgresql", "postgres")):
        pytest.skip("requires Postgres")
    import subprocess
    cwd = os.path.join(os.path.dirname(__file__), "..")
    subprocess.run(["alembic", "upgrade", "head"], cwd=cwd, check=True)
    subprocess.run(["alembic", "downgrade", "-1"], cwd=cwd, check=True)
    subprocess.run(["alembic", "upgrade", "head"], cwd=cwd, check=True)
