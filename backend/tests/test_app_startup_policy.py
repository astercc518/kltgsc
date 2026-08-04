from app import main


def test_production_startup_does_not_create_schema() -> None:
    object.__setattr__(main.settings, "ENVIRONMENT", "production")

    assert main.should_create_tables() is False


def test_development_startup_keeps_local_schema_bootstrap() -> None:
    object.__setattr__(main.settings, "ENVIRONMENT", "development")

    assert main.should_create_tables() is True


def test_moderator_warmup_can_be_disabled() -> None:
    object.__setattr__(main.settings, "LLM_SAFETY_WARMUP", False)

    assert main.should_warmup_moderator() is False
