"""
Tests for app.services.experiment_metrics_service

4 core metrics per spec §10.4:
  1. reply_rate             = sent / total_triggered
  2. private_conversion_rate= private_conversions / sent
  3. kick_rate              = kicks_after_sent / sent
  4. anti_hallucination_failure_rate = suggested / (sent + suggested)
"""
from datetime import datetime, timezone, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.services.experiment_metrics_service import (
    MetricCounters,
    aggregate_metrics_by_tag,
)


# ---------------------------------------------------------------------------
# Test 1: MetricCounters computes all 4 metrics correctly, including zero-
#         division guard (when totals are 0 every rate returns 0.0).
# ---------------------------------------------------------------------------

def test_metric_counters_all_rates():
    """Happy-path: known counters → expected rates."""
    mc = MetricCounters(
        sent=8,
        suggested=2,
        skipped_total=3,
        failed=1,
        private_conversion_count=4,
        kick_count=1,
    )

    # total_triggered = 8 + 2 + 3 + 1 = 14
    assert mc.total_triggered == 14

    # reply_rate = 8 / 14
    assert abs(mc.reply_rate() - 8 / 14) < 1e-9

    # private_conversion_rate = 4 / 8
    assert abs(mc.private_conversion_rate() - 4 / 8) < 1e-9

    # kick_rate = 1 / 8
    assert abs(mc.kick_rate() - 1 / 8) < 1e-9

    # anti_hallucination_failure_rate = 2 / (8 + 2) = 0.2
    assert abs(mc.anti_hallucination_failure_rate() - 0.2) < 1e-9


def test_metric_counters_zero_division_safe():
    """All-zero counters → every rate returns 0.0 without raising."""
    mc = MetricCounters(
        sent=0,
        suggested=0,
        skipped_total=0,
        failed=0,
        private_conversion_count=0,
        kick_count=0,
    )
    assert mc.total_triggered == 0
    assert mc.reply_rate() == 0.0
    assert mc.private_conversion_rate() == 0.0
    assert mc.kick_rate() == 0.0
    assert mc.anti_hallucination_failure_rate() == 0.0


# ---------------------------------------------------------------------------
# Test 2: aggregate_metrics_by_tag stitches together _count_status,
#         _count_private_conversions_after_sent, and _count_kicks_after_sent
#         and returns correct MetricCounters.
# ---------------------------------------------------------------------------

def test_aggregate_metrics_by_tag_stitches_counts():
    """
    aggregate_metrics_by_tag queries each sub-counter and returns a populated
    MetricCounters with the expected values.
    """
    fake_session = MagicMock()
    tag = "exp_layer3_score:v1"

    # Patch internal helpers so we can control each count independently.
    with patch(
        "app.services.experiment_metrics_service._count_status",
        side_effect=lambda *, session, experiment_tag, status: {
            "sent": 10,
            "suggested": 3,
            "skipped_human_replied": 1,
            "skipped_throttled": 2,
            "skipped_dup": 0,
            "skipped_borderline": 1,
            "skipped_no_account": 0,
            "failed": 2,
        }[status],
    ), patch(
        "app.services.experiment_metrics_service._count_private_conversions_after_sent",
        return_value=0,  # Phase 5 placeholder
    ), patch(
        "app.services.experiment_metrics_service._count_kicks_after_sent",
        return_value=2,
    ):
        result = aggregate_metrics_by_tag(
            session=fake_session, experiment_tag=tag,
        )

    assert isinstance(result, MetricCounters)
    assert result.sent == 10
    assert result.suggested == 3
    # skipped_total = 1 + 2 + 0 + 1 + 0 = 4
    assert result.skipped_total == 4
    assert result.failed == 2
    assert result.kick_count == 2
    assert result.private_conversion_count == 0

    # total_triggered = 10 + 3 + 4 + 2 = 19
    assert result.total_triggered == 19

    # reply_rate = 10 / 19
    assert abs(result.reply_rate() - 10 / 19) < 1e-9
