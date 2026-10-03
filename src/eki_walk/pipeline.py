"""Build steps: ekiwalk (network -> water -> admin -> stations -> solve -> surface -> places), then territory."""

from __future__ import annotations

import json
import shutil
import time
import tomllib
from datetime import datetime, timezone
from importlib import metadata

import numpy as np
import pandas as pd
import pyarrow.parquet as pq
import shapely
from ekiwalk import admin, network, places, shortest, stations, surface, water
from ekiwalk.config import Region, load_region, load_scenario
from ekiwalk.fetch import raw_path
from ekiwalk.surface import Grid, cell_centers_mask
from pyproj import CRS

from eki_walk import paths
from eki_walk.config import TerritoryConfig
from eki_walk.territory.clean import absorb_small_islands, drop_small, fill_blank, pad_nearest
from eki_walk.territory.cells import cell_neighbors, densify, per_station_cells
from eki_walk.territory.colors import dsatur, raster_adjacency
from eki_walk.territory.export import LonLat, feature, feature_collection, write_cells, write_json
from eki_walk.territory.groups import merge_groups
from eki_walk.territory.layers import band_mask, far_mask, group_stats, group_table, second_nearest, to_raster
from eki_walk.territory.polygons import cells_polygon, smooth_labels
from eki_walk.territory.reach import access_graph, station_reach
from eki_walk.territory.simplify import simplify_shared
from eki_walk.territory.readings import match_readings, norm_name, read_osm_station_names, station_place_rows, town_readings

PAD_CELLS = 16  # drawing: territories are smoothed 400 m beyond the region, then clipped at its boundary
STEPS = ["network", "water", "admin", "stations", "solve", "surface", "places", "territory"]
BASE_SOURCES = ["osm-kanto", "n02", "n03-11", "n03-12", "n03-13", "n03-14"]


def pref_code(region: Region) -> str:
    """The prefecture code of a region (its display area), e.g. "13" for Tokyo."""
    return region.display_prefixes[0]


def log(msg: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {msg}", flush=True)


def run_build(cfg: TerritoryConfig, start: str = "network") -> None:
    region = load_region(cfg.region, root=paths.ROOT)
    scenario = load_scenario("base", root=paths.ROOT)
    root = paths.ROOT
    pbf = raw_path(root, region.osm_source)
    steps = {
        "network": lambda: network.run(region, pbf),
        "water": lambda: water.run(region, pbf),
        "admin": lambda: admin.run(region, [raw_path(root, f"n03-{c}") for c in region.n03_prefectures]),
        "stations": lambda: stations.run(region, scenario, raw_path(root, "n02")),
        "solve": lambda: shortest.run(region, scenario),
        "surface": lambda: surface.run(region, scenario),
        "places": lambda: places.run(
            region, raw_path(root, f"abr-town-{pref_code(region)}"), raw_path(root, f"abr-town-pos-{pref_code(region)}")
        ),
        "territory": lambda: build_territory(cfg, region),
    }
    for name in STEPS[STEPS.index(start):]:
        t = time.time()
        log(f"step {name}")
        steps[name]()
        log(f"{name} done in {time.time() - t:.1f}s")


def _midpoints(geoms) -> np.ndarray:
    out = []
    for g in geoms:
        try:
            p = g.interpolate(0.5, normalized=True) if "Line" in g.geom_type else g.centroid
        except Exception:  # noqa: BLE001
            p = g.centroid
        out.append((p.x, p.y))
    return np.array(out)


def _ekiwalk_commit() -> str:
    try:
        d = json.loads(metadata.distribution("rail-gap-map").read_text("direct_url.json") or "{}")
        return d.get("vcs_info", {}).get("commit_id", "unknown")
    except metadata.PackageNotFoundError:
        return "unknown"


def drawing_display(cfg: TerritoryConfig, display):
    """The display area used to clip the drawing: its boundary simplified together with the neighbouring
    regions (edge_regions), so the coast costs far fewer points and prefecture borders still match."""
    if cfg.edge_simplify_m <= 0:
        return display
    others = [n for n in dict.fromkeys(cfg.edge_regions) if n != cfg.region]
    geoms = [display]
    for n in others:
        path = load_region(n, root=paths.ROOT).build_dir / "display.wkb"
        if not path.exists():
            raise FileNotFoundError(f"{path}: edge_regions の {n} の admin の段を先に実行してください")
        geoms.append(shapely.from_wkb(path.read_bytes()))
    out = simplify_shared(geoms, cfg.edge_simplify_m)[0]
    log(f"display edge: {shapely.get_num_coordinates(display)} -> {shapely.get_num_coordinates(out)} points")
    return out


def build_territory(cfg: TerritoryConfig, region: Region) -> None:
    b, out = region.build_dir, region.web_dir
    nodes = pq.read_table(b / "nodes.parquet")
    edges = pq.read_table(b / "edges.parquet")
    xy = np.column_stack([nodes["x"].to_numpy(), nodes["y"].to_numpy()])
    u, v, length = edges["u"].to_numpy(), edges["v"].to_numpy(), edges["length_m"].to_numpy()
    st = pq.read_table(b / "stations-base.parquet").to_pandas()
    geoms = list(shapely.from_wkb(st["wkb"].to_numpy()))
    mid = _midpoints(geoms)
    rows = st[["group", "name", "line", "operator"]].assign(x=mid[:, 0], y=mid[:, 1])
    row_group, groups = merge_groups(rows, cfg.merge_same_name_m)
    log(f"stations: {len(st)} rows, {st['group'].nunique()} N02 groups, {len(groups)} merged")

    grid = Grid.load(b / "grid-base.npz")
    ny, nx = grid.dist.shape
    display = shapely.from_wkb((b / "display.wkb").read_bytes())
    in_display = cell_centers_mask(display, grid.x0, grid.y0, grid.cell, (ny, nx))
    inside = in_display & np.isfinite(grid.dist) & (grid.station >= 0)
    cells = np.flatnonzero(inside)
    near_d = grid.dist.reshape(-1)[cells]
    near_g = row_group[grid.station.reshape(-1)[cells]]
    log(f"cells: {len(cells)} in the display area")

    graph = access_graph(xy, u, v, length, geoms, region.access_radius_m)
    reach = station_reach(graph, len(xy), len(geoms), cfg.limit_m)
    pts = densify(xy, u, v, length)
    centers = np.column_stack([grid.x0 + (cells % nx + 0.5) * grid.cell, grid.y0 + (cells // nx + 0.5) * grid.cell])
    nb = cell_neighbors(pts.xy, centers, region.max_offroad_m)
    ps = per_station_cells(pts, nb, reach, u, v, cfg.limit_m)
    gt = group_table(ps, row_group)
    log(f"reach rows: {len(reach)}, cell-station rows: {len(ps)}, cell-group rows: {len(gt)}")

    best = gt.groupby("cell")["dist"].min()
    diff = np.abs(best.to_numpy() - near_d[best.index.to_numpy()])
    missing = (near_d <= cfg.limit_m - 1) & ~np.isin(np.arange(len(cells)), best.index.to_numpy())
    log(f"check vs ekiwalk grid: max diff {diff.max():.3f} m, missing {int(missing.sum())}")
    if diff.max() > 0.5 or missing.any():
        raise RuntimeError("駅ごとの道のりの最小が ekiwalk の格子と一致しません")

    shape = (ny, nx)
    # drawing only: fill blank cells (water, far from roads) and absorb tiny islands; cell data stay exact
    labels, filled = fill_blank(to_raster(near_g, cells, shape, -1), in_display)
    labels, absorbed = absorb_small_islands(labels, cfg.min_island_cells)
    log(f"drawing: {int(filled.sum())} blank cells filled, {int(absorbed.sum())} island cells absorbed")
    second = second_nearest(gt, near_g, len(cells))
    band = band_mask(near_d, second, cfg.limit_m, cfg.band_m)
    far = far_mask(near_d, cfg.limit_m)
    stats = group_stats(near_g, near_d, grid.cell, cfg.limit_m, len(groups))

    smooth = dict(simplify_m=cfg.simplify_m, iterations=cfg.chaikin_iterations)
    min_face_m2 = 16 * grid.cell * grid.cell  # 1 ha: smaller faces are knots from smoothing
    # Smooth a raster padded beyond the region, then clip with the display boundary (N03, simplified together
    # with the neighbouring regions), so that neighbouring regions meet without gaps.
    pad = PAD_CELLS
    px0, py0 = grid.x0 - pad * grid.cell, grid.y0 - pad * grid.cell
    draw = drawing_display(cfg, display)
    shapely.prepare(draw)

    def clip(geom, min_area):
        if not geom.is_empty and not draw.contains(geom):
            geom = shapely.intersection(geom, draw)
        return drop_small(geom, min_area)

    padded = pad_nearest(labels, in_display, pad, -1)
    terr = smooth_labels(padded, px0, py0, grid.cell, **smooth, min_face_m2=min_face_m2)
    terr = {g: q for g, p in terr.items() if not (q := clip(p, min_face_m2)).is_empty}  # e.g. bits of breakwater
    colors = dsatur(sorted(terr), raster_adjacency(labels), cfg.max_colors)
    log(f"territories: {len(terr)}, colours: {max(colors.values()) + 1}")
    min_part_m2 = cfg.min_island_cells * grid.cell * grid.cell
    def mask_poly(mask):
        lab = pad_nearest(np.where(mask, 1, -1), in_display, pad, -1)
        return clip(smooth_labels(lab, px0, py0, grid.cell, **smooth).get(1, shapely.Polygon()), min_part_m2)

    band_poly = mask_poly(to_raster(band, cells, shape, False))
    far_poly = mask_poly(to_raster(far, cells, shape, False) | filled)  # filled cells have no walking distance

    if out.exists():
        for child in out.iterdir():
            if child.name != "places.json":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
    out.mkdir(parents=True, exist_ok=True)
    ll = LonLat(region.crs)
    keys = groups["key"].tolist()
    write_json(out / "territories.geojson", feature_collection([feature(ll(p), {"g": g, "k": keys[g], "c": colors[g]}) for g, p in terr.items()]))
    write_json(out / "adjacency.json", sorted([a, b] for a, b in raster_adjacency(labels)))  # for combine
    write_json(out / "band.geojson", feature_collection([feature(ll(band_poly), {})]))
    write_json(out / "far.geojson", feature_collection([feature(ll(far_poly), {})]))
    # ekiwalk's display area also holds far-off unassigned islets (所属未定地); keep the part the grid covers
    grid_box = shapely.box(grid.x0, grid.y0, grid.x0 + nx * grid.cell, grid.y0 + ny * grid.cell)
    aoi_ll = ll(display.intersection(grid_box).simplify(30))
    write_json(out / "aoi.geojson", feature_collection([feature(aoi_ll, {})]))
    display_edge = draw.boundary.buffer(2 * cfg.simplify_m)
    gpos = gt[gt["dist"] <= cfg.limit_m]
    n_iso = 0
    iso_groups = set()
    for g, part in gpos.groupby("group"):
        cp = cells[part["cell"].to_numpy()]
        poly = drop_small(cells_polygon(cp // nx, cp % nx, grid.x0, grid.y0, grid.cell, **smooth), cfg.min_hole_m2)
        # the outline only: drop the parts that run along the region boundary (prefecture border, coast)
        outline = shapely.difference(poly.boundary, display_edge)
        write_json(out / "iso" / f"{int(g)}.json", feature(ll(outline), {"g": int(g)}))
        n_iso += 1
        iso_groups.add(int(g))
    n_chunks = write_cells(out, cells, nx, cfg.chunk_cells, near_g, near_d, gt, cfg.limit_m)

    station_list = []
    for g, row in groups.iterrows():
        lon, lat = ll.point(row["x"], row["y"])
        s = stats.loc[g]
        station_list.append(
            {
                "id": int(g),
                "key": row["key"],
                "name": row["name"],
                "lon": lon,
                "lat": lat,
                "lines": row["lines"],
                "c": colors.get(int(g)),
                "area_km2": None if pd.isna(s["far_m"]) else round(float(s["area_km2"]), 2),
                "far_m": None if pd.isna(s["far_m"]) else int(np.ceil(s["far_m"])),
                "within": None if pd.isna(s["far_m"]) else round(float(s["within"]), 3),
                "iso": int(g) in iso_groups,  # this region has a 15-minute outline for the station
            }
        )
    write_json(out / "stations.json", station_list)

    # station readings for the search: OSM name:ja-Hira of a same-name station node within 1.5 km
    osm_names = read_osm_station_names(raw_path(paths.ROOT, region.osm_source), region.bbox, region.crs)
    readings = match_readings(groups, osm_names, max_m=1500)
    towns = town_readings(places.read_csv_any(raw_path(paths.ROOT, f"abr-town-{pref_code(region)}")))  # fallback: same-name town
    manual = {norm_name(k): v for k, v in tomllib.loads((paths.ROOT / "configs" / "station-readings.toml").read_text(encoding="utf-8"))["readings"].items()}
    for g in range(len(groups)):
        key = norm_name(groups.loc[g, "name"])
        if g not in readings and (key in towns or key in manual):
            readings[g] = towns.get(key) or manual[key]
    missing = [groups.loc[g, "name"] for g in range(len(groups)) if g not in readings]
    log(f"readings: {len(readings)} of {len(groups)} stations (none for e.g. {missing[:8]})")
    places_path = out / "places.json"
    place_rows = json.loads(places_path.read_text(encoding="utf-8"))
    write_json(places_path, station_place_rows(place_rows, station_list, readings))

    manifest = json.loads((paths.RAW / "manifest.json").read_text(encoding="utf-8"))
    meta = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "region": region.name,
        "label": region.label,
        "bbox": [round(v, 5) for v in aoi_ll.bounds],
        "home_view": region.home_view,
        "m_per_min": region.walk_m_per_min,
        "limit_m": cfg.limit_m,
        "band_m": cfg.band_m,
        "merge_same_name_m": cfg.merge_same_name_m,
        "access_radius_m": region.access_radius_m,
        "grid": {
            "x0": grid.x0, "y0": grid.y0, "cell": grid.cell, "nx": nx, "ny": ny,
            "chunk": cfg.chunk_cells, "crs": region.crs, "proj4": CRS(region.crs).to_proj4(),
        },
        "ekiwalk": {"repo": "https://github.com/isshiki/rail-gap-map", "commit": _ekiwalk_commit()},
        "sources": {k: {f: manifest[k].get(f) for f in ("url", "file", "bytes", "sha256", "retrieved_utc")} for k in BASE_SOURCES + [f"abr-town-{pref_code(region)}", f"abr-town-pos-{pref_code(region)}"] if k in manifest},
        "counts": {"cells": int(len(cells)), "stations": len(station_list), "territories": len(terr), "chunks": n_chunks, "iso": n_iso},
    }
    write_json(out / "meta.json", meta)
    log(f"written to {out}")
