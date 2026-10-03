import numpy as np
from shapely.geometry import LineString, Point

from ekiwalk.shortest import solve
from eki_walk.territory.reach import access_graph, station_reach


def lattice(n=6, step=50.0):
    xs, ys = np.meshgrid(np.arange(n) * step, np.arange(n) * step)
    xy = np.column_stack([xs.ravel(), ys.ravel()])
    idx = np.arange(n * n).reshape(n, n)
    u = np.concatenate([idx[:, :-1].ravel(), idx[:-1, :].ravel()])
    v = np.concatenate([idx[:, 1:].ravel(), idx[1:, :].ravel()])
    return xy, u, v, np.full(len(u), step)


STATIONS = [LineString([(0, -20), (60, -20)]), Point(180, 230), LineString([(260, 100), (260, 160)])]


def test_min_over_stations_equals_ekiwalk_solve():
    xy, u, v, length = lattice()
    dist, nearest = solve(xy, u, v, length, STATIONS, 100)
    g = access_graph(xy, u, v, length, STATIONS, 100)
    r = station_reach(g, len(xy), len(STATIONS), limit_m=10_000)
    best = r.sort_values("dist").groupby("node").first()
    assert np.allclose(best["dist"].reindex(range(len(xy))).to_numpy(), dist, atol=1e-4)
    assert (best["station"].reindex(range(len(xy))).to_numpy() == nearest).mean() > 0.95  # ties may differ


def test_cutoff():
    xy, u, v, length = lattice()
    g = access_graph(xy, u, v, length, STATIONS, 100)
    r = station_reach(g, len(xy), len(STATIONS), limit_m=60)
    assert r["dist"].max() <= 60
    assert set(r["station"]) == {0, 1, 2}
