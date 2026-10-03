import numpy as np
import shapely

from eki_walk.territory.polygons import boundary_segments, cells_polygon, chaikin, smooth_labels


def test_boundary_segments_two_labels():
    lab = np.array([[0, 1], [0, 1]])
    segs = boundary_segments(lab)
    # outer ring (8 unit edges) + the middle line (2 unit edges)
    assert len(segs) == 10


def test_chaikin_keeps_ends_and_rings():
    open_ = chaikin(np.array([[0, 0], [10, 0], [10, 10]], float), closed=False, iterations=2)
    assert tuple(open_[0]) == (0, 0) and tuple(open_[-1]) == (10, 10)
    ring = chaikin(np.array([[0, 0], [10, 0], [10, 10], [0, 0]], float), closed=True, iterations=2)
    assert tuple(ring[0]) == tuple(ring[-1])


def test_smooth_labels_partition_without_gaps_or_overlaps():
    lab = np.full((20, 20), 0)
    lab[:, 10:] = 1
    lab[12:, :8] = 2
    lab[:3, 17:] = -1
    polys = smooth_labels(lab, 1000.0, 2000.0, 25.0, simplify_m=20, iterations=3)
    assert set(polys) == {0, 1, 2}
    total = sum(p.area for p in polys.values())
    assert abs(total - (400 - 9) * 625) / ((400 - 9) * 625) < 0.06  # outer corners get rounded
    for a in polys:
        for b in polys:
            if a < b:
                assert polys[a].intersection(polys[b]).area < 1.0
    assert abs(polys[2].area - 64 * 625) / (64 * 625) < 0.15
    assert polys[0].bounds[0] >= 1000.0 - 1e-6


def test_cells_polygon_window():
    rows = np.array([5, 5, 6, 6])
    cols = np.array([7, 8, 7, 8])
    p = cells_polygon(rows, cols, 0.0, 0.0, 25.0, simplify_m=5, iterations=1)
    assert p.area > 0.8 * 4 * 625
    c = p.centroid
    assert abs(c.x - 200) < 5 and abs(c.y - 150) < 5


def test_merge_tiny_faces_joins_the_longest_shared_neighbour():
    from shapely.geometry import box

    from eki_walk.territory.polygons import merge_tiny_faces

    faces = np.array([box(0, 0, 100, 100), box(100, 0, 200, 100), box(95, 40, 100, 60)], dtype=object)
    # the tiny face shares its long left edge with nothing and its right edge (20 m) with face 1
    faces[0] = faces[0].difference(faces[2])
    owner = np.array([0, 1, 2])
    out = merge_tiny_faces(faces, owner, min_area_m2=500)
    assert out.tolist()[:2] == [0, 1]
    assert out[2] == 0  # shares three sides (30 m) with face 0 vs 20 m with face 1
