"""
experiment_report_service — 按 experiment 生成 JSON 报告 + CSV 导出。

JSON 报告结构:
  {
    "experiment": str,
    "primary_metric": str | None,
    "variants": [
      {
        "tag": str,
        "counters": {sent, suggested, skipped_total, failed, ...},
        "metrics": {reply_rate, private_conversion_rate, kick_rate, anti_hallucination_failure_rate},
        "ci": {
          "reply_rate_ci": (lower, upper),
          "private_conversion_rate_ci": (lower, upper),
          "kick_rate_ci": (lower, upper),
          "anti_hallucination_failure_rate_ci": (lower, upper),
        },
      },
      ...
    ],
    "significance": {
      "primary_metric": str,
      "z_stat": float | None,
      "p_value": float | None,
      "significant": bool,
    } | None,
  }

CSV 结构:
  header row: variant_tag, sent, suggested, skipped_total, failed, total_triggered,
              reply_rate, reply_rate_ci_lo, reply_rate_ci_hi,
              private_conversion_rate, pcr_ci_lo, pcr_ci_hi,
              kick_rate, kick_rate_ci_lo, kick_rate_ci_hi,
              anti_hallucination_failure_rate, ahfr_ci_lo, ahfr_ci_hi
  one row per variant
  significance footer: significant,<bool>,p_value,<val>,z_stat,<val>,primary_metric,<name>

参考 spec §10.4 + §10.5
"""
import csv
import io
import logging
from typing import Optional

from app.services.experiment_metrics_service import MetricCounters, aggregate_metrics_by_tag
from app.services.significance_service import (
    confidence_interval_95,
    is_significant_at_95,
    two_proportion_z_test,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _variant_metrics_block(experiment_tag: str, m: MetricCounters) -> dict:
    """
    Build a single variant's full metrics block including 4 confidence intervals.

    Returns:
      {
        "tag": str,
        "counters": {...},
        "metrics": {reply_rate, private_conversion_rate, kick_rate, anti_hallucination_failure_rate},
        "ci": {
          "reply_rate_ci": (lo, hi),
          "private_conversion_rate_ci": (lo, hi),
          "kick_rate_ci": (lo, hi),
          "anti_hallucination_failure_rate_ci": (lo, hi),
        }
      }
    """
    # Derive tag from experiment_tag (format "exp_name:tag")
    tag = experiment_tag.split(":", 1)[-1] if ":" in experiment_tag else experiment_tag

    # Compute 4 rates
    rr  = m.reply_rate()
    pcr = m.private_conversion_rate()
    kr  = m.kick_rate()
    ahfr = m.anti_hallucination_failure_rate()

    # Compute 4 CIs using the appropriate x/n pairs
    rr_ci   = confidence_interval_95(x=m.sent,                      n=m.total_triggered)
    pcr_ci  = confidence_interval_95(x=m.private_conversion_count,  n=m.sent)
    kr_ci   = confidence_interval_95(x=m.kick_count,                n=m.sent)
    ahfr_ci = confidence_interval_95(x=m.suggested,                 n=m.sent + m.suggested)

    return {
        "tag": tag,
        "counters": {
            "sent":                    m.sent,
            "suggested":               m.suggested,
            "skipped_total":           m.skipped_total,
            "failed":                  m.failed,
            "private_conversion_count": m.private_conversion_count,
            "kick_count":              m.kick_count,
            "total_triggered":         m.total_triggered,
        },
        "metrics": {
            "reply_rate":                      rr,
            "private_conversion_rate":         pcr,
            "kick_rate":                       kr,
            "anti_hallucination_failure_rate": ahfr,
        },
        "ci": {
            "reply_rate_ci":                      list(rr_ci),
            "private_conversion_rate_ci":         list(pcr_ci),
            "kick_rate_ci":                       list(kr_ci),
            "anti_hallucination_failure_rate_ci": list(ahfr_ci),
        },
    }


def _significance_block(
    primary_metric: Optional[str],
    var_blocks: list[dict],
) -> Optional[dict]:
    """
    Run z-test on the primary_metric between the first 2 variants.

    Returns None if fewer than 2 variants, or if primary_metric is unknown.
    """
    if len(var_blocks) < 2:
        return None

    metric = primary_metric or "reply_rate"
    b0, b1 = var_blocks[0], var_blocks[1]

    # Map metric name → (x, n) extractor
    def _get_xn(block: dict, m: str) -> tuple[int, int]:
        c = block["counters"]
        if m == "reply_rate":
            return c["sent"], c["total_triggered"]
        elif m == "private_conversion_rate":
            return c["private_conversion_count"], c["sent"]
        elif m == "kick_rate":
            return c["kick_count"], c["sent"]
        elif m == "anti_hallucination_failure_rate":
            return c["suggested"], c["sent"] + c["suggested"]
        else:
            logger.warning("unknown primary_metric %r; falling back to reply_rate", m)
            return c["sent"], c["total_triggered"]

    x1, n1 = _get_xn(b0, metric)
    x2, n2 = _get_xn(b1, metric)

    z_stat, p_value = two_proportion_z_test(x1=x1, n1=n1, x2=x2, n2=n2)
    significant = is_significant_at_95(p_value=p_value)

    return {
        "primary_metric": metric,
        "variant_ctrl":   b0["tag"],
        "variant_exp":    b1["tag"],
        "z_stat":         z_stat,
        "p_value":        p_value,
        "significant":    significant,
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def build_experiment_report(*, session, experiment) -> dict:
    """
    Orchestrator — aggregate metrics for each variant, compute CIs, run z-test.

    Parameters:
        session:    SQLModel session
        experiment: ABExperiment ORM object (must have .name, .primary_metric, .variants)

    Returns:
        JSON-serialisable report dict (see module docstring).
    """
    exp_name = experiment.name
    primary_metric = experiment.primary_metric
    variants_cfg: list[dict] = experiment.variants or []

    var_blocks: list[dict] = []
    for v in variants_cfg:
        tag = v.get("tag", "")
        experiment_tag = f"{exp_name}:{tag}"
        try:
            m: MetricCounters = aggregate_metrics_by_tag(
                session=session, experiment_tag=experiment_tag
            )
        except Exception:
            logger.exception(
                "aggregate_metrics_by_tag failed for %s; using zero counters", experiment_tag
            )
            m = MetricCounters(
                sent=0, suggested=0, skipped_total=0, failed=0,
                private_conversion_count=0, kick_count=0,
            )
        block = _variant_metrics_block(experiment_tag, m)
        var_blocks.append(block)

    sig = _significance_block(primary_metric, var_blocks)

    return {
        "experiment":     exp_name,
        "primary_metric": primary_metric,
        "variants":       var_blocks,
        "significance":   sig,
    }


def render_csv(report: dict) -> str:
    """
    Render a report dict to CSV string.

    Format:
      Row 0  — header
      Rows 1…N — one row per variant
      Last row  — significance footer: significant,<bool>,p_value,<val>,z_stat,<val>,primary_metric,<name>
    """
    output = io.StringIO()
    writer = csv.writer(output)

    # Header
    writer.writerow([
        "variant_tag",
        "sent", "suggested", "skipped_total", "failed", "total_triggered",
        "reply_rate", "reply_rate_ci_lo", "reply_rate_ci_hi",
        "private_conversion_rate", "pcr_ci_lo", "pcr_ci_hi",
        "kick_rate", "kick_rate_ci_lo", "kick_rate_ci_hi",
        "anti_hallucination_failure_rate", "ahfr_ci_lo", "ahfr_ci_hi",
    ])

    # One row per variant
    for b in report.get("variants", []):
        c  = b["counters"]
        m  = b["metrics"]
        ci = b["ci"]
        rr_ci   = ci["reply_rate_ci"]
        pcr_ci  = ci["private_conversion_rate_ci"]
        kr_ci   = ci["kick_rate_ci"]
        ahfr_ci = ci["anti_hallucination_failure_rate_ci"]
        writer.writerow([
            b["tag"],
            c["sent"], c["suggested"], c["skipped_total"], c["failed"], c["total_triggered"],
            round(m["reply_rate"], 6),
            round(rr_ci[0], 6), round(rr_ci[1], 6),
            round(m["private_conversion_rate"], 6),
            round(pcr_ci[0], 6), round(pcr_ci[1], 6),
            round(m["kick_rate"], 6),
            round(kr_ci[0], 6), round(kr_ci[1], 6),
            round(m["anti_hallucination_failure_rate"], 6),
            round(ahfr_ci[0], 6), round(ahfr_ci[1], 6),
        ])

    # Significance footer
    sig = report.get("significance")
    if sig is not None:
        writer.writerow([
            "significant", sig["significant"],
            "p_value",     sig["p_value"],
            "z_stat",      sig["z_stat"],
            "primary_metric", sig["primary_metric"],
        ])
    else:
        writer.writerow(["significant", "N/A", "p_value", "N/A", "z_stat", "N/A", "primary_metric", "N/A"])

    return output.getvalue()
