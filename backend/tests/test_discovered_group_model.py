"""
Tests for DiscoveredGroup and DiscoveryBlacklist SQLModels (Task 1).

test_models_importable  — pure import/attribute check, no DB required
test_migration_round_trip — alembic upgrade/downgrade/upgrade (Postgres only)
"""
import os
import pytest


def test_models_importable():
    from app.models.discovered_group import DiscoveredGroup
    from app.models.discovery_blacklist import DiscoveryBlacklist

    assert DiscoveredGroup.__tablename__ == "discovered_group"
    assert DiscoveryBlacklist.__tablename__ == "discovery_blacklist"

    # Verify key fields exist on DiscoveredGroup
    dg_fields = DiscoveredGroup.model_fields
    for field in ("customer_id", "chat_username", "chat_link", "chat_id",
                  "source", "score", "status", "metadata_json",
                  "discovered_at", "decided_at", "decided_by"):
        assert field in dg_fields, f"DiscoveredGroup missing field: {field}"

    # Verify key fields exist on DiscoveryBlacklist
    bl_fields = DiscoveryBlacklist.model_fields
    for field in ("customer_id", "chat_link", "reason", "created_at"):
        assert field in bl_fields, f"DiscoveryBlacklist missing field: {field}"


def test_migration_round_trip():
    db = os.environ.get("DATABASE_URL", "")
    if not db.startswith(("postgresql", "postgres")):
        pytest.skip("requires Postgres")

    import subprocess
    cwd = os.path.join(os.path.dirname(__file__), "..")
    subprocess.run(["alembic", "upgrade", "head"], cwd=cwd, check=True)
    subprocess.run(["alembic", "downgrade", "-1"], cwd=cwd, check=True)
    subprocess.run(["alembic", "upgrade", "head"], cwd=cwd, check=True)
