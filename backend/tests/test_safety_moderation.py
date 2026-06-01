"""Tests for L1 toxic-bert moderation wrapper.

Model inference is mocked — these tests verify the wrapper logic, not
the model accuracy. Accuracy is validated separately via a sample-set
calibration step in operations docs.
"""
from unittest.mock import patch
import pytest

from app.services.safety.moderation import (
    Moderator, ModerationScore, ModerationVerdict, DEFAULT_THRESHOLDS,
)


def test_score_dict_has_expected_dims():
    s = ModerationScore(sexual=0.1, violence=0.0, hate=0.2,
                        self_harm=0.0, political=0.05)
    d = s.to_dict()
    assert set(d.keys()) == {"sexual", "violence", "hate", "self_harm", "political"}


def test_max_dim_returns_strongest_signal():
    s = ModerationScore(sexual=0.1, violence=0.8, hate=0.2,
                        self_harm=0.0, political=0.05)
    name, val = s.max_dim()
    assert name == "violence"
    assert val == 0.8


def test_classify_clean_text_returns_clean():
    mod = Moderator()
    with patch.object(mod, "_score", return_value=ModerationScore(
        sexual=0.05, violence=0.02, hate=0.01, self_harm=0.0, political=0.0
    )):
        v = mod.evaluate("买点啥都行,给我个报价")
    assert v.tier == "clean"
    assert v.blocked is False


def test_classify_grey_routes_away_from_vertex():
    mod = Moderator()
    with patch.object(mod, "_score", return_value=ModerationScore(
        sexual=0.45, violence=0.0, hate=0.0, self_harm=0.0, political=0.0
    )):
        v = mod.evaluate("borderline sexual content")
    assert v.tier == "grey"
    assert v.blocked is False
    assert v.avoid_vertex is True


def test_classify_red_blocks():
    mod = Moderator()
    with patch.object(mod, "_score", return_value=ModerationScore(
        sexual=0.95, violence=0.0, hate=0.0, self_harm=0.0, political=0.0
    )):
        v = mod.evaluate("very explicit")
    assert v.tier == "red"
    assert v.blocked is True


def test_thresholds_overridable():
    custom = {"sexual_grey": 0.3, "sexual_red": 0.5}
    mod = Moderator(thresholds={**DEFAULT_THRESHOLDS, **custom})
    with patch.object(mod, "_score", return_value=ModerationScore(
        sexual=0.4, violence=0.0, hate=0.0, self_harm=0.0, political=0.0
    )):
        v = mod.evaluate("borderline")
    assert v.tier == "grey"
