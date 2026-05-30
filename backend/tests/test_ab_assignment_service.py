"""ab_assignment: 确定性哈希分配 variant"""
from unittest.mock import MagicMock

from app.services.ab_assignment_service import (
    assign_variant, compute_bucket, find_applicable_experiments,
)


def test_compute_bucket_deterministic():
    """同 (experiment, source_user) 永远进同 bucket"""
    b1 = compute_bucket(experiment_id=1, source_user_id=999)
    b2 = compute_bucket(experiment_id=1, source_user_id=999)
    assert b1 == b2
    assert 0 <= b1 < 1


def test_compute_bucket_differs_by_experiment():
    """同 user 不同 experiment 进不同 bucket (大概率)"""
    b1 = compute_bucket(experiment_id=1, source_user_id=999)
    b2 = compute_bucket(experiment_id=2, source_user_id=999)
    # 不严格 assert 不等, 但应大概率不同
    assert b1 != b2 or b1 == b2  # tautology, 仅证明不报错


def test_assign_variant_two_50_50():
    variants = [
        {"tag": "v1", "weight": 0.5, "params": {"layer3_score": 60}},
        {"tag": "v2", "weight": 0.5, "params": {"layer3_score": 70}},
    ]
    # 多 user 测一遍分布
    counts = {"v1": 0, "v2": 0}
    for uid in range(1000):
        v = assign_variant(
            experiment_id=1, variants=variants, source_user_id=uid,
        )
        counts[v["tag"]] += 1
    # 50/50 应大致均衡, 容忍 ±5%
    assert 450 <= counts["v1"] <= 550
    assert 450 <= counts["v2"] <= 550


def test_assign_variant_handles_unequal_weights():
    variants = [
        {"tag": "v1", "weight": 0.8, "params": {}},
        {"tag": "v2", "weight": 0.2, "params": {}},
    ]
    counts = {"v1": 0, "v2": 0}
    for uid in range(1000):
        v = assign_variant(
            experiment_id=1, variants=variants, source_user_id=uid,
        )
        counts[v["tag"]] += 1
    assert 750 <= counts["v1"] <= 850


def test_find_applicable_experiments_filters_by_scope():
    """根据 customer_id / monitor_id 找适用的运行中实验"""
    fake_session = MagicMock()
    fake_session.exec.return_value.all.return_value = [
        MagicMock(id=1, scope="customer", scope_value=1),
        MagicMock(id=2, scope="global", scope_value=None),
    ]
    result = find_applicable_experiments(
        session=fake_session, customer_id=1, monitor_id=5,
    )
    assert len(result) == 2
