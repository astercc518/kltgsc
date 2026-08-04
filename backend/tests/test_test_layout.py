from pathlib import Path


def test_pytest_collects_only_automated_test_directory() -> None:
    """Catch removal of the boundary that excludes manual network scripts."""
    config = (Path(__file__).parents[1] / "pytest.ini").read_text()

    assert "testpaths = tests" in config
    assert "python_files = test_*.py" in config
