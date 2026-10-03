"""Few colours for neighbouring territories (DSatur greedy colouring of the adjacency graph)."""

from __future__ import annotations

import numpy as np


def raster_adjacency(labels: np.ndarray) -> set[tuple[int, int]]:
    """Label pairs (a < b) that touch, including diagonally; -1 is ignored."""
    pairs = []
    for a, b in (
        (labels[:, :-1], labels[:, 1:]),
        (labels[:-1, :], labels[1:, :]),
        (labels[:-1, :-1], labels[1:, 1:]),
        (labels[:-1, 1:], labels[1:, :-1]),
    ):
        m = (a != b) & (a >= 0) & (b >= 0)
        pairs.append(np.column_stack([np.minimum(a[m], b[m]), np.maximum(a[m], b[m])]))
    allp = np.unique(np.concatenate(pairs), axis=0) if pairs else np.empty((0, 2), int)
    return {(int(a), int(b)) for a, b in allp}


def dsatur(nodes, pairs, max_colors: int) -> dict[int, int]:
    adj = {int(v): set() for v in nodes}
    for a, b in pairs:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    color: dict[int, int] = {}
    while len(color) < len(adj):
        v = max(
            (x for x in adj if x not in color),
            key=lambda x: (len({color[y] for y in adj[x] if y in color}), len(adj[x]), -x),
        )
        used = {color[y] for y in adj[v] if y in color}
        c = next(i for i in range(len(adj) + 1) if i not in used)
        if c >= max_colors:
            raise ValueError(f"{max_colors} 色では塗り分けられません (駅 {v})")
        color[v] = c
    return color
