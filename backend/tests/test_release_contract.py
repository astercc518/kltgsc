from pathlib import Path

import yaml


ROOT = Path(__file__).parents[2]


def _production_compose() -> dict:
    return yaml.safe_load((ROOT / "docker-compose.prod.yml").read_text())


def test_all_production_python_services_share_backend_environment() -> None:
    services = _production_compose()["services"]
    python_services = ["backend", "worker", "beat", *[f"listener_{i}" for i in range(5)]]

    for name in python_services:
        assert "./backend/.env" in services[name]["env_file"]
        environment = services[name]["environment"]
        assert "ENVIRONMENT=production" in environment
        assert "COMPOSE_DEPLOYMENT=true" in environment


def test_production_backend_migrates_before_serving() -> None:
    command = _production_compose()["services"]["backend"]["command"]

    assert command.index("alembic upgrade head") < command.index("gunicorn")


def test_production_nginx_receives_built_landing_assets() -> None:
    volumes = _production_compose()["services"]["nginx"]["volumes"]

    assert "./landing/dist:/usr/share/nginx/landing:ro" in volumes


def test_load_bearing_release_files_exist() -> None:
    assert list((ROOT / "backend/alembic/versions").glob("41f948211e5f_*.py"))
    assert (ROOT / "frontend/src/lib/queryClient.ts").is_file()
    assert (ROOT / "scripts/release_preflight.sh").is_file()
