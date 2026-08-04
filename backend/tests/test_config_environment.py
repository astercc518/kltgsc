from pathlib import Path

import pytest
from pydantic import ValidationError

from app.core.config import Settings


VALID_PRODUCTION = {
    "ENVIRONMENT": "production",
    "SECRET_KEY": "s" * 32,
    "SESSION_ENCRYPTION_KEY": "e" * 32,
    "ADMIN_PASSWORD": "StrongAdminPassword1",
    "DATABASE_URL": "postgresql://tgsc:password@db/tgsc",
    "REDIS_URL": "redis://:password@redis:6379/0",
    "COMPOSE_DEPLOYMENT": True,
}


def production_settings(**overrides: object) -> Settings:
    values = {**VALID_PRODUCTION, **overrides}
    return Settings(_env_file=None, **values)


@pytest.mark.parametrize("environment", ["staging", "prod", ""])
def test_environment_rejects_unknown_modes(environment: str) -> None:
    with pytest.raises(ValidationError):
        production_settings(ENVIRONMENT=environment)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("SECRET_KEY", ""),
        ("SECRET_KEY", "short"),
        ("SESSION_ENCRYPTION_KEY", ""),
        ("SESSION_ENCRYPTION_KEY", "short"),
        ("ADMIN_PASSWORD", ""),
        ("ADMIN_PASSWORD", "admin123"),
        ("ADMIN_PASSWORD", "Admin@" + "Tgsc2026"),
        ("ADMIN_PASSWORD", "Short1"),
        ("SECURITY_ENABLED", False),
        ("DATABASE_URL", "sqlite:///./tgsc.db"),
        ("REDIS_URL", ""),
        ("REDIS_URL", "redis://redis:6379/0"),
    ],
)
def test_production_rejects_unsafe_runtime_values(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        production_settings(**{field: value})


def test_non_compose_production_allows_external_redis_without_url_password() -> None:
    configured = production_settings(
        COMPOSE_DEPLOYMENT=False,
        REDIS_URL="rediss://managed-redis.example/0",
    )

    assert configured.REDIS_URL == "rediss://managed-redis.example/0"


def test_development_generated_values_are_never_printed(capsys: pytest.CaptureFixture[str]) -> None:
    configured = Settings(
        _env_file=None,
        ENVIRONMENT="development",
        SECRET_KEY="",
        SESSION_ENCRYPTION_KEY="",
        ADMIN_PASSWORD="",
    )

    captured = capsys.readouterr()
    combined_output = captured.out + captured.err
    generated_values = (
        configured.SECRET_KEY,
        configured.SESSION_ENCRYPTION_KEY,
        configured.ADMIN_PASSWORD,
    )
    assert all(generated_values)
    assert all(value not in combined_output for value in generated_values)


def test_example_environment_cannot_be_used_as_production_credentials(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    example = Path(__file__).parents[1] / ".env.example"
    for field in VALID_PRODUCTION:
        monkeypatch.delenv(field, raising=False)
    monkeypatch.delenv("SECURITY_ENABLED", raising=False)

    with pytest.raises(ValidationError):
        Settings(_env_file=example)
