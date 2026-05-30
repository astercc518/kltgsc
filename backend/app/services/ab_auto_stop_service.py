"""
ab_auto_stop_service — 每日检查 running 实验, 若样本充足且显著则自动停。

约定:
- 最小样本: 200 / variant (太少 CI 太宽)
- 显著阈值: p < 0.01 (比标准 0.05 更严, 自动停应该高置信)
- 写 ab_experiment_audit_log reason='significant_result', operator_id=None
"""
import logging
from datetime import datetime, timezone

from sqlmodel import Session, select

from app.core.db import engine
from app.models.ab_experiment import ABExperiment
from app.models.ab_experiment_audit_log import ABExperimentAuditLog
from app.services.experiment_report_service import build_experiment_report

logger = logging.getLogger(__name__)

MIN_SAMPLE_PER_VARIANT = 200
AUTO_STOP_P_THRESHOLD = 0.01


def should_auto_stop(*, experiment, report: dict) -> dict:
    """Decide if an experiment should auto-stop.

    Returns: {"should_stop": bool, "reason": str}
    """
    variants = report.get("variants", [])
    if len(variants) < 2:
        return {"should_stop": False, "reason": "not_enough_variants"}

    # Check sample size
    for v in variants:
        counters = v.get("counters", {})
        total = counters.get("total_triggered", 0)
        if total < MIN_SAMPLE_PER_VARIANT:
            return {
                "should_stop": False,
                "reason": f"sample_too_small (variant {v.get('tag')} = {total} < {MIN_SAMPLE_PER_VARIANT})",
            }

    # Check significance
    sig = report.get("significance") or {}
    p = sig.get("p_value")
    if p is None or p >= AUTO_STOP_P_THRESHOLD:
        return {
            "should_stop": False,
            "reason": f"not_significant (p={p})",
        }

    return {"should_stop": True, "reason": "significant_result"}


def _list_running_experiments() -> list:
    with Session(engine) as session:
        rows = session.exec(
            select(ABExperiment).where(ABExperiment.status == "running")
        ).all()
        return list(rows)


def _stop_experiment_with_audit(*, experiment, reason: str) -> None:
    with Session(engine) as session:
        exp = session.get(ABExperiment, experiment.id)
        if exp is None or exp.status != "running":
            logger.warning("auto_stop: experiment %s not in running state", experiment.id)
            return
        exp.status = "finished"
        exp.ended_at = datetime.now(timezone.utc)
        session.add(exp)

        # audit log
        audit = ABExperimentAuditLog(
            experiment_id=exp.id,
            action="auto_stopped",
            operator_id=None,  # system action
            reason=reason,
            metadata_json=None,
            created_at=datetime.now(timezone.utc),
        )
        session.add(audit)

        session.commit()
    logger.info("auto_stop: experiment %s stopped (reason: %s)", experiment.id, reason)


def run_auto_stop_check() -> int:
    """Main entry. Returns count of experiments auto-stopped."""
    experiments = _list_running_experiments()
    stopped = 0
    for exp in experiments:
        try:
            with Session(engine) as session:
                report = build_experiment_report(session=session, experiment=exp)
        except Exception:
            logger.exception("auto_stop: failed to build report for exp %s", exp.id)
            continue

        decision = should_auto_stop(experiment=exp, report=report)
        if decision["should_stop"]:
            try:
                _stop_experiment_with_audit(
                    experiment=exp, reason=decision["reason"],
                )
                stopped += 1
            except Exception:
                logger.exception("auto_stop: failed to stop exp %s", exp.id)
    return stopped
