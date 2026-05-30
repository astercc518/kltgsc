"""Phase 6: experiment_metrics 真算 private_conversion_rate"""
from unittest.mock import patch, MagicMock

from app.services.experiment_metrics_service import (
    _count_private_conversions_after_sent,
)


def test_count_delegates_to_lead_conversion_service():
    with patch(
        "app.services.lead_conversion_service.count_private_conversions_for_experiment",
        return_value=42,
    ):
        cnt = _count_private_conversions_after_sent(
            session=MagicMock(), experiment_tag="exp:v1",
        )
    assert cnt == 42
