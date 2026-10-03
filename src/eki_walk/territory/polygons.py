"""Grid labels -> smooth polygons that share their boundaries exactly (no gaps, no overlaps).

1. Collect the unit cell edges between different labels (outside and blank cells count as -1).
2. Merge them into arcs between junctions; simplify each arc (Douglas-Peucker) and round its corners (Chaikin).
3. Node the smoothed arcs again, polygonize, and give each face to the label under its interior point.
Because every face comes from the same linework, neighbouring polygons share their boundaries exactly.
"""

from __future__ import annotations

import numpy as np
import shapely
from shapely.geometry import LineString

FINAL_SIMPLIFY_M = 3.0  # drop the near-collinear points Chaikin adds


def boundary_segments(labels: np.ndarray) -> np.ndarray:
    """(m, 2, 2) unit segments in cell-corner coordinates (x = column, y = row) where labels change."""
    lab = np.pad(labels, 1, constant_values=-1)
    r, c = np.nonzero(lab[:, :-1] != lab[:, 1:])  # vertical edges
    v = np.stack([np.column_stack([c, r - 1]), np.column_stack([c, r])], axis=1)
    r2, c2 = np.nonzero(lab[:-1, :] != lab[1:, :])  # horizontal edges
    h = np.stack([np.column_stack([c2 - 1, r2]), np.column_stack([c2, r2])], axis=1)
    return np.concatenate([v, h]).astype(float)


def chaikin(coords: np.ndarray, closed: bool, iterations: int) -> np.ndarray:
    pts = np.asarray(coords, float)
    for _ in range(iterations):
        if closed:
            p = pts[:-1]
            q = np.roll(p, -1, axis=0)
            new = np.empty((2 * len(p), 2))
            new[0::2] = 0.75 * p + 0.25 * q
            new[1::2] = 0.25 * p + 0.75 * q
            pts = np.vstack([new, new[:1]])
        else:
            p, q = pts[:-1], pts[1:]
            mid = np.empty((2 * len(p), 2))
            mid[0::2] = 0.75 * p + 0.25 * q
            mid[1::2] = 0.25 * p + 0.75 * q
            pts = np.vstack([pts[:1], mid[1:-1], pts[-1:]])
    return pts


def _smooth_arc(arc, simplify_m: float, iterations: int):
    a = shapely.simplify(arc, simplify_m)
    coords = np.asarray(a.coords)
    if len(coords) < 3 or (a.is_ring and len(coords) < 4):
        return a
    return shapely.simplify(LineString(chaikin(coords, a.is_ring, iterations)), FINAL_SIMPLIFY_M)


def merge_tiny_faces(faces: np.ndarray, owner: np.ndarray, min_area_m2: float) -> np.ndarray:
    """Faces smaller than min_area_m2 (knots where smoothed arcs cross) take the owner of the neighbour
    they share the longest boundary with."""
    area = shapely.area(faces)
    tiny = np.flatnonzero(area < min_area_m2)
    if len(tiny) == 0:
        return owner
    out = owner.copy()
    tree = shapely.STRtree(faces)
    for i in tiny[np.argsort(area[tiny])]:
        best, best_len = -1, 0.0
        for j in tree.query(faces[i], predicate="intersects"):
            if j == i or area[j] < min_area_m2:
                continue
            shared = shapely.length(shapely.intersection(faces[i].boundary, faces[j].boundary))
            if shared > best_len:
                best, best_len = j, shared
        if best >= 0:
            out[i] = out[best]
    return out


def smooth_labels(
    labels: np.ndarray, x0: float, y0: float, cell: float, simplify_m: float, iterations: int, min_face_m2: float = 0.0
) -> dict:
    """{label: polygon in metres} for every label >= 0. Row r spans y0 + r*cell .. y0 + (r+1)*cell."""
    segs = boundary_segments(labels)
    if len(segs) == 0:
        return {}
    lines = shapely.linestrings(segs * cell + np.array([x0, y0]))
    arcs = shapely.get_parts(shapely.line_merge(shapely.union_all(lines)))
    smooth = [_smooth_arc(a, simplify_m, iterations) for a in arcs]
    faces = shapely.get_parts(shapely.polygonize(shapely.get_parts(shapely.union_all(smooth))))
    if len(faces) == 0:
        return {}
    rp = shapely.point_on_surface(faces)
    col = np.floor((shapely.get_x(rp) - x0) / cell).astype(int)
    row = np.floor((shapely.get_y(rp) - y0) / cell).astype(int)
    ny, nx = labels.shape
    ok = (row >= 0) & (row < ny) & (col >= 0) & (col < nx)
    owner = np.full(len(faces), -1)
    owner[ok] = labels[row[ok], col[ok]]
    if min_face_m2 > 0:
        owner = merge_tiny_faces(faces, owner, min_face_m2)
    return {int(k): shapely.union_all(faces[owner == k]) for k in np.unique(owner[owner >= 0])}


def cells_polygon(rows, cols, x0: float, y0: float, cell: float, simplify_m: float, iterations: int):
    """Smooth polygon of a set of cells, computed on a small window around them."""
    rows, cols = np.asarray(rows), np.asarray(cols)
    if len(rows) == 0:
        return shapely.Polygon()
    r0, c0 = rows.min() - 1, cols.min() - 1
    m = np.full((rows.max() - r0 + 2, cols.max() - c0 + 2), -1)
    m[rows - r0, cols - c0] = 1
    return smooth_labels(m, x0 + c0 * cell, y0 + r0 * cell, cell, simplify_m, iterations).get(1, shapely.Polygon())
