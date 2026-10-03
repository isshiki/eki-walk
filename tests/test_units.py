import pytest

from eki_walk.units import ceil_m, walk_minutes


@pytest.mark.parametrize(
    "d, expected",
    [(0, 1), (1, 1), (80, 1), (80.1, 2), (160, 2), (1199, 15), (1200, 15), (1200.5, 16)],
)
def test_walk_minutes_rounds_up_per_80m(d, expected):
    assert walk_minutes(d) == expected


def test_ceil_m_keeps_minutes_consistent():
    # stored integer metres must give the same minutes as the float distance
    for d in [79.2, 80.0, 80.01, 1199.99]:
        assert walk_minutes(ceil_m(d)) == walk_minutes(d)
