"""Per-cell layers: other groups within the limit, the boundary band, far cells and station stats."""

from __future__ import annotations

import numpy as np
import pandas as pd


def group_table(per_station: pd.DataFrame, row_group: np.ndarray) -> pd.DataFrame:
    """(cell, station, dist) -> (cell, group, dist) with the nearest station row of each merged group."""
    t = per_station.assign(group=row_group[per_station["station"].to_numpy()])
    return t.groupby(["cell", "group"], as_index=False)["dist"].min()


def second_nearest(gt: pd.DataFrame, nearest_group: np.ndarray, n_cells: int) -> np.ndarray:
    """Distance to the nearest group other than the cell's own (inf when none is in the table)."""
    other = gt[gt["group"].to_numpy() != nearest_group[gt["cell"].to_numpy()]]
    out = np.full(n_cells, np.inf)
    m = other.groupby("cell")["dist"].min()
    out[m.index.to_numpy()] = m.to_numpy()
    return out


def band_mask(nearest_d: np.ndarray, second_d: np.ndarray, limit_m: float, band_m: float) -> np.ndarray:
    return (second_d <= limit_m) & (second_d - nearest_d <= band_m)


def far_mask(nearest_d: np.ndarray, limit_m: float) -> np.ndarray:
    return nearest_d > limit_m


def group_stats(nearest_group, nearest_d, cell_m: float, limit_m: float, n_groups: int) -> pd.DataFrame:
    df = pd.DataFrame({"g": nearest_group, "d": nearest_d})
    s = df.groupby("g").agg(cells=("d", "size"), far_m=("d", "max"), within=("d", lambda x: float((x <= limit_m).mean())))
    s = s.reindex(range(n_groups))
    s["area_km2"] = s["cells"].fillna(0) * cell_m * cell_m / 1e6
    return s


def to_raster(values: np.ndarray, cells: np.ndarray, shape: tuple[int, int], fill) -> np.ndarray:
    out = np.full(shape, fill, dtype=np.asarray(values).dtype if len(values) else int)
    out.reshape(-1)[cells] = values
    return out
