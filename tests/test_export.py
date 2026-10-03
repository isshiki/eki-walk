import json

import numpy as np
import pandas as pd
from shapely.geometry import box

from eki_walk.territory.export import LonLat, write_cells


def test_lonlat_converts_metres_to_degrees():
    g = LonLat("EPSG:6677")(box(-10000, -40000, -9000, -39000))
    minx, miny, _, _ = g.bounds
    assert 139.6 < minx < 139.8 and 35.5 < miny < 35.7


def test_write_cells_puts_nearest_first(tmp_path):
    cells = np.array([0, 65])  # row 0 col 0, row 1 col 1 (nx = 64)
    near_g, near_d = np.array([3, 4]), np.array([100.2, 1500.0])
    gt = pd.DataFrame({"cell": [0, 0, 0], "group": [3, 5, 6], "dist": [100.2, 700.0, 1300.0]})
    n = write_cells(tmp_path, cells, 64, 64, near_g, near_d, gt, 1200)
    assert n == 1
    arr = json.loads((tmp_path / "cells" / "0_0.json").read_text())
    assert len(arr) == 64 * 64
    assert arr[0] == [3, 101, 5, 700]
    assert arr[65] == [4, 1500]
    assert arr[1] is None
