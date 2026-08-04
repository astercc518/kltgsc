import os
from pathlib import Path
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url


ROOT = Path(__file__).parents[2]
POSTGRES_TEST_URL = os.getenv("POSTGRES_TEST_URL")
pytestmark = pytest.mark.skipif(
    not POSTGRES_TEST_URL,
    reason="POSTGRES_TEST_URL is required for PostgreSQL migration coverage",
)


def _alembic_config(database_url: URL) -> Config:
    config = Config(str(ROOT / "backend/alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend/alembic"))
    config.set_main_option(
        "sqlalchemy.url",
        database_url.render_as_string(hide_password=False),
    )
    return config


@pytest.fixture
def migration_database_url() -> URL:
    source_url = make_url(POSTGRES_TEST_URL)
    admin_url = source_url.set(database="postgres")
    database_name = f"tgsc_legacy_{uuid4().hex}"
    database_url = source_url.set(database=database_name)
    admin_engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")

    with admin_engine.connect() as connection:
        connection.exec_driver_sql(f'CREATE DATABASE "{database_name}"')

    try:
        yield database_url
    finally:
        with admin_engine.connect() as connection:
            connection.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :database_name AND pid <> pg_backend_pid()"
                ),
                {"database_name": database_name},
            )
            connection.exec_driver_sql(f'DROP DATABASE "{database_name}"')
        admin_engine.dispose()


def test_unversioned_complete_legacy_schema_is_adopted(
    migration_database_url: URL,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        migration_database_url.render_as_string(hide_password=False),
    )
    config = _alembic_config(migration_database_url)
    command.upgrade(config, "000000000001")

    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE alembic_version")
    engine.dispose()

    command.upgrade(config, "head")

    engine = create_engine(migration_database_url)
    with engine.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == (
            "c7d8e9f0a1b2"
        )
    engine.dispose()


@pytest.mark.parametrize(
    "mutation",
    [
        "ALTER TABLE ai_config DROP COLUMN api_key",
        "ALTER TABLE ai_config ALTER COLUMN name TYPE TEXT",
        "ALTER TABLE account DROP CONSTRAINT account_proxy_id_fkey",
        "ALTER TABLE ai_config ADD COLUMN future_flag BOOLEAN",
        "CREATE TABLE unexpected_future_table (id INTEGER PRIMARY KEY)",
    ],
    ids=[
        "missing-unchecked-column",
        "wrong-column-type",
        "missing-foreign-key",
        "unexpected-column",
        "unexpected-table",
    ],
)
def test_modified_unversioned_legacy_schema_is_rejected(
    migration_database_url: URL,
    monkeypatch: pytest.MonkeyPatch,
    mutation: str,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        migration_database_url.render_as_string(hide_password=False),
    )
    config = _alembic_config(migration_database_url)
    command.upgrade(config, "000000000001")

    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        connection.exec_driver_sql("DROP TABLE alembic_version")
        connection.exec_driver_sql(mutation)
    engine.dispose()

    with pytest.raises(RuntimeError, match="partial or unknown unversioned schema"):
        command.upgrade(config, "000000000001")


def test_partial_unversioned_schema_is_rejected(
    migration_database_url: URL,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv(
        "DATABASE_URL",
        migration_database_url.render_as_string(hide_password=False),
    )
    engine = create_engine(migration_database_url)
    with engine.begin() as connection:
        connection.exec_driver_sql("CREATE TABLE account (id INTEGER PRIMARY KEY)")
    engine.dispose()

    with pytest.raises(RuntimeError, match="partial or unknown unversioned schema"):
        command.upgrade(_alembic_config(migration_database_url), "000000000001")
