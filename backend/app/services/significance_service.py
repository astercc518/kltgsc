"""
significance_service — two-proportion z-test + 95% CI.

纯 Python 实现，无需 scipy / numpy，使用 math.erf 计算正态 CDF。
"""
import math
from typing import Optional


def _normal_cdf(z: float) -> float:
    """标准正态分布 CDF，使用 math.erf 精确实现。"""
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def two_proportion_z_test(
    *,
    x1: int,
    n1: int,
    x2: int,
    n2: int,
) -> tuple[Optional[float], Optional[float]]:
    """
    双比例 z 检验。

    参数:
        x1: 对照组转化数
        n1: 对照组总数
        x2: 实验组转化数
        n2: 实验组总数

    返回:
        (z_stat, two_sided_p_value)；若 n=0 或方差=0 则返回 (None, None)。
    """
    if n1 == 0 or n2 == 0:
        return None, None

    p1 = x1 / n1
    p2 = x2 / n2
    p_pool = (x1 + x2) / (n1 + n2)

    variance = p_pool * (1 - p_pool) * (1 / n1 + 1 / n2)
    if variance <= 0:
        return None, None

    z = (p2 - p1) / math.sqrt(variance)
    # 双侧 p 值
    p_value = 2.0 * (1.0 - _normal_cdf(abs(z)))
    return z, p_value


def confidence_interval_95(
    *,
    x: int,
    n: int,
) -> tuple[float, float]:
    """
    单比例 95% 置信区间（正态近似）。

    参数:
        x: 转化数
        n: 总数

    返回:
        (lower, upper)
    """
    if n == 0:
        return 0.0, 0.0

    p = x / n
    z95 = 1.95996398454  # scipy.stats.norm.ppf(0.975)
    margin = z95 * math.sqrt(p * (1 - p) / n)
    lower = max(0.0, p - margin)
    upper = min(1.0, p + margin)
    return lower, upper


def is_significant_at_95(*, p_value: Optional[float]) -> bool:
    """
    判断是否在 95% 置信水平下显著（p < 0.05）。

    None 安全：p_value=None 返回 False。
    """
    if p_value is None:
        return False
    return p_value < 0.05
