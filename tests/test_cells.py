import numpy as np
from shapely.geometry import LineString, Point

from ekiwalk.shortest import solve
from ekiwalk.surface import densify_edges, grid_from_points
from eki_walk.territory.cells import cell_neighbors, densify, per_station_cells
from eki_walk.territory.reach import access_graph, station_reach


def lattice(n=6, step=50.0):
    xs, ys = np.meshgrid(np.arange(n) * step, np.arange(n) * step)
    xy = np.column_stack([xs.ravel(), ys.ravel()])
    idx = np.arange(n * n).reshape(n, n)
    u = np.concatenate([idx[:, :-1].ravel(), idx[:-1, :].ravel()])
    v = np.concatenate([idx[:, 1:].ravel(), idx[1:, :].ravel()])
    return xy, u, v, np.full(len(u), step)


STATIONS = [LineString([(0, -20), (60, -20)]), Point(180, 230), LineString([(260, 100), (260, 160)])]


def test_densify_matches_ekiwalk():
    xy, u, v, length = lattice()
    pts_e, _, _ = densify_edges(xy, u, v, length, np.zeros(len(xy)), np.zeros(len(xy), int), step=20)
    p = densify(xy, u, v, length, 20)
    assert np.allclose(p.xy, pts_e)
    assert p.edge_count.sum() == len(pts_e) - len(xy)


def test_min_over_stations_equals_ekiwalk_grid():
    xy, u, v, length = lattice()
    dist, nearest = solve(xy, u, v, length, STATIONS, 100)
    pts, d, st = densify_edges(xy, u, v, length, dist, nearest, step=20)
    x0, y0, cell, nx, ny = -50.0, -50.0, 25.0, 16, 16
    grid = grid_from_points(pts, d, st, x0, y0, nx, ny, cell, max_offroad=300)

    p = densify(xy, u, v, length, 20)
    cells = np.flatnonzero(np.isfinite(grid.dist.ravel()))
    centers = np.column_stack([x0 + (cells % nx + 0.5) * cell, y0 + (cells // nx + 0.5) * cell])
    nb = cell_neighbors(p.xy, centers, 300)
    reach = station_reach(access_graph(xy, u, v, length, STATIONS, 100), len(xy), len(STATIONS), 10_000)
    ps = per_station_cells(p, nb, reach, u, v, 10_000)
    best = ps.groupby("cell")["dist"].min().reindex(range(len(cells))).to_numpy()
    assert np.allclose(best, grid.dist.ravel()[cells], atol=1e-3)


def test_limit_drops_far_cells():
    xy, u, v, length = lattice()
    p = densify(xy, u, v, length, 20)
    centers = np.array([[0.0, 0.0], [250.0, 250.0]])
    nb = cell_neighbors(p.xy, centers, 300)
    reach = station_reach(access_graph(xy, u, v, length, STATIONS[:1], 100), len(xy), 1, 10_000)
    ps = per_station_cells(p, nb, reach, u, v, 100)
    assert ps["cell"].tolist() == [0]
