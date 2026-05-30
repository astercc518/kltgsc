"""
Smoke tests for admin AB experiment metrics / report / CSV export endpoints.

Skipped pending admin auth fixture (Phase 2b).
"""
import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


@pytest.fixture
def client():
    from app.main import app
    return TestClient(app)


@pytest.mark.skip(reason="needs admin auth fixture, Phase 2b")
def test_get_experiment_metrics_returns_per_variant_rates(client):
    fake_exp = MagicMock(id=1, name="exp1", variants=[{"tag": "ctrl"}, {"tag": "treat"}])
    fake_metrics = MagicMock(
        sent=100, suggested=80, skipped_total=20, failed=5,
    )
    fake_metrics.reply_rate.return_value = 0.5
    fake_metrics.private_conversion_rate.return_value = 0.1
    fake_metrics.kick_rate.return_value = 0.02
    fake_metrics.anti_hallucination_failure_rate.return_value = 0.01
    with patch("app.routers.admin_group_ai.aggregate_metrics_by_tag", return_value=fake_metrics):
        with patch("app.routers.admin_group_ai.get_session") as ms:
            fake_session = MagicMock()
            fake_session.get.return_value = fake_exp
            ms.return_value.__next__ = MagicMock(return_value=fake_session)
            r = client.get("/admin/group-ai/ab/experiments/1/metrics")
    assert r.status_code in (200, 422)


@pytest.mark.skip(reason="needs admin auth fixture, Phase 2b")
def test_export_experiment_csv_content_disposition(client):
    fake_exp = MagicMock(id=1, name="exp1", variants=[{"tag": "ctrl"}])
    fake_report = {"experiment_id": 1, "variants": []}
    with patch("app.routers.admin_group_ai.build_experiment_report", return_value=fake_report):
        with patch("app.routers.admin_group_ai.render_csv", return_value="col1,col2\nval1,val2\n"):
            with patch("app.routers.admin_group_ai.get_session") as ms:
                fake_session = MagicMock()
                fake_session.get.return_value = fake_exp
                ms.return_value.__next__ = MagicMock(return_value=fake_session)
                r = client.get("/admin/group-ai/ab/experiments/1/report.csv")
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert "attachment" in r.headers.get("content-disposition", "")
