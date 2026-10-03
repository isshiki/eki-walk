import numpy as np
import shapely
from shapely.geometry import Polygon

from eki_walk.territory.simplify import simplify_shared


def zigzag(x0, x1, y, n, amp):
    """Points from (x0, y) to (x1, y) with a small zigzag of amplitude amp."""
    xs = np.linspace(x0, x1, n)
    ys = y + amp * (np.arange(n) % 2)
    return list(zip(xs, ys))


def test_simplify_shared_keeps_neighbours_touching():
    border = zigzag(0, 1000, 500, 101, 1.0)  # the shared edge, with 1 m wiggles
    south = Polygon([(0, 0), (1000, 0), *border[::-1]])
    north = Polygon([*border, (1000, 1000), (0, 1000)])
    out = simplify_shared([south, north], 5.0)
    assert shapely.get_num_coordinates(out[0]) < 10 and shapely.get_num_coordinates(out[1]) < 10
    assert abs(out[0].intersection(out[1]).area) < 1e-6  # no overlap
    assert abs(shapely.union_all(out).area - 1_000_000) < 1e-3  # no gap
    assert abs(out[0].area - south.area) < 1000  # no point moved more than the tolerance


def test_simplify_shared_drops_faces_outside_every_input_unless_thin():
    a = Polygon([(0, 0), (100, 0), (100, 100), (0, 100)])
    b = Polygon([(100.5, 0), (200, 0), (200, 100), (100.5, 100)])  # a 0.5 m gap between a and b
    top = Polygon([(0, 100), (200, 100), (200, 150), (0, 150)])  # closes the gap above and below
    bottom = Polygon([(0, -50), (200, -50), (200, 0), (0, 0)])
    kept = simplify_shared([a, b, top, bottom], 1.0)
    filled = simplify_shared([a, b, top, bottom], 1.0, fill_gaps_m=2.0)
    assert abs(sum(g.area for g in kept) - 200 * 200 + 50) < 1e-6  # the 0.5 x 100 m gap stays empty
    assert abs(shapely.union_all(filled).area - 200 * 200) < 1e-6  # the gap went to a neighbour


def test_simplify_shared_handles_empty_input():
    assert simplify_shared([], 5.0) == []
