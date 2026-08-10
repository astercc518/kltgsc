"""
ab_assignment_service — 实验变体分配 (确定性哈希).

参考 spec §10.1-10.3
"""
import hashlib
import logging
from typing import Optional

from sqlmodel import select

from app.models.ab_experiment import ABExperiment

logger = logging.getLogger(__name__)


def compute_bucket(*, experiment_id: int, source_user_id: int) -> float:
    """同 (exp, user) 永远进同一 bucket [0, 1)"""
    seed = f"{experiment_id}:{source_user_id}".encode()
    h = hashlib.md5(seed).hexdigest()
    return int(h[:8], 16) / 0xffffffff


def assign_variant(
    *, experiment_id: int, variants: list[dict], source_user_id: int,
) -> dict:
    """
    按 weights 哈希分桶选 variant。

    variants: [{"tag": str, "weight": float, "params": dict}, ...]
    weight 自动归一。
    """
    if not variants:
        raise ValueError("variants must be non-empty")
    total = sum(v["weight"] for v in variants) or 1.0
    bucket = compute_bucket(experiment_id=experiment_id, source_user_id=source_user_id)
    cumulative = 0.0
    for v in variants:
        cumulative += v["weight"] / total
        if bucket < cumulative:
            return v
    return variants[-1]


def find_applicable_experiments(
    *, session, customer_id: int, monitor_id: int,
) -> list[ABExperiment]:
    """
    取当前 (customer, monitor) 适用的 running 实验:
    - scope=global
    - scope=customer AND scope_value=customer_id
    - scope=monitor AND scope_value=monitor_id
    """
    stmt = select(ABExperiment).where(
        ABExperiment.status == "running",
        (
            (ABExperiment.scope == "global") |
            ((ABExperiment.scope == "customer") & (ABExperiment.scope_value == customer_id)) |
            ((ABExperiment.scope == "monitor") & (ABExperiment.scope_value == monitor_id))
        )
    )
    return list(session.exec(stmt).all())
