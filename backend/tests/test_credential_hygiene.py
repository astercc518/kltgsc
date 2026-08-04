import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[2]
RETIRED_ADMIN_PASSWORD = "Admin@" + "Tgsc2026"


def test_migration_guide_contains_no_literal_host_or_credential_uri() -> None:
    guide = (ROOT / "docs/architecture/MIGRATION_GUIDE.md").read_text()

    assert re.search(r"\b(?:\d{1,3}\.){3}\d{1,3}\b", guide) is None
    assert re.search(r"(?:postgresql|redis)://[^<\s]+:[^<\s@]+@", guide) is None
    assert "<DB_HOST>" in guide
    assert "<REDIS_PASSWORD>" in guide
    assert "<ADMIN_PASSWORD>" in guide


def test_tracked_secret_scanner_passes_without_echoing_values() -> None:
    result = subprocess.run(
        ["bash", "scripts/check_tracked_secrets.sh"],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == "tracked secret scan passed"


def test_retired_admin_password_is_absent_from_tracked_files() -> None:
    result = subprocess.run(
        ["git", "grep", "-l", "-F", RETIRED_ADMIN_PASSWORD],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 1, (
        "retired admin credential remains in tracked files:\n" + result.stdout
    )


def test_smoke_script_requires_admin_password_from_environment() -> None:
    smoke_script = (ROOT / "backend/scripts/bulk_send_e2e_smoke.py").read_text()

    assert 'os.environ["SMOKE_ADMIN_PASSWORD"]' in smoke_script


def test_scanner_rejects_retired_credential_without_echoing_it(tmp_path: Path) -> None:
    sample = tmp_path / "credential.txt"
    sample.write_text(f"ADMIN_PASSWORD={RETIRED_ADMIN_PASSWORD}\n")

    result = subprocess.run(
        ["bash", "scripts/check_tracked_secrets.sh", str(sample)],
        cwd=ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    output = result.stdout + result.stderr

    assert result.returncode == 1
    assert RETIRED_ADMIN_PASSWORD not in output
