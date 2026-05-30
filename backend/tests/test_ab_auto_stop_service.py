"""ab_auto_stop_service: 自动停实验逻辑"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

from app.services.ab_auto_stop_service import (
    should_auto_stop, run_auto_stop_check,
)


def test_should_auto_stop_when_significant_and_enough_sample():
    """primary_metric=reply_rate, total > 1000, p < 0.01 → True"""
    fake_report = {
        "variants": [
            {"counters": {"sent": 600, "total_triggered": 1000}, "metrics": {"reply_rate": 0.6}},
            {"counters": {"sent": 400, "total_triggered": 1000}, "metrics": {"reply_rate": 0.4}},
        ],
        "significance": {"p_value": 0.001, "significant": True},
    }
    fake_exp = MagicMock(primary_metric="reply_rate")
    result = should_auto_stop(experiment=fake_exp, report=fake_report)
    assert result["should_stop"] is True
    assert result["reason"] == "significant_result"


def test_should_not_auto_stop_when_sample_too_small():
    """total < 200 → 即使 significant 也不停 (规则: 最少 200/variant)"""
    fake_report = {
        "variants": [
            {"counters": {"sent": 50, "total_triggered": 100}, "metrics": {"reply_rate": 0.5}},
            {"counters": {"sent": 30, "total_triggered": 100}, "metrics": {"reply_rate": 0.3}},
        ],
        "significance": {"p_value": 0.001, "significant": True},
    }
    fake_exp = MagicMock(primary_metric="reply_rate")
    result = should_auto_stop(experiment=fake_exp, report=fake_report)
    assert result["should_stop"] is False
    assert "sample_too_small" in result["reason"]


def test_should_not_auto_stop_when_not_significant():
    fake_report = {
        "variants": [
            {"counters": {"sent": 500, "total_triggered": 1000}, "metrics": {"reply_rate": 0.5}},
            {"counters": {"sent": 480, "total_triggered": 1000}, "metrics": {"reply_rate": 0.48}},
        ],
        "significance": {"p_value": 0.45, "significant": False},
    }
    fake_exp = MagicMock(primary_metric="reply_rate")
    result = should_auto_stop(experiment=fake_exp, report=fake_report)
    assert result["should_stop"] is False
    assert "not_significant" in result["reason"]


def test_run_auto_stop_check_stops_qualifying_experiments():
    """主 entry: 拉 running 实验 + 每个判断 + stop + audit"""
    fake_exp = MagicMock(id=1, name="test_exp", primary_metric="reply_rate", status="running")
    fake_report = {
        "variants": [
            {"counters": {"sent": 600, "total_triggered": 1000}, "metrics": {"reply_rate": 0.6}},
            {"counters": {"sent": 400, "total_triggered": 1000}, "metrics": {"reply_rate": 0.4}},
        ],
        "significance": {"p_value": 0.001, "significant": True},
    }
    with patch("app.services.ab_auto_stop_service._list_running_experiments", return_value=[fake_exp]), \
         patch("app.services.ab_auto_stop_service.build_experiment_report", return_value=fake_report), \
         patch("app.services.ab_auto_stop_service._stop_experiment_with_audit") as stop_mock:
        n = run_auto_stop_check()
    assert n == 1
    stop_mock.assert_called_once_with(experiment=fake_exp, reason="significant_result")
