import numpy as np
import pandas as pd

from eki_walk.territory.layers import band_mask, group_stats, group_table, second_nearest, to_raster


def test_group_table_takes_nearest_row_per_group():
    ps = pd.DataFrame({"cell": [0, 0, 0, 1], "station": [0, 1, 2, 2], "dist": [300.0, 100.0, 500.0, 50.0]})
    gt = group_table(ps, np.array([7, 7, 9]))
    assert gt.values.tolist() == [[0, 7, 100.0], [0, 9, 500.0], [1, 9, 50.0]]


def test_second_nearest_and_band():
    gt = pd.DataFrame({"cell": [0, 0, 1, 2, 2], "group": [7, 9, 9, 7, 9], "dist": [100.0, 300.0, 50.0, 400.0, 1300.0]})
    near_g = np.array([7, 9, 7])
    near_d = np.array([100.0, 50.0, 400.0])
    second = second_nearest(gt, near_g, 3)
    assert second.tolist() == [300.0, np.inf, 1300.0]
    assert band_mask(near_d, second, 1200, 240).tolist() == [True, False, False]


def test_group_stats():
    s = group_stats(np.array([0, 0, 1]), np.array([100.0, 1300.0, 50.0]), 25.0, 1200, 3)
    assert s.loc[0, "area_km2"] == 2 * 625 / 1e6
    assert s.loc[0, "far_m"] == 1300.0
    assert s.loc[0, "within"] == 0.5
    assert np.isnan(s.loc[2, "far_m"])


def test_to_raster():
    r = to_raster(np.array([5, 6]), np.array([1, 4]), (2, 3), -1)
    assert r.tolist() == [[-1, 5, -1], [-1, 6, -1]]
