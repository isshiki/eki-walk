import numpy as np
from shapely.geometry import Polygon

from eki_walk.territory.clean import absorb_small_islands, drop_small, fill_blank


def test_fill_blank_uses_nearest_label_inside_the_area_only():
    lab = np.array([[0, 0, -1], [0, -1, 1], [-1, 1, 1]])
    area = np.ones_like(lab, dtype=bool)
    area[2, 0] = False  # e.g. sea: stays blank
    out, filled = fill_blank(lab, area)
    assert out[2, 0] == -1
    assert out[0, 2] in (0, 1) and out[1, 1] in (0, 1)
    assert (out[area] >= 0).all()
    assert filled.tolist() == [[False, False, True], [False, True, False], [False, False, False]]


def test_absorb_small_islands_keeps_large_pieces():
    lab = np.zeros((12, 12), dtype=int)
    lab[:, 8:] = 1  # a large piece of 1
    lab[5, 3] = 1  # a one-cell island of 1 inside 0
    lab[0, 0] = -1  # blank stays blank
    out, small = absorb_small_islands(lab, min_cells=4)
    assert out[5, 3] == 0
    assert small.sum() == 1
    assert (out[:, 8:] == 1).all()
    assert out[0, 0] == -1


def test_absorb_keeps_the_largest_piece_even_if_small():
    lab = np.zeros((6, 6), dtype=int)
    lab[2, 2] = 1  # the only piece of label 1
    out, _ = absorb_small_islands(lab, min_cells=4)
    assert out[2, 2] == 1


def test_drop_small_removes_tiny_parts_and_holes():
    big = Polygon([(0, 0), (1000, 0), (1000, 1000), (0, 1000)], [[(100, 100), (110, 100), (110, 110), (100, 110)]])
    tiny = Polygon([(2000, 0), (2005, 0), (2005, 5), (2000, 5)])
    out = drop_small(big.union(tiny), 1000.0)
    assert out.geom_type == "Polygon"
    assert len(out.interiors) == 0
    assert abs(out.area - 1_000_000) < 1e-6


def test_pad_nearest_extends_values_outside_the_area():
    from eki_walk.territory.clean import pad_nearest

    vals = np.array([[1, 2], [3, 4]])
    area = np.array([[True, True], [True, False]])  # (1, 1) is outside the area
    out = pad_nearest(vals, area, pad=1, fill=-1)
    assert out.shape == (4, 4)
    assert out[1:3, 1:3].tolist() == [[1, 2], [3, 2]] or out[1:3, 1:3].tolist() == [[1, 2], [3, 3]]
    assert out[0, 1] == 1  # one cell above the area copies the nearest cell inside
    assert out[0, 0] == -1  # the diagonal corner is farther than one cell
    assert out[2, 2] in (2, 3)  # the cell outside the area copies a neighbour inside
