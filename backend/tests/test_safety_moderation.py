"""Tests for L1 multilingual toxicity moderation wrapper.

Model inference is mocked — these tests verify the wrapper logic, not
the model accuracy. Accuracy is validated via a separate
sample-set calibration step (ops runbook).
"""
from unittest.mock import patch
import pytest

from app.services.safety.moderation import (
    Moderator, ModerationScore, ModerationVerdict, DEFAULT_THRESHOLDS,
)


def test_score_dict_has_toxic_dim():
    s = ModerationScore(toxic=0.42)
    d = s.to_dict()
    assert d == {"toxic": 0.42}


def test_max_dim_returns_toxic():
    s = ModerationScore(toxic=0.7)
    name, val = s.max_dim()
    assert name == "toxic"
    assert val == 0.7


def test_classify_clean_text_returns_clean():
    mod = Moderator()
    with patch.object(mod, "_score", return_value=ModerationScore(toxic=0.05)):
        v = mod.evaluate("买点啥都行,给我个报价")
    assert v.tier == "clean"
    assert v.blocked is False
    assert v.avoid_vertex is False
    assert v.dim_triggered is None


def test_classify_grey_routes_away_from_vertex():
    mod = Moderator()
    with patch.object(mod, "_score", return_value=ModerationScore(toxic=0.6)):
        v = mod.evaluate("borderline toxic content")
    assert v.tier == "grey"
    assert v.blocked is False
    assert v.avoid_vertex is True
    assert v.dim_triggered == "toxic"


def test_classify_red_blocks():
    mod = Moderator()
    with patch.object(mod, "_score", return_value=ModerationScore(toxic=0.95)):
        v = mod.evaluate("very explicit hate")
    assert v.tier == "red"
    assert v.blocked is True
    assert v.avoid_vertex is True
    assert v.dim_triggered == "toxic"


def test_thresholds_overridable():
    custom = {"toxic_grey": 0.3, "toxic_red": 0.5}
    mod = Moderator(thresholds={**DEFAULT_THRESHOLDS, **custom})
    with patch.object(mod, "_score", return_value=ModerationScore(toxic=0.4)):
        v = mod.evaluate("borderline")
    assert v.tier == "grey"


def test_empty_input_short_circuits():
    """Empty/whitespace text returns clean without invoking the model."""
    mod = Moderator()
    with patch.object(mod, "_score", side_effect=AssertionError("should not call")):
        v = mod.evaluate("")
        v2 = mod.evaluate("   ")
    assert v.tier == "clean" and v.score.toxic == 0.0
    assert v2.tier == "clean"


def test_warmup_invokes_loader_once():
    from app.services.safety import moderation as mod_module
    with patch.object(mod_module, "_get_session") as mock_loader:
        Moderator.warmup()
        Moderator.warmup()
    assert mock_loader.call_count == 2
