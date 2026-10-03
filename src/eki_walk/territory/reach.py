"""Per-station walking distance with a cut-off, on exactly the graph ekiwalk.shortest.solve builds.

The virtual-node construction follows ekiwalk.shortest.solve at rail-gap-map@4176263, so the minimum over
stations equals ekiwalk's nearest-station distance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import shapely
from ekiwalk.shortest import EPS
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree


def access_graph(xy: np.ndarray, u, v, length, stations: list, access_radius_m: float) -> csr_matrix:
    """Road edges plus one virtual node per station linked to nodes within access_radius_m of its geometry."""
    n, k = len(xy), len(stations)
    tree = cKDTree(xy)
    su, sv, sw = [], [], []
    for i, geom in enumerate(stations):
        minx, miny, maxx, maxy = geom.bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        reach = np.hypot(maxx - minx, maxy - miny) / 2 + access_radius_m
        cand = np.asarray(tree.query_ball_point([cx, cy], reach), dtype=np.int64)
        d = np.empty(0)
        if len(cand):
            d = shapely.distance(shapely.points(xy[cand]), geom)
            cand, d = cand[d <= access_radius_m], d[d <= access_radius_m]
        if len(cand) == 0:
            pt = geom.interpolate(0.5, normalized=True) if geom.geom_type == "LineString" else geom
            _, j = tree.query([pt.x, pt.y])
            cand, d = np.array([j]), np.array([shapely.distance(shapely.points(xy[j]), geom)])
        su.append(np.full(len(cand), n + i))
        sv.append(cand)
        sw.append(d + EPS)
    uu = np.concatenate([np.asarray(u)] + su)
    vv = np.concatenate([np.asarray(v)] + sv)
    ww = np.concatenate([np.asarray(length, float)] + sw)
    return coo_matrix((ww, (uu, vv)), shape=(n + k, n + k)).tocsr()


def station_reach(graph: csr_matrix, n: int, k: int, limit_m: float, batch: int = 4) -> pd.DataFrame:
    """Rows (station, node, dist) for every node within limit_m of each station (undirected, like ekiwalk)."""
    out = []
    for start in range(0, k, batch):
        ind = np.arange(n + start, n + min(k, start + batch))
        d = dijkstra(graph, directed=False, indices=ind, limit=limit_m + EPS)[:, :n] - EPS
        si, ni = np.nonzero(d <= limit_m)
        out.append(
            pd.DataFrame({"station": (start + si).astype(np.int32), "node": ni.astype(np.int64), "dist": d[si, ni]})
        )
    return pd.concat(out, ignore_index=True)
