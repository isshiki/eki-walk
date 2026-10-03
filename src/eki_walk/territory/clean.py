"""Tidy the label raster before drawing (the per-cell walking distances are not changed).

- Blank cells inside the map area (water, more than 300 m from a road) take the nearest territory, so territories
  have no holes where the basemap's ponds or rivers would show through.
- Pieces of a territory smaller than min_cells (other than its largest piece) join the territory around them,
  so single cells across a railway do not become small circles after smoothing.
"""

from __future__ import annotations

import numpy as np
import shapely
from scipy import ndimage

EIGHT = np.ones((3, 3), dtype=int)


def _nearest_fill(labels: np.ndarray, targets: np.ndarray) -> np.ndarray:
    """Copy of labels where target cells take the label of the nearest cell with a label >= 0."""
    out = labels.copy()
    if not targets.any() or not (labels >= 0).any():
        return out
    _, (ri, ci) = ndimage.distance_transform_edt(labels < 0, return_indices=True)
    out[targets] = labels[ri[targets], ci[targets]]
    return out


def fill_blank(labels: np.ndarray, area: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Blank cells (-1) inside area take the nearest label. Returns (labels, filled mask)."""
    filled = (labels < 0) & area
    return _nearest_fill(labels, filled), filled


def absorb_small_islands(labels: np.ndarray, min_cells: int) -> tuple[np.ndarray, np.ndarray]:
    """Pieces (8-connected) smaller than min_cells, except each label's largest piece, take the nearest other label."""
    small = np.zeros(labels.shape, dtype=bool)
    for lab, sl in enumerate(ndimage.find_objects(labels + 1)):
        if sl is None:
            continue
        comp, n = ndimage.label(labels[sl] == lab, structure=EIGHT)
        if n <= 1:
            continue
        sizes = np.bincount(comp.ravel())[1:]
        keep = int(sizes.argmax()) + 1
        drop = [i + 1 for i in range(n) if sizes[i] < min_cells and i + 1 != keep]
        if drop:
            small[sl] |= np.isin(comp, drop)
    if not small.any():
        return labels.copy(), small
    out = labels.copy()
    out[small] = -1
    return _nearest_fill(out, small), small


def drop_small(geom, min_area_m2: float):
    """Remove polygon parts and holes smaller than min_area_m2 (metric geometry)."""
    parts = []
    for p in shapely.get_parts(geom):
        if p.geom_type != "Polygon" or p.area < min_area_m2:
            continue
        holes = [h for h in p.interiors if shapely.Polygon(h).area >= min_area_m2]
        parts.append(shapely.Polygon(p.exterior, holes))
    if not parts:
        return shapely.Polygon()
    return parts[0] if len(parts) == 1 else shapely.MultiPolygon(parts)


def pad_nearest(values: np.ndarray, area: np.ndarray, pad: int, fill) -> np.ndarray:
    """Pad by `pad` cells on every side; cells outside `area` within `pad` cells of it copy the nearest cell inside.

    Smoothing a raster padded like this and clipping the result with the exact area boundary gives edges that
    follow the boundary itself, so two regions clipped with their shared prefecture border meet without a gap.
    """
    v = np.pad(values, pad, constant_values=fill)
    ok = np.pad(area, pad, constant_values=False)
    dist, (ri, ci) = ndimage.distance_transform_edt(~ok, return_indices=True)
    out = v.copy()
    target = ~ok & (dist <= pad)
    out[target] = v[ri[target], ci[target]]
    out[~ok & ~target] = fill
    return out
