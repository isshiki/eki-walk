"""Per-station distances for grid cells, computed with the same rule as ekiwalk.surface (rail-gap-map@4176263):
a cell takes the minimum over its k nearest road points (within max_offroad) of point distance + straight offset.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

DENSIFY_STEP_M = 20.0  # ekiwalk.surface.run densifies edges every 20 m


@dataclass
class Points:
    xy: np.ndarray  # (P, 2): nodes first, then interior points (same order as ekiwalk.surface.densify_edges)
    a: np.ndarray  # interior point: edge start node (-1 for nodes)
    b: np.ndarray  # interior point: edge end node
    s: np.ndarray  # distance from a along the edge
    L: np.ndarray  # edge length
    edge_first: np.ndarray  # first interior point index of each edge
    edge_count: np.ndarray  # interior points per edge
    n_nodes: int


def densify(xy, u, v, length, step: float = DENSIFY_STEP_M) -> Points:
    u, v, length = np.asarray(u), np.asarray(v), np.asarray(length, float)
    n = np.maximum(np.ceil(length / step).astype(np.int64) - 1, 0)
    e = np.repeat(np.arange(len(u)), n)
    j = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n) + 1
    L = length[e]
    s = j * L / (n[e] + 1)
    t = (s / L)[:, None]
    a, b = u[e], v[e]
    p = xy[a] * (1 - t) + xy[b] * t
    N = len(xy)
    return Points(
        xy=np.vstack([xy, p]),
        a=np.concatenate([np.full(N, -1), a]),
        b=np.concatenate([np.full(N, -1), b]),
        s=np.concatenate([np.zeros(N), s]),
        L=np.concatenate([np.zeros(N), L]),
        edge_first=N + np.cumsum(n) - n,
        edge_count=n,
        n_nodes=N,
    )


@dataclass
class Neighbors:
    idx: np.ndarray  # (C, k) point index, -1 where none
    off: np.ndarray  # (C, k) straight-line offset, inf where none


def cell_neighbors(pts_xy: np.ndarray, centers: np.ndarray, max_offroad: float, k: int = 8, chunk: int = 400_000) -> Neighbors:
    tree = cKDTree(pts_xy)
    kk = min(k, len(pts_xy))
    idx = np.full((len(centers), kk), -1, dtype=np.int32)
    off = np.full((len(centers), kk), np.inf, dtype=np.float32)
    for c0 in range(0, len(centers), chunk):
        dd, ii = tree.query(centers[c0 : c0 + chunk], k=kk, distance_upper_bound=max_offroad, workers=-1)
        if kk == 1:
            dd, ii = dd[:, None], ii[:, None]
        valid = np.isfinite(dd)
        idx[c0 : c0 + chunk] = np.where(valid, ii, -1)
        off[c0 : c0 + chunk] = np.where(valid, dd, np.inf)
    return Neighbors(idx, off)


def _gather(ptr: np.ndarray, values: np.ndarray, keys: np.ndarray) -> np.ndarray:
    """Concatenate values[ptr[k]:ptr[k+1]] for every k in keys (CSR gather)."""
    lens = ptr[keys + 1] - ptr[keys]
    pos = np.repeat(ptr[keys] - (np.cumsum(lens) - lens), lens) + np.arange(lens.sum())
    return values[pos]


def per_station_cells(pts: Points, nb: Neighbors, reach: pd.DataFrame, u, v, limit_m: float) -> pd.DataFrame:
    """Rows (cell, station, dist) for cells within limit_m of each station."""
    u, v = np.asarray(u), np.asarray(v)
    n, P, (C, k) = pts.n_nodes, len(pts.xy), nb.idx.shape
    ends = np.concatenate([u, v])
    order = np.argsort(ends, kind="stable")
    node_ptr = np.searchsorted(ends[order], np.arange(n + 1))
    node_edges = np.concatenate([np.arange(len(u)), np.arange(len(u))])[order]
    flat = nb.idx.ravel()
    valid = flat >= 0
    pt = flat[valid].astype(np.int64)
    cell_of = np.repeat(np.arange(C), k)[valid]
    o2 = np.argsort(pt, kind="stable")
    pt_ptr = np.searchsorted(pt[o2], np.arange(P + 1))
    pt_cells = cell_of[o2]
    idx_safe = np.where(nb.idx >= 0, nb.idx, 0)
    D = np.full(P, np.inf)
    rs = reach.sort_values("station", kind="stable")
    st, nodes_all, d_all = rs["station"].to_numpy(), rs["node"].to_numpy(), rs["dist"].to_numpy(float)
    cut = np.flatnonzero(np.diff(st)) + 1
    out_c, out_s, out_d = [], [], []
    for a0, a1 in zip(np.r_[0, cut], np.r_[cut, len(st)]):
        nodes = nodes_all[a0:a1]
        D[nodes] = d_all[a0:a1]
        eds = np.unique(_gather(node_ptr, node_edges, nodes))
        cnt = pts.edge_count[eds]
        ip = np.repeat(pts.edge_first[eds] - (np.cumsum(cnt) - cnt), cnt) + np.arange(cnt.sum())
        D[ip] = np.minimum(D[pts.a[ip]] + pts.s[ip], D[pts.b[ip]] + (pts.L[ip] - pts.s[ip]))
        aff = np.concatenate([nodes, ip])
        cs = np.unique(_gather(pt_ptr, pt_cells, aff))
        vals = np.min(np.where(nb.idx[cs] >= 0, D[idx_safe[cs]], np.inf) + nb.off[cs], axis=1)
        keep = vals <= limit_m
        out_c.append(cs[keep])
        out_s.append(np.full(int(keep.sum()), st[a0], dtype=np.int32))
        out_d.append(vals[keep].astype(np.float32))
        D[aff] = np.inf
    if not out_c:
        return pd.DataFrame({"cell": [], "station": [], "dist": []})
    return pd.DataFrame({"cell": np.concatenate(out_c), "station": np.concatenate(out_s), "dist": np.concatenate(out_d)})
