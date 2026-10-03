"""Walking time convention: 80 m per minute, fractions rounded up (minimum 1 minute).

This follows the Japanese real-estate advertising rule (不動産の表示に関する公正競争規約施行規則).
"""

import math

M_PER_MIN = 80.0
_EPS = 1e-9


def walk_minutes(distance_m: float, m_per_min: float = M_PER_MIN) -> int:
    return max(1, math.ceil(distance_m / m_per_min - _EPS))


def ceil_m(distance_m: float) -> int:
    """Distance stored in the app data: whole metres, rounded up."""
    return math.ceil(distance_m - _EPS)
