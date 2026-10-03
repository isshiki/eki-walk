import json

import shapely

from shapely.geometry import box, mapping

from eki_walk.territory.combine import combine


def region(root, name, stations, squares, adjacency):
    d = root / name
    d.mkdir(parents=True)
    feats = [{"type": "Feature", "properties": {"g": g, "k": k, "c": 0}, "geometry": mapping(box(*b))} for g, k, b in squares]
    (d / "territories.geojson").write_text(json.dumps({"type": "FeatureCollection", "features": feats}), encoding="utf-8")
    rows = [{"id": i, "key": k, "name": k.upper(), "lon": 139.0 + i * 0.01, "lat": 35.0, "c": 0} for i, k in stations]
    (d / "stations.json").write_text(json.dumps(rows), encoding="utf-8")
    (d / "adjacency.json").write_text(json.dumps(adjacency), encoding="utf-8")
    union = shapely.union_all([box(*b) for *_, b in squares])
    for layer in ("far", "band"):  # a strip along the south edge of the region
        strip = union.intersection(box(-180, -90, 180, union.bounds[1] + 0.002))
        fc = {"type": "FeatureCollection", "features": [{"type": "Feature", "properties": {}, "geometry": mapping(strip)}]}
        (d / f"{layer}.geojson").write_text(json.dumps(fc), encoding="utf-8")
    (d / "meta.json").write_text(
        json.dumps({"label": name.upper(), "bbox": [139.0, 35.0, 139.03, 35.02], "home_view": {"center": [139.0, 35.0], "zoom": 10}}),
        encoding="utf-8",
    )


def test_combine_colours_by_key_across_regions(tmp_path):
    region(tmp_path, "a", [(0, "x"), (1, "y")], [(0, "x", (139.00, 35.00, 139.01, 35.01)), (1, "y", (139.01, 35.00, 139.02, 35.01))], [[0, 1]])
    # region b: y continues east of a's y; z sits on top of a's y (touching across the region border)
    region(tmp_path, "b", [(0, "y"), (1, "z")], [(0, "y", (139.02, 35.00, 139.03, 35.01)), (1, "z", (139.01, 35.01, 139.02, 35.02))], [[0, 1]])
    out = combine(tmp_path, ["a", "b"], max_colors=6)
    color = out["colors"]
    assert color["x"] != color["y"] and color["y"] != color["z"] and color["x"] != color["z"]  # x-z touch at a corner
    a = json.loads((tmp_path / "a" / "territories.geojson").read_text(encoding="utf-8"))["features"]
    b = json.loads((tmp_path / "b" / "territories.geojson").read_text(encoding="utf-8"))["features"]
    assert a[1]["properties"]["c"] == b[0]["properties"]["c"] == color["y"]
    st = json.loads((tmp_path / "b" / "stations.json").read_text(encoding="utf-8"))
    assert st[1]["c"] == color["z"]
    reg = json.loads((tmp_path / "regions.json").read_text(encoding="utf-8"))
    assert [r["name"] for r in reg["regions"]] == ["a", "b"]
    assert reg["regions"][0] == {"name": "a", "label": "A", "bbox": [139.0, 35.0, 139.03, 35.02], "path": "data/a/"}
    assert reg["home"] == {"center": [139.0, 35.0], "zoom": 10}
    assert reg["overview"] == "data/overview.json"


def test_combine_writes_border_lines_only_between_different_stations(tmp_path):
    region(tmp_path, "a", [(0, "x"), (1, "y")], [(0, "x", (139.00, 35.00, 139.01, 35.01)), (1, "y", (139.01, 35.00, 139.02, 35.01))], [[0, 1]])
    region(tmp_path, "b", [(0, "y"), (1, "z")], [(0, "y", (139.02, 35.00, 139.03, 35.01)), (1, "z", (139.01, 35.01, 139.02, 35.02))], [[0, 1]])
    combine(tmp_path, ["a", "b"], max_colors=6)
    la = json.loads((tmp_path / "a" / "lines.geojson").read_text(encoding="utf-8"))["features"]
    lb = json.loads((tmp_path / "b" / "lines.geojson").read_text(encoding="utf-8"))["features"]
    pairs = {(f["properties"]["a"], f["properties"]["b"]) for f in la + lb}
    assert ("x", "y") in pairs or ("y", "x") in pairs  # inside region a
    assert ("y", "z") in pairs or ("z", "y") in pairs  # across the border (a's y meets b's z)
    # a's y and b's y meet at lon 139.02: same station, so no line there
    for f in la + lb:
        p = f["properties"]
        if {p["a"], p["b"]} == {"y"}:
            raise AssertionError("a line between two parts of the same station")
    outer = [f for f in la + lb if f["properties"]["b"] == ""]
    assert outer  # the outer edge of the covered area is drawn


def test_combine_writes_a_light_overview_of_all_regions(tmp_path):
    region(tmp_path, "a", [(0, "x"), (1, "y")], [(0, "x", (139.00, 35.00, 139.01, 35.01)), (1, "y", (139.01, 35.00, 139.02, 35.01))], [[0, 1]])
    region(tmp_path, "b", [(0, "y"), (1, "z")], [(0, "y", (139.02, 35.00, 139.03, 35.01)), (1, "z", (139.01, 35.01, 139.02, 35.02))], [[0, 1]])
    out = combine(tmp_path, ["a", "b"], max_colors=6)
    ov = json.loads((tmp_path / "overview.json").read_text(encoding="utf-8"))
    t = {f["properties"]["k"]: f for f in ov["t"]["features"]}
    assert sorted(t) == ["x", "y", "z"]  # y spans both regions and becomes one feature
    y = shapely.geometry.shape(t["y"]["geometry"])
    assert y.geom_type == "Polygon" and abs(y.area - 0.0002) < 1e-6  # 139.01-139.03 x 35.00-35.01, no seam
    assert t["y"]["properties"]["c"] == out["colors"]["y"]
    assert len(ov["far"]["features"]) == 1 and len(ov["band"]["features"]) == 1
    st = {s[0]: s for s in ov["st"]}  # stations once per key: [key, name, lon, lat, regions]
    assert sorted(st) == ["x", "y", "z"]
    assert st["x"][1] == "X" and st["x"][4] == ["a"] and st["y"][4] == ["a", "b"]
