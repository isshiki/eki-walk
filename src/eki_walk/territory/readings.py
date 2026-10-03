"""Station readings for the place search.

N02 has no readings. Two local sources fill them without any extra download:
1. OpenStreetMap (the extract used for the road network): name:ja-Hira of station, stop and platform nodes
   with the same name within max_m of the station centre.
2. ABR town names (the files used for the place search): the reading of a town (大字・町) with exactly the
   station's name, when all towns with that name read the same (e.g. 中目黒 -> ナカメグロ).
Readings are only used to match what people type, so katakana and hiragana are both fine.
"""

from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd
from pyproj import Transformer

STATION_SQL = """
SELECT tags['name'] AS name, tags['name:ja-Hira'] AS hira, lon, lat
FROM ST_ReadOSM('{pbf}')
WHERE kind = 'node'
  AND (tags['railway'] IN ('station', 'halt', 'stop')
       OR tags['public_transport'] IN ('station', 'stop_position', 'platform')
       OR tags['station'] IN ('subway', 'light_rail', 'monorail'))
  AND tags['name:ja-Hira'] IS NOT NULL
  AND lon BETWEEN {xmin} AND {xmax} AND lat BETWEEN {ymin} AND {ymax}
"""

_BRACKETS = re.compile(r"[（(〈<［\[].*?[）)〉>］\]]")


def norm_name(name: str) -> str:
    """Station names as compared: NFKC, ヶ/ヵ/ケ unified, bracketed notes and a trailing 駅 removed."""
    import unicodedata

    if not isinstance(name, str):  # a node with a reading but no name comes through as NaN
        return ""
    s = unicodedata.normalize("NFKC", name).replace(" ", "")
    s = _BRACKETS.sub("", s)
    s = s.replace("ヶ", "ケ").replace("ヵ", "ケ").replace("ｹ", "ケ")
    return s[:-1] if s.endswith("駅") and len(s) > 1 else s


def read_osm_station_names(pbf: Path, bbox, metric_crs: str) -> pd.DataFrame:
    """OSM station/stop/platform nodes with a hiragana reading: name, hira, x, y (metres)."""
    import duckdb

    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    xmin, ymin, xmax, ymax = bbox
    df = con.execute(STATION_SQL.format(pbf=Path(pbf).as_posix(), xmin=xmin, ymin=ymin, xmax=xmax, ymax=ymax)).df()
    x, y = Transformer.from_crs("EPSG:4326", metric_crs, always_xy=True).transform(df["lon"].to_numpy(), df["lat"].to_numpy())
    return df.assign(x=x, y=y)[["name", "hira", "x", "y"]]


def match_readings(groups: pd.DataFrame, osm: pd.DataFrame, max_m: float) -> dict[int, str]:
    """{group number: hiragana} for groups with a same-name OSM node within max_m (most common reading)."""
    osm = osm[osm["hira"].notna() & (osm["hira"] != "") & osm["name"].notna()]
    by_name = {n: part for n, part in osm.assign(key=osm["name"].map(norm_name)).groupby("key")}
    out = {}
    for g, row in groups.iterrows():
        part = by_name.get(norm_name(row["name"]))
        if part is None:
            continue
        d = np.hypot(part["x"].to_numpy() - row["x"], part["y"].to_numpy() - row["y"])
        near = part[d <= max_m]
        if len(near):
            out[int(g)] = near["hira"].mode().iloc[0]
    return out


def town_readings(towns: list[dict]) -> dict[str, str]:
    """{name: reading} from ABR town rows (大字・町 and city names), only for names that always read the same."""
    seen: dict[str, set] = defaultdict(set)
    for t in towns:
        name, kana = norm_name(t.get("oaza_cho") or ""), (t.get("oaza_cho_kana") or "").strip()
        if name and kana:
            seen[name].add(kana)
        # stations named after the city: "春日部市" -> 春日部 / カスカベ, and the full "狭山市" / サヤマシ
        city, city_kana = norm_name(t.get("city") or ""), (t.get("city_kana") or "").strip()
        if city and city_kana:
            seen[city].add(city_kana)
            base, base_kana = re.sub(r"(市|町|村)$", "", city), re.sub(r"(シ|マチ|チョウ|ムラ|ソン)$", "", city_kana)
            if base and base_kana and base != city:
                seen[base].add(base_kana)
    return {n: next(iter(k)) for n, k in seen.items() if len(k) == 1}


def station_place_rows(places: list[list], stations: list[dict], readings: dict[int, str]) -> list[list]:
    """Replace ekiwalk's station rows with one row per merged station, with its reading (+ えき)."""
    rows = [r for r in places if r[4] != "s"]
    for s in stations:
        kana = readings.get(s["id"], "")
        rows.append([f"{s['name']}駅", f"{kana}えき" if kana else "", s["lon"], s["lat"], "s"])
    return rows
