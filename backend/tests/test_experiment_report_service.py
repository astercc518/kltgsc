"""
experiment_report_service: JSON 报告 + CSV 导出

Test 1: build_experiment_report returns correct structure with variant blocks + significance
Test 2: render_csv returns valid CSV with header + variant rows + significance footer
"""
import csv
import io
from unittest.mock import MagicMock, patch

from app.services.experiment_metrics_service import MetricCounters
from app.services.experiment_report_service import (
    build_experiment_report,
    render_csv,
)


# ---------------------------------------------------------------------------
# Helper: build a fake ABExperiment
# ---------------------------------------------------------------------------

def _fake_experiment(
    *,
    name: str = "exp_layer3_score",
    primary_metric: str = "reply_rate",
    variants: list | None = None,
) -> MagicMock:
    exp = MagicMock()
    exp.name = name
    exp.primary_metric = primary_metric
    exp.variants = variants or [
        {"tag": "ctrl", "weight": 0.5, "params": {"layer3_score": 60}},
        {"tag": "v1",   "weight": 0.5, "params": {"layer3_score": 70}},
    ]
    return exp


def _mc(sent: int, suggested: int, skipped: int, failed: int) -> MetricCounters:
    return MetricCounters(
        sent=sent,
        suggested=suggested,
        skipped_total=skipped,
        failed=failed,
        private_conversion_count=0,
        kick_count=0,
    )


# ---------------------------------------------------------------------------
# Test 1: build_experiment_report structure
# ---------------------------------------------------------------------------

def test_build_experiment_report_structure():
    """
    build_experiment_report must return a dict with:
      - "experiment": name string
      - "primary_metric": string
      - "variants": list of per-variant blocks (one per variant tag)
      - "significance": dict or None

    Each variant block must contain:
      - "tag", "counters", "metrics", and "ci" sub-dict with 4 CIs.
    """
    exp = _fake_experiment()
    fake_session = MagicMock()

    mc_ctrl = _mc(sent=50, suggested=5, skipped=10, failed=2)
    mc_v1   = _mc(sent=60, suggested=4, skipped=8,  failed=2)

    def fake_aggregate(*, session, experiment_tag: str) -> MetricCounters:
        if experiment_tag.endswith(":ctrl"):
            return mc_ctrl
        return mc_v1

    with patch(
        "app.services.experiment_report_service.aggregate_metrics_by_tag",
        side_effect=fake_aggregate,
    ):
        report = build_experiment_report(session=fake_session, experiment=exp)

    # Top-level keys
    assert report["experiment"] == "exp_layer3_score"
    assert report["primary_metric"] == "reply_rate"
    assert len(report["variants"]) == 2

    # Per-variant block shape
    ctrl_block = report["variants"][0]
    assert ctrl_block["tag"] == "ctrl"
    assert "counters" in ctrl_block
    assert "metrics" in ctrl_block
    assert "ci" in ctrl_block

    ci = ctrl_block["ci"]
    assert "reply_rate_ci" in ci
    assert "private_conversion_rate_ci" in ci
    assert "kick_rate_ci" in ci
    assert "anti_hallucination_failure_rate_ci" in ci

    # CI values are (float, float) tuples / lists
    rr_ci = ci["reply_rate_ci"]
    assert len(rr_ci) == 2
    assert rr_ci[0] <= rr_ci[1]

    # Significance block present (2 variants, some difference)
    sig = report["significance"]
    assert sig is not None
    assert "primary_metric" in sig
    assert "z_stat" in sig
    assert "p_value" in sig
    assert "significant" in sig


# ---------------------------------------------------------------------------
# Test 2: render_csv output
# ---------------------------------------------------------------------------

def test_render_csv_structure():
    """
    render_csv(report) must produce valid CSV where:
      - First row is a header
      - Subsequent data rows contain variant tag + metric values
      - Last non-empty line contains significance info (or 'N/A')
    """
    exp = _fake_experiment()
    fake_session = MagicMock()

    mc_ctrl = _mc(sent=50, suggested=5, skipped=10, failed=2)
    mc_v1   = _mc(sent=60, suggested=4, skipped=8,  failed=2)

    def fake_aggregate(*, session, experiment_tag: str) -> MetricCounters:
        if experiment_tag.endswith(":ctrl"):
            return mc_ctrl
        return mc_v1

    with patch(
        "app.services.experiment_report_service.aggregate_metrics_by_tag",
        side_effect=fake_aggregate,
    ):
        report = build_experiment_report(session=fake_session, experiment=exp)

    csv_text = render_csv(report)
    assert isinstance(csv_text, str)
    assert len(csv_text) > 0

    reader = csv.reader(io.StringIO(csv_text))
    rows = [r for r in reader if any(cell.strip() for cell in r)]

    # Must have at least: header + 2 variant rows + 1 significance row
    assert len(rows) >= 4

    header = rows[0]
    assert "tag" in header[0].lower() or "variant" in header[0].lower() or header[0] != ""

    # Variant rows: first column is tag name
    variant_tags = {rows[1][0], rows[2][0]}
    assert "ctrl" in variant_tags
    assert "v1" in variant_tags

    # Significance footer: last non-empty row should mention significance
    footer = rows[-1]
    footer_str = ",".join(footer).lower()
    assert "significant" in footer_str or "p_value" in footer_str or "sig" in footer_str
