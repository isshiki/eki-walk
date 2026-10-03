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
    min_island_cells: int
    min_hole_m2: float
    # drawing: the region boundary (coast, prefecture borders) is simplified together with these regions
    # (their admin step must be done), so that neighbouring regions still meet exactly; 0 keeps it exact
    edge_regions: tuple[str, ...] = ()
    edge_simplify_m: float = 0.0


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
        min_island_cells=int(d["min_island_cells"]),
        min_hole_m2=float(d["min_hole_m2"]),
        edge_regions=tuple(d.get("edge_regions", ())),
        edge_simplify_m=float(d.get("edge_simplify_m", 0.0)),
    )
