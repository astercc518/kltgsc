"""Smoke test that the reranker settings load with the expected defaults."""
import importlib
import sys


def test_reranker_settings_defaults(monkeypatch):
    # Force a fresh import so default env values take effect (no .env override)
    for key in ("RERANK_ENABLED", "RERANK_MODEL", "RERANK_CANDIDATE_MULTIPLIER", "RERANK_TIMEOUT_MS"):
        monkeypatch.delenv(key, raising=False)
    sys.modules.pop("app.core.config", None)
    import app.core.config as cfg

    s = cfg.Settings()
    assert s.RERANK_ENABLED is False
    assert s.RERANK_MODEL == "BAAI/bge-reranker-v2-m3"
    assert s.RERANK_CANDIDATE_MULTIPLIER == 5
    assert s.RERANK_TIMEOUT_MS == 800


def test_reranker_settings_env_override(monkeypatch):
    monkeypatch.setenv("RERANK_ENABLED", "true")
    monkeypatch.setenv("RERANK_CANDIDATE_MULTIPLIER", "8")
    sys.modules.pop("app.core.config", None)
    import app.core.config as cfg

    s = cfg.Settings()
    assert s.RERANK_ENABLED is True
    assert s.RERANK_CANDIDATE_MULTIPLIER == 8
