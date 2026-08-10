"""significance_service: 双比例 z 检验 + 95% CI"""
import math

import pytest

from app.services.significance_service import (
    _normal_cdf,
    confidence_interval_95,
    is_significant_at_95,
    two_proportion_z_test,
)


def test_normal_cdf_midpoint():
    """正态 CDF: Phi(0) == 0.5"""
    assert abs(_normal_cdf(0.0) - 0.5) < 1e-9


def test_normal_cdf_1_96():
    """Phi(1.96) ≈ 0.975 (双侧 5% 临界值)"""
    assert abs(_normal_cdf(1.96) - 0.975) < 1e-3


def test_two_proportion_z_test_significant():
    """明显差异 (10% vs 20%, n=1000) 应 p < 0.05"""
    z, p = two_proportion_z_test(x1=100, n1=1000, x2=200, n2=1000)
    assert z is not None and p is not None
    assert p < 0.05
    # p2 - p1 = 0.2 - 0.1 = 0.1 > 0 => z > 0
    assert z > 0


def test_two_proportion_z_test_not_significant():
    """几乎相同的比例 (10% vs 10.1%, n=100) 应 p > 0.05"""
    z, p = two_proportion_z_test(x1=10, n1=100, x2=11, n2=100)
    assert p is not None
    assert p > 0.05


def test_two_proportion_z_test_zero_n():
    """n=0 时返回 (None, None)"""
    z, p = two_proportion_z_test(x1=0, n1=0, x2=5, n2=100)
    assert z is None and p is None


def test_confidence_interval_95_basic():
    """50% 比例, n=1000: CI 应在 [0.469, 0.531] 附近"""
    lo, hi = confidence_interval_95(x=500, n=1000)
    assert lo < 0.5 < hi
    assert abs(lo - 0.469) < 0.01
    assert abs(hi - 0.531) < 0.01


def test_is_significant_at_95_none_safe():
    """p_value=None 应返回 False"""
    assert is_significant_at_95(p_value=None) is False


def test_is_significant_at_95_boundary():
    """p=0.04 显著，p=0.06 不显著"""
    assert is_significant_at_95(p_value=0.04) is True
    assert is_significant_at_95(p_value=0.06) is False
