# 駅の縄張りマップ 実装計画

> 開発時の計画の記録です。作業ツールやAIエージェントの指定はありません。現在の実装・起動手順は README.md、計算方法は docs/method.md を参照してください。チェックボックスは当時の計画であり、現在の未完了作業を表すものではありません。

**Goal:** walk15 を置き換え、道路網のボロノイで作った「駅の縄張り」を主役にした静的な地図アプリを、rail-gap-map の `ekiwalk` を共通部品として作る。

**Architecture:** `ekiwalk` (rail-gap-map@4176263, git 依存) で OSM の道路網・駅・全駅からの最短路・25m 格子を作る。eki-walk の `territory` パッケージで、駅のまとめ (600m)、駅ごとの 1,200m 打ち切りの最短路 (`ekiwalk` と同じ起点の付け方)、格子ごとの駅ごとの道のり (`ekiwalk` と同じ 8 点の規則)、縄張りの平滑な面・塗り分け・帯・15 分超・駅数・駅ごとの数字を作り、`web/data/<region>/` に書き出す。画面は MapLibre GL JS (ESM) と proj4 をビルドなしで使う。

**Tech Stack:** Python 3.11+ / uv、ekiwalk (rail-gap-map@4176263)、numpy、scipy、shapely 2.1、pyproj、pandas、pyarrow、pytest。画面は MapLibre GL JS 6.11.2、proj4 2.22.0、OpenFreeMap Liberty、地理院 航空写真。

設計書: `docs/superpowers/specs/2026-10-03-territory-design.md`

コードの書き方: この計画の **File: `path`** の直後のコードブロックが、そのファイルの完全な内容。

---

## ファイル構成

| パス | 役割 |
|---|---|
| `configs/territory.toml` / `configs/territory-oizumi.toml` | 縄張りの設定 (本番 / 試運転) |
| `configs/regions/tokyo.toml` / `configs/regions/oizumi-test.toml` | `ekiwalk` の範囲の設定 (rail-gap-map@4176263 と同じ値) |
| `configs/sources.toml` | `ekiwalk` の `raw_path` が読む生データの一覧 |
| `src/eki_walk/config.py` | 縄張りの設定の読み込み |
| `src/eki_walk/raw.py` | rail-gap-map の生データを写し、SHA-256 を確かめる |
| `src/eki_walk/territory/groups.py` | 駅のまとめ (N02 グループ + 同名 600m) |
| `src/eki_walk/territory/reach.py` | `ekiwalk` と同じグラフで、駅ごとの打ち切り最短路 |
| `src/eki_walk/territory/cells.py` | 格子ごとの駅ごとの道のり (`ekiwalk.surface` と同じ規則) |
| `src/eki_walk/territory/polygons.py` | 格子のラベル → 平滑で隙間のない面 |
| `src/eki_walk/territory/colors.py` | となり合う縄張りの塗り分け |
| `src/eki_walk/territory/layers.py` | 2 番目の駅・帯・15 分超・駅数・駅ごとの数字 |
| `src/eki_walk/territory/export.py` | 画面用ファイルの書き出し |
| `src/eki_walk/pipeline.py` / `cli.py` | 手順の実行 |
| `web/index.html` / `web/app.js` / `web/style.css` | 画面 |
| `web/js/search.js` / `web/js/lookup.js` | rail-gap-map@4176263 から写した検索・面の判定 |
| `web/walk15/index.html` | 旧 walk15 からの案内 |

消すもの: `src/eki_walk/{sources,network,reach,stations,products}/`, 旧 `pipeline.py`・`cli.py`, `configs/tokyo*.toml`, `scripts/validate_walk15.py`, `web/walk15/{app.js,style.css}`, 旧テスト (`test_config`・`test_units` 以外)。

---

### Task 0: ブランチ

- [ ] `git -C C:/Projects-GitHub/eki-walk switch -c territory`

### Task 1: 依存と設定

- [ ] **Step 1: `ekiwalk` を git 依存で入れる**

```powershell
uv add "rail-gap-map @ git+https://github.com/isshiki/rail-gap-map@4176263"
uv run python -c "import ekiwalk.shortest, ekiwalk.surface; print('ok')"
```

- [ ] **Step 2: 設定ファイル**

**File: `configs/territory.toml`**

```toml
# 駅の縄張りマップの設定。道路網・駅・格子は configs/regions/<region>.toml (ekiwalk の形式)
region = "tokyo"
limit_m = 1200          # 15 分 (80 m = 1 分)
band_m = 240            # 2 番目に近い駅との差が 3 分以内 = 境界付近の帯
merge_same_name_m = 600 # 同じ駅名で 600 m 以内のグループを 1 駅にまとめる
simplify_m = 20         # 境界の単純化 (Douglas-Peucker)
chaikin_iterations = 3  # 角を丸める回数
chunk_cells = 64        # 画面用の区画 (64 × 25 m = 1.6 km 四方)
max_colors = 6
max_count_band = 5      # 駅数の塗りは 5 以上をまとめる
```

**File: `configs/territory-oizumi.toml`**

```toml
# 試運転: 大泉学園町付近 (ekiwalk の oizumi-test)
region = "oizumi-test"
limit_m = 1200
band_m = 240
merge_same_name_m = 600
simplify_m = 20
chaikin_iterations = 3
chunk_cells = 64
max_colors = 6
max_count_band = 5
```

`configs/regions/tokyo.toml` と `configs/regions/oizumi-test.toml` は `git -C ../rail-gap-map show 4176263:configs/regions/<name>.toml` の内容をそのまま写す (先頭に「rail-gap-map@4176263 から写した」とコメントを足す)。
`configs/sources.toml` は `git -C ../rail-gap-map show 4176263:configs/sources.toml` から `oedo-pdf` を除いたもの。

- [ ] **Step 3: 設定の読み込み (テストから)**

**File: `tests/test_config.py`**

```python
from pathlib import Path

from eki_walk.config import load_config

ROOT = Path(__file__).resolve().parents[1]


def test_load_territory_config():
    c = load_config(ROOT / "configs" / "territory.toml")
    assert c.region == "tokyo"
    assert c.limit_m == 1200
    assert c.band_m == 240
    assert c.merge_same_name_m == 600
    assert c.chunk_cells == 64


def test_trial_config_uses_oizumi_region():
    assert load_config(ROOT / "configs" / "territory-oizumi.toml").region == "oizumi-test"


def test_region_configs_load_with_ekiwalk():
    from ekiwalk.config import load_region

    r = load_region("tokyo", root=ROOT)
    assert r.cell_m == 25 and r.access_radius_m == 100 and r.max_offroad_m == 300
    assert r.build_dir == ROOT / "data" / "build" / "tokyo"
```

**File: `src/eki_walk/config.py`**

```python
"""Settings for the station territory map (configs/territory*.toml)."""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class TerritoryConfig:
    region: str
    limit_m: float
    band_m: float
    merge_same_name_m: float
    simplify_m: float
    chaikin_iterations: int
    chunk_cells: int
    max_colors: int
    max_count_band: int


def load_config(path: Path | str) -> TerritoryConfig:
    d = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    return TerritoryConfig(
        region=d["region"],
        limit_m=float(d["limit_m"]),
        band_m=float(d["band_m"]),
        merge_same_name_m=float(d["merge_same_name_m"]),
        simplify_m=float(d["simplify_m"]),
        chaikin_iterations=int(d["chaikin_iterations"]),
        chunk_cells=int(d["chunk_cells"]),
        max_colors=int(d["max_colors"]),
        max_count_band=int(d["max_count_band"]),
    )
```

- [ ] **Step 4:** `uv run pytest tests/test_config.py -v` → 3 passed
- [ ] **Step 5: コミット** — `feat: add ekiwalk dependency and territory configs`

### Task 2: 生データを rail-gap-map から写す

**File: `tests/test_raw.py`**

```python
import hashlib
import json

import pytest

from eki_walk.raw import import_raw


def setup(tmp_path, content=b"pbf-bytes", recorded=None):
    src, dst = tmp_path / "src", tmp_path / "dst"
    (src / "data" / "raw").mkdir(parents=True)
    (dst / "configs").mkdir(parents=True)
    (src / "data" / "raw" / "a.pbf").write_bytes(content)
    sha = recorded or hashlib.sha256(content).hexdigest()
    (src / "data" / "raw" / "manifest.json").write_text(
        json.dumps({"osm": {"url": "https://example/a.pbf", "file": "a.pbf", "bytes": len(content), "sha256": sha}}),
        encoding="utf-8",
    )
    (dst / "configs" / "sources.toml").write_text('[osm]\nurl = "https://example/a.pbf"\nfile = "a.pbf"\n', encoding="utf-8")
    return src, dst


def test_import_copies_and_records(tmp_path):
    src, dst = setup(tmp_path)
    man = import_raw(src, dst)
    assert (dst / "data" / "raw" / "a.pbf").read_bytes() == b"pbf-bytes"
    assert man["osm"]["copied_from"] == "rail-gap-map data/raw"
    saved = json.loads((dst / "data" / "raw" / "manifest.json").read_text(encoding="utf-8"))
    assert saved["osm"]["sha256"] == hashlib.sha256(b"pbf-bytes").hexdigest()


def test_import_rejects_sha_mismatch(tmp_path):
    src, dst = setup(tmp_path, recorded="0" * 64)
    with pytest.raises(ValueError, match="SHA-256"):
        import_raw(src, dst)
    assert not (dst / "data" / "raw" / "a.pbf").exists()
```

**File: `src/eki_walk/raw.py`**

```python
"""Reuse raw files that rail-gap-map already downloaded (no new download), checking SHA-256."""

from __future__ import annotations

import hashlib
import json
import shutil
import tomllib
from datetime import datetime, timezone
from pathlib import Path


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(1 << 20):
            h.update(chunk)
    return h.hexdigest()


def load_sources(root: Path) -> dict:
    return tomllib.loads((root / "configs" / "sources.toml").read_text(encoding="utf-8"))


def import_raw(src_root: Path, dst_root: Path, keys=None) -> dict:
    """Copy data/raw/<file> for each source key from src_root, verified against src_root's manifest."""
    sources = load_sources(dst_root)
    keys = list(keys or sources)
    src_manifest = json.loads((src_root / "data" / "raw" / "manifest.json").read_text(encoding="utf-8"))
    dst_dir = dst_root / "data" / "raw"
    dst_dir.mkdir(parents=True, exist_ok=True)
    man_path = dst_dir / "manifest.json"
    manifest = json.loads(man_path.read_text(encoding="utf-8")) if man_path.exists() else {}
    for key in keys:
        entry = src_manifest.get(key)
        if entry is None:
            raise KeyError(f"rail-gap-map の取得記録に {key} がありません")
        file = sources[key]["file"]
        if entry["file"] != file:
            raise ValueError(f"{key}: ファイル名が違います ({entry['file']} / {file})")
        dst = dst_dir / file
        if not dst.exists() or sha256_file(dst) != entry["sha256"]:
            shutil.copyfile(src_root / "data" / "raw" / file, dst)
        if sha256_file(dst) != entry["sha256"]:
            dst.unlink()
            raise ValueError(f"{file}: SHA-256 が取得記録と一致しません")
        manifest[key] = {
            **entry,
            "copied_from": "rail-gap-map data/raw",
            "copied_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
    man_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest
```

- [ ] `uv run pytest tests/test_raw.py -v` → 2 passed → コミット `feat: import raw files from rail-gap-map with SHA-256 check`

### Task 3: 駅のまとめ

**File: `tests/test_groups.py`**

```python
import pandas as pd

from eki_walk.territory.groups import display_line, merge_groups


def rows():
    return pd.DataFrame(
        {
            "group": ["a", "a", "b", "c", "d", "e"],
            "name": ["池袋", "池袋", "池袋", "早稲田", "早稲田", "目白"],
            "line": ["山手線", "山手線", "13号線副都心線", "荒川線", "5号線東西線", "山手線"],
            "operator": ["東日本旅客鉄道", "東日本旅客鉄道", "東京地下鉄", "東京都", "東京地下鉄", "東日本旅客鉄道"],
            "x": [0.0, 10.0, 361.0, 0.0, 744.0, 100.0],
            "y": [0.0, 0.0, 0.0, 5000.0, 5000.0, 2000.0],
        }
    )


def test_same_name_within_600m_is_merged():
    row_group, g = merge_groups(rows(), 600)
    assert row_group[0] == row_group[1] == row_group[2]
    assert row_group[3] != row_group[4]  # 早稲田 744 m apart stays separate
    assert len(g) == 4
    ike = g.loc[row_group[0]]
    assert ike["name"] == "池袋"
    assert [x["line"] for x in ike["lines"]] == ["副都心線", "山手線"]
    assert ike["members"] == [0, 1, 2]


def test_different_names_are_not_merged():
    row_group, _ = merge_groups(rows(), 10_000)
    assert row_group[5] != row_group[0]


def test_display_line():
    assert display_line("4号線丸ノ内線") == "丸ノ内線"
    assert display_line("中央線") == "中央線"
    assert display_line("1号線") == "1号線"
```

**File: `src/eki_walk/territory/__init__.py`**

```python
"""Station territory map: territories, overlaps and web data built on top of ekiwalk."""
```

**File: `src/eki_walk/territory/groups.py`**

```python
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

    Returns (merged group number per row, one row per merged group with name, x, y, lines, members).
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
            }
        )
    return row_group, pd.DataFrame(out)
```

- [ ] `uv run pytest tests/test_groups.py -v` → 3 passed → コミット `feat: merge same-name station groups within 600 m`

### Task 4: 駅ごとの打ち切り最短路 (`ekiwalk` と同じグラフ)

**File: `tests/test_reach.py`**

```python
import numpy as np
from shapely.geometry import LineString, Point

from ekiwalk.shortest import solve
from eki_walk.territory.reach import access_graph, station_reach


def lattice(n=6, step=50.0):
    xs, ys = np.meshgrid(np.arange(n) * step, np.arange(n) * step)
    xy = np.column_stack([xs.ravel(), ys.ravel()])
    idx = np.arange(n * n).reshape(n, n)
    u = np.concatenate([idx[:, :-1].ravel(), idx[:-1, :].ravel()])
    v = np.concatenate([idx[:, 1:].ravel(), idx[1:, :].ravel()])
    return xy, u, v, np.full(len(u), step)


STATIONS = [LineString([(0, -20), (60, -20)]), Point(180, 230), LineString([(260, 100), (260, 160)])]


def test_min_over_stations_equals_ekiwalk_solve():
    xy, u, v, length = lattice()
    dist, nearest = solve(xy, u, v, length, STATIONS, 100)
    g = access_graph(xy, u, v, length, STATIONS, 100)
    r = station_reach(g, len(xy), len(STATIONS), limit_m=10_000)
    best = r.sort_values("dist").groupby("node").first()
    assert np.allclose(best["dist"].reindex(range(len(xy))).to_numpy(), dist, atol=1e-4)
    assert (best["station"].reindex(range(len(xy))).to_numpy() == nearest).mean() > 0.95  # ties may differ


def test_cutoff():
    xy, u, v, length = lattice()
    g = access_graph(xy, u, v, length, STATIONS, 100)
    r = station_reach(g, len(xy), len(STATIONS), limit_m=60)
    assert r["dist"].max() <= 60
    assert set(r["station"]) == {0, 1, 2}
```

**File: `src/eki_walk/territory/reach.py`**

```python
"""Per-station walking distance with a cut-off, on exactly the graph ekiwalk.shortest.solve builds.

The virtual-node construction follows ekiwalk.shortest.solve at rail-gap-map@4176263, so the minimum over
stations equals ekiwalk's nearest-station distance.
"""

from __future__ import annotations

import numpy as np
import pandas as pd
import shapely
from ekiwalk.shortest import EPS
from scipy.sparse import coo_matrix, csr_matrix
from scipy.sparse.csgraph import dijkstra
from scipy.spatial import cKDTree


def access_graph(xy: np.ndarray, u, v, length, stations: list, access_radius_m: float) -> csr_matrix:
    """Road edges plus one virtual node per station linked to nodes within access_radius_m of its geometry."""
    n, k = len(xy), len(stations)
    tree = cKDTree(xy)
    su, sv, sw = [], [], []
    for i, geom in enumerate(stations):
        minx, miny, maxx, maxy = geom.bounds
        cx, cy = (minx + maxx) / 2, (miny + maxy) / 2
        reach = np.hypot(maxx - minx, maxy - miny) / 2 + access_radius_m
        cand = np.asarray(tree.query_ball_point([cx, cy], reach), dtype=np.int64)
        d = np.empty(0)
        if len(cand):
            d = shapely.distance(shapely.points(xy[cand]), geom)
            cand, d = cand[d <= access_radius_m], d[d <= access_radius_m]
        if len(cand) == 0:
            pt = geom.interpolate(0.5, normalized=True) if geom.geom_type == "LineString" else geom
            _, j = tree.query([pt.x, pt.y])
            cand, d = np.array([j]), np.array([shapely.distance(shapely.points(xy[j]), geom)])
        su.append(np.full(len(cand), n + i))
        sv.append(cand)
        sw.append(d + EPS)
    uu = np.concatenate([np.asarray(u)] + su)
    vv = np.concatenate([np.asarray(v)] + sv)
    ww = np.concatenate([np.asarray(length, float)] + sw)
    return coo_matrix((ww, (uu, vv)), shape=(n + k, n + k)).tocsr()


def station_reach(graph: csr_matrix, n: int, k: int, limit_m: float, batch: int = 4) -> pd.DataFrame:
    """Rows (station, node, dist) for every node within limit_m of each station (undirected, like ekiwalk)."""
    out = []
    for start in range(0, k, batch):
        ind = np.arange(n + start, n + min(k, start + batch))
        d = dijkstra(graph, directed=False, indices=ind, limit=limit_m + EPS)[:, :n] - EPS
        si, ni = np.nonzero(d <= limit_m)
        out.append(
            pd.DataFrame({"station": (start + si).astype(np.int32), "node": ni.astype(np.int64), "dist": d[si, ni]})
        )
    return pd.concat(out, ignore_index=True)
```

- [ ] `uv run pytest tests/test_reach.py -v` → 2 passed → コミット `feat: per-station cut-off reach on the ekiwalk graph`

### Task 5: 格子ごとの駅ごとの道のり

**File: `tests/test_cells.py`**

```python
import numpy as np
from shapely.geometry import LineString, Point

from ekiwalk.shortest import solve
from ekiwalk.surface import densify_edges, grid_from_points
from eki_walk.territory.cells import cell_neighbors, densify, per_station_cells
from eki_walk.territory.reach import access_graph, station_reach


def lattice(n=6, step=50.0):
    xs, ys = np.meshgrid(np.arange(n) * step, np.arange(n) * step)
    xy = np.column_stack([xs.ravel(), ys.ravel()])
    idx = np.arange(n * n).reshape(n, n)
    u = np.concatenate([idx[:, :-1].ravel(), idx[:-1, :].ravel()])
    v = np.concatenate([idx[:, 1:].ravel(), idx[1:, :].ravel()])
    return xy, u, v, np.full(len(u), step)


STATIONS = [LineString([(0, -20), (60, -20)]), Point(180, 230), LineString([(260, 100), (260, 160)])]


def test_densify_matches_ekiwalk():
    xy, u, v, length = lattice()
    pts_e, _, _ = densify_edges(xy, u, v, length, np.zeros(len(xy)), np.zeros(len(xy), int), step=20)
    p = densify(xy, u, v, length, 20)
    assert np.allclose(p.xy, pts_e)
    assert p.edge_count.sum() == len(pts_e) - len(xy)


def test_min_over_stations_equals_ekiwalk_grid():
    xy, u, v, length = lattice()
    dist, nearest = solve(xy, u, v, length, STATIONS, 100)
    pts, d, st = densify_edges(xy, u, v, length, dist, nearest, step=20)
    x0, y0, cell, nx, ny = -50.0, -50.0, 25.0, 16, 16
    grid = grid_from_points(pts, d, st, x0, y0, nx, ny, cell, max_offroad=300)

    p = densify(xy, u, v, length, 20)
    cells = np.flatnonzero(np.isfinite(grid.dist.ravel()))
    centers = np.column_stack([x0 + (cells % nx + 0.5) * cell, y0 + (cells // nx + 0.5) * cell])
    nb = cell_neighbors(p.xy, centers, 300)
    reach = station_reach(access_graph(xy, u, v, length, STATIONS, 100), len(xy), len(STATIONS), 10_000)
    ps = per_station_cells(p, nb, reach, u, v, 10_000)
    best = ps.groupby("cell")["dist"].min().reindex(range(len(cells))).to_numpy()
    assert np.allclose(best, grid.dist.ravel()[cells], atol=1e-3)


def test_limit_drops_far_cells():
    xy, u, v, length = lattice()
    p = densify(xy, u, v, length, 20)
    centers = np.array([[0.0, 0.0], [250.0, 250.0]])
    nb = cell_neighbors(p.xy, centers, 300)
    reach = station_reach(access_graph(xy, u, v, length, STATIONS[:1], 100), len(xy), 1, 10_000)
    ps = per_station_cells(p, nb, reach, u, v, 100)
    assert ps["cell"].tolist() == [0]
```

**File: `src/eki_walk/territory/cells.py`**

```python
"""Per-station distances for grid cells, computed with the same rule as ekiwalk.surface (rail-gap-map@4176263):
a cell takes the minimum over its k nearest road points (within max_offroad) of point distance + straight offset.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from scipy.spatial import cKDTree

DENSIFY_STEP_M = 20.0  # ekiwalk.surface.run densifies edges every 20 m


@dataclass
class Points:
    xy: np.ndarray  # (P, 2): nodes first, then interior points (same order as ekiwalk.surface.densify_edges)
    a: np.ndarray  # interior point: edge start node (-1 for nodes)
    b: np.ndarray  # interior point: edge end node
    s: np.ndarray  # distance from a along the edge
    L: np.ndarray  # edge length
    edge_first: np.ndarray  # first interior point index of each edge
    edge_count: np.ndarray  # interior points per edge
    n_nodes: int


def densify(xy, u, v, length, step: float = DENSIFY_STEP_M) -> Points:
    u, v, length = np.asarray(u), np.asarray(v), np.asarray(length, float)
    n = np.maximum(np.ceil(length / step).astype(np.int64) - 1, 0)
    e = np.repeat(np.arange(len(u)), n)
    j = np.arange(n.sum()) - np.repeat(np.cumsum(n) - n, n) + 1
    L = length[e]
    s = j * L / (n[e] + 1)
    t = (s / L)[:, None]
    a, b = u[e], v[e]
    p = xy[a] * (1 - t) + xy[b] * t
    N = len(xy)
    return Points(
        xy=np.vstack([xy, p]),
        a=np.concatenate([np.full(N, -1), a]),
        b=np.concatenate([np.full(N, -1), b]),
        s=np.concatenate([np.zeros(N), s]),
        L=np.concatenate([np.zeros(N), L]),
        edge_first=N + np.cumsum(n) - n,
        edge_count=n,
        n_nodes=N,
    )


@dataclass
class Neighbors:
    idx: np.ndarray  # (C, k) point index, -1 where none
    off: np.ndarray  # (C, k) straight-line offset, inf where none


def cell_neighbors(pts_xy: np.ndarray, centers: np.ndarray, max_offroad: float, k: int = 8, chunk: int = 400_000) -> Neighbors:
    tree = cKDTree(pts_xy)
    kk = min(k, len(pts_xy))
    idx = np.full((len(centers), kk), -1, dtype=np.int32)
    off = np.full((len(centers), kk), np.inf, dtype=np.float32)
    for c0 in range(0, len(centers), chunk):
        dd, ii = tree.query(centers[c0 : c0 + chunk], k=kk, distance_upper_bound=max_offroad, workers=-1)
        if kk == 1:
            dd, ii = dd[:, None], ii[:, None]
        valid = np.isfinite(dd)
        idx[c0 : c0 + chunk] = np.where(valid, ii, -1)
        off[c0 : c0 + chunk] = np.where(valid, dd, np.inf)
    return Neighbors(idx, off)


def _gather(ptr: np.ndarray, values: np.ndarray, keys: np.ndarray) -> np.ndarray:
    """Concatenate values[ptr[k]:ptr[k+1]] for every k in keys (CSR gather)."""
    lens = ptr[keys + 1] - ptr[keys]
    pos = np.repeat(ptr[keys] - (np.cumsum(lens) - lens), lens) + np.arange(lens.sum())
    return values[pos]


def per_station_cells(pts: Points, nb: Neighbors, reach: pd.DataFrame, u, v, limit_m: float) -> pd.DataFrame:
    """Rows (cell, station, dist) for cells within limit_m of each station."""
    u, v = np.asarray(u), np.asarray(v)
    n, P, (C, k) = pts.n_nodes, len(pts.xy), nb.idx.shape
    ends = np.concatenate([u, v])
    order = np.argsort(ends, kind="stable")
    node_ptr = np.searchsorted(ends[order], np.arange(n + 1))
    node_edges = np.concatenate([np.arange(len(u)), np.arange(len(u))])[order]
    flat = nb.idx.ravel()
    valid = flat >= 0
    pt = flat[valid].astype(np.int64)
    cell_of = np.repeat(np.arange(C), k)[valid]
    o2 = np.argsort(pt, kind="stable")
    pt_ptr = np.searchsorted(pt[o2], np.arange(P + 1))
    pt_cells = cell_of[o2]
    idx_safe = np.where(nb.idx >= 0, nb.idx, 0)
    D = np.full(P, np.inf)
    rs = reach.sort_values("station", kind="stable")
    st, nodes_all, d_all = rs["station"].to_numpy(), rs["node"].to_numpy(), rs["dist"].to_numpy(float)
    cut = np.flatnonzero(np.diff(st)) + 1
    out_c, out_s, out_d = [], [], []
    for a0, a1 in zip(np.r_[0, cut], np.r_[cut, len(st)]):
        nodes = nodes_all[a0:a1]
        D[nodes] = d_all[a0:a1]
        eds = np.unique(_gather(node_ptr, node_edges, nodes))
        cnt = pts.edge_count[eds]
        ip = np.repeat(pts.edge_first[eds] - (np.cumsum(cnt) - cnt), cnt) + np.arange(cnt.sum())
        D[ip] = np.minimum(D[pts.a[ip]] + pts.s[ip], D[pts.b[ip]] + (pts.L[ip] - pts.s[ip]))
        aff = np.concatenate([nodes, ip])
        cs = np.unique(_gather(pt_ptr, pt_cells, aff))
        vals = np.min(np.where(nb.idx[cs] >= 0, D[idx_safe[cs]], np.inf) + nb.off[cs], axis=1)
        keep = vals <= limit_m
        out_c.append(cs[keep])
        out_s.append(np.full(int(keep.sum()), st[a0], dtype=np.int32))
        out_d.append(vals[keep].astype(np.float32))
        D[aff] = np.inf
    if not out_c:
        return pd.DataFrame({"cell": [], "station": [], "dist": []})
    return pd.DataFrame({"cell": np.concatenate(out_c), "station": np.concatenate(out_s), "dist": np.concatenate(out_d)})
```

- [ ] `uv run pytest tests/test_cells.py -v` → 3 passed → コミット `feat: per-station cell distances matching ekiwalk's grid rule`

### Task 6: 平滑で隙間のない面

**File: `tests/test_polygons.py`**

```python
import numpy as np
import shapely

from eki_walk.territory.polygons import boundary_segments, cells_polygon, chaikin, smooth_labels


def test_boundary_segments_two_labels():
    lab = np.array([[0, 1], [0, 1]])
    segs = boundary_segments(lab)
    # outer ring (8 unit edges) + the middle line (2 unit edges)
    assert len(segs) == 10


def test_chaikin_keeps_ends_and_rings():
    open_ = chaikin(np.array([[0, 0], [10, 0], [10, 10]], float), closed=False, iterations=2)
    assert tuple(open_[0]) == (0, 0) and tuple(open_[-1]) == (10, 10)
    ring = chaikin(np.array([[0, 0], [10, 0], [10, 10], [0, 0]], float), closed=True, iterations=2)
    assert tuple(ring[0]) == tuple(ring[-1])


def test_smooth_labels_partition_without_gaps_or_overlaps():
    lab = np.full((20, 20), 0)
    lab[:, 10:] = 1
    lab[12:, :8] = 2
    lab[:3, 17:] = -1
    polys = smooth_labels(lab, 1000.0, 2000.0, 25.0, simplify_m=20, iterations=3)
    assert set(polys) == {0, 1, 2}
    total = sum(p.area for p in polys.values())
    assert abs(total - (400 - 9) * 625) / ((400 - 9) * 625) < 0.06  # outer corners get rounded
    for a in polys:
        for b in polys:
            if a < b:
                assert polys[a].intersection(polys[b]).area < 1.0
    assert abs(polys[2].area - 64 * 625) / (64 * 625) < 0.15
    assert polys[0].bounds[0] >= 1000.0 - 1e-6


def test_cells_polygon_window():
    rows = np.array([5, 5, 6, 6])
    cols = np.array([7, 8, 7, 8])
    p = cells_polygon(rows, cols, 0.0, 0.0, 25.0, simplify_m=5, iterations=1)
    assert p.area > 0.8 * 4 * 625
    c = p.centroid
    assert abs(c.x - 200) < 5 and abs(c.y - 150) < 5
```

**File: `src/eki_walk/territory/polygons.py`**

```python
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

FINAL_SIMPLIFY_M = 1.5  # drop the near-collinear points Chaikin adds


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


def smooth_labels(labels: np.ndarray, x0: float, y0: float, cell: float, simplify_m: float, iterations: int) -> dict:
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
```

- [ ] `uv run pytest tests/test_polygons.py -v` → 4 passed → コミット `feat: smooth gap-free polygons from grid labels`

### Task 7: 塗り分け

**File: `tests/test_colors.py`**

```python
import numpy as np
import pytest

from eki_walk.territory.colors import dsatur, raster_adjacency


def test_adjacency_includes_diagonals_and_skips_blank():
    lab = np.array([[0, 1], [2, -1]])
    assert raster_adjacency(lab) == {(0, 1), (0, 2), (1, 2)}


def test_dsatur_gives_neighbours_different_colours():
    lab = np.array([[0, 0, 1, 1], [2, 2, 3, 3], [4, 4, 5, 5]])
    pairs = raster_adjacency(lab)
    col = dsatur(range(6), pairs, max_colors=6)
    assert all(col[a] != col[b] for a, b in pairs)
    assert max(col.values()) < 4


def test_dsatur_raises_when_too_few_colours():
    pairs = {(a, b) for a in range(5) for b in range(5) if a < b}  # K5
    with pytest.raises(ValueError):
        dsatur(range(5), pairs, max_colors=4)
```

**File: `src/eki_walk/territory/colors.py`**

```python
"""Few colours for neighbouring territories (DSatur greedy colouring of the adjacency graph)."""

from __future__ import annotations

import numpy as np


def raster_adjacency(labels: np.ndarray) -> set[tuple[int, int]]:
    """Label pairs (a < b) that touch, including diagonally; -1 is ignored."""
    pairs = []
    for a, b in (
        (labels[:, :-1], labels[:, 1:]),
        (labels[:-1, :], labels[1:, :]),
        (labels[:-1, :-1], labels[1:, 1:]),
        (labels[:-1, 1:], labels[1:, :-1]),
    ):
        m = (a != b) & (a >= 0) & (b >= 0)
        pairs.append(np.column_stack([np.minimum(a[m], b[m]), np.maximum(a[m], b[m])]))
    allp = np.unique(np.concatenate(pairs), axis=0) if pairs else np.empty((0, 2), int)
    return {(int(a), int(b)) for a, b in allp}


def dsatur(nodes, pairs, max_colors: int) -> dict[int, int]:
    adj = {int(v): set() for v in nodes}
    for a, b in pairs:
        adj.setdefault(a, set()).add(b)
        adj.setdefault(b, set()).add(a)
    color: dict[int, int] = {}
    while len(color) < len(adj):
        v = max(
            (x for x in adj if x not in color),
            key=lambda x: (len({color[y] for y in adj[x] if y in color}), len(adj[x]), -x),
        )
        used = {color[y] for y in adj[v] if y in color}
        c = next(i for i in range(len(adj) + 1) if i not in used)
        if c >= max_colors:
            raise ValueError(f"{max_colors} 色では塗り分けられません (駅 {v})")
        color[v] = c
    return color
```

- [ ] `uv run pytest tests/test_colors.py -v` → 3 passed → コミット `feat: colour neighbouring territories differently`

### Task 8: 帯・15 分超・駅数・駅ごとの数字

**File: `tests/test_layers.py`**

```python
import numpy as np
import pandas as pd

from eki_walk.territory.layers import band_mask, counts, group_stats, group_table, second_nearest, to_raster


def test_group_table_takes_nearest_row_per_group():
    ps = pd.DataFrame({"cell": [0, 0, 0, 1], "station": [0, 1, 2, 2], "dist": [300.0, 100.0, 500.0, 50.0]})
    gt = group_table(ps, np.array([7, 7, 9]))
    assert gt.values.tolist() == [[0, 7, 100.0], [0, 9, 500.0], [1, 9, 50.0]]


def test_second_nearest_and_band():
    gt = pd.DataFrame({"cell": [0, 0, 1, 2, 2], "group": [7, 9, 9, 7, 9], "dist": [100.0, 300.0, 50.0, 400.0, 1300.0]})
    near_g = np.array([7, 9, 7])
    near_d = np.array([100.0, 50.0, 400.0])
    second = second_nearest(gt, near_g, 3)
    assert second.tolist() == [300.0, np.inf, 1300.0]
    assert band_mask(near_d, second, 1200, 240).tolist() == [True, False, False]
    assert counts(gt[gt["dist"] <= 1200], 3).tolist() == [2, 1, 1]


def test_group_stats():
    s = group_stats(np.array([0, 0, 1]), np.array([100.0, 1300.0, 50.0]), 25.0, 1200, 3)
    assert s.loc[0, "area_km2"] == 2 * 625 / 1e6
    assert s.loc[0, "far_m"] == 1300.0
    assert s.loc[0, "within"] == 0.5
    assert np.isnan(s.loc[2, "far_m"])


def test_to_raster():
    r = to_raster(np.array([5, 6]), np.array([1, 4]), (2, 3), -1)
    assert r.tolist() == [[-1, 5, -1], [-1, 6, -1]]
```

**File: `src/eki_walk/territory/layers.py`**

```python
"""Per-cell layers: other groups within the limit, the boundary band, far cells, counts and station stats."""

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


def counts(gt_within: pd.DataFrame, n_cells: int) -> np.ndarray:
    c = np.zeros(n_cells, dtype=int)
    vc = gt_within.groupby("cell").size()
    c[vc.index.to_numpy()] = vc.to_numpy()
    return c


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
```

- [ ] `uv run pytest tests/test_layers.py -v` → 4 passed → コミット `feat: band, far and count layers with station stats`

### Task 9: 画面用ファイルの書き出し

**File: `tests/test_export.py`**

```python
import json

import numpy as np
import pandas as pd
from shapely.geometry import box

from eki_walk.territory.export import LonLat, write_cells


def test_lonlat_converts_metres_to_degrees():
    g = LonLat("EPSG:6677")(box(-10000, -40000, -9000, -39000))
    minx, miny, _, _ = g.bounds
    assert 139.6 < minx < 139.8 and 35.5 < miny < 35.7


def test_write_cells_puts_nearest_first(tmp_path):
    cells = np.array([0, 65])  # row 0 col 0, row 1 col 1 (nx = 64)
    near_g, near_d = np.array([3, 4]), np.array([100.2, 1500.0])
    gt = pd.DataFrame({"cell": [0, 0, 0], "group": [3, 5, 6], "dist": [100.2, 700.0, 1300.0]})
    n = write_cells(tmp_path, cells, 64, 64, near_g, near_d, gt, 1200)
    assert n == 1
    arr = json.loads((tmp_path / "cells" / "0_0.json").read_text())
    assert len(arr) == 64 * 64
    assert arr[0] == [3, 101, 5, 700]
    assert arr[65] == [4, 1500]
    assert arr[1] is None
```

**File: `src/eki_walk/territory/export.py`**

```python
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
```

- [ ] `uv run pytest tests/test_export.py -v` → 2 passed → コミット `feat: write territory web data files`

### Task 10: 手順の実行とコマンド

**File: `tests/test_cli.py`**

```python
from eki_walk.cli import build_parser


def test_parser():
    p = build_parser()
    a = p.parse_args(["import-raw", "--from", "../rail-gap-map"])
    assert a.command == "import-raw" and a.src == "../rail-gap-map"
    a = p.parse_args(["build", "--config", "configs/territory.toml", "--from", "territory"])
    assert a.start == "territory"
```

**File: `src/eki_walk/pipeline.py`**

```python
"""Build steps: ekiwalk (network -> water -> admin -> stations -> solve -> surface -> places), then territory."""

from __future__ import annotations

import json
import shutil
import time
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
from eki_walk.territory.cells import cell_neighbors, densify, per_station_cells
from eki_walk.territory.colors import dsatur, raster_adjacency
from eki_walk.territory.export import LonLat, feature, feature_collection, write_cells, write_json
from eki_walk.territory.groups import merge_groups
from eki_walk.territory.layers import band_mask, counts, far_mask, group_stats, group_table, second_nearest, to_raster
from eki_walk.territory.polygons import cells_polygon, smooth_labels
from eki_walk.territory.reach import access_graph, station_reach

STEPS = ["network", "water", "admin", "stations", "solve", "surface", "places", "territory"]
SOURCE_KEYS = ["osm-kanto", "n02", "n03-11", "n03-12", "n03-13", "n03-14", "abr-town-13", "abr-town-pos-13"]


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
        "places": lambda: places.run(region, raw_path(root, "abr-town-13"), raw_path(root, "abr-town-pos-13")),
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
    inside = cell_centers_mask(display, grid.x0, grid.y0, grid.cell, (ny, nx)) & np.isfinite(grid.dist) & (grid.station >= 0)
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
    labels = to_raster(near_g, cells, shape, -1)
    second = second_nearest(gt, near_g, len(cells))
    band = band_mask(near_d, second, cfg.limit_m, cfg.band_m)
    far = far_mask(near_d, cfg.limit_m)
    cnt = np.minimum(counts(gt, len(cells)), cfg.max_count_band)
    stats = group_stats(near_g, near_d, grid.cell, cfg.limit_m, len(groups))

    smooth = dict(simplify_m=cfg.simplify_m, iterations=cfg.chaikin_iterations)
    terr = smooth_labels(labels, grid.x0, grid.y0, grid.cell, **smooth)
    colors = dsatur(sorted(terr), raster_adjacency(labels), cfg.max_colors)
    log(f"territories: {len(terr)}, colours: {max(colors.values()) + 1}")
    count_polys = smooth_labels(to_raster(np.where(cnt > 0, cnt, -1), cells, shape, -1), grid.x0, grid.y0, grid.cell, **smooth)
    r_all, c_all = cells // nx, cells % nx
    band_poly = cells_polygon(r_all[band], c_all[band], grid.x0, grid.y0, grid.cell, **smooth)
    far_poly = cells_polygon(r_all[far], c_all[far], grid.x0, grid.y0, grid.cell, **smooth)

    if out.exists():
        for child in out.iterdir():
            if child.name != "places.json":
                shutil.rmtree(child) if child.is_dir() else child.unlink()
    out.mkdir(parents=True, exist_ok=True)
    ll = LonLat(region.crs)
    write_json(out / "territories.geojson", feature_collection([feature(ll(p), {"g": g, "c": colors[g]}) for g, p in terr.items()]))
    write_json(out / "count.geojson", feature_collection([feature(ll(p), {"n": n}) for n, p in count_polys.items()]))
    write_json(out / "band.geojson", feature_collection([feature(ll(band_poly), {})]))
    write_json(out / "far.geojson", feature_collection([feature(ll(far_poly), {})]))
    write_json(out / "aoi.geojson", feature_collection([feature(ll(display.simplify(10)), {})]))
    gpos = gt[gt["dist"] <= cfg.limit_m]
    n_iso = 0
    for g, part in gpos.groupby("group"):
        cp = cells[part["cell"].to_numpy()]
        poly = cells_polygon(cp // nx, cp % nx, grid.x0, grid.y0, grid.cell, **smooth)
        write_json(out / "iso" / f"{int(g)}.json", feature(ll(poly), {"g": int(g)}))
        n_iso += 1
    n_chunks = write_cells(out, cells, nx, cfg.chunk_cells, near_g, near_d, gt, cfg.limit_m)

    station_list = []
    for g, row in groups.iterrows():
        lon, lat = ll.point(row["x"], row["y"])
        s = stats.loc[g]
        station_list.append(
            {
                "id": int(g),
                "name": row["name"],
                "lon": lon,
                "lat": lat,
                "lines": row["lines"],
                "c": colors.get(int(g)),
                "area_km2": None if pd.isna(s["far_m"]) else round(float(s["area_km2"]), 2),
                "far_m": None if pd.isna(s["far_m"]) else int(np.ceil(s["far_m"])),
                "within": None if pd.isna(s["far_m"]) else round(float(s["within"]), 3),
            }
        )
    write_json(out / "stations.json", station_list)

    manifest = json.loads((paths.RAW / "manifest.json").read_text(encoding="utf-8"))
    meta = {
        "built_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "region": region.name,
        "label": region.label,
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
        "sources": {k: {f: manifest[k].get(f) for f in ("url", "file", "bytes", "sha256", "retrieved_utc")} for k in SOURCE_KEYS if k in manifest},
        "counts": {"cells": int(len(cells)), "stations": len(station_list), "territories": len(terr), "chunks": n_chunks, "iso": n_iso},
    }
    write_json(out / "meta.json", meta)
    log(f"written to {out}")
```

**File: `src/eki_walk/cli.py`**

```python
"""eki-walk import-raw --from ../rail-gap-map | eki-walk build --config configs/territory.toml"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from eki_walk import paths, pipeline
from eki_walk.config import load_config
from eki_walk.raw import import_raw


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="eki-walk")
    sub = p.add_subparsers(dest="command", required=True)
    i = sub.add_parser("import-raw", help="copy raw files from a local rail-gap-map checkout (SHA-256 checked)")
    i.add_argument("--from", dest="src", required=True)
    i.add_argument("keys", nargs="*")
    b = sub.add_parser("build", help="run ekiwalk steps, then the territory step")
    b.add_argument("--config", required=True)
    b.add_argument("--from", dest="start", choices=pipeline.STEPS, default="network")
    return p


def main(argv=None) -> None:
    a = build_parser().parse_args(argv)
    if a.command == "import-raw":
        man = import_raw(Path(a.src).resolve(), paths.ROOT, a.keys or None)
        print(json.dumps({k: {"file": v["file"], "bytes": v["bytes"]} for k, v in man.items()}, ensure_ascii=False, indent=2))
    elif a.command == "build":
        pipeline.run_build(load_config(a.config), a.start)


if __name__ == "__main__":
    main()
```

- [ ] 旧コード・旧テスト・旧設定を消す (`git rm`)。`src/eki_walk/paths.py` と `units.py` と `tests/test_units.py` は残す。
- [ ] `uv remove h3 geopandas pyogrio duckdb` (使わなくなった依存。`ekiwalk` が必要とするものは `ekiwalk` 側の依存で入る)
- [ ] `.gitignore` に `/web/data/` を足す
- [ ] `uv run pytest -v` → 全部通る → コミット `feat: territory pipeline and CLI; remove walk15 pipeline`

### Task 11: 試運転 (大泉学園町付近)

- [ ] `uv run eki-walk import-raw --from ../rail-gap-map` (生データを写す。ダウンロードはしない)
- [ ] `uv run eki-walk build --config configs/territory-oizumi.toml` — 時間・件数・一致の点検 (max diff・missing) を記録
- [ ] 出力 (`web/data/oizumi-test/`) の大きさを見る

### Task 12: 画面

**File: `web/index.html`**

```html
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>駅の縄張りマップ</title>
  <meta name="description" content="住んでいる所・これから住む所が、どの駅の勢力圏 (縄張り) に入るかを、歩く道のりで示す地図です。">
  <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/maplibre-gl@6.11.2/dist/maplibre-gl.css">
  <link rel="stylesheet" href="style.css">
</head>
<body>
  <header id="bar">
    <h1>駅の縄張りマップ</h1>
    <form id="search" role="search" autocomplete="off">
      <input id="q" type="search" placeholder="駅名・町丁目で探す" aria-label="駅名・町丁目で探す">
      <ul id="hits" hidden></ul>
    </form>
    <button id="locate" type="button">現在地</button>
    <div class="seg" role="group" aria-label="表示">
      <button type="button" data-mode="territory" aria-pressed="true">縄張り</button>
      <button type="button" data-mode="count" aria-pressed="false">駅の数</button>
    </div>
    <div class="seg" role="group" aria-label="背景">
      <button type="button" data-base="map" aria-pressed="true">地図</button>
      <button type="button" data-base="photo" aria-pressed="false">航空写真</button>
    </div>
    <button id="about-open" type="button">このマップについて</button>
  </header>
  <main id="map" aria-label="地図"></main>
  <div id="legend" aria-label="凡例"></div>
  <p id="hint">地図を押すと、その地点がどの駅の勢力圏かを表示します。駅名を押すと、その駅の縄張りを表示します。</p>
  <section id="panel" hidden aria-live="polite">
    <button id="panel-close" type="button" aria-label="閉じる">×</button>
    <div id="result"></div>
    <p class="note">道のりで測った目安です。<button type="button" class="link" data-open-about>この計算の限界</button></p>
  </section>
  <dialog id="about">
    <h2>このマップについて</h2>
    <p>色分けは、歩く道のりでいちばん近い駅の範囲 (駅の「縄張り」) です。となり合う縄張りは別の色にしています。80m を 1 分として、端数は切り上げています。</p>
    <ul>
      <li>斜線: となりの駅とほぼ同じ近さ (差 3 分以内) の所です。</li>
      <li>色の薄い所: いちばん近い駅まで 15 分を超える所です。</li>
      <li>同じ名前の乗換駅は、600m 以内なら 1 駅にまとめています (名前の違う乗換駅はまとめていません)。</li>
    </ul>
    <h3>この計算の限界</h3>
    <ul>
      <li>道のりは、ホームの線から 100m 以内の道を起点に測っています。駅の出口からではありません。</li>
      <li>信号待ち・坂・階段・踏切・地下の上り下りは入れていません。</li>
      <li>縄張りの境界は見やすさのために滑らかにしています (位置のずれは数十 m 程度)。</li>
      <li>道から 300m を超える所、海・川・池は空白です。</li>
      <li>物件広告の「徒歩○分」(駅の出入口から物件の敷地まで) とは測り方が違います。</li>
    </ul>
    <h3>出典</h3>
    <ul>
      <li>道路・水面: © OpenStreetMap contributors (ODbL) <span data-meta="osm"></span></li>
      <li>駅・行政区域: 「国土数値情報（鉄道データ・行政区域データ）」（国土交通省）を加工して作成 <span data-meta="ksj"></span></li>
      <li>町丁目の検索: 「アドレス・ベース・レジストリ」（デジタル庁）を加工して作成</li>
      <li>背景地図: OpenFreeMap © OpenMapTiles, Data from OpenStreetMap / 航空写真: 地理院タイル</li>
      <li>計算: <a href="https://github.com/isshiki/eki-walk">eki-walk</a> と <a href="https://github.com/isshiki/rail-gap-map">rail-gap-map</a> の ekiwalk <span data-meta="ekiwalk"></span></li>
    </ul>
    <p>計算した縄張り・道のりのデータは ODbL で提供します。プログラムは Apache-2.0 です。<span data-meta="built"></span></p>
    <p>現在地と検索の文字はブラウザの中だけで使い、外へは送りません。</p>
    <form method="dialog"><button>閉じる</button></form>
  </dialog>
  <script type="module" src="app.js"></script>
</body>
</html>
```

**File: `web/app.js`**

```js
import * as maplibregl from "https://cdn.jsdelivr.net/npm/maplibre-gl@6.11.2/dist/maplibre-gl.mjs";
import proj4 from "https://cdn.jsdelivr.net/npm/proj4@2.22.0/+esm";
import { search } from "./js/search.js";
import { pointInFeature } from "./js/lookup.js";

const REGION = new URLSearchParams(location.search).get("region") || "tokyo";
const DATA = `data/${REGION}/`;
const STYLE = "https://tiles.openfreemap.org/styles/liberty";
const PHOTO = "https://cyberjapandata.gsi.go.jp/xyz/seamlessphoto/{z}/{x}/{y}.jpg";
const PALETTE = ["#8dd3c7", "#fdb462", "#bebada", "#80b1d3", "#b3de69", "#fccde5"];
const COUNT = ["#cfe3f3", "#9dc7e8", "#5fa3d6", "#2f74b5", "#163f7a"];
const OWN = "#c2410c";
const OTHER = "#1d4ed8";

const state = { chunks: new Map(), iso: new Map(), marker: null, isoReq: 0, places: null };
const $ = (id) => document.getElementById(id);
const minutes = (m) => Math.max(1, Math.ceil(m / state.meta.m_per_min - 1e-9));
const approx = (m) => `約${(Math.round(m / 10) * 10).toLocaleString()}m`;

async function getJSON(path) {
  const r = await fetch(DATA + path);
  if (!r.ok) throw new Error(`${path}: ${r.status}`);
  return r.json();
}

function el(tag, attrs = {}, ...children) {
  const e = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") e.className = v;
    else if (k.startsWith("on")) e.addEventListener(k.slice(2), v);
    else e.setAttribute(k, v);
  }
  for (const c of children) e.append(c);
  return e;
}

// --- data lookups ---
function loadChunk(cx, cy) {
  const key = `${cx}_${cy}`;
  if (!state.chunks.has(key)) {
    state.chunks.set(key, fetch(`${DATA}cells/${key}.json`).then((r) => (r.ok ? r.json() : null)));
  }
  return state.chunks.get(key);
}

async function cellValues(lng, lat) {
  const g = state.meta.grid;
  const [x, y] = proj4("EPSG:4326", g.proj4, [lng, lat]);
  const c = Math.floor((x - g.x0) / g.cell);
  const r = Math.floor((y - g.y0) / g.cell);
  if (c < 0 || r < 0 || c >= g.nx || r >= g.ny) return null;
  const arr = await loadChunk(Math.floor(c / g.chunk), Math.floor(r / g.chunk));
  const v = arr?.[(r % g.chunk) * g.chunk + (c % g.chunk)];
  if (!v) return null;
  const out = [];
  for (let i = 0; i < v.length; i += 2) out.push({ g: v[i], d: v[i + 1] });
  return out;
}

function ownerAt(lng, lat) {
  const f = state.territories.features.find((f) => pointInFeature([lng, lat], f));
  return f ? f.properties.g : null;
}

async function lookup(lng, lat) {
  if (!state.aoi.features.some((f) => pointInFeature([lng, lat], f))) return { status: "outside" };
  const vals = await cellValues(lng, lat);
  if (!vals) return { status: "blank" };
  const owner = ownerAt(lng, lat) ?? vals[0].g;
  const ownD = (vals.find((x) => x.g === owner) ?? vals[0]).d;
  const others = vals.filter((x) => x.g !== owner && x.d <= state.meta.limit_m).sort((a, b) => a.d - b.d);
  return { status: "ok", owner, ownD, others };
}

function loadIso(id) {
  if (!state.iso.has(id)) state.iso.set(id, fetch(`${DATA}iso/${id}.json`).then((r) => (r.ok ? r.json() : null)));
  return state.iso.get(id);
}

async function highlight(owner, others) {
  const req = ++state.isoReq;
  map.setFilter("sel-line", ["==", ["get", "g"], owner ?? -1]);
  map.setFilter("st-sel", ["==", ["get", "id"], owner ?? -1]);
  const ids = owner == null ? [] : [owner, ...others];
  const feats = (await Promise.all(ids.map(loadIso))).filter(Boolean);
  if (req !== state.isoReq) return;
  map.getSource("iso").setData({
    type: "FeatureCollection",
    features: feats.map((f) => ({ ...f, properties: { g: f.properties.g, own: f.properties.g === owner } })),
  });
}

// --- panels ---
const station = (g) => state.stations[g];
const lineText = (s) => s.lines.map((l) => l.line).join("・");

function showPanel(...children) {
  $("result").replaceChildren(...children);
  $("panel").hidden = false;
  $("hint").hidden = true;
}

function renderPoint(res) {
  if (res.status === "outside") {
    showPanel(el("p", { class: "status" }, `対象範囲の外です (${state.meta.label})。`));
    highlight(null, []);
    return;
  }
  if (res.status === "blank") {
    showPanel(el("p", { class: "status" }, "この地点は計算していません (海・川・池や、道から遠い所です)。"));
    highlight(null, []);
    return;
  }
  const own = station(res.owner);
  const head = el("h2", {}, "ここは ", el("b", {}, `${own.name}駅`), ` の勢力圏 (徒歩 ${minutes(res.ownD)} 分)`);
  const sub =
    res.others.length > 0
      ? el("p", {}, `${res.others.map((o) => `${station(o.g).name}駅 (${minutes(o.d)} 分)`).join("・")} の 15 分圏とも重なります。`)
      : res.ownD > state.meta.limit_m
        ? el("p", {}, "徒歩 15 分以内に行ける駅はありません。")
        : el("p", {}, "ほかの駅の 15 分圏とは重なりません。");
  const rows = [{ g: res.owner, d: res.ownD, own: true }, ...res.others].map((o) =>
    el(
      "tr",
      { class: o.own ? "own" : "" },
      el("td", {}, el("button", { type: "button", class: "link", onclick: () => selectStation(o.g, false) }, station(o.g).name)),
      el("td", { class: "sub" }, lineText(station(o.g))),
      el("td", { class: "r" }, el("b", {}, `${minutes(o.d)} 分`), ` ${approx(o.d)}`),
    ),
  );
  showPanel(head, sub, el("table", {}, ...rows), el("p", { class: "sub" }, "太線 = 勢力圏の駅の縄張り / 破線 = 15 分圏 (橙: 勢力圏の駅、青: 重なる駅)"));
  highlight(res.owner, res.others.map((o) => o.g));
}

function renderStation(g) {
  const s = station(g);
  const stats =
    s.area_km2 == null
      ? [el("tr", {}, el("td", {}, "縄張り"), el("td", { class: "r" }, "対象範囲の外"))]
      : [
          el("tr", {}, el("td", {}, "縄張りの広さ"), el("td", { class: "r" }, el("b", {}, `${s.area_km2} km²`))),
          el("tr", {}, el("td", {}, "縄張りでいちばん遠い所"), el("td", { class: "r" }, el("b", {}, `徒歩 ${minutes(s.far_m)} 分`), ` (${approx(s.far_m)})`)),
          el("tr", {}, el("td", {}, "縄張りのうち 15 分以内"), el("td", { class: "r" }, el("b", {}, `${Math.round(s.within * 100)}%`))),
        ];
  showPanel(
    el("h2", {}, `${s.name}駅の縄張り`),
    el("p", { class: "sub" }, lineText(s)),
    el("table", {}, ...stats),
    el("p", { class: "sub" }, "太線 = 縄張り / 破線 = 15 分圏 (縄張りの外にもはみ出します)"),
  );
  highlight(g, []);
}

async function showPoint(lng, lat) {
  if (!state.marker) state.marker = new maplibregl.Marker({ color: OWN });
  state.marker.setLngLat([lng, lat]).addTo(map);
  await ready;
  renderPoint(await lookup(lng, lat));
}

async function selectStation(g, fly = true) {
  await ready;
  state.marker?.remove();
  if (fly) map.flyTo({ center: [station(g).lon, station(g).lat], zoom: 14 });
  renderStation(g);
}

// --- map ---
const map = new maplibregl.Map({
  container: "map",
  style: STYLE,
  center: [139.6, 35.69],
  zoom: 10,
  hash: true,
  attributionControl: {
    compact: true,
    customAttribution: [
      "道路: © OpenStreetMap contributors (ODbL)",
      "駅・行政区域: 国土数値情報（国土交通省）を加工",
      "町丁目: アドレス・ベース・レジストリ（デジタル庁）を加工",
    ],
  },
});
map.addControl(new maplibregl.NavigationControl({ showCompass: false }), "bottom-right");

const dataReady = Promise.all([getJSON("meta.json"), getJSON("stations.json"), getJSON("territories.geojson"), getJSON("aoi.geojson")]).then(
  ([meta, stations, territories, aoi]) => {
    Object.assign(state, { meta, stations, territories, aoi });
    if (!location.hash && meta.home_view) map.jumpTo({ center: meta.home_view.center, zoom: meta.home_view.zoom + 1 });
    fillMeta();
    setMode("territory");
  },
);

function japaneseLabels() {
  for (const layer of map.getStyle().layers) {
    const tf = layer.layout?.["text-field"];
    if (tf && JSON.stringify(tf).includes("name")) {
      map.setLayoutProperty(layer.id, "text-field", ["coalesce", ["get", "name:ja"], ["get", "name"]]);
    }
    if (layer.id.startsWith("poi_")) map.setLayoutProperty(layer.id, "visibility", "none");
  }
}

// Our fills go above every basemap fill (buildings included) and below the labels that follow them.
function overlayAnchor() {
  const layers = map.getStyle().layers;
  let last = -1;
  layers.forEach((l, i) => {
    if (l.type === "fill" || l.type === "fill-extrusion") last = i;
  });
  return layers.slice(last + 1).find((l) => l.type === "symbol")?.id;
}

function hatch() {
  const cv = document.createElement("canvas");
  cv.width = cv.height = 12;
  const cx = cv.getContext("2d");
  cx.strokeStyle = "rgba(40,40,40,0.55)";
  cx.lineWidth = 1.4;
  for (const o of [-12, 0, 12]) {
    cx.beginPath();
    cx.moveTo(o, 12);
    cx.lineTo(o + 12, 0);
    cx.stroke();
  }
  return cx.getImageData(0, 0, 12, 12);
}

function addOverlays() {
  const below = overlayAnchor();
  map.addImage("hatch", hatch());
  map.addSource("photo", {
    type: "raster", tiles: [PHOTO], tileSize: 256, maxzoom: 18,
    attribution: '<a href="https://maps.gsi.go.jp/development/ichiran.html">地理院タイル</a>',
  });
  map.addLayer({ id: "photo", type: "raster", source: "photo", layout: { visibility: "none" } }, below);
  map.addSource("t", { type: "geojson", data: state.territories });
  const colorExpr = ["match", ["get", "c"], 0, PALETTE[0], 1, PALETTE[1], 2, PALETTE[2], 3, PALETTE[3], 4, PALETTE[4], PALETTE[5]];
  map.addLayer({ id: "t-fill", type: "fill", source: "t", paint: { "fill-color": colorExpr, "fill-opacity": 0.55 } }, below);
  map.addSource("far", { type: "geojson", data: DATA + "far.geojson" });
  map.addLayer({ id: "far", type: "fill", source: "far", paint: { "fill-color": "#fff", "fill-opacity": 0.55 } }, below);
  map.addSource("band", { type: "geojson", data: DATA + "band.geojson" });
  map.addLayer({ id: "band", type: "fill", source: "band", paint: { "fill-pattern": "hatch", "fill-opacity": 0.6 } }, below);
  map.addLayer({
    id: "t-line", type: "line", source: "t",
    paint: { "line-color": "#3a3f45", "line-width": ["interpolate", ["linear"], ["zoom"], 10, 0.4, 13, 0.9, 16, 1.8] },
  }, below);
  map.addSource("count", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  map.addLayer({
    id: "count", type: "fill", source: "count", layout: { visibility: "none" },
    paint: { "fill-color": ["match", ["get", "n"], 1, COUNT[0], 2, COUNT[1], 3, COUNT[2], 4, COUNT[3], COUNT[4]], "fill-opacity": 0.5 },
  }, below);
  map.addSource("aoi", { type: "geojson", data: state.aoi });
  map.addLayer({ id: "aoi", type: "line", source: "aoi", paint: { "line-color": "#555", "line-width": 1, "line-dasharray": [2, 2] } }, below);
  map.addSource("iso", { type: "geojson", data: { type: "FeatureCollection", features: [] } });
  map.addLayer({ id: "sel-line", type: "line", source: "t", filter: ["==", ["get", "g"], -1], paint: { "line-color": OWN, "line-width": 4 } });
  map.addLayer({ id: "iso-own", type: "line", source: "iso", filter: ["==", ["get", "own"], true], paint: { "line-color": OWN, "line-width": 2, "line-dasharray": [3, 2] } });
  map.addLayer({ id: "iso-other", type: "line", source: "iso", filter: ["==", ["get", "own"], false], paint: { "line-color": OTHER, "line-width": 1.6, "line-dasharray": [3, 2] } });
  map.addSource("st", {
    type: "geojson",
    data: {
      type: "FeatureCollection",
      features: state.stations.map((s) => ({ type: "Feature", properties: { id: s.id, name: s.name }, geometry: { type: "Point", coordinates: [s.lon, s.lat] } })),
    },
  });
  map.addLayer({ id: "st-dot", type: "circle", source: "st", minzoom: 11, paint: { "circle-radius": 4, "circle-color": "#fff", "circle-stroke-color": "#1f2328", "circle-stroke-width": 2 } });
  map.addLayer({ id: "st-sel", type: "circle", source: "st", filter: ["==", ["get", "id"], -1], paint: { "circle-radius": 7, "circle-color": OWN, "circle-stroke-color": "#fff", "circle-stroke-width": 2 } });
  map.addLayer({
    id: "st-name", type: "symbol", source: "st", minzoom: 11.5,
    layout: { "text-field": ["get", "name"], "text-font": ["Noto Sans Bold"], "text-size": 13, "text-offset": [0, 1.0], "text-anchor": "top" },
    paint: { "text-color": "#111", "text-halo-color": "#fff", "text-halo-width": 2 },
  });
}

const ready = new Promise((resolve) => {
  map.once("style.load", async () => {
    japaneseLabels();
    await dataReady;
    addOverlays();
    resolve();
  });
});

map.on("click", async (e) => {
  await ready;
  const hit = map.queryRenderedFeatures(e.point, { layers: ["st-dot", "st-name"] })[0];
  if (hit) selectStation(hit.properties.id, false);
  else showPoint(e.lngLat.lng, e.lngLat.lat);
});
for (const id of ["st-dot", "st-name"]) {
  map.on("mouseenter", id, () => (map.getCanvas().style.cursor = "pointer"));
  map.on("mouseleave", id, () => (map.getCanvas().style.cursor = ""));
}

// --- controls ---
let countLoaded = false;
async function setMode(mode) {
  for (const b of document.querySelectorAll("[data-mode]")) b.setAttribute("aria-pressed", String(b.dataset.mode === mode));
  await ready;
  if (mode === "count" && !countLoaded) {
    map.getSource("count").setData(DATA + "count.geojson");
    countLoaded = true;
  }
  const show = (ids, on) => ids.forEach((id) => map.setLayoutProperty(id, "visibility", on ? "visible" : "none"));
  show(["t-fill", "far", "band", "t-line"], mode === "territory");
  show(["count"], mode === "count");
  $("legend").replaceChildren(...legend(mode));
}

function legend(mode) {
  if (mode === "count") {
    return [
      el("div", {}, "徒歩 15 分以内の駅の数"),
      el("div", {}, ...COUNT.map((c, i) => el("span", { class: "item" }, el("i", { class: "sw", style: `background:${c}` }), i === 4 ? "5+" : String(i + 1)))),
    ];
  }
  return [
    el("div", {}, ...PALETTE.slice(0, 4).map((c) => el("i", { class: "sw", style: `background:${c}` })), " 駅ごとの縄張り"),
    el("div", {}, el("i", { class: "sw hatch" }), " となりの駅とほぼ同じ (差 3 分以内)"),
    el("div", {}, el("i", { class: "sw pale" }), " いちばん近い駅まで 15 分超"),
  ];
}

for (const b of document.querySelectorAll("[data-mode]")) b.addEventListener("click", () => setMode(b.dataset.mode));
for (const b of document.querySelectorAll("[data-base]")) {
  b.addEventListener("click", async () => {
    await ready;
    map.setLayoutProperty("photo", "visibility", b.dataset.base === "photo" ? "visible" : "none");
    for (const x of document.querySelectorAll("[data-base]")) x.setAttribute("aria-pressed", String(x === b));
  });
}

$("locate").addEventListener("click", () => {
  if (!navigator.geolocation) return alert("このブラウザでは現在地を使えません。");
  navigator.geolocation.getCurrentPosition(
    (p) => {
      const { longitude: lng, latitude: lat } = p.coords;
      map.flyTo({ center: [lng, lat], zoom: 16 });
      showPoint(lng, lat);
    },
    () => alert("現在地を取得できませんでした。"),
    { enableHighAccuracy: true, timeout: 10000 },
  );
});

$("panel-close").addEventListener("click", () => {
  $("panel").hidden = true;
  state.marker?.remove();
  highlight(null, []);
});

const about = $("about");
for (const b of document.querySelectorAll("#about-open, [data-open-about]")) b.addEventListener("click", () => about.showModal());

function fillMeta() {
  const s = state.meta.sources;
  const date = (k) => s[k]?.file ?? "";
  document.querySelector('[data-meta="osm"]').textContent = `(${date("osm-kanto")})`;
  document.querySelector('[data-meta="ksj"]').textContent = `(${date("n02")}, N03 2026)`;
  document.querySelector('[data-meta="ekiwalk"]').textContent = `(${state.meta.ekiwalk.commit.slice(0, 7)})`;
  document.querySelector('[data-meta="built"]').textContent = ` 計算日: ${state.meta.built_at_utc.slice(0, 10)}`;
}

// --- search (places.json is loaded on first use) ---
async function places() {
  if (!state.places) state.places = await getJSON("places.json");
  return state.places;
}

function stationForPlace(row) {
  const name = row[0].replace(/駅$/, "");
  const cands = state.stations.filter((s) => s.name === name);
  const pool = cands.length ? cands : state.stations;
  return pool.reduce((best, s) => {
    const d = (s.lon - row[2]) ** 2 + (s.lat - row[3]) ** 2;
    return !best || d < best.d ? { s, d } : best;
  }, null).s;
}

function choose(row) {
  $("hits").hidden = true;
  $("q").value = row[0];
  if (row[4] === "s") {
    selectStation(stationForPlace(row).id, true);
  } else {
    map.flyTo({ center: [row[2], row[3]], zoom: 16 });
    showPoint(row[2], row[3]);
  }
}

let timer = 0;
$("q").addEventListener("input", () => {
  clearTimeout(timer);
  timer = setTimeout(async () => {
    const q = $("q").value.trim();
    const hits = q ? search(await places(), q, 8) : [];
    $("hits").replaceChildren(
      ...hits.map((row) =>
        el("li", {}, el("button", { type: "button", onclick: () => choose(row) }, row[0], el("span", { class: "kind" }, row[4] === "s" ? "駅" : "町丁目"))),
      ),
    );
    $("hits").hidden = hits.length === 0;
  }, 150);
});
$("search").addEventListener("submit", async (e) => {
  e.preventDefault();
  const hit = search(await places(), $("q").value.trim(), 1)[0];
  if (hit) choose(hit);
});

// the legacy walk15 hash (#zoom/lat/lng) keeps working; ?point=lat,lng opens a point
const pt = new URLSearchParams(location.search).get("point");
if (pt) {
  const [lat, lng] = pt.split(",").map(Number);
  if (Number.isFinite(lat) && Number.isFinite(lng)) showPoint(lng, lat);
}
```

**File: `web/style.css`**

```css
:root {
  --accent: #c2410c; --fg: #1f2328; --muted: #57606a; --bg: #ffffff; --line: #d0d7de;
  font-family: system-ui, -apple-system, "Hiragino Sans", "Noto Sans JP", "Yu Gothic UI", sans-serif;
  color: var(--fg);
}
* { box-sizing: border-box; }
html, body { margin: 0; height: 100%; background: var(--bg); }
#map { position: absolute; inset: 0; }
#bar {
  position: absolute; z-index: 3; top: 8px; left: 8px; right: 8px;
  display: flex; flex-wrap: wrap; gap: 6px; align-items: center;
  padding: 6px 8px; background: rgba(255, 255, 255, .96); border: 1px solid var(--line); border-radius: 8px;
}
#bar h1 { font-size: 15px; margin: 0 6px 0 2px; white-space: nowrap; }
#search { position: relative; margin: 0; }
#q { width: 15em; padding: 5px 8px; font-size: 14px; border: 1px solid var(--line); border-radius: 6px; }
#hits {
  position: absolute; top: 34px; left: 0; width: 22em; max-width: calc(100vw - 32px); margin: 0; padding: 4px 0;
  list-style: none; background: #fff; border: 1px solid var(--line); border-radius: 6px; box-shadow: 0 2px 10px rgba(0, 0, 0, .12);
}
#hits[hidden] { display: none; }
#hits button { display: flex; justify-content: space-between; width: 100%; border: 0; border-radius: 0; text-align: left; }
#hits button:hover, #hits button:focus-visible { background: #f3f4f6; }
#hits .kind { color: var(--muted); font-size: 12px; margin-left: 8px; }
button { font: inherit; font-size: 13px; padding: 5px 9px; cursor: pointer; border: 1px solid var(--line); border-radius: 6px; background: #fff; color: var(--fg); }
button[aria-pressed="true"] { background: var(--fg); color: #fff; border-color: var(--fg); }
.seg { display: inline-flex; }
.seg button:first-child { border-radius: 6px 0 0 6px; }
.seg button:last-child { border-radius: 0 6px 6px 0; border-left: 0; }
#legend {
  position: absolute; z-index: 1; left: 8px; bottom: 28px; padding: 6px 8px; font-size: 12px; line-height: 1.8;
  background: rgba(255, 255, 255, .94); border: 1px solid var(--line); border-radius: 6px;
}
#legend .item { margin-right: 8px; }
.sw { display: inline-block; width: 12px; height: 12px; margin-right: 2px; vertical-align: -2px; border: 1px solid #666; }
.sw.hatch { background: repeating-linear-gradient(135deg, rgba(40, 40, 40, .55) 0 1.5px, transparent 1.5px 6px); }
.sw.pale { background: #f4f4f4; }
#hint {
  position: absolute; z-index: 1; left: 50%; bottom: 28px; transform: translateX(-50%); margin: 0; padding: 6px 10px;
  font-size: 13px; max-width: min(560px, calc(100% - 16px)); background: rgba(255, 255, 255, .94); border: 1px solid var(--line); border-radius: 6px;
}
#hint[hidden] { display: none; }
#panel {
  position: absolute; z-index: 2; top: 64px; right: 8px; width: 360px; max-height: calc(100% - 100px); overflow: auto;
  padding: 12px 14px; background: #fff; border: 1px solid var(--line); border-radius: 8px; box-shadow: 0 2px 10px rgba(0, 0, 0, .12);
  font-size: 14px; line-height: 1.55;
}
#panel[hidden] { display: none; }
#panel h2 { font-size: 17px; margin: 0 24px 6px 0; }
#panel p { margin: 4px 0; }
#panel table { border-collapse: collapse; width: 100%; margin-top: 6px; font-size: 13px; }
#panel td { padding: 4px; border-top: 1px solid #eaeef2; vertical-align: top; }
#panel tr.own td { background: #fff7ed; }
#panel td.r { text-align: right; white-space: nowrap; }
#panel-close { position: absolute; top: 6px; right: 6px; border: 0; font-size: 18px; line-height: 1; }
.sub { color: var(--muted); font-size: 12px; }
.status { margin: 0 24px 0 0; }
.note { font-size: 12px; color: var(--muted); }
.link { border: 0; padding: 0; background: none; color: #0969da; text-decoration: underline; font-size: inherit; }
dialog { max-width: min(600px, calc(100% - 32px)); padding: 16px 20px; font-size: 14px; line-height: 1.6; border: 1px solid var(--line); border-radius: 8px; }
dialog h2 { font-size: 18px; margin-top: 0; }
dialog h3 { font-size: 15px; margin-bottom: 4px; }
@media (max-width: 640px) {
  #bar h1 { flex: 1 1 auto; }
  #search { order: 1; flex: 1 1 100%; }
  #q { width: 100%; }
  #hits { width: 100%; }
  #legend { bottom: auto; top: 128px; }
  #hint { bottom: auto; top: 200px; left: 8px; transform: none; }
  #panel { top: auto; bottom: 0; left: 0; right: 0; width: auto; max-height: 55%; border-radius: 12px 12px 0 0; }
}
```

`web/js/search.js` と `web/js/lookup.js` は `git -C ../rail-gap-map show 4176263:web/js/<name>.js` をそのまま写し、先頭に次の 1 行を足す:
`// Copied from isshiki/rail-gap-map@4176263 web/js/<name>.js (Apache-2.0).`

**File: `web/walk15/index.html`**

```html
<!doctype html>
<html lang="ja">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>駅の縄張りマップへ移動しました</title>
  <script>location.replace("../" + location.hash);</script>
  <meta http-equiv="refresh" content="0; url=../">
</head>
<body>
  <p>「徒歩15分 駅マップ」は <a href="../">駅の縄張りマップ</a> に変わりました。</p>
</body>
</html>
```

- [ ] proj4 の ESM が `https://cdn.jsdelivr.net/npm/proj4@2.22.0/+esm` で読めることを確かめる (読めなければ版を変えずに別の配布形 (dist) を使う)
- [ ] コミット `feat: add station territory map web app`

### Task 13: 画面の確認 (試運転のデータ)

- [ ] `uv run python -m http.server 8815 -d web --bind 127.0.0.1` を起動し、`http://127.0.0.1:8815/?region=oizumi-test` を開く
- [ ] 縄張りの塗り分け・境界線・駅名・帯・薄い所、地点を押したときの文と破線、駅を押したときの数字、検索 (駅・町丁目)、駅の数への切り替え、航空写真、スマホ幅、コンソールのエラーなし

### Task 14: 東京全域

- [ ] `uv run eki-walk build --config configs/territory.toml` — 時間・メモリ・一致の点検・大きさ (合計、最初に読むもの) を記録
- [ ] 最初に読むもの (territories・band・far・stations・aoi・meta) が合計 5MB を超えたら `simplify_m` を上げて作り直す
- [ ] 乗換駅 5 組 (池袋・武蔵小杉・両国・東京・浅草) が 1 駅になっていること、早稲田が 2 つあることを `stations.json` で確かめる
- [ ] 画面で、高円寺・新宿・都境 (赤羽)・奥多摩・東京湾岸を確かめる

### Task 15: 文書

- [ ] `README.md` (縄張りマップの説明、手順 `import-raw` → `build`、ライセンス)、`AGENTS.md` (ekiwalk 依存と生データの写し方)、`docs/data-sources.md` (OSM・N03 4 都県・ABR を足し、Overture は旧版へ)、`docs/method.md` (縄張りの作り方)、`docs/validation.md` (一致の点検・画面の確認) を書き換え、walk15 の記録は `docs/walk15/` に移す
- [ ] コミット `docs: describe the station territory map`

### Task 16: 公開 (利用者の確認が要る)

- [ ] `territory` ブランチを main にマージしてよいか、push してよいか確認を取る
- [ ] gh-pages を置き換えてよいか確認を取る: 中身は `web/` (index.html・app.js・style.css・js/・data/tokyo/・walk15/index.html) と `.nojekyll`、`data/tokyo/README.md` (データのライセンス)。`data/oizumi-test` は含めない

---

## 自己点検

- 設計書の各節 → タスク: 2 (Task 1)、3.1 (Task 1・10・11)、3.2 (Task 3〜10)、3.3 (Task 10・15)、4 (Task 2・15)、5 (Task 4〜8)、6 (Task 9・10)、7 (Task 12・13)、8 (Task 12・15)、9 (各タスクのテスト・Task 13・14)。
- 型と名前: `merge_groups` → `(row_group, groups)`、`access_graph`/`station_reach`、`densify`/`cell_neighbors`/`per_station_cells`、`smooth_labels`/`cells_polygon`、`raster_adjacency`/`dsatur`、`group_table`/`second_nearest`/`band_mask`/`far_mask`/`counts`/`group_stats`/`to_raster`、`LonLat`/`write_cells` を pipeline で同じ名前で使っている。
