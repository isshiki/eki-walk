"""Station groups: the N02 group code first, then same-name groups within merge_m become one station."""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

_NUMBERED = re.compile(r"^\d+号線(?=.)")


def display_line(line: str) -> str:
    """'4号線丸ノ内線' -> '丸ノ内線' (N02 prefixes some subway lines with their number)."""
    return _NUMBERED.sub("", line or "")


def merge_groups(rows: pd.DataFrame, merge_m: float) -> tuple[np.ndarray, pd.DataFrame]:
    """rows: one per station row (group, name, line, operator, x, y in metres), index = station row number.

    Returns (merged group number per row, one row per merged group with name, x, y, lines, members, key).
    key joins the N02 group codes of the merged station, so the same station has the same key in every region.
    """
    base = (
        rows.groupby("group", sort=True)
        .agg(name=("name", lambda s: s.mode().iloc[0]), x=("x", "mean"), y=("y", "mean"))
        .reset_index()
    )
    parent = list(range(len(base)))

    def find(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    bx, by = base["x"].to_numpy(), base["y"].to_numpy()
    for _, part in base.groupby("name"):
        idx = part.index.to_numpy()
        for a in range(len(idx)):
            for b in range(a + 1, len(idx)):
                i, j = idx[a], idx[b]
                if np.hypot(bx[i] - bx[j], by[i] - by[j]) <= merge_m:
                    parent[find(i)] = find(j)
    roots = np.array([find(i) for i in range(len(base))])
    _, merged_of_base = np.unique(roots, return_inverse=True)
    base_index = {code: i for i, code in enumerate(base["group"])}
    row_group = merged_of_base[rows["group"].map(base_index).to_numpy()]

    out = []
    for gi in range(int(merged_of_base.max()) + 1 if len(base) else 0):
        r = rows[row_group == gi]
        lines = sorted({(display_line(l), o) for l, o in zip(r["line"], r["operator"]) if l})
        out.append(
            {
                "name": base.loc[merged_of_base == gi, "name"].iloc[0],
                "x": float(r["x"].mean()),
                "y": float(r["y"].mean()),
                "lines": [{"line": l, "operator": o} for l, o in lines],
                "members": [int(i) for i in r.index],
                "key": "|".join(sorted({str(c) for c in r["group"]})),
            }
        )
    return row_group, pd.DataFrame(out)
