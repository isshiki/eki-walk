"""Write the files the web app reads (web/data/<region>/)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
import shapely
from pyproj import Transformer
from shapely.geometry import mapping

from eki_walk.units import ceil_m

PRECISION_DEG = 1e-5  # about 1 m


class LonLat:
    """Metric geometry -> lon/lat geometry rounded to about 1 m."""

    def __init__(self, crs: str):
        self.tr = Transformer.from_crs(crs, "EPSG:4326", always_xy=True)

    def __call__(self, geom):
        g = shapely.transform(geom, lambda xy: np.column_stack(self.tr.transform(xy[:, 0], xy[:, 1])))
        return shapely.set_precision(g, PRECISION_DEG)

    def point(self, x: float, y: float) -> tuple[float, float]:
        lon, lat = self.tr.transform(x, y)
        return round(float(lon), 6), round(float(lat), 6)


def write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def feature(geom, props: dict) -> dict:
    return {"type": "Feature", "properties": props, "geometry": mapping(geom)}


def feature_collection(features: list[dict]) -> dict:
    return {"type": "FeatureCollection", "features": [f for f in features if f["geometry"]["coordinates"]]}


def write_cells(out: Path, cells: np.ndarray, nx: int, chunk: int, near_g, near_d, gt: pd.DataFrame, limit_m: float) -> int:
    """cells/<cx>_<cy>.json: chunk*chunk entries (row-major), each [own, m, other, m, ...] or null."""
    order = gt.sort_values(["cell", "dist"])
    oc, og, od = order["cell"].to_numpy(), order["group"].to_numpy(), order["dist"].to_numpy()
    pos = np.arange(len(cells))
    starts, stops = np.searchsorted(oc, pos), np.searchsorted(oc, pos, side="right")
    rows, cols = cells // nx, cells % nx
    files: dict[tuple[int, int], list] = {}
    for i in range(len(cells)):
        g0 = int(near_g[i])
        val = [g0, ceil_m(float(near_d[i]))]
        for j in range(starts[i], stops[i]):
            if og[j] != g0 and od[j] <= limit_m:
                val += [int(og[j]), ceil_m(float(od[j]))]
        key = (int(cols[i] // chunk), int(rows[i] // chunk))
        arr = files.setdefault(key, [None] * (chunk * chunk))
        arr[int(rows[i] % chunk) * chunk + int(cols[i] % chunk)] = val
    for (cx, cy), arr in files.items():
        write_json(out / "cells" / f"{cx}_{cy}.json", arr)
    return len(files)
