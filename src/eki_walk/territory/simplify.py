"""Simplify polygons that share boundaries (prefectures, territories) so that they still share them exactly.

The boundaries are cut into arcs between junctions, each arc is simplified once (Douglas-Peucker, so no point
moves more than the tolerance), and the faces are rebuilt from the simplified arcs. Two polygons that met
before meet along the same simplified line, with no gap or overlap.
"""

from __future__ import annotations

import numpy as np
import shapely


def simplify_shared(geoms: list, tolerance: float, fill_gaps_m: float = 0.0) -> list:
    """Simplified copies of polygons that touch along shared edges (metric).

    Faces that no input covers (gaps between the inputs) are dropped, except those whose interior point lies
    within fill_gaps_m of an input: these hairline gaps (inputs that meet only to rounding) go to the nearest one.
    """
    if not geoms:
        return []
    edges = shapely.union_all([g.boundary for g in geoms if not g.is_empty])
    arcs = shapely.get_parts(shapely.line_merge(edges))
    simple = shapely.simplify(arcs, tolerance, preserve_topology=True)
    faces = shapely.get_parts(shapely.polygonize(shapely.get_parts(shapely.union_all(simple))))
    if len(faces) == 0:
        return [shapely.Polygon() for _ in geoms]
    rp = shapely.point_on_surface(faces)
    tree = shapely.STRtree(geoms)
    pt, gi = tree.query(rp, predicate="within")
    owner = np.full(len(faces), -1)
    owner[pt[::-1]] = gi[::-1]  # a face inside two inputs (an overlap in the data) goes to the first one
    if fill_gaps_m > 0:
        gap = np.flatnonzero(owner < 0)
        if len(gap):
            gp, gg = tree.query_nearest(rp[gap], max_distance=fill_gaps_m, all_matches=False)
            owner[gap[gp]] = gg
    return [shapely.union_all(faces[owner == i]) if (owner == i).any() else shapely.Polygon() for i in range(len(geoms))]
