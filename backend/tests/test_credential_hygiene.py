import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[2]


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
