from pathlib import Path

import yaml


ROOT = Path(__file__).parents[2]
WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"


def _job_commands(job: dict) -> str:
    return "\n".join(
        step.get("run", "")
        for step in job.get("steps", [])
        if isinstance(step, dict)
    )


def test_ci_workflow_defines_independent_release_gates() -> None:
    assert WORKFLOW.is_file(), "CI workflow is required"

    jobs = yaml.safe_load(WORKFLOW.read_text())["jobs"]
    assert {"backend", "frontend", "landing", "release-contract"} <= set(jobs)


def test_backend_ci_collects_tests_and_checks_release_inputs() -> None:
    jobs = yaml.safe_load(WORKFLOW.read_text())["jobs"]
    commands = _job_commands(jobs["backend"])

    for required in (
        "pytest --collect-only -q",
        "pytest -q",
        "alembic heads",
        "alembic upgrade head",
        "scripts/check_tracked_secrets.sh",
    ):
        assert required in commands

    postgres = jobs["backend"]["services"]["postgres"]
    assert postgres["image"].startswith("pgvector/pgvector:pg16")
    migration_step = next(
        step
        for step in jobs["backend"]["steps"]
        if "alembic upgrade head" in step.get("run", "")
    )
    assert migration_step["env"]["DATABASE_URL"].startswith("postgresql://")


def test_web_ci_uses_locked_installs_and_separate_gates() -> None:
    jobs = yaml.safe_load(WORKFLOW.read_text())["jobs"]

    for job_name in ("frontend", "landing"):
        commands = _job_commands(jobs[job_name])
        for required in (
            "npm ci",
            "npm run typecheck",
            "npm test -- --run",
            "npm run build",
        ):
            assert required in commands


def test_release_ci_validates_compose_and_contract_files() -> None:
    jobs = yaml.safe_load(WORKFLOW.read_text())["jobs"]
    commands = _job_commands(jobs["release-contract"])

    for required in (
        "test -f landing/dist/index.html",
        "test -f frontend/src/lib/queryClient.ts",
        "test -f scripts/release_preflight.sh",
        "docker compose --env-file .env -f docker-compose.yml config -q",
        "docker compose --env-file .env -f docker-compose.prod.yml config -q",
    ):
        assert required in commands
