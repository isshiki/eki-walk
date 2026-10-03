"""Make regions consistent after they are built one by one.

- Colours: all territories of all regions form one adjacency graph over station keys (the N02 group codes of a
  station), so a station keeps its colour across a prefecture border and neighbours across it differ.
- overview.json: all regions in one light file for the wide view (simplified territories joined across
  prefecture borders, pale areas, hatch, and every station once), so the first screen loads no region.
- regions.json: the list of regions the web app loads on demand.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import shapely
import shapely.geometry
from pyproj import Transformer
from shapely.geometry import shape

from eki_walk.territory.clean import drop_small
from eki_walk.territory.colors import dsatur
from eki_walk.territory.export import write_json
from eki_walk.territory.simplify import simplify_shared

BORDER_M = 30.0  # territories of two regions closer than this touch across the border
SHARED_M = 2.0  # boundaries closer than this are the same line (coordinates are rounded to about 1 m)
MIN_LINE_M = 1.0
OVERVIEW_M = 20.0  # overview: simplification (shown below zoom 12, where a pixel is 30 m or more)
OVERVIEW_MIN_M2 = 10_000.0  # overview: parts and holes smaller than 1 ha are left out


def _line_parts(geom) -> list:
    """LineStrings (merged, longer than MIN_LINE_M) in any geometry."""
    lines = [g for g in shapely.get_parts(geom) if g.geom_type in ("LineString", "MultiLineString")]
    if not lines:
        return []
    merged = shapely.line_merge(shapely.union_all(lines))
    return [g for g in shapely.get_parts(merged) if g.length > MIN_LINE_M]


def border_lines(geoms: dict[str, list]) -> dict[str, list]:
    """Lines to draw for each region: borders between different stations (a, b) and the outer edge (a, "").

    Two parts of the same station that meet at a prefecture border get no line, so a territory that spans
    two regions looks like one.
    """
    flat = [(r, i, k, g) for r, items in geoms.items() for i, (k, g) in enumerate(items)]
    tree = shapely.STRtree([g for *_, g in flat])
    out = {r: [] for r in geoms}
    for n, (r, i, k, g) in enumerate(flat):
        near = [m for m in tree.query(g, predicate="dwithin", distance=SHARED_M) if m != n]
        edge = g.boundary
        for m in near:
            r2, i2, k2, g2 = flat[m]
            if k2 == k or (r2, i2) < (r, i):  # same station: no line; other pairs once
                continue
            for part in _line_parts(shapely.intersection(edge, g2.buffer(SHARED_M))):
                out[r].append((k, k2, part))
        covered = shapely.union_all([flat[m][3].buffer(SHARED_M) for m in near]) if near else shapely.Polygon()
        for part in _line_parts(shapely.difference(edge, covered)):
            out[r].append((k, "", part))
    return out



def overview_layers(pieces: list, far: list, band: list) -> tuple[dict, object, object]:
    """({key: polygon}, far, band) for the wide view, metric.

    The pieces of all regions are simplified together, so territories still share their boundaries, and the
    pieces of one station on both sides of a prefecture border join into one polygon."""
    simple = simplify_shared([g for _, g in pieces], OVERVIEW_M, fill_gaps_m=OVERVIEW_M)
    by_key: dict[str, list] = {}
    for (k, _), g in zip(pieces, simple):
        if not g.is_empty:
            by_key.setdefault(k, []).append(g)
    terr = {k: drop_small(shapely.union_all(gs), OVERVIEW_MIN_M2) for k, gs in by_key.items()}

    def merged(geoms):
        return drop_small(shapely.union_all(simplify_shared(geoms, OVERVIEW_M, fill_gaps_m=OVERVIEW_M)), OVERVIEW_MIN_M2)

    return {k: g for k, g in terr.items() if not g.is_empty}, merged(far), merged(band)


def _load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def combine(
    web_data: Path, regions: list[str], max_colors: int, metric_crs: str = "EPSG:6677", manifest_name: str = "regions.json"
) -> dict:
    web_data = Path(web_data)
    data = {}
    for r in regions:
        d = web_data / r
        data[r] = {
            "meta": _load(d / "meta.json"),
            "stations": _load(d / "stations.json"),
            "terr": _load(d / "territories.geojson"),
            "adj": _load(d / "adjacency.json"),
            "far": _load(d / "far.geojson"),
            "band": _load(d / "band.geojson"),
        }

    keys, edges = set(), set()
    for x in data.values():
        key = {s["id"]: s["key"] for s in x["stations"]}
        keys.update(f["properties"]["k"] for f in x["terr"]["features"])
        for a, b in x["adj"]:
            if key[a] != key[b]:
                edges.add(tuple(sorted((key[a], key[b]))))

    tr = Transformer.from_crs("EPSG:4326", metric_crs, always_xy=True)

    def to_m(g):
        return shapely.transform(g, lambda xy: np.column_stack(tr.transform(xy[:, 0], xy[:, 1])))

    geoms = {r: [(f["properties"]["k"], to_m(shape(f["geometry"]))) for f in x["terr"]["features"]] for r, x in data.items()}
    for i, r1 in enumerate(regions):
        for r2 in regions[i + 1 :]:
            if not geoms[r2]:
                continue
            tree = shapely.STRtree([g for _, g in geoms[r2]])
            for k1, g1 in geoms[r1]:
                for j in tree.query(g1, predicate="dwithin", distance=BORDER_M):
                    k2 = geoms[r2][j][0]
                    if k1 != k2:
                        edges.add(tuple(sorted((k1, k2))))

    inv = Transformer.from_crs(metric_crs, "EPSG:4326", always_xy=True)

    def to_ll(g):
        g = shapely.transform(g, lambda xy: np.column_stack(inv.transform(xy[:, 0], xy[:, 1])))
        return shapely.set_precision(g, 1e-5)

    for r, items in border_lines(geoms).items():
        feats = [
            {"type": "Feature", "properties": {"a": a, "b": b}, "geometry": shapely.geometry.mapping(to_ll(line))}
            for a, b, line in items
        ]
        write_json(web_data / r / "lines.geojson", {"type": "FeatureCollection", "features": feats})

    order = sorted(keys)
    idx = {k: i for i, k in enumerate(order)}
    col = dsatur(range(len(order)), {(idx[a], idx[b]) for a, b in edges if a in idx and b in idx}, max_colors)
    colors = {k: col[idx[k]] for k in order}

    for r, x in data.items():
        for f in x["terr"]["features"]:
            f["properties"]["c"] = colors[f["properties"]["k"]]
        for s in x["stations"]:
            s["c"] = colors.get(s["key"])
        write_json(web_data / r / "territories.geojson", x["terr"])
        write_json(web_data / r / "stations.json", x["stations"])

    def polys(r, layer):
        return [to_m(shape(f["geometry"])) for f in data[r][layer]["features"]]

    terr_ov, far_ov, band_ov = overview_layers(
        [p for r in regions for p in geoms[r]], [g for r in regions for g in polys(r, "far")], [g for r in regions for g in polys(r, "band")]
    )
    stations: dict[str, list] = {}  # key -> [key, name, lon, lat, regions that list it]
    for r in regions:
        for s in data[r]["stations"]:
            stations.setdefault(s["key"], [s["key"], s["name"], s["lon"], s["lat"], []])[4].append(r)

    def fc(items):
        return {"type": "FeatureCollection", "features": [
            {"type": "Feature", "properties": props, "geometry": shapely.geometry.mapping(to_ll(g))} for props, g in items if not g.is_empty
        ]}

    write_json(web_data / "overview.json", {
        "t": fc([({"k": k, "c": colors[k]}, g) for k, g in sorted(terr_ov.items())]),
        "far": fc([({}, far_ov)]),
        "band": fc([({}, band_ov)]),
        "st": list(stations.values()),
    })

    manifest = {
        "regions": [
            {"name": r, "label": data[r]["meta"]["label"], "bbox": data[r]["meta"]["bbox"], "path": f"data/{r}/"}
            for r in regions
        ],
        "home": data[regions[0]]["meta"]["home_view"],
        "overview": "data/overview.json",
    }
    write_json(web_data / manifest_name, manifest)
    return {"colors": colors, "edges": len(edges), "regions": manifest["regions"]}
